import datetime
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import HTTPException
from llm.governance import ConversationMetrics
from world.engine import SimulationStepObservability, SimulationStepResult

import api.main as api_main
from api.main import (
    _require_runtime,
    _restore_or_create_runtime_bundle,
    app,
    get_world_spatial_state,
    get_world_state,
    on_shutdown,
    on_startup,
    post_world_spatial_step,
    post_world_step,
    post_world_tick_start,
    post_world_tick_stop,
)
from api.schemas import (
    WorldMapPointResponse,
    WorldObserveRequest,
    WorldPathRequest,
)
from world.spatial import SpatialAgentSeed, SpatialWorldRuntime
from world.world_map import load_world_map
from persistence.repository import GameSessionRepository


@dataclass(frozen=True)
class DummyState:
    turn: int
    current_time: datetime.datetime
    parse_failures: int
    silent_turns: int
    history_size: int
    scheduler_running: bool
    tick_interval_seconds: float
    cognitive_active: bool = False
    effective_time_step_seconds: int = 300


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
            cognitive_active=self._state.cognitive_active,
            effective_time_step_seconds=self._state.effective_time_step_seconds,
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


def test_startup_quarantines_incompatible_save_and_restores_older_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incompatible_id = uuid.uuid4()
    compatible_id = uuid.uuid4()
    incompatible_state = SimpleNamespace(
        scheduler_was_running=True,
        planning_error=None,
    )
    compatible_state = SimpleNamespace(
        scheduler_was_running=False,
        planning_error="retry planning",
    )

    class StartupRuntime:
        def __init__(self, *, restore_error: Exception | None = None) -> None:
            self.restore_error = restore_error
            self.restored_state: object | None = None

        def restore_save_state(self, state: object) -> None:
            if self.restore_error is not None:
                raise self.restore_error
            self.restored_state = state

    class StartupRepository:
        def __init__(self) -> None:
            self.candidates = [
                (SimpleNamespace(id=incompatible_id), incompatible_state),
                (SimpleNamespace(id=compatible_id), compatible_state),
            ]
            self.marked_error_ids: list[uuid.UUID] = []
            self.activated_ids: list[uuid.UUID] = []

        def latest_session(self) -> object | None:
            return self.candidates.pop(0) if self.candidates else None

        def mark_error(self, *, session_id: uuid.UUID) -> object:
            self.marked_error_ids.append(session_id)
            return SimpleNamespace(id=session_id)

        def activate(self, *, session_id: uuid.UUID) -> object:
            self.activated_ids.append(session_id)
            return SimpleNamespace(id=session_id)

    failed_runtime = StartupRuntime(
        restore_error=ValueError("saved character roster does not match runtime")
    )
    restored_runtime = StartupRuntime()
    bundles = iter(
        [
            (failed_runtime, SimpleNamespace(name="failed spatial")),
            (restored_runtime, SimpleNamespace(name="restored spatial")),
        ]
    )
    monkeypatch.setattr("api.main._build_runtime_bundle", lambda: next(bundles))
    repository = StartupRepository()

    runtime, spatial, session_id, should_start = _restore_or_create_runtime_bundle(
        cast(GameSessionRepository, repository)
    )

    assert repository.marked_error_ids == [incompatible_id]
    assert repository.activated_ids == [compatible_id]
    assert runtime is restored_runtime
    assert spatial.name == "restored spatial"
    assert session_id == compatible_id
    assert should_start is True
    assert restored_runtime.restored_state is compatible_state


def test_require_runtime_raises_when_unavailable() -> None:
    app.state.world_runtime = None

    with pytest.raises(HTTPException):
        _ = _require_runtime()


@pytest.mark.anyio
async def test_startup_keeps_spatial_world_active_when_cognitive_runtime_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_database_startup() -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("api.main.init_db", fail_database_startup)

    await on_startup()
    try:
        assert app.state.world_runtime is None
        assert app.state.cognitive_runtime_error == "database unavailable"
        assert app.state.spatial_runtime.snapshot().agents
        assert app.state.spatial_stream.running is True
        assert app.state.world_map is not None
    finally:
        await on_shutdown()


