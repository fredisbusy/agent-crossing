import asyncio
import datetime
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from agents.sim_agent import SimAgent
from agents.planning.lifecycle import LifeAgent, PlanningCoordinator
from agents.planning.models import DayPlanItem
from llm.governance import (
    ConversationMetrics,
    build_conversation_metrics,
)
from llm.clients.provider_factory import build_provider_client
from agents.world_factory import init_agents

from .engine import (
    SimulationEngine,
    SimulationEngineConfig,
    SimulationStepResult,
    build_failed_step_result,
)
from .session import WorldConversationSession
from .spatial import SpatialWorldRuntime

logger = logging.getLogger(__name__)


def _as_life_agent(agent: SimAgent) -> LifeAgent:
    return cast(LifeAgent, cast(object, agent))


@dataclass(frozen=True)
class WorldRuntimeConfig:
    agent_persona_names: list[str]
    base_url: str | None
    api_key: str | None
    llm_model: str
    embedding_model: str
    timeout_seconds: float
    persona_dir: str
    dialogue_turn_window: int | None = None
    dialogue_target_turns: int = 5
    language: Literal["ko"] = "ko"
    fallback_on_empty_reply: bool = False
    suppress_repeated_replies: bool = True
    repetition_window: int = 4
    turn_time_step_seconds: int = 300
    cognitive_time_step_seconds: int = 30
    tick_interval_seconds: float = 1.0


@dataclass(frozen=True)
class WorldRuntimeState:
    turn: int
    current_time: datetime.datetime
    parse_failures: int
    silent_turns: int
    history_size: int
    scheduler_running: bool
    tick_interval_seconds: float
    cognitive_active: bool
    effective_time_step_seconds: int


