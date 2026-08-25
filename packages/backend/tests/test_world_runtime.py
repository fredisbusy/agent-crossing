import asyncio
import datetime
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import pytest

from agents.sim_agent import SimAgent
from agents.planning.lifecycle import PlanningCoordinator
from agents.reaction.encounter import EncounterDecision, EncounterGate
from agents.planning.react_gate import PlanDisruptionDecision, PlanDisruptionGate
from world.engine import (
    SimulationEngine,
    SimulationStepObservability,
    SimulationStepResult,
)
from world.runtime import WorldRuntime
from world.session import WorldConversationSession
from world.spatial import SpatialAgentSeed, SpatialWorldRuntime
from world.world_map import load_world_map


@dataclass
class DummyIdentity:
    id: str


@dataclass
class DummyAgent:
    name: str
    agent_id: str = ""

    @property
    def identity(self) -> DummyIdentity:
        return DummyIdentity(id=self.agent_id or self.name.lower())


@dataclass
class DummyEngine:
    result: SimulationStepResult

    @property
    def config(self) -> SimpleNamespace:
        return SimpleNamespace(turn_time_step_seconds=300)

    def step(
        self,
        *,
        turn: int,
        current_time: datetime.datetime,
        speaker: SimAgent,
        speaking_partner: SimAgent,
    ) -> SimulationStepResult:
        _ = turn
        _ = current_time
        _ = speaker
        _ = speaking_partner
        return self.result


class FailingEngine:
    def __init__(self) -> None:
        self.config: SimpleNamespace = SimpleNamespace(turn_time_step_seconds=300)

    def step(self, **kwargs: object) -> SimulationStepResult:
        _ = kwargs
        raise RuntimeError("cognitive provider unavailable")


class BlockingEngine:
    def __init__(self) -> None:
        self.config: SimpleNamespace = SimpleNamespace(turn_time_step_seconds=300)
        self.started: threading.Event = threading.Event()
        self.release: threading.Event = threading.Event()

    def step(self, **kwargs: object) -> SimulationStepResult:
        _ = kwargs
        self.started.set()
        if not self.release.wait(timeout=1):
            raise TimeoutError("test cognitive turn was not released")
        return SimulationStepResult(
            now=datetime.datetime(2026, 8, 24, 18, 40),
            speaker_name="Jiho",
            trace={},
            reply="안녕",
            silent_reason="",
            parse_failure=False,
            observability=SimulationStepObservability(
                thought="",
                model_thought="",
                self_critique="",
                decision_reason="",
                action_summary="talk",
                decision_process={},
            ),
        )


class DelayedPlanningCoordinator:
    def __init__(self) -> None:
        self.started: threading.Event = threading.Event()
        self.release: threading.Event = threading.Event()
        self.refresh_times: list[datetime.datetime] = []

    def refresh_current(self, **kwargs: object) -> object:
        now = kwargs["now"]
        assert isinstance(now, datetime.datetime)
        self.started.set()
        if not self.release.wait(timeout=1):
            raise TimeoutError("test plan generation was not released")
        self.refresh_times.append(now)
        return object()


class CountingPlanningCoordinator:
    def __init__(self) -> None:
        self.ensure_calls: int = 0

    def ensure_current(self, **kwargs: object) -> object:
        _ = kwargs
        self.ensure_calls += 1
        return object()


class FailingSecondPlanningCoordinator:
    def __init__(self) -> None:
        self.calls = 0

    def ensure_current(self, **kwargs: object) -> object:
        _ = kwargs
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("second agent plan failed")
        return object()


class RecordingSpatialRuntime:
    def __init__(self) -> None:
        self.schedules: list[object] = []

    def set_schedule(self, schedule: object) -> None:
        self.schedules.append(schedule)


def test_world_runtime_updates_counters_on_step() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(
            SimulationEngine,
            cast(
                object,
                DummyEngine(
                    result=SimulationStepResult(
                        now=datetime.datetime(2026, 3, 4, 10, 0, 0),
                        speaker_name="Jiho",
                        trace={"parse_success": False},
                        reply="",
                        silent_reason="llm_declined",
                        parse_failure=True,
                        observability=SimulationStepObservability(
                            thought="",
                            model_thought="",
                            self_critique="",
                            decision_reason="",
                            action_summary="",
                            decision_process={},
                        ),
                    )
                ),
            ),
        ),
        current_time=datetime.datetime(2026, 3, 4, 9, 0, 0),
    )

    result = runtime.step()

    assert result.parse_failure is True
    assert runtime.turn == 1
    assert runtime.parse_failures == 1
    assert runtime.silent_turns == 1


