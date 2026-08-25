import asyncio
import datetime
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import numpy as np

from agents.sim_agent import SimAgent
from agents.memory.memory_object import MemoryObject, NodeType
from agents.planning.lifecycle import (
    AgentPlanSnapshot,
    LifeAgent,
    PlanningCoordinator,
    PlanningGenerationError,
)
from llm.governance import (
    ConversationMetrics,
    build_conversation_metrics,
)
from llm.clients.provider_factory import build_provider_client
from agents.world_factory import init_agents
from persistence.contracts import (
    CharacterSave,
    DashboardEventSave,
    MemorySave,
    RuntimeSaveState,
    sanitized_diagnostics,
)

from .engine import (
    SimulationEngine,
    SimulationEngineConfig,
    SimulationStepResult,
    build_failed_step_result,
)
from .session import WorldConversationSession
from .observability import DashboardEvent, DashboardEventBuffer
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
    timeout_seconds: float | None
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
        self._scheduler_stop_requested: bool = False
        self._plan_refresh_task: asyncio.Task[None] | None = None
        self._cognitive_task: asyncio.Task[None] | None = None
        self.planning_coordinator: PlanningCoordinator | None = planning_coordinator
        self.spatial_runtime: SpatialWorldRuntime | None = spatial_runtime
        self._last_dialogue_end_time: datetime.datetime | None = None
        self._dashboard_events: DashboardEventBuffer = DashboardEventBuffer()
        self.planning_error: str | None = None

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
                        generate=True,
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
            self._record_dashboard_event(speaker=speaker, result=step_result)
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
        self._scheduler_stop_requested = False
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        return True

    async def pause_scheduler(self) -> bool:
        """Stop at a safe boundary and wait for in-flight cognition/planning to finish."""
        was_running = self.scheduler_running
        task = self._scheduler_task
        if task is not None and not task.done():
            self._scheduler_stop_requested = True
            await task
        self._scheduler_task = None
        cognitive_task = self._cognitive_task
        if cognitive_task is not None and not cognitive_task.done():
            await cognitive_task
        if cognitive_task is not None and cognitive_task.done():
            _ = cognitive_task.exception()
        self._cognitive_task = None
        plan_task = self._plan_refresh_task
        if plan_task is not None and not plan_task.done():
            await plan_task
        if plan_task is not None and plan_task.done():
            _ = plan_task.exception()
        self._plan_refresh_task = None
        if self.spatial_runtime is not None:
            self.spatial_runtime.update_world_state(
                current_time=self.current_time,
                turn=self.turn,
                scheduler_running=False,
            )
        return was_running

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
        if self.planning_coordinator is not None:
            try:
                schedules = [
                    self.planning_coordinator.ensure_current(
                        agent=_as_life_agent(agent),
                        now=self.current_time,
                        generate=False,
                    )
                    for agent in self.agents
                ]
                if self.spatial_runtime is not None:
                    for schedule in schedules:
                        self.spatial_runtime.set_schedule(schedule)
            except PlanningGenerationError:
                try:
                    await self._refresh_plans()
                except Exception as error:
                    self._set_planning_error(error)
                    logger.exception("Authoritative plan generation failed")
                    return
            except Exception as error:
                self._set_planning_error(error)
                logger.exception("Authoritative restored plan validation failed")
                return
        while not self._scheduler_stop_requested:
            try:
                await asyncio.to_thread(self._advance_world_tick)
            except Exception as error:
                self._set_planning_error(error)
                logger.exception("Authoritative plan transition failed")
                return
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
                self._sync_or_schedule_plan_generation(planning_time)
            self._start_dialogue_for_real_encounter(planning_time)
            self.current_time = planning_time
            if self.spatial_runtime is not None:
                self.spatial_runtime.update_world_state(
                    current_time=self.current_time,
                    turn=self.turn,
                    scheduler_running=self.scheduler_running,
                )

    def _sync_or_schedule_plan_generation(
        self, planning_time: datetime.datetime
    ) -> None:
        """Apply already-current plans immediately; hand off regeneration to the background.

        `PlanningCoordinator.ensure_current(generate=True)` can cascade into up to three
        sequential LLM calls per agent on a day/hour/minute boundary. Running that inline
        here would stall the tick loop (and dialogue) for as long as the local model takes
        to answer, so this only reads the already-valid plan synchronously (no LLM I/O) and
        offloads regeneration to `_generate_plans_blocking` via `_plan_refresh_task`. Agents
        whose plan is mid-regeneration simply keep their last known schedule for this tick.
        """
        assert self.planning_coordinator is not None
        schedules: list[AgentPlanSnapshot] = []
        needs_generation = False
        for agent in self.agents:
            try:
                schedules.append(
                    self.planning_coordinator.ensure_current(
                        agent=_as_life_agent(agent),
                        now=planning_time,
                        generate=False,
                    )
                )
            except PlanningGenerationError:
                needs_generation = True
        if self.spatial_runtime is not None:
            for schedule in schedules:
                self.spatial_runtime.set_schedule(schedule)
        if needs_generation:
            self._ensure_plan_generation_task(planning_time)

    def _ensure_plan_generation_task(self, planning_time: datetime.datetime) -> None:
        if self._plan_refresh_task is not None and not self._plan_refresh_task.done():
            return
        self._plan_refresh_task = asyncio.create_task(
            asyncio.to_thread(self._generate_plans_blocking, planning_time)
        )

    def _generate_plans_blocking(self, planning_time: datetime.datetime) -> None:
        """Runs off the tick loop's critical path; may issue several sequential LLM calls."""
        assert self.planning_coordinator is not None
        try:
            schedules = [
                self.planning_coordinator.ensure_current(
                    agent=_as_life_agent(agent),
                    now=planning_time,
                    generate=True,
                )
                for agent in self.agents
            ]
        except Exception as error:
            with self._step_lock:
                self._set_planning_error(error)
                self._scheduler_stop_requested = True
            logger.exception("Background plan generation failed")
            return
        with self._step_lock:
            self._set_planning_error(None)
            if self.spatial_runtime is not None:
                for schedule in schedules:
                    self.spatial_runtime.set_schedule(schedule)

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
                - datetime.timedelta(seconds=self.engine.config.turn_time_step_seconds),
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
            self._record_dashboard_event(speaker=speaker, result=step_result)

    def _record_dashboard_event(
        self, *, speaker: SimAgent, result: SimulationStepResult
    ) -> None:
        _ = self._dashboard_events.append(
            turn=self.turn,
            agent_id=str(speaker.identity.id),
            agent_name=speaker.name,
            result=result,
        )

    def dashboard_events(
        self, *, after_sequence: int = 0, limit: int = 100
    ) -> tuple[DashboardEvent, ...]:
        """Return a stable copy of recent diagnostics events."""
        return self._dashboard_events.snapshot(
            after_sequence=after_sequence,
            limit=limit,
        )

    @property
    def latest_dashboard_sequence(self) -> int:
        return self._dashboard_events.latest_sequence

    async def _refresh_plans(self) -> None:
        if self.planning_coordinator is None:
            return
        planning_date = self.current_time
        schedules = []
        for agent in self.agents:
            schedules.append(
                await asyncio.to_thread(
                    self.planning_coordinator.refresh_current,
                    agent=_as_life_agent(agent),
                    now=planning_date,
                )
            )
        self._set_planning_error(None)
        if self.spatial_runtime is not None:
            for schedule in schedules:
                self.spatial_runtime.set_schedule(schedule)

    def _set_planning_error(self, error: Exception | None) -> None:
        self.planning_error = None if error is None else str(error)
        if self.spatial_runtime is not None:
            self.spatial_runtime.set_planning_error(self.planning_error)
            self.spatial_runtime.update_world_state(
                current_time=self.current_time,
                turn=self.turn,
                scheduler_running=(self.scheduler_running if error is None else False),
            )

    def bootstrap_plans(self) -> None:
        """Retained for compatibility; authoritative plans start asynchronously."""
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

    def export_save_state(self, *, scheduler_was_running: bool) -> RuntimeSaveState:
        if self.spatial_runtime is None:
            raise RuntimeError("spatial runtime is required for session persistence")
        if self.scheduler_running or self.cognitive_active:
            raise RuntimeError("runtime must be quiescent before it can be saved")
        with self._step_lock:
            spatial_snapshot = self.spatial_runtime.snapshot()
            characters: list[CharacterSave] = []
            for agent in self.agents:
                movement = self.spatial_runtime.export_character_state(
                    agent_id=str(agent.identity.id)
                )
                memories = [
                    MemorySave(
                        id=memory.id,
                        node_type=memory.node_type.value,
                        citations=(
                            list(memory.citations)
                            if memory.citations is not None
                            else None
                        ),
                        content=memory.content,
                        created_at=memory.created_at,
                        last_accessed_at=memory.last_accessed_at,
                        importance=memory.importance,
                        embedding=[float(value) for value in memory.embedding.tolist()],
                    )
                    for memory in agent.memory_service.memory_stream.snapshot()
                ]
                planning = (
                    self.planning_coordinator.export_state(
                        agent_id=str(agent.identity.id)
                    )
                    if self.planning_coordinator is not None
                    else None
                )
                characters.append(
                    CharacterSave(
                        tile_position=movement.tile_position,
                        goal=movement.goal,
                        route=movement.route,
                        destination_path=movement.destination_path,
                        explicit_location=movement.explicit_location,
                        current_action=movement.current_action,
                        plan=movement.plan,
                        cognitive_kind=movement.cognitive_kind,
                        cognitive_text=movement.cognitive_text,
                        agent_id=str(agent.identity.id),
                        name=agent.name,
                        age=agent.identity.age,
                        traits=list(agent.identity.traits),
                        identity_stable_set=list(
                            agent.profile.fixed.identity_stable_set
                        ),
                        lifestyle_and_routine=list(
                            agent.profile.extended.lifestyle_and_routine
                        ),
                        current_plan_context=list(
                            agent.profile.extended.current_plan_context
                        ),
                        reflection_accumulated_importance=(
                            agent.brain.reflection_graph.reflection.accumulated_importance
                        ),
                        memories=memories,
                        planning=planning,
                    )
                )
            dashboard_events: list[DashboardEventSave] = []
            for event in self.dashboard_events(limit=500):
                decision_process = sanitized_diagnostics(event.decision_process)
                governance_trace = sanitized_diagnostics(event.governance_trace)
                dashboard_events.append(
                    DashboardEventSave(
                        sequence=event.sequence,
                        turn=event.turn,
                        occurred_at=event.occurred_at,
                        agent_id=event.agent_id,
                        agent_name=event.agent_name,
                        reply=event.reply[:8192],
                        silent_reason=event.silent_reason[:8192],
                        parse_failure=event.parse_failure,
                        thought=event.thought[:8192],
                        model_thought=event.model_thought[:8192],
                        self_critique=event.self_critique[:8192],
                        decision_reason=event.decision_reason[:8192],
                        action_summary=event.action_summary[:8192],
                        decision_process=(
                            decision_process
                            if isinstance(decision_process, dict)
                            else {}
                        ),
                        governance_trace=(
                            governance_trace
                            if isinstance(governance_trace, dict)
                            else {}
                        ),
                    )
                )
            return RuntimeSaveState(
                map_id=spatial_snapshot.map_id,
                current_time=self.current_time,
                turn=self.turn,
                revision=spatial_snapshot.revision,
                parse_failures=self.parse_failures,
                silent_turns=self.silent_turns,
                scheduler_was_running=scheduler_was_running,
                planning_error=self.planning_error,
                last_dialogue_end_time=self._last_dialogue_end_time,
                conversation=self.session.export_state(),
                characters=characters,
                dashboard_events=dashboard_events,
            )

    def restore_save_state(self, state: RuntimeSaveState) -> None:
        if self.scheduler_running or self.cognitive_active:
            raise RuntimeError("runtime must be quiescent before restore")
        if self.spatial_runtime is None:
            raise RuntimeError("spatial runtime is required for session restore")
        if state.map_id != self.spatial_runtime.world_map.id:
            raise ValueError(f"saved map is not supported: {state.map_id}")
        saved_by_id = {character.agent_id: character for character in state.characters}
        runtime_ids = {str(agent.identity.id) for agent in self.agents}
        if (
            len(state.characters) != len(saved_by_id)
            or len(saved_by_id) != len(runtime_ids)
            or set(saved_by_id) != runtime_ids
        ):
            raise ValueError("saved character roster does not match runtime")

        with self._step_lock:
            self.current_time = state.current_time
            self.turn = state.turn
            self.parse_failures = state.parse_failures
            self.silent_turns = state.silent_turns
            self.planning_error = state.planning_error
            self._last_dialogue_end_time = state.last_dialogue_end_time
            for agent in self.agents:
                saved = saved_by_id[str(agent.identity.id)]
                agent.identity.name = saved.name
                agent.identity.age = saved.age
                agent.identity.traits = list(saved.traits)
                agent.profile.fixed.identity_stable_set = list(
                    saved.identity_stable_set
                )
                agent.profile.extended.lifestyle_and_routine = list(
                    saved.lifestyle_and_routine
                )
                agent.profile.extended.current_plan_context = list(
                    saved.current_plan_context
                )
                agent.memory_service.memory_stream.restore(
                    [
                        MemoryObject(
                            id=memory.id,
                            node_type=NodeType(memory.node_type),
                            citations=(
                                list(memory.citations)
                                if memory.citations is not None
                                else None
                            ),
                            content=memory.content,
                            created_at=memory.created_at,
                            last_accessed_at=memory.last_accessed_at,
                            importance=memory.importance,
                            embedding=np.asarray(memory.embedding, dtype=np.float32),
                        )
                        for memory in saved.memories
                    ]
                )
                agent.brain.reflection_graph.reflection.restore_importance(
                    saved.reflection_accumulated_importance
                )
                if self.planning_coordinator is not None and saved.planning is not None:
                    self.planning_coordinator.restore_state(
                        agent_id=saved.agent_id,
                        state=saved.planning,
                    )
                    try:
                        schedule = self.planning_coordinator.ensure_current(
                            agent=_as_life_agent(agent),
                            now=self.current_time,
                            generate=False,
                        )
                    except PlanningGenerationError:
                        # A failed generation can persist an intentionally empty
                        # cache. Restore the rest of the session and let scheduler
                        # startup regenerate the authoritative hierarchy.
                        pass
                    else:
                        self.spatial_runtime.set_schedule(schedule)
            self.session.restore_state(state.conversation)
            self.spatial_runtime.restore_state(
                revision=state.revision,
                current_time=state.current_time,
                turn=state.turn,
                planning_error=state.planning_error,
                characters=state.characters,
            )
            self._dashboard_events.restore(
                [
                    DashboardEvent(
                        sequence=event.sequence,
                        turn=event.turn,
                        occurred_at=event.occurred_at,
                        agent_id=event.agent_id,
                        agent_name=event.agent_name,
                        reply=event.reply,
                        silent_reason=event.silent_reason,
                        parse_failure=event.parse_failure,
                        thought=event.thought,
                        model_thought=event.model_thought,
                        self_critique=event.self_critique,
                        decision_reason=event.decision_reason,
                        action_summary=event.action_summary,
                        decision_process=dict(event.decision_process),
                        governance_trace=dict(event.governance_trace),
                    )
                    for event in state.dashboard_events
                ]
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
    return runtime


def default_persona_dir() -> str:
    return str(Path(__file__).resolve().parents[2] / "persona")