class WorldRuntime:
    def __init__(
        self,
        *,
        agents: list[SimAgent],
        session: WorldConversationSession,
        engine: SimulationEngine,
        current_time: datetime.datetime,
        tick_interval_seconds: float = 1.0,
        cognitive_time_step_seconds: int = 30,
        planning_coordinator: PlanningCoordinator | None = None,
        spatial_runtime: SpatialWorldRuntime | None = None,
    ) -> None:
        if len(agents) != 2:
            raise ValueError("WorldRuntime currently supports exactly two agents")
        if tick_interval_seconds <= 0:
            raise ValueError("tick_interval_seconds must be greater than 0")
        if cognitive_time_step_seconds <= 0:
            raise ValueError("cognitive_time_step_seconds must be greater than 0")
        if cognitive_time_step_seconds > engine.config.turn_time_step_seconds:
            raise ValueError(
                "cognitive_time_step_seconds must not exceed turn_time_step_seconds"
            )

        self.agents: list[SimAgent] = agents
        self.session: WorldConversationSession = session
        self.engine: SimulationEngine = engine
        self.current_time: datetime.datetime = current_time
        self.tick_interval_seconds: float = tick_interval_seconds
        self.cognitive_time_step_seconds: int = cognitive_time_step_seconds
        self.turn: int = 0
        self.parse_failures: int = 0
        self.silent_turns: int = 0
        self._initiator: SimAgent = agents[0]
        self._partner: SimAgent = agents[1]
        self._step_lock: threading.Lock = threading.Lock()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._plan_refresh_task: asyncio.Task[None] | None = None
        self._cognitive_task: asyncio.Task[None] | None = None
        self.planning_coordinator: PlanningCoordinator | None = planning_coordinator
        self.spatial_runtime: SpatialWorldRuntime | None = spatial_runtime
        self._last_dialogue_end_time: datetime.datetime | None = None

    def step(self) -> SimulationStepResult:
        with self._step_lock:
            self.turn += 1
            planning_time = self.current_time
            if self.planning_coordinator is not None:
                planning_time = self.current_time + datetime.timedelta(
                    seconds=self.engine.config.turn_time_step_seconds
                )
                for agent in self.agents:
                    schedule = self.planning_coordinator.ensure_current(
                        agent=_as_life_agent(agent),
                        now=planning_time,
                        generate=False,
                    )
                    if self.spatial_runtime is not None:
                        self.spatial_runtime.set_schedule(schedule)
            self._start_dialogue_for_real_encounter(planning_time)
            dialogue_was_active = self.session.is_active
            speaker = self.session.next_speaker()
            speaking_partner = (
                self._partner if speaker is self._initiator else self._initiator
            )
            try:
                step_result = self.engine.step(
                    turn=self.turn,
                    current_time=self.current_time,
                    speaker=speaker,
                    speaking_partner=speaking_partner,
                )
            except Exception as error:
                logger.exception(
                    "Agent action loop failed; continuing the world clock",
                    extra={"agent_id": str(speaker.identity.id), "turn": self.turn},
                )
                self.session.finish_dialogue()
                step_result = build_failed_step_result(
                    current_time=self.current_time,
                    speaker_name=speaker.name,
                    error=error,
                    turn_time_step_seconds=self.engine.config.turn_time_step_seconds,
                )
            self.current_time = step_result.now
            if self.spatial_runtime is not None:
                self.spatial_runtime.clear_cognitive_overlays()
                if step_result.reply:
                    self.spatial_runtime.set_cognitive_overlay(
                        agent_id=speaker.identity.id,
                        kind="speech",
                        text=step_result.reply,
                    )
                elif step_result.observability.thought:
                    self.spatial_runtime.set_cognitive_overlay(
                        agent_id=speaker.identity.id,
                        kind="thought",
                        text=step_result.observability.thought,
                    )
            if dialogue_was_active and not self.session.is_active:
                self._last_dialogue_end_time = self.current_time
            if self.spatial_runtime is not None:
                self.spatial_runtime.update_world_state(
                    current_time=self.current_time,
                    turn=self.turn,
                    scheduler_running=self.scheduler_running,
                )
            if step_result.parse_failure:
                self.parse_failures += 1
            if not step_result.reply:
                self.silent_turns += 1
            return step_result

    def _start_dialogue_for_real_encounter(self, now: datetime.datetime) -> None:
        cognitive_turn_in_flight = (
            self._cognitive_task is not None and not self._cognitive_task.done()
        )
        if (
            self.session.is_active
            or cognitive_turn_in_flight
            or self.spatial_runtime is None
        ):
            return
        if (
            self._last_dialogue_end_time is not None
            and now - self._last_dialogue_end_time < datetime.timedelta(minutes=30)
        ):
            return
        agents = self.spatial_runtime.snapshot().agents
        if len(agents) != 2:
            return
        first, second = agents
        distance = abs(first.tile_position.x - second.tile_position.x) + abs(
            first.tile_position.y - second.tile_position.y
        )
        both_arrived = first.current_action.startswith(("at:", "arrived_at:")) and (
            second.current_action.startswith(("at:", "arrived_at:"))
        )
        if (
            both_arrived
            and first.destination is not None
            and first.destination == second.destination
            and distance <= 1
        ):
            self.session.start_dialogue()

    def tick(self) -> SimulationStepResult:
        """Advance the single runtime clock by one perceive-plan-act tick."""
        return self.step()

    @property
    def scheduler_running(self) -> bool:
        return self._scheduler_task is not None and not self._scheduler_task.done()

    @property
    def cognitive_active(self) -> bool:
        cognitive_turn_in_flight = (
            self._cognitive_task is not None and not self._cognitive_task.done()
        )
        return self.session.is_active or cognitive_turn_in_flight

    @property
    def effective_time_step_seconds(self) -> int:
        if self.cognitive_active:
            return self.cognitive_time_step_seconds
        return self.engine.config.turn_time_step_seconds

    async def start_scheduler(self) -> bool:
        if self.scheduler_running:
            return False
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        if self.planning_coordinator is not None:
            self._plan_refresh_task = asyncio.create_task(self._refresh_plans())
        return True

    async def stop_scheduler(self) -> bool:
        if self._scheduler_task is None:
            return False
        task = self._scheduler_task
        self._scheduler_task = None
        refresh_task = self._plan_refresh_task
        self._plan_refresh_task = None
        if task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        if refresh_task is not None and not refresh_task.done():
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass
        if self.spatial_runtime is not None:
            self.spatial_runtime.update_world_state(
                current_time=self.current_time,
                turn=self.turn,
                scheduler_running=False,
            )
        return True

    async def _run_scheduler(self) -> None:
        while True:
            await asyncio.to_thread(self._advance_world_tick)
            if self.session.is_active and (
                self._cognitive_task is None or self._cognitive_task.done()
            ):
                if self._cognitive_task is not None:
                    _ = self._cognitive_task.exception()
                self._cognitive_task = asyncio.create_task(
                    asyncio.to_thread(self._run_cognitive_turn)
                )
            await asyncio.sleep(self.tick_interval_seconds)

    def _advance_world_tick(self) -> None:
        """Advance plans, movement time, and encounter detection without LLM I/O."""
        with self._step_lock:
            self.turn += 1
            cognitive_active = self.cognitive_active
            planning_time = self.current_time + datetime.timedelta(
                seconds=(
                    self.cognitive_time_step_seconds
                    if cognitive_active
                    else self.engine.config.turn_time_step_seconds
                )
            )
            if self.planning_coordinator is not None and not cognitive_active:
                for agent in self.agents:
                    schedule = self.planning_coordinator.ensure_current(
                        agent=_as_life_agent(agent),
                        now=planning_time,
                        generate=False,
                    )
                    if self.spatial_runtime is not None:
                        self.spatial_runtime.set_schedule(schedule)
            self._start_dialogue_for_real_encounter(planning_time)
            self.current_time = planning_time
            if self.spatial_runtime is not None:
                self.spatial_runtime.update_world_state(
                    current_time=self.current_time,
                    turn=self.turn,
                    scheduler_running=self.scheduler_running,
                )

    def _run_cognitive_turn(self) -> None:
        """Run one dialogue turn independently from the authoritative world clock."""
        if not self.session.is_active:
            return
        dialogue_was_active = self.session.is_active
        speaker = self.session.next_speaker()
        speaking_partner = (
            self._partner if speaker is self._initiator else self._initiator
        )
        turn = self.turn
        cognitive_time = self.current_time
        try:
            step_result = self.engine.step(
                turn=turn,
                current_time=cognitive_time
                - datetime.timedelta(
                    seconds=self.engine.config.turn_time_step_seconds
                ),
                speaker=speaker,
                speaking_partner=speaking_partner,
            )
        except Exception as error:
            logger.exception(
                "Agent action loop failed; continuing the world clock",
                extra={"agent_id": str(speaker.identity.id), "turn": turn},
            )
            self.session.finish_dialogue()
            step_result = build_failed_step_result(
                current_time=cognitive_time,
                speaker_name=speaker.name,
                error=error,
                turn_time_step_seconds=0,
            )

        with self._step_lock:
            if self.spatial_runtime is not None:
                self.spatial_runtime.clear_cognitive_overlays()
                if step_result.reply:
                    self.spatial_runtime.set_cognitive_overlay(
                        agent_id=speaker.identity.id,
                        kind="speech",
                        text=step_result.reply,
                    )
                elif step_result.observability.thought:
                    self.spatial_runtime.set_cognitive_overlay(
                        agent_id=speaker.identity.id,
                        kind="thought",
                        text=step_result.observability.thought,
                    )
            if dialogue_was_active and not self.session.is_active:
                self._last_dialogue_end_time = self.current_time
            if step_result.parse_failure:
                self.parse_failures += 1
            if not step_result.reply:
                self.silent_turns += 1

    async def _refresh_plans(self) -> None:
        if self.planning_coordinator is None:
            return
        day_plans: list[list[DayPlanItem]] = []
        planning_date = self.current_time
        for agent in self.agents:
            day_plans.append(
                await asyncio.to_thread(
                    self.planning_coordinator.generate_day_plan,
                    agent=_as_life_agent(agent),
                    now=planning_date,
                )
            )
        apply_time = self.current_time
        schedules = [
            self.planning_coordinator.install_day_plan(
                agent=_as_life_agent(agent),
                now=apply_time,
                day_items=day_items,
                reason="llm_refresh",
            )
            for agent, day_items in zip(self.agents, day_plans, strict=True)
        ]
        if self.spatial_runtime is not None:
            for schedule in schedules:
                self.spatial_runtime.set_schedule(schedule)

    def bootstrap_plans(self) -> None:
        if self.planning_coordinator is None:
            return
        for agent in self.agents:
            schedule = self.planning_coordinator.bootstrap(
                agent=_as_life_agent(agent),
                now=self.current_time,
            )
            if self.spatial_runtime is not None:
                self.spatial_runtime.set_schedule(schedule)
        if self.spatial_runtime is not None:
            self.spatial_runtime.update_world_state(
                current_time=self.current_time,
                turn=self.turn,
                scheduler_running=False,
            )

    def metrics(self) -> ConversationMetrics:
        return build_conversation_metrics(
            turns=self.turn,
            parse_failures=self.parse_failures,
            silent_turns=self.silent_turns,
            session_history=self.session.history,
        )

    def state(self) -> WorldRuntimeState:
        return WorldRuntimeState(
            turn=self.turn,
            current_time=self.current_time,
            parse_failures=self.parse_failures,
            silent_turns=self.silent_turns,
            history_size=len(self.session.history),
            scheduler_running=self.scheduler_running,
            tick_interval_seconds=self.tick_interval_seconds,
            cognitive_active=self.cognitive_active,
            effective_time_step_seconds=self.effective_time_step_seconds,
        )