def test_world_runtime_tick_uses_single_step_clock() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(
            SimulationEngine,
            cast(
                object,
                DummyEngine(
                    result=SimulationStepResult(
                        now=datetime.datetime(2026, 3, 4, 10, 15, 0),
                        speaker_name="Jiho",
                        trace={"parse_success": True},
                        reply="안녕",
                        silent_reason="",
                        parse_failure=False,
                        observability=SimulationStepObservability(
                            thought="",
                            model_thought="",
                            self_critique="",
                            decision_reason="",
                            action_summary="",
                            decision_process={},
                        ),
                    )
                ),
            ),
        ),
        current_time=datetime.datetime(2026, 3, 4, 9, 0, 0),
    )

    result = runtime.tick()

    assert result.reply == "안녕"
    assert runtime.turn == 1
    assert runtime.current_time == datetime.datetime(2026, 3, 4, 10, 15, 0)
    assert runtime.state().scheduler_running is False


def test_world_runtime_keeps_clock_running_when_cognitive_step_fails() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    current_time = datetime.datetime(2026, 8, 24, 18, 35)
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(SimulationEngine, cast(object, FailingEngine())),
        current_time=current_time,
    )

    result = runtime.tick()

    assert result.silent_reason == "action_loop_error"
    assert result.trace == {"runtime_error": "RuntimeError"}
    assert runtime.current_time == current_time + datetime.timedelta(minutes=5)
    assert runtime.turn == 1
    assert runtime.parse_failures == 1


def test_authoritative_plan_refresh_holds_world_time_until_ready() -> None:
    asyncio.run(_assert_authoritative_plan_refresh_holds_world_time_until_ready())


async def _assert_authoritative_plan_refresh_holds_world_time_until_ready() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    coordinator = DelayedPlanningCoordinator()
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(
            SimulationEngine,
            cast(
                object,
                DummyEngine(
                    result=SimulationStepResult(
                        now=datetime.datetime(2026, 8, 24, 6, 5),
                        speaker_name="Jiho",
                        trace={},
                        reply="",
                        silent_reason="dialogue_session_ended",
                        parse_failure=False,
                        observability=SimulationStepObservability(
                            thought="",
                            model_thought="",
                            self_critique="",
                            decision_reason="",
                            action_summary="continue_current_plan",
                            decision_process={},
                        ),
                    )
                ),
            ),
        ),
        current_time=datetime.datetime(2026, 8, 24, 6, 0),
        planning_coordinator=cast(PlanningCoordinator, cast(object, coordinator)),
    )

    refresh_task = asyncio.create_task(runtime._refresh_plans())
    started = await asyncio.to_thread(coordinator.started.wait, 1)
    assert started is True
    coordinator.release.set()
    await refresh_task

    planning_time = datetime.datetime(2026, 8, 24, 6, 0)
    assert runtime.current_time == planning_time
    assert coordinator.refresh_times == [planning_time, planning_time]


def test_scheduler_clock_gates_on_in_flight_cognitive_turn() -> None:
    """§3.1.1: the world clock only advances after the in-flight cognitive
    turn (dialogue generation) for this tick has actually finished -- it must
    not free-run on the wall-clock timer while an agent action is still being
    decided.
    """
    asyncio.run(_assert_scheduler_clock_gates_on_cognitive_turn())


