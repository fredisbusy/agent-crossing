import datetime
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from llm.governance import ConversationMetrics
from world.engine import SimulationStepObservability, SimulationStepResult

from api.main import (
    _require_runtime,
    app,
    get_world_spatial_state,
    get_world_state,
    post_world_spatial_step,
    post_world_step,
    post_world_tick_start,
    post_world_tick_stop,
)
from world.spatial import SpatialAgentSeed, SpatialWorldRuntime
from world.world_map import load_world_map


@dataclass(frozen=True)
class DummyState:
    turn: int
    current_time: datetime.datetime
    parse_failures: int
    silent_turns: int
    history_size: int
    scheduler_running: bool
    tick_interval_seconds: float


@dataclass
class DummyAgent:
    name: str


@dataclass
class DummyRuntime:
    turn: int
    agents: list[DummyAgent]
    _state: DummyState
    _step: SimulationStepResult
    _metrics: ConversationMetrics
    scheduler_running: bool = False

    def state(self) -> DummyState:
        return DummyState(
            turn=self._state.turn,
            current_time=self._state.current_time,
            parse_failures=self._state.parse_failures,
            silent_turns=self._state.silent_turns,
            history_size=self._state.history_size,
            scheduler_running=self.scheduler_running,
            tick_interval_seconds=self._state.tick_interval_seconds,
        )

    def step(self) -> SimulationStepResult:
        self.turn += 1
        return self._step

    def metrics(self) -> ConversationMetrics:
        return self._metrics

    async def start_scheduler(self) -> bool:
        if self.scheduler_running:
            return False
        self.scheduler_running = True
        return True

    async def stop_scheduler(self) -> bool:
        if not self.scheduler_running:
            return False
        self.scheduler_running = False
        return True


def test_require_runtime_raises_when_unavailable() -> None:
    app.state.world_runtime = None

    with pytest.raises(HTTPException):
        _ = _require_runtime()


@pytest.mark.anyio
async def test_spatial_state_and_step_endpoints_advance_planned_route() -> None:
    app.state.spatial_runtime = SpatialWorldRuntime(
        world_map=load_world_map(),
        seeds=[
            SpatialAgentSeed(
                agent_id="jiho",
                name="Jiho Park",
                plan_context=("Jiho is visiting Morning Dew Cafe.",),
            )
        ],
    )

    initial = await get_world_spatial_state()
    stepped = await post_world_spatial_step()

    assert initial.revision == 0
    assert stepped.revision == 1
    assert stepped.agents[0].destination == "Briar Cove > The Honey Cup"
    assert stepped.agents[0].position != initial.agents[0].position


@pytest.mark.anyio
async def test_get_world_state_returns_runtime_snapshot() -> None:
    runtime = DummyRuntime(
        turn=3,
        agents=[DummyAgent(name="Jiho"), DummyAgent(name="Sujin")],
        _state=DummyState(
            turn=3,
            current_time=datetime.datetime(2026, 3, 4, 10, 30, 0),
            parse_failures=1,
            silent_turns=1,
            history_size=2,
            scheduler_running=False,
            tick_interval_seconds=1.0,
        ),
        _step=SimulationStepResult(
            now=datetime.datetime(2026, 3, 4, 10, 31, 0),
            speaker_name="Jiho",
            trace={"parse_success": True},
            reply="안녕하세요",
            silent_reason="",
            parse_failure=False,
            observability=SimulationStepObservability(
                thought="hi",
                model_thought="",
                self_critique="",
                decision_reason="",
                action_summary="react",
                decision_process={},
            ),
        ),
        _metrics=ConversationMetrics(
            parse_failure_rate=0.1,
            silent_rate=0.1,
            semantic_repeat_rate=0.2,
            topic_progress_rate=0.8,
        ),
    )
    app.state.world_runtime = runtime

    response = await get_world_state()

    assert response.turn == 3
    assert response.history_size == 2
    assert response.agent_names == ["Jiho", "Sujin"]
    assert response.scheduler_running is False
    assert response.tick_interval_seconds == 1.0


@pytest.mark.anyio
async def test_post_world_step_returns_metrics_and_trace() -> None:
    runtime = DummyRuntime(
        turn=0,
        agents=[DummyAgent(name="Jiho"), DummyAgent(name="Sujin")],
        _state=DummyState(
            turn=0,
            current_time=datetime.datetime(2026, 3, 4, 10, 30, 0),
            parse_failures=0,
            silent_turns=0,
            history_size=0,
            scheduler_running=False,
            tick_interval_seconds=1.0,
        ),
        _step=SimulationStepResult(
            now=datetime.datetime(2026, 3, 4, 10, 31, 0),
            speaker_name="Jiho",
            trace={"parse_success": True},
            reply="안녕하세요",
            silent_reason="",
            parse_failure=False,
            observability=SimulationStepObservability(
                thought="greet",
                model_thought="",
                self_critique="",
                decision_reason="",
                action_summary="react_to_partner",
                decision_process={},
            ),
        ),
        _metrics=ConversationMetrics(
            parse_failure_rate=0.0,
            silent_rate=0.0,
            semantic_repeat_rate=0.0,
            topic_progress_rate=1.0,
        ),
    )
    app.state.world_runtime = runtime

    response = await post_world_step()

    assert response.turn == 1
    assert response.speaker_name == "Jiho"
    assert response.reply == "안녕하세요"
    assert response.parse_failure_rate == 0.0


@pytest.mark.anyio
async def test_world_tick_start_and_stop_return_scheduler_state() -> None:
    runtime = DummyRuntime(
        turn=0,
        agents=[DummyAgent(name="Jiho"), DummyAgent(name="Sujin")],
        _state=DummyState(
            turn=0,
            current_time=datetime.datetime(2026, 3, 4, 10, 30, 0),
            parse_failures=0,
            silent_turns=0,
            history_size=0,
            scheduler_running=False,
            tick_interval_seconds=1.5,
        ),
        _step=SimulationStepResult(
            now=datetime.datetime(2026, 3, 4, 10, 31, 0),
            speaker_name="Jiho",
            trace={"parse_success": True},
            reply="안녕하세요",
            silent_reason="",
            parse_failure=False,
            observability=SimulationStepObservability(
                thought="greet",
                model_thought="",
                self_critique="",
                decision_reason="",
                action_summary="react_to_partner",
                decision_process={},
            ),
        ),
        _metrics=ConversationMetrics(
            parse_failure_rate=0.0,
            silent_rate=0.0,
            semantic_repeat_rate=0.0,
            topic_progress_rate=1.0,
        ),
    )
    app.state.world_runtime = runtime

    started = await post_world_tick_start()
    stopped = await post_world_tick_stop()

    assert started.running is True
    assert stopped.running is False
    assert started.tick_interval_seconds == 1.5
