"""town.json의 furniture·decor 객체 검사 (SPEC §15). 통행 가능성은 check_town_map.py가 본다."""

import json
from pathlib import Path
from typing import Any

import pytest
from world.space import TownSpace, load_town_space

TOWN_JSON = Path(__file__).resolve().parents[4] / "shared" / "maps" / "town.json"
TILE = 16
ROAD_GID = 2
FURNITURE_GID = 6

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
    "flower_bed_c", "planter", "signpost", "lily_pad", "lily_pad_b", "reeds", "fence_h", "fence_post",
    "mailbox", "tilled", "tomato_ripe", "sunflower_ripe", "scarecrow", "beehive", "keg",
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




def _ground(raw: dict[str, Any]) -> list[int]:
    return next(g["data"] for g in raw["layers"] if g["name"] == "ground")




def _top(obj: dict[str, Any]) -> int:
    """객체 윗변 y(px). 그림 타일 객체(gid)는 Tiled 규칙상 y가 아랫변이다."""
    return int(obj["y"]) - int(obj["height"]) if obj.get("gid") else int(obj["y"])


def _cells(obj: dict[str, Any]) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(_top(obj) // TILE, (_top(obj) + obj["height"]) // TILE)
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




def test_blocking_decor_is_collision_only(raw: dict[str, Any], town: TownSpace) -> None:
    ground = _ground(raw)
    decor = _objects(raw, "decor")
    fountain = next(o for o in decor if o["name"] == "fountain_0")
    fx, fy = fountain["x"] // TILE, _top(fountain) // TILE
    assert not town.grid.is_walkable(fx + 1, fy + 1)
    assert ground[(fy + 1) * raw["width"] + fx + 1] == ROAD_GID
    lamps = [o for o in decor if o["name"] == "lamp_post"]
    assert len(lamps) >= 8
    assert all(not town.grid.is_walkable(o["x"] // TILE, _top(o) // TILE + 1) for o in lamps)
    assert len([o for o in decor if o["name"] == "light"]) == len(lamps)
