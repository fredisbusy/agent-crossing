import asyncio
import datetime
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

from agents.sim_agent import SimAgent
from agents.planning.lifecycle import PlanningCoordinator
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
        self.install_times: list[datetime.datetime] = []

    def generate_day_plan(self, **kwargs: object) -> list[object]:
        _ = kwargs
        self.started.set()
        if not self.release.wait(timeout=1):
            raise TimeoutError("test plan generation was not released")
        return []

    def install_day_plan(self, **kwargs: object) -> object:
        now = kwargs["now"]
        assert isinstance(now, datetime.datetime)
        self.install_times.append(now)
        return object()


class CountingPlanningCoordinator:
    def __init__(self) -> None:
        self.ensure_calls: int = 0

    def ensure_current(self, **kwargs: object) -> object:
        _ = kwargs
        self.ensure_calls += 1
        return object()


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


def test_background_plan_refresh_applies_against_latest_world_time() -> None:
    asyncio.run(_assert_background_plan_refresh_uses_latest_world_time())


async def _assert_background_plan_refresh_uses_latest_world_time() -> None:
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
        planning_coordinator=cast(
            PlanningCoordinator, cast(object, coordinator)
        ),
    )

    refresh_task = asyncio.create_task(runtime._refresh_plans())
    started = await asyncio.to_thread(coordinator.started.wait, 1)
    assert started is True
    latest_time = datetime.datetime(2026, 8, 24, 18, 35)
    runtime.current_time = latest_time
    coordinator.release.set()
    await refresh_task

    assert coordinator.install_times == [latest_time, latest_time]


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
    assert runtime.current_time >= initial_time + datetime.timedelta(minutes=1, seconds=30)
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
        planning_coordinator=cast(
            PlanningCoordinator, cast(object, coordinator)
        ),
    )

    runtime._advance_world_tick()

    assert runtime.current_time == initial_time + datetime.timedelta(seconds=30)
    assert runtime.effective_time_step_seconds == 30
    assert coordinator.ensure_calls == 0


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
