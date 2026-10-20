import asyncio
import datetime
from dataclasses import dataclass
from typing import cast

from agents.sim_agent import SimAgent
from world.engine import (
    SimulationEngine,
    SimulationStepObservability,
    SimulationStepResult,
)
from world.runtime import WorldRuntime
from world.session import WorldConversationSession


@dataclass
class DummyAgent:
    name: str


@dataclass
class DummyEngine:
    result: SimulationStepResult

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
