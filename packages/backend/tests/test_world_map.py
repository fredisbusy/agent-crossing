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
    assert world_map.height == 44
    assert len(world_map.locations) == 16
    assert len(world_map.paths) == 13
    assert len(world_map.collisions) == 50
    assert len(world_map.interactables) == 9
    assert [spawn.agent_id for spawn in world_map.spawns] == [
        "Jiho",
        "Sujin",
        "Minji",
        "Jungwoo",
        "Haeun",
        "Taeo",
        "Woosik",
        "Yongjun",
        "Byeongyong",
        "Wonjun",
    ]
    location = world_map.location_at(MapPoint(640, 464))
    assert location is not None
    assert location.name == "마을 광장"


def test_all_homes_use_path_connected_doors_and_keep_walls_solid() -> None:
    world_map = load_world_map()
    expected_entrances = {
        "지호의 집": MapPoint(5, 15),
        "수진의 집": MapPoint(34, 15),
        "민지의 집": MapPoint(4, 33),
        "정우의 집": MapPoint(12, 33),
        "하은의 집": MapPoint(20, 33),
        "태오의 집": MapPoint(28, 33),
        "우식의 집": MapPoint(4, 42),
        "용준의 집": MapPoint(12, 42),
        "병용의 집": MapPoint(20, 42),
        "원준의 집": MapPoint(28, 42),
    }
    homes = [location for location in world_map.locations if location.kind == "home"]

    assert {home.name for home in homes} == set(expected_entrances)

    for home in homes:
        entrance = expected_entrances[home.name]
        wall_behind_door = MapPoint(
            entrance.x - home.entrance_direction.x,
            entrance.y - home.entrance_direction.y,
        )
        assert home.entrance == entrance
        assert world_map.is_walkable_tile(entrance)
        assert world_map.is_connected_to_authored_path(entrance)
        assert not world_map.is_walkable_tile(wall_behind_door)
        assert (
            world_map.destination_tile(location=home, origin=MapPoint(20, 16))
            == entrance
        )

        path = world_map.find_path(MapPoint(20, 16), entrance)
        assert path[-1] == entrance
        assert wall_behind_door not in path
        assert all(world_map.is_walkable_tile(point) for point in path)


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


def test_starlight_tavern_is_path_connected_and_has_social_games() -> None:
    world_map = load_world_map()
    tavern = next(
        location for location in world_map.locations if location.name == "별빛 주점"
    )

    assert tavern.kind == "tavern"
    assert tavern.location_path == "브라이어 코브 > 별빛 주점"
    assert tavern.entrance == MapPoint(36, 33)
    assert world_map.is_walkable_tile(tavern.entrance)
    assert world_map.is_connected_to_authored_path(tavern.entrance)
    assert world_map.find_path(MapPoint(20, 34), tavern.entrance)

    tavern_objects = {
        item.name
        for item in world_map.interactables
        if item.location_path.startswith("브라이어 코브 > 별빛 주점 >")
    }
    assert tavern_objects == {"별빛 바 카운터", "다트 보드", "카드게임 테이블"}


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