async def _assert_scheduler_clock_gates_on_cognitive_turn() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    engine = BlockingEngine()
    initial_time = datetime.datetime(2026, 8, 24, 18, 35)
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(SimulationEngine, cast(object, engine)),
        current_time=initial_time,
        tick_interval_seconds=0.01,
    )

    assert await runtime.start_scheduler() is True
    started = await asyncio.to_thread(engine.started.wait, 1)
    assert started is True

    # While the cognitive turn is blocked inside engine.step(), the clock
    # must stay parked at the tick that dispatched it -- no further ticks may
    # elapse until that turn resolves.
    blocked_time = runtime.current_time
    await asyncio.sleep(0.05)
    assert runtime.scheduler_running is True
    assert runtime.current_time == blocked_time
    assert runtime.cognitive_active is True

    engine.release.set()
    await asyncio.sleep(0.05)

    # Once released, the gate clears and the clock is free to advance again.
    assert runtime.current_time > blocked_time

    assert await runtime.stop_scheduler() is True


def test_cognitive_tick_slows_clock_and_holds_current_plan() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    coordinator = CountingPlanningCoordinator()
    initial_time = datetime.datetime(2026, 8, 24, 18, 35)
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(SimulationEngine, cast(object, BlockingEngine())),
        current_time=initial_time,
        planning_coordinator=cast(PlanningCoordinator, cast(object, coordinator)),
    )

    runtime._advance_world_tick()

    assert runtime.current_time == initial_time + datetime.timedelta(seconds=30)
    assert runtime.effective_time_step_seconds == 30
    assert coordinator.ensure_calls == 0


def test_world_tick_installs_agent_schedules_atomically() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    session.finish_dialogue()
    coordinator = FailingSecondPlanningCoordinator()
    spatial = RecordingSpatialRuntime()
    initial_time = datetime.datetime(2026, 8, 24, 6, 25)
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(
            SimulationEngine,
            cast(
                object,
                DummyEngine(
                    result=SimulationStepResult(
                        now=initial_time,
                        speaker_name="Jiho",
                        trace={},
                        reply="",
                        silent_reason="",
                        parse_failure=False,
                        observability=SimulationStepObservability(
                            thought="",
                            model_thought="",
                            self_critique="",
                            decision_reason="",
                            action_summary="",
                            decision_process={},
                        ),
                    )
                ),
            ),
        ),
        current_time=initial_time,
        planning_coordinator=cast(PlanningCoordinator, cast(object, coordinator)),
        spatial_runtime=cast(SpatialWorldRuntime, cast(object, spatial)),
    )

    try:
        runtime._advance_world_tick()
    except RuntimeError as error:
        assert str(error) == "second agent plan failed"
    else:
        raise AssertionError("expected the second plan generation to fail")

    assert spatial.schedules == []
    assert runtime.current_time == initial_time


def test_world_runtime_scheduler_starts_and_stops() -> None:
    asyncio.run(_assert_world_runtime_scheduler_starts_and_stops())


async def _assert_world_runtime_scheduler_starts_and_stops() -> None:
    agents = cast(list[SimAgent], [DummyAgent(name="Jiho"), DummyAgent(name="Sujin")])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(
            SimulationEngine,
            cast(
                object,
                DummyEngine(
                    result=SimulationStepResult(
                        now=datetime.datetime(2026, 3, 4, 10, 15, 0),
                        speaker_name="Jiho",
                        trace={"parse_success": True},
                        reply="안녕",
                        silent_reason="",
                        parse_failure=False,
                        observability=SimulationStepObservability(
                            thought="",
                            model_thought="",
                            self_critique="",
                            decision_reason="",
                            action_summary="",
                            decision_process={},
                        ),
                    )
                ),
            ),
        ),
        current_time=datetime.datetime(2026, 3, 4, 9, 0, 0),
        tick_interval_seconds=60,
    )

    started = await runtime.start_scheduler()
    started_again = await runtime.start_scheduler()

    assert started is True
    assert started_again is False
    assert runtime.scheduler_running is True

    stopped = await runtime.stop_scheduler()

    assert stopped is True
    assert runtime.scheduler_running is False


