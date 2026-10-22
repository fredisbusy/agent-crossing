"""town.json의 furniture·decor 객체와 방 안 통행 가능성 검사 (SPEC §15)."""

import json
from collections import deque
from pathlib import Path
from typing import Any

import pytest
from world.contracts import TilePosition
from world.space import TownSpace, load_town_space

TOWN_JSON = Path(__file__).resolve().parents[4] / "shared" / "maps" / "town.json"
TILE = 16
ROAD_GID = 2
DOOR_GID = 7
FURNITURE_GID = 6
REACHABLE_RATIO = 0.9
ROAD_START = (0, 19)

CONTRACT_FURNITURE = {
    "furn_shelf", "furn_counter", "furn_cabinet", "furn_plant", "furn_bed", "furn_bed_double",
    "furn_table_round", "furn_chair_down", "furn_chair_up", "furn_chair_right",
    "furn_dining_table", "furn_desk", "furn_sofa", "furn_cafe_counter", "furn_pastry_case",
    "furn_bar_counter", "furn_bottle_shelf", "furn_keg", "furn_chalkboard", "furn_easel",
    "furn_canvas_stack", "furn_stove", "furn_fridge", "furn_market_shelf", "furn_crate",
    "furn_register", "rug_a", "rug_b", "mat_door",
}  # fmt: skip
CONTRACT_DECOR = {
    "fountain_0", "bench_h", "bench_v", "lamp_post", "light", "flower_bed_a", "flower_bed_b",
    "flower_bed_c", "planter", "signpost", "lily_pad", "lily_pad_b", "reeds",
}  # fmt: skip
SIZES = {"furn_bed": (1, 2), "furn_bed_double": (2, 2), "rug_b": (3, 2), "fountain_0": (3, 3)}
WALKABLE = {"rug_a", "rug_b", "mat_door", "furn_chair_down", "furn_chair_up", "furn_chair_right"}


@pytest.fixture(scope="module")
def raw() -> dict[str, Any]:
    return json.loads(TOWN_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def town() -> TownSpace:
    return load_town_space()


def _objects(raw: dict[str, Any], layer: str) -> list[dict[str, Any]]:
    return next(g["objects"] for g in raw["layers"] if g["name"] == layer)


def _path_of(obj: dict[str, Any]) -> str:
    return str(obj["properties"][0]["value"])


def _ground(raw: dict[str, Any]) -> list[int]:
    return next(g["data"] for g in raw["layers"] if g["name"] == "ground")


def _reachable(town: TownSpace, start: tuple[int, int]) -> set[tuple[int, int]]:
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for n in town.grid.neighbors(TilePosition(x=x, y=y)):
            if (n.x, n.y) not in seen:
                seen.add((n.x, n.y))
                queue.append((n.x, n.y))
    return seen


def _cells(obj: dict[str, Any]) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(obj["y"] // TILE, (obj["y"] + obj["height"]) // TILE)
        for x in range(obj["x"] // TILE, (obj["x"] + obj["width"]) // TILE)
    ]


def test_object_names_and_alignment(raw: dict[str, Any]) -> None:
    ids = [o["id"] for g in raw["layers"] if g["type"] == "objectgroup" for o in g["objects"]]
    assert len(ids) == len(set(ids)) and raw["nextobjectid"] > max(ids)
    for layer, allowed in (("furniture", CONTRACT_FURNITURE), ("decor", CONTRACT_DECOR)):
        objects = _objects(raw, layer)
        assert objects, layer
        for o in objects:
            assert o["name"] in allowed, o
            assert all(o[k] % TILE == 0 for k in ("x", "y", "width", "height")), o
            if o["name"] in SIZES:
                assert (o["width"] // TILE, o["height"] // TILE) == SIZES[o["name"]], o


def test_blocking_furniture_blocks_and_soft_furniture_does_not(
    raw: dict[str, Any], town: TownSpace
) -> None:
    ground = _ground(raw)
    for o in _objects(raw, "furniture"):
        for x, y in _cells(o):
            if o["name"] not in WALKABLE:
                assert ground[y * raw["width"] + x] == FURNITURE_GID, o
                assert not town.grid.is_walkable(x, y), o
            elif o["name"] != "rug_a" and o["name"] != "rug_b":  # 깔개는 탁자 등이 겹칠 수 있다
                assert town.grid.is_walkable(x, y), o


def test_rooms_are_reachable_from_building_doors(raw: dict[str, Any], town: TownSpace) -> None:
    ground = _ground(raw)
    locations = _objects(raw, "locations")
    buildings = [
        o for o in locations
        if _path_of(o).count(" > ") == 1 and o["name"] not in ("Town Square", "Johnson Park")
    ]  # fmt: skip
    assert len(buildings) == 9
    for b in buildings:
        by = b["y"] // TILE
        bh = b["height"] // TILE
        doors = [
            (x, y)
            for x, y in _cells(b)
            if ground[y * raw["width"] + x] == DOOR_GID and y in (by, by + bh - 1)
        ]
        assert len(doors) == 1, b["name"]
        reached = _reachable(town, doors[0])
        rooms = [o for o in locations if _path_of(o).startswith(_path_of(b) + " > ")]
        assert rooms
        for room in rooms:
            free = [c for c in _cells(room) if town.grid.is_walkable(*c)]
            ratio = len([c for c in free if c in reached]) / len(free)
            assert ratio >= REACHABLE_RATIO, (_path_of(room), ratio)


def test_chairs_and_door_mats_are_reachable(raw: dict[str, Any], town: TownSpace) -> None:
    reached = _reachable(town, ROAD_START)
    for o in _objects(raw, "furniture"):
        if o["name"].startswith("furn_chair") or o["name"] == "mat_door":
            assert (o["x"] // TILE, o["y"] // TILE) in reached, o


def test_blocking_decor_is_collision_only(raw: dict[str, Any], town: TownSpace) -> None:
    ground = _ground(raw)
    decor = _objects(raw, "decor")
    fountain = next(o for o in decor if o["name"] == "fountain_0")
    fx, fy = fountain["x"] // TILE, fountain["y"] // TILE
    assert not town.grid.is_walkable(fx + 1, fy + 1)
    assert ground[(fy + 1) * raw["width"] + fx + 1] == ROAD_GID
    lamps = [o for o in decor if o["name"] == "lamp_post"]
    assert len(lamps) >= 8
    assert all(not town.grid.is_walkable(o["x"] // TILE, o["y"] // TILE + 1) for o in lamps)
    assert len([o for o in decor if o["name"] == "light"]) == len(lamps)


def test_decor_does_not_cut_the_road(town: TownSpace) -> None:
    reached = _reachable(town, ROAD_START)
    assert all(any((x, y) in reached for y in range(18, 22)) for x in range(64))
