from __future__ import annotations

import threading
import datetime
from dataclasses import dataclass
from typing import Literal

from agents.planning.lifecycle import AgentPlanSnapshot, PlanItemSnapshot

from .world_map import MapLocation, MapPoint, MapSpawn, WorldMap


@dataclass(frozen=True)
class SpatialAgentSeed:
    agent_id: str
    name: str
    plan_context: tuple[str, ...]


@dataclass(frozen=True)
class SpatialAgentSnapshot:
    agent_id: str
    name: str
    tile_position: MapPoint
    pixel_position: MapPoint
    destination: str | None
    current_action: str
    plan: str
    route_remaining: int
    active_day: PlanItemSnapshot | None
    active_hourly: PlanItemSnapshot | None
    active_minute: PlanItemSnapshot | None
    day_plan: tuple[PlanItemSnapshot, ...]
    bubble_kind: Literal["speech", "thought", "action"]
    bubble_text: str


@dataclass(frozen=True)
class SpatialWorldSnapshot:
    revision: int
    map_id: str
    agents: tuple[SpatialAgentSnapshot, ...]
    current_time: datetime.datetime | None
    turn: int
    scheduler_running: bool
    planning_error: str | None


@dataclass
class _MutableAgentMovement:
    agent_id: str
    name: str
    tile_position: MapPoint
    plan: str
    destination: MapLocation | None = None
    goal: MapPoint | None = None
    route: list[MapPoint] | None = None
    current_action: str = "idle"
    explicit_location: str | None = None
    schedule: AgentPlanSnapshot | None = None
    cognitive_kind: Literal["speech", "thought"] | None = None
    cognitive_text: str = ""