def test_world_runtime_bridges_speech_and_public_thought_to_spatial_state() -> None:
    agents = cast(
        list[SimAgent],
        [
            DummyAgent(name="Jiho", agent_id="jiho"),
            DummyAgent(name="Sujin", agent_id="sujin"),
        ],
    )
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
    spatial = SpatialWorldRuntime(
        world_map=load_world_map(),
        seeds=[
            SpatialAgentSeed(agent_id="jiho", name="Jiho", plan_context=("카페",)),
            SpatialAgentSeed(agent_id="sujin", name="Sujin", plan_context=("카페",)),
        ],
    )
    engine = DummyEngine(
        result=SimulationStepResult(
            now=datetime.datetime(2026, 3, 4, 10, 0),
            speaker_name="Jiho",
            trace={},
            reply="수진아, 좋은 저녁이야.",
            silent_reason="",
            parse_failure=False,
            observability=SimulationStepObservability(
                thought="",
                model_thought="노출하면 안 되는 내부 사고",
                self_critique="노출하면 안 되는 자기비평",
                decision_reason="",
                action_summary="",
                decision_process={"private": "노출 금지"},
            ),
        )
    )
    runtime = WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(SimulationEngine, cast(object, engine)),
        current_time=datetime.datetime(2026, 3, 4, 9, 55),
        spatial_runtime=spatial,
    )

    runtime.step()

    jiho = next(
        agent for agent in spatial.snapshot().agents if agent.agent_id == "jiho"
    )
    assert jiho.bubble_kind == "speech"
    assert jiho.bubble_text == "수진아, 좋은 저녁이야."
    assert "내부 사고" not in jiho.bubble_text
    assert "자기비평" not in jiho.bubble_text

    engine.result = SimulationStepResult(
        now=datetime.datetime(2026, 3, 4, 10, 5),
        speaker_name="Sujin",
        trace={},
        reply="",
        silent_reason="상대의 말을 생각하는 중",
        parse_failure=False,
        observability=SimulationStepObservability(
            thought="지호의 안부를 반갑게 받아들인다",
            model_thought="노출하면 안 되는 더 자세한 내부 사고",
            self_critique="",
            decision_reason="",
            action_summary="",
            decision_process={},
        ),
    )

    runtime.step()

    sujin = next(
        agent for agent in spatial.snapshot().agents if agent.agent_id == "sujin"
    )
    assert sujin.bubble_kind == "thought"
    assert sujin.bubble_text == "지호의 안부를 반갑게 받아들인다"
    assert "더 자세한 내부 사고" not in sujin.bubble_text


class StubEncounterGate:
    def __init__(self, should_converse: bool) -> None:
        self.should_converse: bool = should_converse
        self.calls: int = 0

    def evaluate(self, input: object) -> EncounterDecision:
        _ = input
        self.calls += 1
        return EncounterDecision(
            should_converse=self.should_converse,
            relationship_summary="관계 요약",
            context_summary="상황 요약",
            reason="스텁 판정",
        )


class StubPlanReactGate:
    def __init__(self, *, should_react: bool = False) -> None:
        self.should_react: bool = should_react
        self.calls: list[object] = []

    def evaluate(self, input: object) -> PlanDisruptionDecision:
        self.calls.append(input)
        return PlanDisruptionDecision(should_react=self.should_react, reason="스텁 판정")


class FakeAgentSnapshot:
    def __init__(
        self,
        *,
        agent_id: str,
        current_action: str,
        tile_position: object = None,
        destination: object = None,
    ) -> None:
        self.agent_id: str = agent_id
        self.current_action: str = current_action
        self.tile_position: object = tile_position
        self.destination: object = destination


class FakeSpatialSnapshot:
    def __init__(self, *, agents: tuple[object, ...]) -> None:
        self.agents: tuple[object, ...] = agents


class FakeSpatialRuntime:
    def __init__(self, *, agents: tuple[object, ...]) -> None:
        self._agents: tuple[object, ...] = agents

    def snapshot(self) -> FakeSpatialSnapshot:
        return FakeSpatialSnapshot(agents=self._agents)

    def update_world_state(self, **kwargs: object) -> None:
        _ = kwargs


def _dummy_full_agent(name: str, *, agent_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        identity=DummyIdentity(id=agent_id),
        profile=SimpleNamespace(
            fixed=SimpleNamespace(identity_stable_set=[]),
            extended=SimpleNamespace(current_plan_context=[]),
        ),
        memory_service=SimpleNamespace(
            get_retrieval_memories=lambda *args, **kwargs: [],
            create_observation_from_text=lambda *args, **kwargs: None,
        ),
    )


