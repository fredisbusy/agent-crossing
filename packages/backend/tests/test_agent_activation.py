import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.main import app, patch_agent_activation
from api.schemas import AgentActivationRequest


class ActivationRuntime:
    def __init__(self, enabled_agent_ids: set[str]) -> None:
        self.agents = [
            SimpleNamespace(identity=SimpleNamespace(id=agent_id), name=agent_id)
            for agent_id in ("jiho", "sujin", "minji")
        ]
        self.enabled_agent_ids = frozenset(enabled_agent_ids)
        self.scheduler_running = True
        self.pause_calls = 0
        self.start_calls = 0

    @property
    def active_agents(self) -> list[object]:
        return [
            agent
            for agent in self.agents
            if agent.identity.id in self.enabled_agent_ids
        ]

    async def pause_scheduler(self) -> bool:
        self.pause_calls += 1
        self.scheduler_running = False
        return True

    async def start_scheduler(self) -> bool:
        self.start_calls += 1
        self.scheduler_running = True
        return True

    def set_enabled_agent_ids(self, agent_ids: set[str]) -> None:
        self.enabled_agent_ids = frozenset(agent_ids)


class ActivationRepository:
    def __init__(self) -> None:
        self.saved: list[tuple[str, bool]] = []

    def set_agent_enabled(self, *, agent_id: str, enabled: bool) -> object:
        self.saved.append((agent_id, enabled))
        return SimpleNamespace(agent_id=agent_id, enabled=enabled)


class ActivationStream:
    def __init__(self) -> None:
        self.publish_calls = 0

    def publish_current(self) -> None:
        self.publish_calls += 1


@pytest.mark.anyio
async def test_agent_activation_persists_and_publishes_at_safe_boundary() -> None:
    runtime = ActivationRuntime({"jiho", "sujin", "minji"})
    repository = ActivationRepository()
    stream = ActivationStream()
    app.state.world_runtime = runtime
    app.state.session_repository = repository
    app.state.spatial_stream = stream
    app.state.session_lock = asyncio.Lock()

    response = await patch_agent_activation(
        "minji", AgentActivationRequest(enabled=False)
    )

    assert response.enabled is False
    assert runtime.enabled_agent_ids == frozenset({"jiho", "sujin"})
    assert repository.saved == [("minji", False)]
    assert stream.publish_calls == 1
    assert runtime.pause_calls == 1
    assert runtime.start_calls == 1
    assert app.state.enabled_agent_ids == {"jiho", "sujin"}


@pytest.mark.anyio
async def test_agent_activation_rejects_fewer_than_two_enabled_agents() -> None:
    runtime = ActivationRuntime({"jiho", "sujin"})
    repository = ActivationRepository()
    app.state.world_runtime = runtime
    app.state.session_repository = repository
    app.state.spatial_stream = ActivationStream()
    app.state.session_lock = asyncio.Lock()

    with pytest.raises(HTTPException) as raised:
        await patch_agent_activation("sujin", AgentActivationRequest(enabled=False))

    assert raised.value.status_code == 409
    assert runtime.pause_calls == 0
    assert repository.saved == []
