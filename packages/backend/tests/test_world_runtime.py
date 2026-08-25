import asyncio
import datetime
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

from agents.sim_agent import SimAgent
from agents.planning.lifecycle import PlanningCoordinator
from agents.reaction.encounter import EncounterDecision, EncounterGate
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


def test_scheduler_clock_advances_while_cognitive_turn_is_blocked() -> None:
    asyncio.run(_assert_scheduler_clock_advances_during_cognitive_turn())


async def _assert_scheduler_clock_advances_during_cognitive_turn() -> None:
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
    await asyncio.sleep(0.05)

    assert runtime.scheduler_running is True
    assert runtime.current_time >= initial_time + datetime.timedelta(
        minutes=1, seconds=30
    )
    assert runtime.cognitive_active is True
    assert runtime.effective_time_step_seconds == 30

    engine.release.set()
    await asyncio.sleep(0.02)
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


def _encounter_test_runtime(*, encounter_gate: object | None) -> WorldRuntime:
    agent1 = SimpleNamespace(
        name="Jiho",
        identity=DummyIdentity(id="jiho"),
        profile=SimpleNamespace(),
        memory_service=SimpleNamespace(
            get_retrieval_memories=lambda *args, **kwargs: []
        ),
    )
    agent2 = SimpleNamespace(
        name="Sujin",
        identity=DummyIdentity(id="sujin"),
        profile=SimpleNamespace(),
        memory_service=SimpleNamespace(
            get_retrieval_memories=lambda *args, **kwargs: []
        ),
    )
    agents = cast(list[SimAgent], [agent1, agent2])
    session = WorldConversationSession(agents=agents, dialogue_turn_window=None)
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
    )


def test_should_converse_on_encounter_defaults_true_without_gate() -> None:
    """TODO.md §3-C: encounter_gate가 구성되지 않으면 기존 동작(항상 대화)을 유지한다."""
    runtime = _encounter_test_runtime(encounter_gate=None)

    assert runtime._should_converse_on_encounter(runtime.current_time) is True


def test_should_converse_on_encounter_uses_configured_gate_for_pass_by() -> None:
    """TODO.md §3-C: 조우 시 pass-by vs converse 결정이 게이트 판정을 따른다."""
    gate = StubEncounterGate(should_converse=False)
    runtime = _encounter_test_runtime(encounter_gate=gate)

    assert runtime._should_converse_on_encounter(runtime.current_time) is False
    assert gate.calls == 1


def test_should_converse_on_encounter_uses_configured_gate_for_converse() -> None:
    gate = StubEncounterGate(should_converse=True)
    runtime = _encounter_test_runtime(encounter_gate=gate)

    assert runtime._should_converse_on_encounter(runtime.current_time) is True
    assert gate.calls == 1