def _encounter_test_runtime(
    *,
    encounter_gate: object | None = None,
    plan_react_gate: object | None = None,
    spatial_runtime: object | None = None,
    agent_names: tuple[str, ...] = ("Jiho", "Sujin"),
) -> WorldRuntime:
    agents = cast(
        list[SimAgent],
        [
            _dummy_full_agent(name, agent_id=name.lower())
            for name in agent_names
        ],
    )
    session = WorldConversationSession(agents=agents[:2], dialogue_turn_window=None)
    return WorldRuntime(
        agents=agents,
        session=session,
        engine=cast(
            SimulationEngine,
            cast(
                object,
                DummyEngine(
                    result=SimulationStepResult(
                        now=datetime.datetime(2026, 3, 4, 9, 0, 0),
                        speaker_name="Jiho",
                        trace={},
                        reply="",
                        silent_reason="",
                        parse_failure=False,
                        observability=SimulationStepObservability(
                            thought="",
                            model_thought="",
                            self_critique="",
                            decision_reason="",
                            action_summary="",
                            decision_process={},
                        ),
                    )
                ),
            ),
        ),
        current_time=datetime.datetime(2026, 3, 4, 9, 0, 0),
        encounter_gate=cast(EncounterGate, encounter_gate) if encounter_gate else None,
        plan_react_gate=(
            cast(PlanDisruptionGate, plan_react_gate) if plan_react_gate else None
        ),
        spatial_runtime=(
            cast(SpatialWorldRuntime, spatial_runtime) if spatial_runtime else None
        ),
    )


def test_should_converse_on_encounter_defaults_true_without_gate() -> None:
    """TODO.md §3-C: encounter_gate가 구성되지 않으면 기존 동작(항상 대화)을 유지한다."""
    runtime = _encounter_test_runtime(encounter_gate=None)
    speaker, other = runtime.agents

    assert (
        runtime._should_converse_on_encounter(
            runtime.current_time, speaker=speaker, other=other
        )
        is True
    )


def test_should_converse_on_encounter_uses_configured_gate_for_pass_by() -> None:
    """TODO.md §3-C: 조우 시 pass-by vs converse 결정이 게이트 판정을 따른다."""
    gate = StubEncounterGate(should_converse=False)
    runtime = _encounter_test_runtime(encounter_gate=gate)
    speaker, other = runtime.agents

    assert (
        runtime._should_converse_on_encounter(
            runtime.current_time, speaker=speaker, other=other
        )
        is False
    )
    assert gate.calls == 1


def test_should_converse_on_encounter_uses_configured_gate_for_converse() -> None:
    gate = StubEncounterGate(should_converse=True)
    runtime = _encounter_test_runtime(encounter_gate=gate)
    speaker, other = runtime.agents

    assert (
        runtime._should_converse_on_encounter(
            runtime.current_time, speaker=speaker, other=other
        )
        is True
    )
    assert gate.calls == 1


def test_tick_plan_disruption_dispatches_on_changed_observation() -> None:
    """TODO.md §3-B: 대화 밖 tick에서 상대 행동 변화가 관찰되면 react_gate를 호출한다."""
    gate = StubPlanReactGate()
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(agent_id="jiho", current_action="idle"),
            FakeAgentSnapshot(agent_id="sujin", current_action="moving_to:cafe"),
        )
    )
    runtime = _encounter_test_runtime(
        plan_react_gate=gate, spatial_runtime=spatial_runtime
    )
    runtime.session.finish_dialogue()

    runtime._dispatch_tick_plan_disruption_check(runtime.current_time)
    assert runtime._plan_react_thread is not None
    runtime._plan_react_thread.join(timeout=1)

    assert len(gate.calls) == 1


def test_tick_plan_disruption_stores_observation_before_judging() -> None:
    """TODO.md §4-A: tick 관찰을 판정 전에 MemoryObject로 저장한다 (store 절반)."""
    gate = StubPlanReactGate()
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(agent_id="jiho", current_action="idle"),
            FakeAgentSnapshot(agent_id="sujin", current_action="moving_to:cafe"),
        )
    )
    runtime = _encounter_test_runtime(
        plan_react_gate=gate, spatial_runtime=spatial_runtime
    )
    runtime.session.finish_dialogue()

    stored: list[str] = []
    cast(
        SimpleNamespace, runtime.agents[0]
    ).memory_service.create_observation_from_text = lambda *, content, **kwargs: (
        stored.append(content)
    )

    runtime._dispatch_tick_plan_disruption_check(runtime.current_time)
    assert runtime._plan_react_thread is not None
    runtime._plan_react_thread.join(timeout=1)

    assert stored == ["Sujin가 moving_to:cafe 상태이다."]
    assert len(gate.calls) == 1


