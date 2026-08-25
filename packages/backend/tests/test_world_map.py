import pytest

from api.main import get_world_map, post_world_observe, post_world_path
from api.schemas import (
    WorldMapPointResponse,
    WorldObserveRequest,
    WorldPathRequest,
)
from world.world_map import MapPoint, load_world_map


def test_load_world_map_parses_semantic_layers() -> None:
    world_map = load_world_map()

    assert world_map.id == "briar-cove"
    assert world_map.width == 40
    assert world_map.height == 28
    assert len(world_map.locations) == 7
    assert len(world_map.paths) == 8
    assert len(world_map.collisions) == 21
    assert len(world_map.interactables) == 6
    assert [spawn.agent_id for spawn in world_map.spawns] == [
        "Jiho",
        "Sujin",
        "Minji",
        "Jungwoo",
        "Haeun",
        "Taeo",
    ]
    location = world_map.location_at(MapPoint(640, 464))
    assert location is not None
    assert location.name == "마을 광장"


def test_world_map_pathfinding_avoids_collision_bounds() -> None:
    world_map = load_world_map()
    path = world_map.find_path(MapPoint(17, 16), MapPoint(15, 12))

    assert path[0] == MapPoint(17, 16)
    assert path[-1] == MapPoint(15, 12)
    assert all(world_map.is_walkable_tile(point) for point in path)
    assert MapPoint(16, 12) not in path


def test_world_map_pathfinding_rejects_blocked_goal() -> None:
    world_map = load_world_map()

    assert world_map.find_path(MapPoint(17, 16), MapPoint(6, 4)) == []


def test_world_map_routes_buildings_through_authored_door() -> None:
    world_map = load_world_map()
    cafe = next(
        location for location in world_map.locations if location.name == "허니컵 카페"
    )

    assert cafe.entrance == MapPoint(8, 8)
    assert world_map.destination_tile(
        location=cafe, origin=MapPoint(17, 16)
    ) == MapPoint(8, 8)
    assert world_map.is_walkable_tile(MapPoint(8, 8))
    assert not world_map.is_walkable_tile(MapPoint(8, 7))


def test_world_map_avoids_dynamic_occupancy_and_prefers_authored_paths() -> None:
    world_map = load_world_map()
    start = MapPoint(17, 16)
    goal = MapPoint(29, 8)
    blocked = MapPoint(17, 15)
    path = world_map.find_path(start, goal, blocked_tiles={blocked})

    assert path
    assert blocked not in path
    assert sum(world_map.movement_cost(point) for point in path[1:]) < 4 * (
        abs(goal.x - start.x) + abs(goal.y - start.y)
    )


@pytest.mark.anyio
async def test_world_map_api_exposes_render_and_agent_data() -> None:
    response = await get_world_map()

    assert response.name == "브라이어 코브"
    assert response.tile_width == 32
    assert response.locations[0].location_path.startswith("브라이어 코브")
    assert "plan_event" in response.interactables[0].affordances


@pytest.mark.anyio
async def test_world_observation_returns_location_and_nearby_affordances() -> None:
    response = await post_world_observe(
        WorldObserveRequest(position=WorldMapPointResponse(x=640, y=464), radius=144)
    )

    assert response.location_path == "브라이어 코브 > 마을 광장"
    assert {item.name for item in response.nearby_interactables} == {
        "마을 게시판",
        "분수",
    }


@pytest.mark.anyio
async def test_world_path_api_returns_authoritative_tile_path() -> None:
    response = await post_world_path(
        WorldPathRequest(
            start=WorldMapPointResponse(x=17, y=16),
            goal=WorldMapPointResponse(x=15, y=12),
        )
    )

    assert response.reachable is True
    assert response.path[0] == WorldMapPointResponse(x=17, y=16)
    assert response.path[-1] == WorldMapPointResponse(x=15, y=12)
