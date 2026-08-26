import datetime
from types import SimpleNamespace

import numpy as np
import pytest

from agents.memory.memory_object import MemoryObject, NodeType
from api.main import (
    _dashboard_event_response,
    _dashboard_location,
    _dashboard_memory_response,
    app,
    get_dashboard_agent_memories,
)
from world.observability import DashboardEvent
from world.spatial import SpatialAgentSnapshot
from world.world_map import MapPoint, load_world_map


def _spatial_agent(
    *,
    pixel_position: MapPoint,
    destination: str | None = None,
    current_action: str = "idle",
    route_remaining: int = 0,
) -> SpatialAgentSnapshot:
    return SpatialAgentSnapshot(
        agent_id="jiho",
        name="지호",
        tile_position=MapPoint(0, 0),
        pixel_position=pixel_position,
        destination=destination,
        current_action=current_action,
        plan="",
        route_remaining=route_remaining,
        active_day=None,
        active_hourly=None,
        active_minute=None,
        day_plan=(),
        bubble_kind="action",
        bubble_text="",
    )


def test_public_dashboard_event_excludes_private_model_diagnostics() -> None:
    response = _dashboard_event_response(
        DashboardEvent(
            sequence=4,
            turn=7,
            occurred_at=datetime.datetime(2026, 8, 26, 10, 0),
            agent_id="jiho",
            agent_name="지호",
            reply="안녕하세요.",
            silent_reason="",
            parse_failure=False,
            display_thought="PRIVATE_THOUGHT_SENTINEL",
            model_thought="PRIVATE_MODEL_SENTINEL",
            self_critique="PRIVATE_CRITIQUE_SENTINEL",
            decision_reason="대화에 응답함",
            action_summary="인사함",
            decision_process={"RAW_RESPONSE": "PRIVATE_RAW_SENTINEL"},
            governance_trace={"Authorization": "PRIVATE_TOKEN_SENTINEL"},
        )
    ).model_dump()

    serialized = repr(response)
    assert "PRIVATE_" not in serialized
    assert set(response) == {
        "sequence",
        "turn",
        "occurred_at",
        "agent_id",
        "agent_name",
        "reply",
        "silent_reason",
        "parse_failure",
        "decision_reason",
        "action_summary",
    }


def test_public_dashboard_memory_exposes_content_but_not_embedding() -> None:
    now = datetime.datetime(2026, 8, 26, 10, 0)
    response = _dashboard_memory_response(
        MemoryObject(
            id=12,
            node_type=NodeType.OBSERVATION,
            citations=None,
            content="하은은 공원에서 노을을 스케치했다.",
            created_at=now,
            last_accessed_at=now,
            importance=7,
            embedding=np.array([0.1]),
        )
    ).model_dump()

    assert response["content"] == "하은은 공원에서 노을을 스케치했다."
    assert "embedding" not in response
    assert response["importance"] == 7


def test_dashboard_location_uses_authoritative_pixel_position() -> None:
    location_path, source = _dashboard_location(
        world_map=load_world_map(),
        agent=_spatial_agent(pixel_position=MapPoint(640, 464)),
    )

    assert location_path == "브라이어 코브 > 마을 광장"
    assert source == "map"


def test_dashboard_location_marks_completed_door_arrival_explicitly() -> None:
    location_path, source = _dashboard_location(
        world_map=load_world_map(),
        agent=_spatial_agent(
            pixel_position=MapPoint(272, 304),
            destination="브라이어 코브 > 허니컵 카페",
            current_action="at:허니컵 카페",
        ),
    )

    assert location_path == "브라이어 코브 > 허니컵 카페"
    assert source == "arrival"


def test_dashboard_location_does_not_replace_a_moving_location_with_destination() -> (
    None
):
    location_path, source = _dashboard_location(
        world_map=load_world_map(),
        agent=_spatial_agent(
            pixel_position=MapPoint(16, 16),
            destination="브라이어 코브 > 허니컵 카페",
            current_action="moving_to:허니컵 카페",
            route_remaining=4,
        ),
    )

    assert location_path is None
    assert source == "unknown"


def test_dashboard_location_does_not_treat_home_facade_as_interior() -> None:
    location_path, source = _dashboard_location(
        world_map=load_world_map(),
        agent=_spatial_agent(
            pixel_position=MapPoint(176, 496),
            destination="브라이어 코브 > 지호의 집",
            current_action="arrived_at_door:지호의 집",
        ),
    )

    assert location_path is None
    assert source == "unknown"


def test_dashboard_location_requires_explicit_inside_state_for_home() -> None:
    location_path, source = _dashboard_location(
        world_map=load_world_map(),
        agent=_spatial_agent(
            pixel_position=MapPoint(176, 496),
            destination="브라이어 코브 > 지호의 집",
            current_action="inside:지호의 집",
        ),
    )

    assert location_path == "브라이어 코브 > 지호의 집"
    assert source == "interior"


@pytest.mark.anyio
async def test_dashboard_memory_page_uses_stable_descending_id_cursor() -> None:
    now = datetime.datetime(2026, 8, 26, 10, 0)
    memories = tuple(
        MemoryObject(
            id=index,
            node_type=NodeType.REFLECTION if index % 2 else NodeType.OBSERVATION,
            citations=[0] if index % 2 else None,
            content=f"기억 {index}",
            created_at=now,
            last_accessed_at=now,
            importance=(index % 10) + 1,
            embedding=np.array([0.1]),
        )
        for index in range(7)
    )
    agent = SimpleNamespace(
        identity=SimpleNamespace(id="jiho"),
        memory_service=SimpleNamespace(
            memory_stream=SimpleNamespace(snapshot=lambda: memories)
        ),
    )
    app.state.world_runtime = SimpleNamespace(agents=[agent])

    first = await get_dashboard_agent_memories("jiho", limit=3)
    second = await get_dashboard_agent_memories(
        "jiho", before_id=first.next_cursor, limit=3
    )

    assert [item.id for item in first.items] == [6, 5, 4]
    assert [item.id for item in second.items] == [3, 2, 1]
    assert first.total == 7
    assert first.has_more is True
    assert second.next_cursor == 1
    assert [item.content for item in first.items] == ["기억 6", "기억 5", "기억 4"]

    reflections = await get_dashboard_agent_memories(
        "jiho", limit=10, node_type="REFLECTION"
    )
    assert [item.id for item in reflections.items] == [5, 3, 1]
    assert [item.content for item in reflections.items] == [
        "기억 5",
        "기억 3",
        "기억 1",
    ]
    assert all(item.citations == [0] for item in reflections.items)