def test_tick_plan_disruption_dispatches_across_three_agents() -> None:
    """N-agent 확장: 2명 고정 쌍이 아니라 모든 agent 쌍의 관찰 변화를 본다."""
    gate = StubPlanReactGate()
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(agent_id="jiho", current_action="idle"),
            FakeAgentSnapshot(agent_id="sujin", current_action="idle"),
            FakeAgentSnapshot(agent_id="minji", current_action="moving_to:도서관"),
        )
    )
    runtime = _encounter_test_runtime(
        plan_react_gate=gate,
        spatial_runtime=spatial_runtime,
        agent_names=("Jiho", "Sujin", "Minji"),
    )
    runtime.session.finish_dialogue()

    seen_observations: set[str] = set()
    for _ in range(6):
        runtime._dispatch_tick_plan_disruption_check(runtime.current_time)
        if runtime._plan_react_thread is not None:
            runtime._plan_react_thread.join(timeout=1)
        seen_observations.update(call.observation_content for call in gate.calls)

    assert any("Minji가 moving_to:도서관" in obs for obs in seen_observations)


def test_tick_plan_disruption_skips_unchanged_observation() -> None:
    """동일한 관찰이 반복되면 게이트를 다시 호출하지 않는다 (호출량 억제)."""
    gate = StubPlanReactGate()
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(agent_id="jiho", current_action="idle"),
            FakeAgentSnapshot(agent_id="sujin", current_action="moving_to:cafe"),
        )
    )
    runtime = _encounter_test_runtime(
        plan_react_gate=gate, spatial_runtime=spatial_runtime
    )
    runtime.session.finish_dialogue()

    # First tick catches up the initiator's perception of the partner; the
    # second catches up the partner's perception of the initiator (dispatch
    # only starts one background check per call, mirroring the single
    # in-flight `_plan_refresh_task` pattern used for plan generation).
    runtime._dispatch_tick_plan_disruption_check(runtime.current_time)
    assert runtime._plan_react_thread is not None
    runtime._plan_react_thread.join(timeout=1)
    assert len(gate.calls) == 1

    runtime._dispatch_tick_plan_disruption_check(runtime.current_time)
    assert runtime._plan_react_thread is not None
    runtime._plan_react_thread.join(timeout=1)
    assert len(gate.calls) == 2

    # Both agents' last-perceived state is now up to date; a further tick
    # with no spatial change dispatches nothing new.
    runtime._dispatch_tick_plan_disruption_check(runtime.current_time)
    if runtime._plan_react_thread is not None:
        runtime._plan_react_thread.join(timeout=1)

    assert len(gate.calls) == 2


def test_tick_plan_disruption_skipped_without_gate() -> None:
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(agent_id="jiho", current_action="idle"),
            FakeAgentSnapshot(agent_id="sujin", current_action="moving_to:cafe"),
        )
    )
    runtime = _encounter_test_runtime(
        plan_react_gate=None, spatial_runtime=spatial_runtime
    )
    runtime.session.finish_dialogue()

    runtime._dispatch_tick_plan_disruption_check(runtime.current_time)

    assert runtime._plan_react_thread is None


def test_tick_plan_disruption_skipped_during_active_dialogue() -> None:
    gate = StubPlanReactGate()
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(agent_id="jiho", current_action="idle"),
            FakeAgentSnapshot(agent_id="sujin", current_action="moving_to:cafe"),
        )
    )
    runtime = _encounter_test_runtime(
        plan_react_gate=gate, spatial_runtime=spatial_runtime
    )
    assert runtime.session.is_active is True

    runtime._dispatch_tick_plan_disruption_check(runtime.current_time)

    assert runtime._plan_react_thread is None
    assert len(gate.calls) == 0


