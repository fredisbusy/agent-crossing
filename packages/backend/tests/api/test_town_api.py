"""마을 API: 전원 규칙 마음으로 LLM·네트워크·DB 없이 확인한다."""

import json
from collections.abc import Iterator

import pytest
from api.main import create_app
from fastapi.testclient import TestClient
from world.scenarios import build_town, load_scenario
from world.town import TownRuntime


async def _rule_runtime() -> TownRuntime:
    town = build_town(load_scenario("valentine"), agent_count=0, seed=0)
    return TownRuntime(town.simulation, tick_interval_seconds=0.001)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(runtime_factory=_rule_runtime, init_database=lambda: None)
    with TestClient(app) as test_client:
        yield test_client


def test_status(client: TestClient) -> None:
    assert client.get("/").json() == {"status": "online", "version": "0.1.0"}


def test_state_has_snapshot_and_scheduler_flags(client: TestClient) -> None:
    body = client.get("/world/state").json()
    assert body["scheduler_running"] is False
    assert body["tick_interval_seconds"] == 0.001
    snapshot = body["snapshot"]
    assert snapshot["tick"] == 0
    assert isinstance(snapshot["sim_time"], str)
    assert snapshot["residents"] and snapshot["residents"][0]["mind_kind"] == "schedule"


def test_text_is_text_state_json(client: TestClient) -> None:
    body = client.get("/world/text").json()
    assert body["tick"] == 0 and body["residents"]


def test_advance_increases_tick_and_validates_range(client: TestClient) -> None:
    response = client.post("/world/advance", params={"minutes": 5})
    assert response.status_code == 200
    assert response.json()["tick"] == 5
    assert json.loads(client.get("/world/text").text)["tick"] == 5
    for bad in (0, 1441, -3):
        assert client.post("/world/advance", params={"minutes": bad}).status_code == 422
    assert client.post("/world/advance").status_code == 422


def test_scheduler_start_and_stop(client: TestClient) -> None:
    assert client.post("/world/tick/start").json()["running"] is True
    assert client.get("/world/state").json()["scheduler_running"] is True
    stopped = client.post("/world/tick/stop").json()
    assert stopped["running"] is False
    assert client.get("/world/state").json()["scheduler_running"] is False


def test_websocket_sends_initial_and_advance_snapshots(client: TestClient) -> None:
    with client.websocket_connect("/ws/world") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert first["snapshot"]["tick"] == 0
        assert isinstance(first["snapshot"]["sim_time"], str)
        client.post("/world/advance", params={"minutes": 2})
        ticks = [ws.receive_json()["snapshot"]["tick"]]
        while ticks[-1] < 2:
            ticks.append(ws.receive_json()["snapshot"]["tick"])
        assert ticks[-1] == 2


def test_state_exposes_last_error_null(client: TestClient) -> None:
    assert client.get("/world/state").json()["last_error"] is None


def test_websocket_ignores_binary_frames(client: TestClient) -> None:
    with client.websocket_connect("/ws/world") as ws:
        ws.receive_json()
        ws.send_bytes(b"\x00\x01")
        client.post("/world/advance", params={"minutes": 1})
        assert ws.receive_json()["snapshot"]["tick"] == 1


def test_startup_survives_init_db_failure() -> None:
    def broken() -> None:
        raise RuntimeError("no db")

    app = create_app(runtime_factory=_rule_runtime, init_database=broken)
    with TestClient(app) as test_client:
        assert test_client.get("/world/state").status_code == 200