@pytest.mark.anyio
async def test_startup_caches_world_map_and_handlers_reuse_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_calls = 0
    real_load_world_map = api_main.load_world_map

    def counting_load_world_map(*args: object, **kwargs: object) -> object:
        nonlocal load_calls
        load_calls += 1
        return real_load_world_map(*args, **kwargs)

    monkeypatch.setattr("api.main.load_world_map", counting_load_world_map)
    app.state.world_map = None

    await on_startup()
    try:
        assert load_calls == 1

        await api_main.get_world_map()
        await api_main.post_world_observe(
            WorldObserveRequest(position=WorldMapPointResponse(x=640, y=464), radius=1)
        )
        await api_main.post_world_path(
            WorldPathRequest(
                start=WorldMapPointResponse(x=17, y=16),
                goal=WorldMapPointResponse(x=15, y=12),
            )
        )

        assert load_calls == 1
    finally:
        await on_shutdown()


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
    assert stepped.agents[0].destination == "브라이어 코브 > 허니컵 카페"
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
    assert response.cognitive_active is False
    assert response.effective_time_step_seconds == 300


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
    assert started.cognitive_active is False
    assert started.effective_time_step_seconds == 300


class FakeGodModeMemoryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime.datetime, object]] = []

    def create_observation_from_text(self, *, content, now, context, importance=None):
        self.calls.append((content, now, context))
        return _GodModeMemory(id=42, content=content, created_at=now)


@dataclass(frozen=True)
class _GodModeMemory:
    id: int
    content: str
    created_at: datetime.datetime


@dataclass
class GodModeAgent:
    name: str
    identity: object
    profile: object
    memory_service: FakeGodModeMemoryService


class GodModeRuntime:
    def __init__(self, *, agents, current_time, plan_react_gate=None):
        self.agents = agents
        self._current_time = current_time
        self.plan_react_gate = plan_react_gate

    def state(self):
        return DummyState(
            turn=0,
            current_time=self._current_time,
            parse_failures=0,
            silent_turns=0,
            history_size=0,
            scheduler_running=False,
            tick_interval_seconds=1.0,
        )


def _god_mode_agent(memory_service: FakeGodModeMemoryService) -> GodModeAgent:
    from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona

    return GodModeAgent(
        name="Jiho",
        identity=AgentIdentity(id="jiho", name="Jiho", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        memory_service=memory_service,
    )


@pytest.mark.anyio
async def test_post_god_mode_perception_stores_observation_for_target_agent() -> None:
    from api.main import post_god_mode_perception
    from api.schemas import GodModePerceptionRequest

    memory_service = FakeGodModeMemoryService()
    agent = _god_mode_agent(memory_service)
    api_main.app.state.world_runtime = GodModeRuntime(
        agents=[agent],
        current_time=datetime.datetime(2026, 8, 24, 10, 0),
    )

    response = await post_god_mode_perception(
        GodModePerceptionRequest(
            agent_id="jiho", content="주방 스토브에 불이 났다."
        )
    )

    assert response.agent_id == "jiho"
    assert response.memory_id == 42
    assert memory_service.calls[0][0] == "주방 스토브에 불이 났다."


@pytest.mark.anyio
async def test_post_god_mode_perception_rejects_unknown_agent() -> None:
    from api.main import post_god_mode_perception
    from api.schemas import GodModePerceptionRequest

    api_main.app.state.world_runtime = GodModeRuntime(
        agents=[_god_mode_agent(FakeGodModeMemoryService())],
        current_time=datetime.datetime(2026, 8, 24, 10, 0),
    )

    with pytest.raises(HTTPException):
        await post_god_mode_perception(
            GodModePerceptionRequest(agent_id="unknown", content="아무 일도 없다.")
        )


@pytest.mark.anyio
async def test_post_god_mode_perception_rejects_blank_content() -> None:
    from api.main import post_god_mode_perception
    from api.schemas import GodModePerceptionRequest

    api_main.app.state.world_runtime = GodModeRuntime(
        agents=[_god_mode_agent(FakeGodModeMemoryService())],
        current_time=datetime.datetime(2026, 8, 24, 10, 0),
    )

    with pytest.raises(HTTPException):
        await post_god_mode_perception(
            GodModePerceptionRequest(agent_id="jiho", content="   ")
        )
