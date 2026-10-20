import json
from pathlib import Path
from typing import Any

import pytest
from world.space import load_tiled_map, parse_tiled_map

TOWN_JSON = Path(__file__).resolve().parents[4] / "shared" / "maps" / "town.json"


def tiny_map(collision: list[int] | None = None) -> dict[str, Any]:
    data = collision if collision is not None else [0] * 12
    return {
        "width": 4,
        "height": 3,
        "tilewidth": 16,
        "tileheight": 16,
        "layers": [
            {"name": "ground", "type": "tilelayer", "data": [1] * 12},
            {"name": "collision", "type": "tilelayer", "data": data},
            {
                "name": "locations",
                "type": "objectgroup",
                "objects": [
                    {
                        "x": 16,
                        "y": 16,
                        "width": 32,
                        "height": 16,
                        "properties": [
                            {"name": "location_path", "type": "string", "value": "Smallville > A"}
                        ],
                    },
                    {"x": 0, "y": 0, "width": 16, "height": 16, "properties": []},
                ],
            },
        ],
    }


def test_parse_reads_dimensions_layers_and_regions() -> None:
    tiled = parse_tiled_map(tiny_map())
    assert (tiled.width, tiled.height, tiled.tile_size) == (4, 3, 16)
    assert len(tiled.ground) == 12 and len(tiled.collision) == 12
    assert len(tiled.regions) == 1  # location_path 없는 객체는 무시
    region = tiled.regions[0]
    assert region.location_path == "Smallville > A"
    assert (region.rect.x, region.rect.y, region.rect.width, region.rect.height) == (1, 1, 2, 1)
    assert region.rect.contains(2, 1) and not region.rect.contains(3, 1)


def test_parse_rejects_missing_layer() -> None:
    raw = tiny_map()
    raw["layers"] = raw["layers"][:2]
    with pytest.raises(ValueError, match="locations"):
        parse_tiled_map(raw)


def test_parse_rejects_wrong_layer_size() -> None:
    with pytest.raises(ValueError, match="크기"):
        parse_tiled_map(tiny_map(collision=[0, 0]))


def test_load_real_town_file() -> None:
    assert json.loads(TOWN_JSON.read_text(encoding="utf-8"))["version"] == "1.10"
    tiled = load_tiled_map(TOWN_JSON)
    assert (tiled.width, tiled.height, tiled.tile_size) == (64, 40, 16)
