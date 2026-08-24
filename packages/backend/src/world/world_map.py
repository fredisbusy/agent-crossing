from __future__ import annotations

import heapq
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class MapPoint:
    x: int
    y: int


@dataclass(frozen=True)
class MapBounds:
    x: int
    y: int
    width: int
    height: int

    def contains(self, point: MapPoint) -> bool:
        return (
            self.x <= point.x < self.x + self.width
            and self.y <= point.y < self.y + self.height
        )


@dataclass(frozen=True)
class MapLocation:
    id: str
    name: str
    kind: str
    location_path: str
    color: str
    bounds: MapBounds


@dataclass(frozen=True)
class MapInteractable:
    id: str
    name: str
    kind: str
    location_path: str
    affordances: tuple[str, ...]
    position: MapPoint


@dataclass(frozen=True)
class MapSpawn:
    id: str
    agent_id: str
    color: str
    position: MapPoint


@dataclass(frozen=True)
class WorldMap:
    id: str
    name: str
    width: int
    height: int
    tile_width: int
    tile_height: int
    locations: tuple[MapLocation, ...]
    collisions: tuple[MapBounds, ...]
    interactables: tuple[MapInteractable, ...]
    spawns: tuple[MapSpawn, ...]

    @property
    def pixel_width(self) -> int:
        return self.width * self.tile_width

    @property
    def pixel_height(self) -> int:
        return self.height * self.tile_height

    def location_at(self, position: MapPoint) -> MapLocation | None:
        return next(
            (
                location
                for location in self.locations
                if location.bounds.contains(position)
            ),
            None,
        )

    def is_walkable_tile(self, tile: MapPoint) -> bool:
        if not 0 <= tile.x < self.width or not 0 <= tile.y < self.height:
            return False
        center = MapPoint(
            x=(tile.x * self.tile_width) + (self.tile_width // 2),
            y=(tile.y * self.tile_height) + (self.tile_height // 2),
        )
        return not any(bounds.contains(center) for bounds in self.collisions)

    def find_path(self, start: MapPoint, goal: MapPoint) -> list[MapPoint]:
        """Return a deterministic four-direction A* path in tile coordinates."""
        if not self.is_walkable_tile(start) or not self.is_walkable_tile(goal):
            return []

        frontier: list[tuple[int, int, MapPoint]] = [(0, 0, start)]
        came_from: dict[MapPoint, MapPoint | None] = {start: None}
        cost_so_far: dict[MapPoint, int] = {start: 0}
        sequence = 0

        while frontier:
            _, _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for neighbor in self._neighbors(current):
                new_cost = cost_so_far[current] + 1
                if neighbor in cost_so_far and new_cost >= cost_so_far[neighbor]:
                    continue
                cost_so_far[neighbor] = new_cost
                sequence += 1
                priority = (
                    new_cost + abs(goal.x - neighbor.x) + abs(goal.y - neighbor.y)
                )
                heapq.heappush(frontier, (priority, sequence, neighbor))
                came_from[neighbor] = current

        if goal not in came_from:
            return []
        path: list[MapPoint] = []
        current: MapPoint | None = goal
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    def _neighbors(self, point: MapPoint) -> tuple[MapPoint, ...]:
        candidates = (
            MapPoint(point.x, point.y - 1),
            MapPoint(point.x + 1, point.y),
            MapPoint(point.x, point.y + 1),
            MapPoint(point.x - 1, point.y),
        )
        return tuple(
            candidate for candidate in candidates if self.is_walkable_tile(candidate)
        )


def default_world_map_path() -> Path:
    return Path(__file__).resolve().parents[3] / "shared" / "assets" / "briar-cove.tmj"


def load_world_map(path: Path | None = None) -> WorldMap:
    source_path = path or default_world_map_path()
    raw_value = cast(object, json.loads(source_path.read_text(encoding="utf-8")))
    raw = _as_object(raw_value, "map root")
    map_properties = _properties(raw)
    layers = {
        _string(layer, "name"): layer
        for layer in _object_list(raw.get("layers", []), "layers")
    }

    locations = tuple(
        MapLocation(
            id=str(item.get("id", "")),
            name=_string(item, "name"),
            kind=str(_property(item, "kind", "location")),
            location_path=str(_property(item, "location_path", _string(item, "name"))),
            color=str(_property(item, "color", "#c7d8b4")),
            bounds=_bounds(item),
        )
        for item in _objects(layers, "locations")
    )
    collisions = tuple(_bounds(item) for item in _objects(layers, "collision"))
    interactables = tuple(
        MapInteractable(
            id=str(item.get("id", "")),
            name=_string(item, "name"),
            kind=str(item.get("type", "object")),
            location_path=str(_property(item, "location_path", _string(item, "name"))),
            affordances=tuple(
                part.strip()
                for part in str(_property(item, "affordances", "observe")).split(",")
                if part.strip()
            ),
            position=_point(item),
        )
        for item in _objects(layers, "interactables")
    )
    spawns = tuple(
        MapSpawn(
            id=str(item.get("id", "")),
            agent_id=str(_property(item, "agent_id", _string(item, "name"))),
            color=str(_property(item, "color", "#6b8fd6")),
            position=_point(item),
        )
        for item in _objects(layers, "spawns")
    )

    return WorldMap(
        id=str(map_properties.get("id", source_path.stem)),
        name=str(map_properties.get("name", source_path.stem)),
        width=_integer(raw, "width"),
        height=_integer(raw, "height"),
        tile_width=_integer(raw, "tilewidth"),
        tile_height=_integer(raw, "tileheight"),
        locations=locations,
        collisions=collisions,
        interactables=interactables,
        spawns=spawns,
    )


def _objects(
    layers: dict[str, dict[str, object]], name: str
) -> list[dict[str, object]]:
    layer = layers.get(name, {})
    return _object_list(layer.get("objects", []), f"{name}.objects")


def _properties(source: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in _object_list(source.get("properties", []), "properties"):
        name = item.get("name")
        if isinstance(name, str):
            result[name] = item.get("value")
    return result


def _property(source: dict[str, object], name: str, default: object) -> object:
    return _properties(source).get(name, default)


def _point(source: dict[str, object]) -> MapPoint:
    return MapPoint(x=round(_number(source, "x")), y=round(_number(source, "y")))


def _bounds(source: dict[str, object]) -> MapBounds:
    return MapBounds(
        x=round(_number(source, "x")),
        y=round(_number(source, "y")),
        width=round(_number(source, "width", default=0)),
        height=round(_number(source, "height", default=0)),
    )


def _as_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    return cast(dict[str, object], value)


def _object_list(value: object, context: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return [_as_object(item, context) for item in cast(list[object], value)]


def _string(source: dict[str, object], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _number(
    source: dict[str, object], key: str, *, default: int | None = None
) -> float:
    value = source.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number")
    return float(value)


def _integer(source: dict[str, object], key: str) -> int:
    return round(_number(source, key))