def _tile(x: int, y: int) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def test_start_dialogue_picks_the_qualifying_pair_among_three_agents() -> None:
    """N-agent 확장: 조건을 만족하는 쌍만 대화를 시작하고 나머지는 그대로다."""
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(
                agent_id="jiho",
                current_action="at:카페",
                tile_position=_tile(0, 0),
                destination="다른 곳",
            ),
            FakeAgentSnapshot(
                agent_id="sujin",
                current_action="arrived_at:카페",
                tile_position=_tile(10, 10),
                destination="카페",
            ),
            FakeAgentSnapshot(
                agent_id="minji",
                current_action="arrived_at:카페",
                tile_position=_tile(10, 11),
                destination="카페",
            ),
        )
    )
    runtime = _encounter_test_runtime(
        spatial_runtime=spatial_runtime,
        agent_names=("Jiho", "Sujin", "Minji"),
    )
    runtime.session.finish_dialogue()

    runtime._start_dialogue_for_real_encounter(runtime.current_time)

    assert runtime.session.is_active is True
    assert {agent.name for agent in runtime.session.agents} == {"Sujin", "Minji"}


def test_start_dialogue_respects_per_pair_cooldown_independently() -> None:
    """A-B 쌍의 쿨다운이 C-D 쌍의 조우를 막지 않는다."""
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(
                agent_id="jiho",
                current_action="arrived_at:카페",
                tile_position=_tile(0, 0),
                destination="카페",
            ),
            FakeAgentSnapshot(
                agent_id="sujin",
                current_action="arrived_at:카페",
                tile_position=_tile(0, 1),
                destination="카페",
            ),
            FakeAgentSnapshot(
                agent_id="minji",
                current_action="arrived_at:도서관",
                tile_position=_tile(20, 20),
                destination="도서관",
            ),
            FakeAgentSnapshot(
                agent_id="yuna",
                current_action="arrived_at:도서관",
                tile_position=_tile(20, 21),
                destination="도서관",
            ),
        )
    )
    runtime = _encounter_test_runtime(
        spatial_runtime=spatial_runtime,
        agent_names=("Jiho", "Sujin", "Minji", "Yuna"),
    )
    runtime.session.finish_dialogue()
    jiho, sujin, minji, yuna = runtime.agents
    from world.runtime import _pair_key

    runtime._pair_cooldown_until[_pair_key(jiho, sujin)] = runtime.current_time

    runtime._start_dialogue_for_real_encounter(runtime.current_time)

    assert runtime.session.is_active is True
    assert {agent.name for agent in runtime.session.agents} == {"Minji", "Yuna"}


def test_start_dialogue_does_nothing_while_another_dialogue_is_active() -> None:
    spatial_runtime = FakeSpatialRuntime(
        agents=(
            FakeAgentSnapshot(
                agent_id="jiho",
                current_action="arrived_at:카페",
                tile_position=_tile(0, 0),
                destination="카페",
            ),
            FakeAgentSnapshot(
                agent_id="sujin",
                current_action="arrived_at:카페",
                tile_position=_tile(0, 1),
                destination="카페",
            ),
        )
    )
    runtime = _encounter_test_runtime(
        spatial_runtime=spatial_runtime,
        agent_names=("Jiho", "Sujin"),
    )
    assert runtime.session.is_active is True
    original_session = runtime.session

    runtime._start_dialogue_for_real_encounter(runtime.current_time)

    assert runtime.session is original_session


def test_reopen_session_for_restore_rebuilds_session_for_saved_pair() -> None:
    """persistence: 저장된 참가자 쌍으로 세션을 재구성한다 (N-agent 확장)."""
    runtime = _encounter_test_runtime(agent_names=("Jiho", "Sujin", "Minji"))
    runtime.session.finish_dialogue()

    runtime._reopen_session_for_restore(("Sujin", "Minji"))

    assert {agent.name for agent in runtime.session.agents} == {"Sujin", "Minji"}
    assert runtime.engine.session is runtime.session


def test_reopen_session_for_restore_rejects_unknown_participant() -> None:
    runtime = _encounter_test_runtime(agent_names=("Jiho", "Sujin", "Minji"))
    runtime.session.finish_dialogue()

    with pytest.raises(ValueError):
        runtime._reopen_session_for_restore(("Sujin", "Nobody"))