class SpatialWorldRuntime:
    """Deterministic plan-to-navigation runtime independent from LLM latency."""

    def __init__(self, *, world_map: WorldMap, seeds: list[SpatialAgentSeed]) -> None:
        if not seeds:
            raise ValueError("spatial runtime requires at least one agent")
        if len(seeds) > len(world_map.spawns):
            raise ValueError("world map does not contain enough spawn points")

        self.world_map: WorldMap = world_map
        self.revision: int = 0
        self._lock: threading.RLock = threading.RLock()
        self._agents: dict[str, _MutableAgentMovement] = {}
        self._current_time: datetime.datetime | None = None
        self._turn: int = 0
        self._scheduler_running: bool = False
        self._planning_error: str | None = None
        for index, seed in enumerate(seeds):
            spawn = self._resolve_spawn(seed=seed, fallback_index=index)
            tile_position = MapPoint(
                x=spawn.position.x // world_map.tile_width,
                y=spawn.position.y // world_map.tile_height,
            )
            self._agents[seed.agent_id] = _MutableAgentMovement(
                agent_id=seed.agent_id,
                name=seed.name,
                tile_position=tile_position,
                plan=" | ".join(seed.plan_context),
                route=[],
            )

    def set_plan(self, *, agent_id: str, plan: str) -> None:
        with self._lock:
            agent = self._require_agent(agent_id)
            if agent.plan == plan:
                return
            agent.plan = plan
            agent.destination = None
            agent.goal = None
            agent.route = []
            agent.current_action = "planning_route"

    def set_schedule(self, schedule: AgentPlanSnapshot) -> None:
        with self._lock:
            agent = self._require_agent(schedule.agent_id)
            plan = schedule.active_minute.action_content
            location = schedule.active_minute.location
            changed = agent.plan != plan or agent.explicit_location != location
            agent.plan = plan
            agent.explicit_location = location
            agent.schedule = schedule
            if changed:
                agent.destination = None
                agent.goal = None
                agent.route = []
                agent.current_action = "planning_route"

    def update_world_state(
        self,
        *,
        current_time: datetime.datetime,
        turn: int,
        scheduler_running: bool,
    ) -> None:
        with self._lock:
            self._current_time = current_time
            self._turn = turn
            self._scheduler_running = scheduler_running

    def set_planning_error(self, error: str | None) -> None:
        with self._lock:
            self._planning_error = error
            if error is not None:
                for agent in self._agents.values():
                    agent.plan = ""
                    agent.explicit_location = None
                    agent.schedule = None
                    agent.destination = None
                    agent.goal = None
                    agent.route = []
                    agent.current_action = "planning_error"

    def clear_cognitive_overlays(self) -> None:
        with self._lock:
            for agent in self._agents.values():
                agent.cognitive_kind = None
                agent.cognitive_text = ""

    def set_cognitive_overlay(
        self,
        *,
        agent_id: str,
        kind: Literal["speech", "thought"],
        text: str,
    ) -> None:
        normalized_text = text.strip()
        if not normalized_text:
            return
        with self._lock:
            agent = self._require_agent(agent_id)
            agent.cognitive_kind = kind
            agent.cognitive_text = normalized_text

    def tick(self) -> SpatialWorldSnapshot:
        with self._lock:
            if self._planning_error is None:
                occupied_tiles = {
                    agent.tile_position for agent in self._agents.values()
                }
                for agent in self._agents.values():
                    occupied_tiles.discard(agent.tile_position)
                    self._advance(agent, blocked_tiles=occupied_tiles)
                    occupied_tiles.add(agent.tile_position)
            self.revision += 1
            return self._snapshot_unlocked()

    def snapshot(self) -> SpatialWorldSnapshot:
        with self._lock:
            return self._snapshot_unlocked()

    def _advance(
        self,
        agent: _MutableAgentMovement,
        *,
        blocked_tiles: set[MapPoint],
    ) -> None:
        resolved_destination = self.world_map.resolve_location(
            agent.explicit_location or agent.plan
        )
        destination_changed = (
            resolved_destination.id if resolved_destination else None
        ) != (agent.destination.id if agent.destination else None)
        route_exhausted_before_goal = (
            not (agent.route or []) and agent.goal != agent.tile_position
        )
        if destination_changed or agent.goal is None or route_exhausted_before_goal:
            self._build_route(
                agent=agent,
                destination=resolved_destination,
                blocked_tiles=blocked_tiles,
            )

        route = agent.route or []
        if route and route[0] in blocked_tiles:
            self._build_route(
                agent=agent,
                destination=resolved_destination,
                blocked_tiles=blocked_tiles,
            )
            route = agent.route or []
        if route:
            agent.tile_position = route.pop(0)
            agent.current_action = (
                f"moving_to:{agent.destination.name}"
                if agent.destination is not None
                else "moving"
            )
            if (
                not route
                and agent.goal == agent.tile_position
                and agent.destination is not None
            ):
                agent.current_action = f"arrived_at:{agent.destination.name}"
            return

        if agent.destination is None:
            agent.current_action = "idle:no_mapped_destination"
        elif agent.goal == agent.tile_position:
            agent.current_action = f"at:{agent.destination.name}"
        elif not agent.current_action.startswith("blocked:"):
            agent.current_action = f"waiting_for_clear_path:{agent.destination.name}"

    def _build_route(
        self,
        *,
        agent: _MutableAgentMovement,
        destination: MapLocation | None,
        blocked_tiles: set[MapPoint],
    ) -> None:
        agent.destination = destination
        agent.route = []
        if destination is None:
            agent.goal = None
            return
        goal = self.world_map.destination_tile(
            location=destination,
            origin=agent.tile_position,
            blocked_tiles=blocked_tiles,
        )
        agent.goal = goal
        if goal is None:
            agent.current_action = "blocked:no_walkable_destination"
            return
        path = self.world_map.find_path(
            agent.tile_position,
            goal,
            blocked_tiles=blocked_tiles,
        )
        if not path:
            agent.current_action = "blocked:no_route"
            return
        agent.route = path[1:]
        agent.current_action = (
            f"at:{destination.name}"
            if goal == agent.tile_position
            else f"moving_to:{destination.name}"
        )

    def _snapshot_unlocked(self) -> SpatialWorldSnapshot:
        return SpatialWorldSnapshot(
            revision=self.revision,
            map_id=self.world_map.id,
            current_time=self._current_time,
            turn=self._turn,
            scheduler_running=self._scheduler_running,
            planning_error=self._planning_error,
            agents=tuple(
                SpatialAgentSnapshot(
                    agent_id=agent.agent_id,
                    name=agent.name,
                    tile_position=agent.tile_position,
                    pixel_position=MapPoint(
                        x=(agent.tile_position.x * self.world_map.tile_width)
                        + (self.world_map.tile_width // 2),
                        y=(agent.tile_position.y * self.world_map.tile_height)
                        + (self.world_map.tile_height // 2),
                    ),
                    destination=(
                        agent.destination.location_path
                        if agent.destination is not None
                        else None
                    ),
                    current_action=agent.current_action,
                    plan=agent.plan,
                    route_remaining=len(agent.route or []),
                    active_day=(agent.schedule.active_day if agent.schedule else None),
                    active_hourly=(
                        agent.schedule.active_hourly if agent.schedule else None
                    ),
                    active_minute=(
                        agent.schedule.active_minute if agent.schedule else None
                    ),
                    day_plan=agent.schedule.day_plan if agent.schedule else (),
                    bubble_kind=agent.cognitive_kind or "action",
                    bubble_text=(
                        agent.cognitive_text
                        if agent.cognitive_kind is not None
                        else agent.plan
                    ),
                )
                for agent in self._agents.values()
            ),
        )

    def _resolve_spawn(
        self, *, seed: SpatialAgentSeed, fallback_index: int
    ) -> MapSpawn:
        normalized_id = _normalize_agent_id(seed.agent_id)
        normalized_name = _normalize_agent_id(seed.name.split()[0])
        for spawn in self.world_map.spawns:
            normalized_spawn = _normalize_agent_id(spawn.agent_id)
            if normalized_spawn in {normalized_id, normalized_name}:
                return spawn
        return self.world_map.spawns[fallback_index]

    def _require_agent(self, agent_id: str) -> _MutableAgentMovement:
        try:
            return self._agents[agent_id]
        except KeyError as error:
            raise KeyError(f"unknown spatial agent: {agent_id}") from error


def _normalize_agent_id(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())