def build_world_runtime(
    *, config: WorldRuntimeConfig, spatial_runtime: SpatialWorldRuntime | None = None
) -> WorldRuntime:
    wall_now = datetime.datetime.now()
    now = wall_now.replace(hour=6, minute=0, second=0, microsecond=0)
    llm_client = build_provider_client(
        timeout_seconds=config.timeout_seconds,
        generation_model=config.llm_model,
        embedding_model=config.embedding_model,
        base_url=config.base_url,
        api_key=config.api_key,
    )
    agents = init_agents(
        persona_dir=config.persona_dir,
        agent_persona_names=config.agent_persona_names,
        llm_client=llm_client,
        embedding_model=config.embedding_model,
        now=now,
    )
    session = WorldConversationSession(
        agents=agents,
        dialogue_turn_window=config.dialogue_turn_window,
        dialogue_target_turns=config.dialogue_target_turns,
    )
    session.finish_dialogue()
    engine = SimulationEngine(
        session=session,
        config=SimulationEngineConfig(
            language=config.language,
            turn_time_step_seconds=config.turn_time_step_seconds,
            suppress_repeated_replies=config.suppress_repeated_replies,
            repetition_window=config.repetition_window,
            fallback_on_empty_reply=config.fallback_on_empty_reply,
        ),
    )
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=engine,
        current_time=now,
        tick_interval_seconds=config.tick_interval_seconds,
        cognitive_time_step_seconds=config.cognitive_time_step_seconds,
        planning_coordinator=PlanningCoordinator(),
        spatial_runtime=spatial_runtime,
    )
    runtime.bootstrap_plans()
    return runtime


def default_persona_dir() -> str:
    return str(Path(__file__).resolve().parents[2] / "persona")
