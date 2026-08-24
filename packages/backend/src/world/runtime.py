import asyncio
import datetime
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from agents.sim_agent import SimAgent
from agents.planning.lifecycle import LifeAgent, PlanningCoordinator
from llm.governance import (
    ConversationMetrics,
    build_conversation_metrics,
)
from llm.clients.provider_factory import build_provider_client
from agents.world_factory import init_agents

from .engine import SimulationEngine, SimulationEngineConfig, SimulationStepResult
from .session import WorldConversationSession
from .spatial import SpatialWorldRuntime


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


class WorldRuntime:
    def __init__(
        self,
        *,
        agents: list[SimAgent],
        session: WorldConversationSession,
        engine: SimulationEngine,
        current_time: datetime.datetime,
        tick_interval_seconds: float = 1.0,
        planning_coordinator: PlanningCoordinator | None = None,
        spatial_runtime: SpatialWorldRuntime | None = None,
    ) -> None:
        if len(agents) != 2:
            raise ValueError("WorldRuntime currently supports exactly two agents")
        if tick_interval_seconds <= 0:
            raise ValueError("tick_interval_seconds must be greater than 0")

        self.agents: list[SimAgent] = agents
        self.session: WorldConversationSession = session
        self.engine: SimulationEngine = engine
        self.current_time: datetime.datetime = current_time
        self.tick_interval_seconds: float = tick_interval_seconds
        self.turn: int = 0
        self.parse_failures: int = 0
        self.silent_turns: int = 0
        self._initiator: SimAgent = agents[0]
        self._partner: SimAgent = agents[1]
        self._step_lock: threading.Lock = threading.Lock()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._plan_refresh_task: asyncio.Task[None] | None = None
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
                        agent=cast(LifeAgent, agent),
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
            step_result = self.engine.step(
                turn=self.turn,
                current_time=self.current_time,
                speaker=speaker,
                speaking_partner=speaking_partner,
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
        if self.session.is_active or self.spatial_runtime is None:
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
            await asyncio.to_thread(self.tick)
            await asyncio.sleep(self.tick_interval_seconds)

    async def _refresh_plans(self) -> None:
        if self.planning_coordinator is None:
            return
        schedules = []
        refresh_time = self.current_time
        for agent in self.agents:
            schedules.append(
                await asyncio.to_thread(
                    self.planning_coordinator.refresh_current,
                    agent=cast(LifeAgent, agent),
                    now=refresh_time,
                )
            )
        if self.spatial_runtime is not None:
            for schedule in schedules:
                self.spatial_runtime.set_schedule(schedule)

    def bootstrap_plans(self) -> None:
        if self.planning_coordinator is None:
            return
        for agent in self.agents:
            schedule = self.planning_coordinator.bootstrap(
                agent=cast(LifeAgent, agent),
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
        planning_coordinator=PlanningCoordinator(),
        spatial_runtime=spatial_runtime,
    )
    runtime.bootstrap_plans()
    return runtime


def default_persona_dir() -> str:
    return str(Path(__file__).resolve().parents[2] / "persona")
