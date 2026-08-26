import asyncio
import datetime
import itertools
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
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
from agents.decision_diagnostics import (
    build_encounter_diagnostics,
    build_plan_disruption_diagnostics,
)
from agents.home_access import HomeAccessPolicy
from agents.reaction.encounter import (
    EncounterDecision,
    EncounterDecisionInput,
    EncounterGate,
)
from agents.relationships import (
    RelationshipEvent,
    RelationshipEventType,
    RelationshipMetrics,
    RelationshipService,
    RelationshipState,
)
from agents.planning.react_gate import (
    PlanDisruptionDecision,
    PlanDisruptionGate,
    PlanDisruptionInput,
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
    RelationshipDeltaSave,
    RelationshipEventSave,
    RelationshipMetricsSave,
    RelationshipStateSave,
    RuntimeSaveState,
    sanitized_diagnostics,
)
from settings import PLAN_GENERATION_MAX_CONCURRENCY

from .engine import (
    SimulationEngine,
    SimulationEngineConfig,
    SimulationStepResult,
    build_failed_step_result,
)
from .session import WorldConversationSession, build_turn_world_context
from .observability import DashboardEvent, DashboardEventBuffer
from .spatial import SpatialAgentSnapshot, SpatialWorldRuntime

logger = logging.getLogger(__name__)


def _as_life_agent(agent: SimAgent) -> LifeAgent:
    return cast(LifeAgent, cast(object, agent))


