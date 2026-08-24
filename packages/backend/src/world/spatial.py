from __future__ import annotations

import threading
from dataclasses import dataclass

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


@dataclass(frozen=True)
class SpatialWorldSnapshot:
    revision: int
    map_id: str
    agents: tuple[SpatialAgentSnapshot, ...]


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

    def tick(self) -> SpatialWorldSnapshot:
        with self._lock:
            for agent in self._agents.values():
                self._advance(agent)
            self.revision += 1
            return self._snapshot_unlocked()

    def snapshot(self) -> SpatialWorldSnapshot:
        with self._lock:
            return self._snapshot_unlocked()

    def _advance(self, agent: _MutableAgentMovement) -> None:
        resolved_destination = self.world_map.resolve_location(agent.plan)
        destination_changed = (
            resolved_destination.id if resolved_destination else None
        ) != (agent.destination.id if agent.destination else None)
        if destination_changed or agent.goal is None:
            self._build_route(agent=agent, destination=resolved_destination)

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

    def _build_route(
        self,
        *,
        agent: _MutableAgentMovement,
        destination: MapLocation | None,
    ) -> None:
        agent.destination = destination
        agent.route = []
        if destination is None:
            agent.goal = None
            return
        goal = self.world_map.nearest_walkable_tile(
            bounds=destination.bounds,
            origin=agent.tile_position,
        )
        agent.goal = goal
        if goal is None:
            agent.current_action = "blocked:no_walkable_destination"
            return
        path = self.world_map.find_path(agent.tile_position, goal)
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
