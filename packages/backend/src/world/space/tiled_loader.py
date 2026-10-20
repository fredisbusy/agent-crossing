"""Tiled 1.10 JSON 로더. 지도 파일 하나를 `TiledMap`으로 읽는다 (SPEC §15)."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from world.contracts import LocationPath

GROUND_LAYER = "ground"
COLLISION_LAYER = "collision"
LOCATIONS_LAYER = "locations"
LOCATION_PROPERTY = "location_path"


class TileRect(BaseModel):
    """타일 단위 사각형. x, y는 왼쪽 위, 끝은 포함하지 않는다."""

    model_config = ConfigDict(frozen=True)

    x: int
    y: int
    width: int
    height: int

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    @property
    def area(self) -> int:
        return self.width * self.height


class LocationRegion(BaseModel):
    """`location_path` 속성을 가진 장소 객체 하나."""

    model_config = ConfigDict(frozen=True)

    location_path: LocationPath
    rect: TileRect


class TiledMap(BaseModel):
    """공간 모듈이 쓰는 지도 내용. 타일 데이터는 행 우선(row-major) 1차원."""

    model_config = ConfigDict(frozen=True)

    width: int
    height: int
    tile_size: int
    ground: tuple[int, ...]
    collision: tuple[int, ...]
    regions: tuple[LocationRegion, ...]


def _layer(layers: list[dict[str, Any]], name: str, kind: str) -> dict[str, Any]:
    for layer in layers:
        if layer.get("name") == name and layer.get("type") == kind:
            return layer
    raise ValueError(f"Tiled 지도에 {kind} 레이어 '{name}'이(가) 없습니다.")


def _region_of(obj: dict[str, Any], tile_size: int) -> LocationRegion | None:
    props = {p["name"]: p.get("value") for p in obj.get("properties", [])}
    path = props.get(LOCATION_PROPERTY)
    if not isinstance(path, str) or not path:
        return None
    rect = TileRect(
        x=int(obj["x"]) // tile_size,
        y=int(obj["y"]) // tile_size,
        width=int(obj["width"]) // tile_size,
        height=int(obj["height"]) // tile_size,
    )
    return LocationRegion(location_path=path, rect=rect)


def parse_tiled_map(raw: dict[str, Any]) -> TiledMap:
    width, height = int(raw["width"]), int(raw["height"])
    tile_size = int(raw["tilewidth"])
    layers: list[dict[str, Any]] = raw["layers"]
    ground = tuple(int(v) for v in _layer(layers, GROUND_LAYER, "tilelayer")["data"])
    collision = tuple(int(v) for v in _layer(layers, COLLISION_LAYER, "tilelayer")["data"])
    if len(ground) != width * height or len(collision) != width * height:
        raise ValueError("타일 레이어 크기가 지도 크기와 다릅니다.")
    objects = _layer(layers, LOCATIONS_LAYER, "objectgroup").get("objects", [])
    regions = tuple(r for o in objects if (r := _region_of(o, tile_size)) is not None)
    return TiledMap(
        width=width,
        height=height,
        tile_size=tile_size,
        ground=ground,
        collision=collision,
        regions=regions,
    )


def load_tiled_map(path: Path) -> TiledMap:
    with path.open(encoding="utf-8") as handle:
        return parse_tiled_map(json.load(handle))
