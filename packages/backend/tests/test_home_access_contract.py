from world.world_map import MapPoint, load_world_map


def test_every_home_uses_a_path_connected_door_and_keeps_its_wall_solid() -> None:
    world_map = load_world_map()
    homes = [location for location in world_map.locations if location.kind == "home"]

    assert homes
    for home in homes:
        entrance = home.entrance
        assert entrance is not None
        wall_behind_door = MapPoint(
            entrance.x - home.entrance_direction.x,
            entrance.y - home.entrance_direction.y,
        )

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
