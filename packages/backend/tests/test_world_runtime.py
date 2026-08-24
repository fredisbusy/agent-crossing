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
