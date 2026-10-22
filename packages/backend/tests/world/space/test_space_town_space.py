import pytest
from world.contracts import Space, TilePosition
from world.space import TownSpace, load_town_space

REQUIRED_LOCATIONS = (
    "Smallville > Town Square",
    "Smallville > Johnson Park > Garden",
    "Smallville > Hobbs Cafe > Counter",
    "Smallville > Hobbs Cafe > Seating",
    "Smallville > The Willows Market > Store",
    "Smallville > Oak Hill College > Classroom",
    "Smallville > Oak Hill College > Library",
    "Smallville > The Rose and Crown Pub > Bar",
    "Smallville > Lin Family House > Kitchen",
    "Smallville > Lin Family House > Bedroom",
    "Smallville > Moore Family House > Living Room",
    "Smallville > Moore Family House > Bedroom",
    "Smallville > Dorm for Oak Hill College > Klaus's Room",
    "Smallville > Dorm for Oak Hill College > Maria's Room",
    "Smallville > Dorm for Oak Hill College > Common Room",
    "Smallville > Isabella's Apartment > Bedroom",
    "Smallville > Artist's Co-living Space > Common Room",
    "Smallville > Artist's Co-living Space > Studio",
)


@pytest.fixture(scope="module")
def town() -> TownSpace:
    return load_town_space()


def test_town_space_satisfies_space_protocol(town: TownSpace) -> None:
    space: Space = town
    assert space.location_paths()


def test_all_required_locations_exist(town: TownSpace) -> None:
    paths = set(town.location_paths())
    assert set(REQUIRED_LOCATIONS) <= paths
    assert "Smallville > Hobbs Cafe" in paths and "Smallville > Johnson Park" in paths


def test_every_location_has_walkable_tile_inside_its_rect(town: TownSpace) -> None:
    for path in town.location_paths():
        tile = town.tile_of(path)
        assert tile is not None, path
        assert town.grid.is_walkable(tile.x, tile.y), path


def test_required_locations_mutually_reachable(town: TownSpace) -> None:
    tiles = {p: town.tile_of(p) for p in REQUIRED_LOCATIONS}
    anchor = tiles[REQUIRED_LOCATIONS[0]]
    assert anchor is not None
    for path, tile in tiles.items():
        assert tile is not None, path
        assert town.find_path(anchor, tile) is not None, path
        assert town.find_path(tile, anchor) is not None, path


def test_pairwise_reachability(town: TownSpace) -> None:
    tiles = [t for p in REQUIRED_LOCATIONS if (t := town.tile_of(p)) is not None]
    assert len(tiles) == len(REQUIRED_LOCATIONS)
    for a in tiles:
        for b in tiles:
            assert town.find_path(a, b) is not None


def test_location_at_roundtrip_for_rooms(town: TownSpace) -> None:
    for path in REQUIRED_LOCATIONS:
        tile = town.tile_of(path)
        assert tile is not None
        if path != "Smallville > Johnson Park > Garden":  # 정원 중심은 공원과 겹쳐도 Garden이 더 깊다
            assert town.location_at(tile) == path
    garden = town.tile_of("Smallville > Johnson Park > Garden")
    assert garden is not None
    assert town.location_at(garden) == "Smallville > Johnson Park > Garden"


def test_building_tile_is_near_building_rect_center(town: TownSpace) -> None:
    tile = town.tile_of("Smallville > Hobbs Cafe")
    assert tile is not None
    assert town.location_at(tile).startswith("Smallville > Hobbs Cafe")


def test_location_at_outside_is_town_name(town: TownSpace) -> None:
    assert town.location_at(TilePosition(x=0, y=0)) == "Smallville"


def test_unknown_path_has_no_tile(town: TownSpace) -> None:
    assert town.tile_of("Smallville > Nowhere") is None


def test_tile_of_root_is_walkable(town: TownSpace) -> None:
    tile = town.tile_of("Smallville")
    assert tile is not None and town.grid.is_walkable(tile.x, tile.y)


def test_find_path_edge_cases(town: TownSpace) -> None:
    start = town.tile_of("Smallville > Town Square")
    assert start is not None
    assert town.find_path(start, start) == ()
    assert town.find_path(start, TilePosition(x=1, y=8)) is None  # 건물 벽


def test_tree_contains_all_paths(town: TownSpace) -> None:
    assert set(town.location_paths()) <= set(town.tree.paths())
    sub = town.tree.subtree(["Smallville > Hobbs Cafe > Counter"])
    assert sub.paths() == (
        "Smallville",
        "Smallville > Hobbs Cafe",
        "Smallville > Hobbs Cafe > Counter",
    )


def test_committed_map_matches_generator() -> None:
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[5] / "scripts" / "maps" / "generate_town_map.py"
    spec = importlib.util.spec_from_file_location("generate_town_map", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (script.parents[2] / "packages" / "shared" / "maps" / "town.json").read_text(
        encoding="utf-8"
    )
    assert module.render(module.to_tiled(module.build())) == committed