def _pair_key(agent_a: SimAgent, agent_b: SimAgent) -> str:
    """Order-independent identifier for an agent pair's per-pair cooldown."""
    return "|".join(sorted((str(agent_a.identity.id), str(agent_b.identity.id))))


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
    cognitive_time_step_seconds: int = 60
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
        dialogue_turn_window: int | None = None,
        dialogue_target_turns: int = 5,
        tick_interval_seconds: float = 1.0,
        cognitive_time_step_seconds: int = 60,
        planning_coordinator: PlanningCoordinator | None = None,
        spatial_runtime: SpatialWorldRuntime | None = None,
        encounter_gate: EncounterGate | None = None,
        plan_react_gate: PlanDisruptionGate | None = None,
    ) -> None:
        if len(agents) < 2:
            raise ValueError("WorldRuntime requires at least two agents")
        if tick_interval_seconds <= 0:
            raise ValueError("tick_interval_seconds must be greater than 0")
        if cognitive_time_step_seconds <= 0:
            raise ValueError("cognitive_time_step_seconds must be greater than 0")
        if cognitive_time_step_seconds > engine.config.turn_time_step_seconds:
            raise ValueError(
                "cognitive_time_step_seconds must not exceed turn_time_step_seconds"
            )

        self.agents: list[SimAgent] = agents
        # `_idle_session` exists purely so `step()` has a session object to
        # hand `engine.step()` when no dialogue is active (see
        # `_primary_session()`) — it's never itself entered into
        # `self.sessions` unless the caller constructed it already active
        # (e.g. tests seeding an in-progress dialogue), in which case it's
        # also this runtime's first live session.
        self._idle_session: WorldConversationSession = session
        self.sessions: dict[str, WorldConversationSession] = {}
        if session.is_active:
            self.sessions[_pair_key(*session.agents)] = session
        self.engine: SimulationEngine = engine
        self.current_time: datetime.datetime = current_time
        self._dialogue_turn_window: int | None = dialogue_turn_window
        self._dialogue_target_turns: int = dialogue_target_turns
        self.tick_interval_seconds: float = tick_interval_seconds
        self.cognitive_time_step_seconds: int = cognitive_time_step_seconds
        self.turn: int = 0
        self.parse_failures: int = 0
        self.silent_turns: int = 0
        self._step_lock: threading.Lock = threading.Lock()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._scheduler_stop_requested: bool = False
        self._plan_refresh_thread: threading.Thread | None = None
        self._cognitive_tasks: dict[str, asyncio.Task[None]] = {}
        self.planning_coordinator: PlanningCoordinator | None = planning_coordinator
        self.spatial_runtime: SpatialWorldRuntime | None = spatial_runtime
        self.encounter_gate: EncounterGate | None = encounter_gate
        self.plan_react_gate: PlanDisruptionGate | None = plan_react_gate
        self._pair_cooldown_until: dict[str, datetime.datetime] = {}
        self._co_present_pair_keys: set[str] = set()
        self._pending_encounter_pair_keys: set[str] = set()
        self._last_perceived_action: dict[str, str] = {}
        self._plan_react_thread: threading.Thread | None = None
        self._dashboard_events: DashboardEventBuffer = DashboardEventBuffer()
        relationship_baselines: dict[tuple[str, str], RelationshipMetrics] = {}
        for agent in agents:
            profile = getattr(agent, "profile", None)
            fixed = getattr(profile, "fixed", None)
            for target_id, baseline in getattr(
                fixed, "relationship_baselines", {}
            ).items():
                relationship_baselines[(str(agent.identity.id), target_id)] = (
                    RelationshipMetrics(
                        familiarity=baseline.familiarity,
                        trust=baseline.trust,
                        affinity=baseline.affinity,
                        tension=baseline.tension,
                        romantic_interest=baseline.romantic_interest,
                    )
                )
        self.relationships = RelationshipService(
            (str(agent.identity.id) for agent in agents),
            baselines=relationship_baselines,
        )
        self.home_access_policy: HomeAccessPolicy | None = None
        if all(getattr(agent.identity, "home", "") for agent in agents):
            self.home_access_policy = HomeAccessPolicy(
                agents=agents,
                relationships=self.relationships,
            )
            if self.planning_coordinator is not None:
                self.planning_coordinator.set_location_access_policy(
                    self.home_access_policy
                )
            if self.spatial_runtime is not None:
                self.spatial_runtime.set_home_access_checker(
                    self.home_access_policy.can_enter_home
                )
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
            session, pair_key = self._primary_session()
            dialogue_was_active = session.is_active
            speaker = session.next_speaker()
            speaking_partner = self._partner_of(speaker, session)
            try:
                step_result = self.engine.step(
                    turn=self.turn,
                    current_time=self.current_time,
                    speaker=speaker,
                    speaking_partner=speaking_partner,
                    session=session,
                    world_context=self._dialogue_world_context(
                        speaker=speaker,
                        partner=speaking_partner,
                    ),
                    recent_speaker_replies=self._recent_replies_for_agent(
                        agent_id=str(speaker.identity.id)
                    ),
                )
            except Exception as error:
                logger.exception(
                    "Agent action loop failed; continuing the world clock",
                    extra={"agent_id": str(speaker.identity.id), "turn": self.turn},
                )
                session.finish_dialogue()
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
            if pair_key is not None and dialogue_was_active and not session.is_active:
                self._record_completed_dialogue_relationships(
                    pair_key=pair_key,
                    session=session,
                    occurred_at=self.current_time,
                )
                self._pair_cooldown_until[pair_key] = self.current_time
                self.sessions.pop(pair_key, None)
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

    def evaluate_plan_disruption(
        self, *, agent: SimAgent, observation_content: str
    ) -> PlanDisruptionDecision | None:
        """§4.3.1 tick-level continue-vs-react gate.

        Distinct from `session`'s in-dialogue `should_react`: this judges
        whether an arbitrary observation (e.g. a God-mode injected
        perception event) disrupts `agent`'s existing plan enough to
        warrant reacting. On react, only the current-time-forward segment
        of the plan is regenerated via `PlanningCoordinator.react_replan`.
        """
        if self.plan_react_gate is None:
            return None

        current_plan_context = agent.profile.extended.current_plan_context
        agent_status = current_plan_context[0] if current_plan_context else "Idle"
        decision = self.plan_react_gate.evaluate(
            PlanDisruptionInput(
                agent_identity=agent.identity,
                profile=agent.profile,
                current_time=self.current_time,
                agent_status=agent_status,
                observation_content=observation_content,
            )
        )
        diagnostics = build_plan_disruption_diagnostics(
            agent_name=agent.name, decision=decision
        )
        logger.info(
            "plan disruption decision agent=%s should_react=%s reason=%s",
            agent.name,
            diagnostics.should_react,
            diagnostics.reason,
        )
        if decision.should_react and self.planning_coordinator is not None:
            try:
                self.planning_coordinator.react_replan(
                    agent=_as_life_agent(agent),
                    now=self.current_time,
                    reason=f"tick_react:{decision.reason}",
                )
            except PlanningGenerationError:
                logger.exception(
                    "react replan failed for agent=%s; keeping previous schedule",
                    agent.name,
                )
        return decision

    def _partner_of(
        self, speaker: SimAgent, session: WorldConversationSession
    ) -> SimAgent:
        first, second = session.agents
        return second if speaker is first else first

    def _dialogue_world_context(
        self, *, speaker: SimAgent, partner: SimAgent
    ) -> dict[str, str]:
        spatial_agents: tuple[SpatialAgentSnapshot, ...] = ()
        if self.spatial_runtime is not None:
            try:
                spatial_agents = self.spatial_runtime.snapshot().agents
            except AttributeError:
                # Lightweight test doubles may implement encounter methods only.
                pass
        snapshots = {
            snapshot.agent_id: snapshot for snapshot in spatial_agents
        }
        speaker_snapshot = snapshots.get(str(speaker.identity.id))
        partner_snapshot = snapshots.get(str(partner.identity.id))
        shared_location = (
            speaker_snapshot.destination
            if speaker_snapshot is not None
            else None
        ) or (
            partner_snapshot.destination if partner_snapshot is not None else None
        )
        return build_turn_world_context(
            speaker_name=speaker.name,
            partner_name=partner.name,
            location=shared_location,
            speaker_action=(
                speaker_snapshot.current_action
                if speaker_snapshot is not None
                else None
            ),
            partner_action=(
                partner_snapshot.current_action
                if partner_snapshot is not None
                else None
            ),
        )

    def _recent_replies_for_agent(
        self, *, agent_id: str, limit: int = 12
    ) -> list[str]:
        if limit < 1:
            return []
        replies = [
            event.reply
            for event in self._dashboard_events.snapshot(limit=500)
            if event.agent_id == agent_id and event.reply.strip()
        ]
        return replies[-limit:]

    @staticmethod
    def _dialogue_goal_from_encounter(decision: EncounterDecision) -> str:
        return " | ".join(
            (
                f"관계 맥락: {decision.relationship_summary}",
                f"현재 상황: {decision.context_summary}",
                f"대화 의도: {decision.reason}",
            )
        )

    def _primary_session(self) -> tuple[WorldConversationSession, str | None]:
        """The session `step()`/`metrics()`/`state()` treat as *the* dialogue.

        `step()` is a single-call, single-result driver (used by the CLI
        harness and tests), so it can only ever advance one session per
        call even when several are running concurrently. It picks
        whichever active session was opened first; callers that need every
        concurrent dialogue advanced should rely on the scheduler
        (`_run_scheduler`/`_run_cognitive_turn`) instead, which does drive
        all of `self.sessions` in parallel. Returns `(session, None)` with
        `self._idle_session` when nothing is active — that placeholder is
        intentionally never added to `self.sessions`.
        """
        if self.sessions:
            pair_key, session = next(iter(self.sessions.items()))
            return session, pair_key
        return self._idle_session, None

    def _engaged_agent_ids(self) -> set[str]:
        return {
            str(agent.identity.id)
            for session in self.sessions.values()
            for agent in session.agents
        }

    def _open_session_for_pair(
        self,
        agent_a: SimAgent,
        agent_b: SimAgent,
        *,
        dialogue_goal: str | None = None,
    ) -> WorldConversationSession:
        """Start a new session for this pair alongside any other sessions
        already running (§3.4 pairwise model — multiple disjoint pairs may
        converse at once; an agent already in `self.sessions` is never
        offered a second pair, see `_engaged_agent_ids`).
        """
        session = WorldConversationSession(
            agents=[agent_a, agent_b],
            dialogue_turn_window=self._dialogue_turn_window,
            dialogue_target_turns=self._dialogue_target_turns,
            dialogue_goal=dialogue_goal,
        )
        self.sessions[_pair_key(agent_a, agent_b)] = session
        return session

    def _reopen_session_for_restore(
        self, participant_agent_names: tuple[str, str]
    ) -> WorldConversationSession:
        """Rebuild (and register in `self.sessions`) the session for
        whichever pair a save snapshot names.

        Called after the per-agent identity fields are already restored
        (`agent.identity.name = saved.name`), so `participant_agent_names`
        (captured from the same snapshot) and current agent names agree.
        `restore_save_state` then calls `session.restore_state(...)` on the
        result to fill in the saved history/turn counters/is_active flag.
        """
        agents_by_name = {agent.name: agent for agent in self.agents}
        try:
            agent_a = agents_by_name[participant_agent_names[0]]
            agent_b = agents_by_name[participant_agent_names[1]]
        except KeyError as error:
            raise ValueError(
                "saved dialogue participants do not match current agent roster"
            ) from error
        return self._open_session_for_pair(agent_a, agent_b)

    def _start_dialogue_for_real_encounter(self, now: datetime.datetime) -> None:
        """Open one new pairwise dialogue per call, if a qualifying and
        not-yet-engaged pair is found (§3.4). Multiple sessions can be
        active at once — an agent already in `self.sessions` is skipped so
        it's never double-booked into a second concurrent dialogue — but
        only one *new* session is opened per call, mirroring the
        one-thing-per-tick pattern `_dispatch_tick_plan_disruption_check`
        already uses to bound how much LLM-calling work a single tick does.
        """
        if self.spatial_runtime is None:
            return

        qualifying_pairs = self._qualifying_encounter_pairs()
        current_pair_keys = {
            _pair_key(agent_a, agent_b) for agent_a, agent_b in qualifying_pairs
        }
        departed_pair_keys = self._co_present_pair_keys - current_pair_keys
        self._pending_encounter_pair_keys.difference_update(departed_pair_keys)
        self._pending_encounter_pair_keys.update(
            current_pair_keys - self._co_present_pair_keys
        )
        self._co_present_pair_keys = current_pair_keys

        engaged = self._engaged_agent_ids()
        for agent_a, agent_b in qualifying_pairs:
            pair_key = _pair_key(agent_a, agent_b)
            if pair_key not in self._pending_encounter_pair_keys:
                continue
            if (
                str(agent_a.identity.id) in engaged
                or str(agent_b.identity.id) in engaged
            ):
                self._pending_encounter_pair_keys.discard(pair_key)
                continue
            self._pending_encounter_pair_keys.discard(pair_key)
            cooldown_until = self._pair_cooldown_until.get(pair_key)
            if (
                cooldown_until is not None
                and now - cooldown_until < datetime.timedelta(minutes=30)
            ):
                continue

            decision = self._should_converse_on_encounter(
                now, speaker=agent_a, other=agent_b
            )
            if not decision.should_converse:
                self._pair_cooldown_until[pair_key] = now
                continue

            self._open_session_for_pair(
                agent_a,
                agent_b,
                dialogue_goal=self._dialogue_goal_from_encounter(decision),
            )
            return

    def _qualifying_encounter_pairs(self) -> list[tuple[SimAgent, SimAgent]]:
        if self.spatial_runtime is None:
            return []
        snapshots = {
            snapshot.agent_id: snapshot
            for snapshot in self.spatial_runtime.snapshot().agents
        }
        qualifying: list[tuple[SimAgent, SimAgent]] = []
        for agent_a, agent_b in itertools.combinations(self.agents, 2):
            first = snapshots.get(str(agent_a.identity.id))
            second = snapshots.get(str(agent_b.identity.id))
            if first is None or second is None:
                continue
            distance = abs(first.tile_position.x - second.tile_position.x) + abs(
                first.tile_position.y - second.tile_position.y
            )
            first_inside = first.current_action.startswith("inside:")
            second_inside = second.current_action.startswith("inside:")
            both_arrived = first.current_action.startswith(
                ("at:", "arrived_at:", "inside:")
            ) and second.current_action.startswith(("at:", "arrived_at:", "inside:"))
            if (
                both_arrived
                and first_inside == second_inside
                and first.destination is not None
                and first.destination == second.destination
                and distance <= 1
            ):
                qualifying.append((agent_a, agent_b))
        return qualifying

    def _dispatch_tick_plan_disruption_check(self, now: datetime.datetime) -> None:
        """§4.3.1 organic per-tick perception (outside dialogue and god-mode).

        Distinct from `evaluate_plan_disruption`'s only other caller (the
        god-mode injection endpoint): this observes the other agent's
        current spatial action every tick, and only when it changed since
        the last tick does it hand the continue-vs-react judgment to a
        background thread. This keeps `_advance_world_tick` LLM-free (its
        documented contract) while still surfacing organic observations
        (movement, arrival) to the gate, not just injected ones.

        Runs a plain `threading.Thread` rather than `asyncio.create_task`:
        `_advance_world_tick` itself executes inside `asyncio.to_thread`
        (see the scheduler loop), so no event loop is running on this
        thread and `create_task` would raise `RuntimeError`.
        """
        if (
            self.plan_react_gate is None
            or self.spatial_runtime is None
            or self.sessions
        ):
            return
        if self._plan_react_thread is not None and self._plan_react_thread.is_alive():
            return

        snapshots = {
            snapshot.agent_id: snapshot
            for snapshot in self.spatial_runtime.snapshot().agents
        }
        for agent, other in itertools.permutations(self.agents, 2):
            other_snapshot = snapshots.get(str(other.identity.id))
            if other_snapshot is None:
                continue
            observation = f"{other.name}가 {other_snapshot.current_action} 상태이다."
            agent_key = str(agent.identity.id)
            if self._last_perceived_action.get(agent_key) == observation:
                continue
            self._last_perceived_action[agent_key] = observation
            self._plan_react_thread = threading.Thread(
                target=self._run_plan_disruption_check,
                kwargs={"agent": agent, "observation_content": observation},
                daemon=True,
            )
            self._plan_react_thread.start()
            return

    def _run_plan_disruption_check(
        self, *, agent: SimAgent, observation_content: str
    ) -> None:
        """Store the tick-perceived observation as a memory, then judge it.

        Runs off `_advance_world_tick`'s fast no-LLM loop (see
        `_dispatch_tick_plan_disruption_check`), so it's safe to do both the
        embedding/importance-scoring LLM calls of `create_observation_from_text`
        and the disruption-gate call here. Mirrors the god-mode injection
        endpoint's store-then-evaluate sequence (`api/main.py`
        `post_god_mode_perception`) so organic tick observations feed
        retrieval/reflection the same way injected ones do (§4 Perceive→Store).
        """
        from agents.memory.memory_manager import ObservationContext

        try:
            current_plan_context = agent.profile.extended.current_plan_context
            agent.memory_service.create_observation_from_text(
                content=observation_content,
                now=self.current_time,
                context=ObservationContext(
                    agent_name=agent.name,
                    identity_stable_set=list(agent.profile.fixed.identity_stable_set),
                    current_plan=(
                        current_plan_context[0] if current_plan_context else None
                    ),
                ),
            )
        except Exception:
            logger.exception(
                "tick-level observation memory write failed for agent=%s", agent.name
            )

        try:
            self.evaluate_plan_disruption(
                agent=agent, observation_content=observation_content
            )
        except Exception:
            logger.exception(
                "tick-level plan disruption check failed for agent=%s", agent.name
            )

    def _should_converse_on_encounter(
        self, now: datetime.datetime, *, speaker: SimAgent, other: SimAgent
    ) -> EncounterDecision:
        """§3.4/§4.3 조우 시 pass-by vs converse 결정.

        `encounter_gate`가 구성되지 않은 경우 기존 동작(항상 대화)을 그대로
        유지한다.
        """
        if self.encounter_gate is None:
            return EncounterDecision(
                should_converse=True,
                relationship_summary=f"{speaker.name}와 {other.name}의 관계 정보 없음",
                context_summary=f"{speaker.name}와 {other.name}가 같은 장소에 도착함",
                reason="현재 계획과 관계 맥락에 맞는 짧은 대화를 나눈다",
            )

        try:
            retrieved_memories = speaker.memory_service.get_retrieval_memories(
                f"{other.name}와의 관계와 최근 있었던 일",
                current_time=now,
                top_k=3,
            )
        except Exception:
            retrieved_memories = []

        try:
            decision = self.encounter_gate.evaluate(
                EncounterDecisionInput(
                    self_identity=speaker.identity,
                    other_identity=other.identity,
                    self_profile=speaker.profile,
                    current_time=now,
                    retrieved_memories=retrieved_memories,
                )
            )
        except Exception:
            logger.exception("encounter gate evaluation failed; defaulting to converse")
            return EncounterDecision(
                should_converse=True,
                relationship_summary="관계 요약 생성 실패",
                context_summary="같은 장소에 도착함",
                reason="조우 판정 실패로 기존 대화 동작을 유지한다",
            )

        diagnostics = build_encounter_diagnostics(
            self_name=speaker.name, other_name=other.name, decision=decision
        )
        logger.info(
            "encounter decision agent=%s other=%s should_converse=%s reason=%s",
            speaker.name,
            other.name,
            diagnostics.should_converse,
            diagnostics.reason,
        )
        return decision

    def tick(self) -> SimulationStepResult:
        """Advance the single runtime clock by one perceive-plan-act tick."""
        return self.step()

    @property
    def scheduler_running(self) -> bool:
        return self._scheduler_task is not None and not self._scheduler_task.done()

    @property
    def cognitive_active(self) -> bool:
        cognitive_turn_in_flight = any(
            not task.done() for task in self._cognitive_tasks.values()
        )
        return bool(self.sessions) or cognitive_turn_in_flight

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
        cognitive_tasks = list(self._cognitive_tasks.values())
        for cognitive_task in cognitive_tasks:
            if not cognitive_task.done():
                await cognitive_task
            if cognitive_task.done():
                _ = cognitive_task.exception()
        self._cognitive_tasks = {}
        plan_thread = self._plan_refresh_thread
        if plan_thread is not None and plan_thread.is_alive():
            await asyncio.to_thread(plan_thread.join)
        self._plan_refresh_thread = None
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
        refresh_thread = self._plan_refresh_thread
        self._plan_refresh_thread = None
        if task.done():
            return False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        if refresh_thread is not None and refresh_thread.is_alive():
            # A background thread can't be forcibly cancelled like a task;
            # it's a daemon thread already mid-flight on (at most) one more
            # round of LLM calls, so just wait for it to finish naturally.
            await asyncio.to_thread(refresh_thread.join)
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
                schedules: list[AgentPlanSnapshot] = []
                needs_generation = False
                for agent in self.agents:
                    try:
                        schedules.append(
                            self.planning_coordinator.ensure_current(
                                agent=_as_life_agent(agent),
                                now=self.current_time,
                                generate=False,
                            )
                        )
                    except PlanningGenerationError:
                        needs_generation = True
                if self.spatial_runtime is not None:
                    for schedule in schedules:
                        self.spatial_runtime.set_schedule(schedule)
                if needs_generation:
                    await self._refresh_plans()
            except Exception as error:
                self._set_planning_error(error)
                logger.exception("Authoritative restored plan validation failed")
                return
        while not self._scheduler_stop_requested:
            try:
                await asyncio.to_thread(self._advance_world_tick)
            except Exception as error:
                # Do not kill the scheduler task on a single bad tick: that
                # previously froze every agent's movement forever (spatial
                # movement no longer gates on `planning_error`, but nothing
                # advances `current_time`/plans either once this task is
                # dead, and only a manual `POST /world/tick/start` could
                # recover). Log, surface the error for diagnostics, and
                # retry on the next tick interval instead.
                self._set_planning_error(error)
                logger.exception("Authoritative plan transition failed")
                await asyncio.sleep(self.tick_interval_seconds)
                continue
            for pair_key, session in list(self.sessions.items()):
                existing_task = self._cognitive_tasks.get(pair_key)
                if not session.is_active:
                    continue
                if existing_task is not None and not existing_task.done():
                    continue
                if existing_task is not None:
                    _ = existing_task.exception()
                self._cognitive_tasks[pair_key] = asyncio.create_task(
                    asyncio.to_thread(self._run_cognitive_turn, pair_key)
                )
            # §3.1.1 gate: the world clock only advances once every pair's
            # in-flight turn for this tick has actually finished (§3.4:
            # several pairs may be conversing concurrently). Wait for both
            # the dialogue-turn cognitive tasks and any background
            # plan-disruption check (which can mutate the plan via
            # `react_replan`) before letting the loop reach the next
            # `_advance_world_tick` call.
            in_flight_tasks = list(self._cognitive_tasks.values())
            if in_flight_tasks:
                results = await asyncio.gather(
                    *in_flight_tasks, return_exceptions=True
                )
                for result in results:
                    if isinstance(result, Exception):
                        logger.exception(
                            "Cognitive turn task failed", exc_info=result
                        )
                self._cognitive_tasks = {}
            plan_react_thread = self._plan_react_thread
            if plan_react_thread is not None:
                await asyncio.to_thread(plan_react_thread.join)
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
            if self.planning_coordinator is not None:
                self._sync_or_schedule_plan_generation(planning_time)
            self._start_dialogue_for_real_encounter(planning_time)
            self._dispatch_tick_plan_disruption_check(planning_time)
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
        offloads regeneration to `_generate_plans_blocking` via `_plan_refresh_thread`
        (all agents needing regeneration run concurrently there, not one at a time).
        Agents whose plan is mid-regeneration simply keep their last known schedule
        for this tick.

        SPEC.md §7 ("cognitive 구간에는 참여 agent의 현재 공간 계획과 목적지를
        유지") only freezes the plan/destination of the agents *actually in an
        active dialogue session* (`_engaged_agent_ids`), not every agent in the
        world. Agents outside any session must keep receiving schedule updates
        (and therefore keep walking toward their canonical destination) even
        while some other pair is talking — otherwise a single long-running
        conversation anywhere in the village freezes everyone's movement.
        """
        assert self.planning_coordinator is not None
        engaged_agent_ids = self._engaged_agent_ids()
        schedules: list[AgentPlanSnapshot] = []
        needs_generation = False
        for agent in self.agents:
            if str(agent.identity.id) in engaged_agent_ids:
                continue
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
        """Runs a background thread rather than `asyncio.create_task`:
        this is called from `_advance_world_tick`, which itself executes
        inside `asyncio.to_thread` (see the scheduler loop), so no event
        loop is running here and `create_task` would raise `RuntimeError`
        (same reasoning as `_dispatch_tick_plan_disruption_check`).
        """
        if (
            self._plan_refresh_thread is not None
            and self._plan_refresh_thread.is_alive()
        ):
            return
        self._plan_refresh_thread = threading.Thread(
            target=self._generate_plans_blocking,
            args=(planning_time,),
            daemon=True,
        )
        self._plan_refresh_thread.start()

    def _generate_plans_blocking(self, planning_time: datetime.datetime) -> None:
        """Runs off the tick loop's critical path. Regenerates every
        agent's plan concurrently (each `ensure_current` call can issue
        several sequential LLM calls) via a thread pool — this only helps
        wall-clock time because `PlanningCoordinator` now locks per agent
        rather than coordinator-wide, so different agents' LLM calls
        actually overlap instead of queuing behind one shared lock.

        The pool is capped at `PLAN_GENERATION_MAX_CONCURRENCY` rather than
        `len(self.agents)`: fanning out one LLM call per agent (6 for the
        current village) exceeds the local Ollama server's parallel request
        slots, which makes the server queue the overflow and risks tripping
        `LLM_TIMEOUT_SECONDS` on the waiting requests.

        Each agent's `ensure_current` call is isolated: one agent's
        persistent failure (bad LLM output, timeout, ...) must not discard
        every *other* agent's freshly-generated schedule, and must not stop
        the scheduler — `_sync_or_schedule_plan_generation` naturally
        re-queues only the still-stale agents on the next tick, so this is
        a self-healing retry with the tick interval as backoff, not a
        one-shot all-or-nothing batch.
        """
        assert self.planning_coordinator is not None
        planning_coordinator = self.planning_coordinator

        def _generate_one(
            agent: SimAgent,
        ) -> tuple[AgentPlanSnapshot | None, Exception | None]:
            try:
                return (
                    planning_coordinator.ensure_current(
                        agent=_as_life_agent(agent),
                        now=planning_time,
                        generate=True,
                    ),
                    None,
                )
            except Exception as error:  # noqa: BLE001 - isolated per agent below
                return None, error

        with ThreadPoolExecutor(
            max_workers=min(PLAN_GENERATION_MAX_CONCURRENCY, len(self.agents))
        ) as executor:
            results = list(executor.map(_generate_one, self.agents))

        schedules = [schedule for schedule, _ in results if schedule is not None]
        errors = [error for _, error in results if error is not None]
        for error in errors:
            logger.exception(
                "Background plan generation failed for one agent; other "
                "agents' schedules still applied, this agent retries next cycle",
                exc_info=error,
            )

        with self._step_lock:
            self._set_planning_error(
                f"{len(errors)}/{len(self.agents)} agent(s) failed to (re)plan "
                f"this cycle, retrying next tick: {errors[0]}"
                if errors
                else None
            )
            if self.spatial_runtime is not None:
                for schedule in schedules:
                    self.spatial_runtime.set_schedule(schedule)

    def _run_cognitive_turn(self, pair_key: str) -> None:
        """Run one dialogue turn for `pair_key`'s session, independently
        from the authoritative world clock. Several of these can run
        concurrently in different worker threads (§3.4 — multiple pairs
        conversing at once), one per active session; `self._step_lock`
        below serializes their shared-state writes (spatial overlays,
        counters, dashboard events). Each session object is only ever
        touched by its own pair's turn (`_engaged_agent_ids` keeps an
        agent out of more than one active session), so there's no race on
        session-local state either.
        """
        session = self.sessions.get(pair_key)
        if session is None or not session.is_active:
            return
        dialogue_was_active = session.is_active
        speaker = session.next_speaker()
        speaking_partner = self._partner_of(speaker, session)
        turn = self.turn
        cognitive_time = self.current_time
        try:
            step_result = self.engine.step(
                turn=turn,
                current_time=cognitive_time
                - datetime.timedelta(seconds=self.engine.config.turn_time_step_seconds),
                speaker=speaker,
                speaking_partner=speaking_partner,
                session=session,
                world_context=self._dialogue_world_context(
                    speaker=speaker,
                    partner=speaking_partner,
                ),
                recent_speaker_replies=self._recent_replies_for_agent(
                    agent_id=str(speaker.identity.id)
                ),
            )
        except Exception as error:
            logger.exception(
                "Agent action loop failed; continuing the world clock",
                extra={"agent_id": str(speaker.identity.id), "turn": turn},
            )
            session.finish_dialogue()
            step_result = build_failed_step_result(
                current_time=cognitive_time,
                speaker_name=speaker.name,
                error=error,
                turn_time_step_seconds=0,
            )

        with self._step_lock:
            if self.spatial_runtime is not None:
                self.spatial_runtime.clear_cognitive_overlay(
                    agent_id=speaker.identity.id
                )
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
            if dialogue_was_active and not session.is_active:
                self._record_completed_dialogue_relationships(
                    pair_key=pair_key,
                    session=session,
                    occurred_at=self.current_time,
                )
                self._pair_cooldown_until[pair_key] = self.current_time
                self.sessions.pop(pair_key, None)
            if step_result.parse_failure:
                self.parse_failures += 1
            if not step_result.reply:
                self.silent_turns += 1
            self._record_dashboard_event(speaker=speaker, result=step_result)

    def _record_completed_dialogue_relationships(
        self,
        *,
        pair_key: str,
        session: WorldConversationSession,
        occurred_at: datetime.datetime,
    ) -> None:
        """Apply one deterministic, bidirectional update per completed dialogue."""
        if not session.history:
            return
        source_event_id = f"dialogue:{pair_key}:{self.turn}"
        left, right = session.agents
        for subject, target in ((left, right), (right, left)):
            self.relationships.record_event(
                subject_agent_id=str(subject.identity.id),
                target_agent_id=str(target.identity.id),
                event_type=RelationshipEventType.DIALOGUE_COMPLETED,
                source_event_id=source_event_id,
                occurred_at=occurred_at,
                source_kind="dialogue",
            )

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
        planning_coordinator = self.planning_coordinator
        # Same rationale as `_generate_plans_blocking`: cap concurrent LLM
        # calls at `PLAN_GENERATION_MAX_CONCURRENCY` so this doesn't fan out
        # one request per agent and overrun the Ollama server's parallel
        # request slots (which would queue past `LLM_TIMEOUT_SECONDS`).
        semaphore = asyncio.Semaphore(
            min(PLAN_GENERATION_MAX_CONCURRENCY, len(self.agents))
        )

        async def _refresh_one(
            agent: SimAgent,
        ) -> tuple[AgentPlanSnapshot | None, Exception | None]:
            async with semaphore:
                try:
                    return (
                        await asyncio.to_thread(
                            planning_coordinator.refresh_current,
                            agent=_as_life_agent(agent),
                            now=planning_date,
                        ),
                        None,
                    )
                except Exception as error:  # noqa: BLE001 - isolate each resident
                    return None, error

        results = await asyncio.gather(
            *[_refresh_one(agent) for agent in self.agents]
        )
        schedules = [schedule for schedule, _ in results if schedule is not None]
        errors = [error for _, error in results if error is not None]
        for error in errors:
            logger.error(
                "Initial plan generation failed for one resident; successful "
                "resident plans remain active and only this resident will retry",
                exc_info=error,
            )
        with self._step_lock:
            self._set_planning_error(
                f"{len(errors)}/{len(self.agents)} agent(s) failed to plan; "
                f"successful plans are active and failures will retry: {errors[0]}"
                if errors
                else None
            )
            if self.spatial_runtime is not None:
                for schedule in schedules:
                    self.spatial_runtime.set_schedule(schedule)

    def _set_planning_error(self, error: Exception | str | None) -> None:
        self.planning_error = None if error is None else str(error)
        if self.spatial_runtime is not None:
            self.spatial_runtime.set_planning_error(self.planning_error)
            self.spatial_runtime.update_world_state(
                current_time=self.current_time,
                turn=self.turn,
                scheduler_running=self.scheduler_running,
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
        """Repetition/topic-progress metrics for the primary session
        (`_primary_session()`) — merging histories across concurrently
        active sessions would compare unrelated dialogues' turns as if
        they were adjacent, so with 2+ sessions active this reports only
        one of them rather than a meaningless blend.
        """
        session, _ = self._primary_session()
        return build_conversation_metrics(
            turns=self.turn,
            parse_failures=self.parse_failures,
            silent_turns=self.silent_turns,
            session_history=session.history,
        )

    def state(self) -> WorldRuntimeState:
        session, _ = self._primary_session()
        return WorldRuntimeState(
            turn=self.turn,
            current_time=self.current_time,
            parse_failures=self.parse_failures,
            silent_turns=self.silent_turns,
            history_size=len(session.history),
            scheduler_running=self.scheduler_running,
            tick_interval_seconds=self.tick_interval_seconds,
            cognitive_active=self.cognitive_active,
            effective_time_step_seconds=self.effective_time_step_seconds,
        )

    def export_save_state(self, *, scheduler_was_running: bool) -> RuntimeSaveState:
        if self.spatial_runtime is None:
            raise RuntimeError("spatial runtime is required for session persistence")
        cognitive_turn_in_flight = any(
            not task.done() for task in self._cognitive_tasks.values()
        )
        plan_refresh_in_flight = bool(
            self._plan_refresh_thread is not None
            and self._plan_refresh_thread.is_alive()
        )
        if self.scheduler_running or cognitive_turn_in_flight or plan_refresh_in_flight:
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
                pair_cooldown_until=dict(self._pair_cooldown_until),
                conversations=[
                    session.export_state() for session in self.sessions.values()
                ],
                characters=characters,
                dashboard_events=dashboard_events,
                position_history=self.spatial_runtime.export_position_history(),
                relationship_states=[
                    RelationshipStateSave(
                        subject_agent_id=state.subject_agent_id,
                        target_agent_id=state.target_agent_id,
                        metrics=RelationshipMetricsSave(**vars(state.metrics)),
                        last_interaction_at=state.last_interaction_at,
                        updated_at=state.updated_at,
                        revision=state.revision,
                    )
                    for state in self.relationships.states()
                ],
                relationship_events=[
                    RelationshipEventSave(
                        id=event.id,
                        source_event_id=event.source_event_id,
                        subject_agent_id=event.subject_agent_id,
                        target_agent_id=event.target_agent_id,
                        event_type=event.event_type.value,
                        occurred_at=event.occurred_at,
                        requested_delta=RelationshipDeltaSave(
                            **vars(event.requested_delta)
                        ),
                        applied_delta=RelationshipDeltaSave(
                            **vars(event.applied_delta)
                        ),
                        before=RelationshipMetricsSave(**vars(event.before)),
                        after=RelationshipMetricsSave(**vars(event.after)),
                        rule_version=event.rule_version,
                        source_kind=event.source_kind,
                    )
                    for event in self.relationships.events()
                ],
                relationship_event_namespace=str(self.relationships.event_namespace),
                relationship_event_ids_verified=(self.relationships.event_ids_verified),
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
            self._pair_cooldown_until = dict(state.pair_cooldown_until)
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
            self.sessions = {}
            for conversation in state.conversations:
                session = self._reopen_session_for_restore(
                    conversation.participant_agent_names
                )
                session.restore_state(conversation)
                if not session.is_active:
                    # Defensive: exported snapshots only ever contain active
                    # sessions (`export_save_state` reads `self.sessions`,
                    # which only holds active ones), but keep the "only
                    # active sessions live in `self.sessions`" invariant
                    # even if a hand-edited/older snapshot violates it.
                    self.sessions.pop(_pair_key(*session.agents), None)
            self.spatial_runtime.restore_state(
                revision=state.revision,
                current_time=state.current_time,
                turn=state.turn,
                planning_error=state.planning_error,
                characters=state.characters,
            )
            self.spatial_runtime.restore_position_history(state.position_history)
            self._co_present_pair_keys = {
                _pair_key(agent_a, agent_b)
                for agent_a, agent_b in self._qualifying_encounter_pairs()
            }
            self._pending_encounter_pair_keys = set()
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
            if state.relationship_states:
                self.relationships.restore(
                    states=[
                        RelationshipState(
                            subject_agent_id=item.subject_agent_id,
                            target_agent_id=item.target_agent_id,
                            metrics=RelationshipMetrics(**item.metrics.model_dump()),
                            last_interaction_at=item.last_interaction_at,
                            updated_at=item.updated_at,
                            revision=item.revision,
                        )
                        for item in state.relationship_states
                    ],
                    events=[
                        RelationshipEvent(
                            id=item.id,
                            source_event_id=item.source_event_id,
                            subject_agent_id=item.subject_agent_id,
                            target_agent_id=item.target_agent_id,
                            event_type=RelationshipEventType(item.event_type),
                            occurred_at=item.occurred_at,
                            requested_delta=RelationshipMetrics(
                                **item.requested_delta.model_dump()
                            ),
                            applied_delta=RelationshipMetrics(
                                **item.applied_delta.model_dump()
                            ),
                            before=RelationshipMetrics(**item.before.model_dump()),
                            after=RelationshipMetrics(**item.after.model_dump()),
                            rule_version=item.rule_version,
                            source_kind=item.source_kind,
                        )
                        for item in state.relationship_events
                    ],
                    event_namespace=uuid.UUID(state.relationship_event_namespace),
                    verify_event_ids=state.relationship_event_ids_verified,
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
    # 초기 세션은 항상 비활성 placeholder다 — 실제 참가 쌍은
    # `_start_dialogue_for_real_encounter`가 조우 시점에 결정해
    # `_open_session_for_pair`로 매번 새로 만든다 (§3.4 pairwise 대화 모델).
    session = WorldConversationSession(
        agents=[agents[0], agents[1]],
        dialogue_turn_window=config.dialogue_turn_window,
        dialogue_target_turns=config.dialogue_target_turns,
    )
    session.finish_dialogue()
    engine = SimulationEngine(
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
        dialogue_turn_window=config.dialogue_turn_window,
        dialogue_target_turns=config.dialogue_target_turns,
        tick_interval_seconds=config.tick_interval_seconds,
        cognitive_time_step_seconds=config.cognitive_time_step_seconds,
        planning_coordinator=PlanningCoordinator(),
        spatial_runtime=spatial_runtime,
        encounter_gate=EncounterGate(generation_client=llm_client),
        plan_react_gate=PlanDisruptionGate(generation_client=llm_client),
    )
    return runtime


def default_persona_dir() -> str:
    return str(Path(__file__).resolve().parents[2] / "persona")
