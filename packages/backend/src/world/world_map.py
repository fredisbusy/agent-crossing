from __future__ import annotations

import heapq
import json
from collections.abc import Collection
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
    aliases: tuple[str, ...]
    bounds: MapBounds
    entrance: MapPoint | None
    entrance_direction: MapPoint


@dataclass(frozen=True)
class MapPath:
    id: str
    name: str
    points: tuple[MapPoint, ...]


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
    paths: tuple[MapPath, ...]
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

    def resolve_location(self, plan_text: str) -> MapLocation | None:
        normalized_plan = _normalize_label(plan_text)
        if not normalized_plan:
            return None
        candidates: list[tuple[int, int, MapLocation]] = []
        for index, location in enumerate(self.locations):
            labels = (
                location.name,
                location.kind,
                location.location_path,
                *location.aliases,
            )
            matches = [
                len(normalized_label)
                for label in labels
                if (normalized_label := _normalize_label(label))
                and normalized_label in normalized_plan
            ]
            if matches:
                candidates.append((-max(matches), index, location))
        return min(candidates)[2] if candidates else None

    def nearest_walkable_tile(
        self,
        *,
        bounds: MapBounds,
        origin: MapPoint,
        blocked_tiles: Collection[MapPoint] = (),
    ) -> MapPoint | None:
        candidates: list[tuple[int, int, int, MapPoint]] = []
        for tile_y in range(self.height):
            for tile_x in range(self.width):
                tile = MapPoint(tile_x, tile_y)
                if not self.is_walkable_tile(tile, blocked_tiles=blocked_tiles):
                    continue
                center_x = (tile_x * self.tile_width) + (self.tile_width // 2)
                center_y = (tile_y * self.tile_height) + (self.tile_height // 2)
                distance_to_bounds = _distance_to_bounds(
                    x=center_x,
                    y=center_y,
                    bounds=bounds,
                )
                distance_from_origin = abs(tile_x - origin.x) + abs(tile_y - origin.y)
                candidates.append(
                    (
                        distance_to_bounds,
                        distance_from_origin,
                        tile_y * self.width + tile_x,
                        tile,
                    )
                )
        return min(candidates)[3] if candidates else None

    def destination_tile(
        self,
        *,
        location: MapLocation,
        origin: MapPoint,
        blocked_tiles: Collection[MapPoint] = (),
    ) -> MapPoint | None:
        """Resolve a building through its door or an open location by bounds."""
        if location.entrance is None:
            return self.nearest_walkable_tile(
                bounds=location.bounds,
                origin=origin,
                blocked_tiles=blocked_tiles,
            )

        queue_length = max(len(self.spawns) + 1, 2)
        for offset in range(queue_length):
            candidate = MapPoint(
                x=location.entrance.x + location.entrance_direction.x * offset,
                y=location.entrance.y + location.entrance_direction.y * offset,
            )
            if self.is_walkable_tile(candidate, blocked_tiles=blocked_tiles):
                return candidate
        return None

    def is_walkable_tile(
        self,
        tile: MapPoint,
        *,
        blocked_tiles: Collection[MapPoint] = (),
    ) -> bool:
        if not 0 <= tile.x < self.width or not 0 <= tile.y < self.height:
            return False
        if tile in blocked_tiles:
            return False
        center = MapPoint(
            x=(tile.x * self.tile_width) + (self.tile_width // 2),
            y=(tile.y * self.tile_height) + (self.tile_height // 2),
        )
        return not any(bounds.contains(center) for bounds in self.collisions)

    def movement_cost(self, tile: MapPoint) -> int:
        """Prefer authored paths and open public areas over traversable grass."""
        center = self.tile_center(tile)
        on_authored_path = any(
            _distance_to_polyline(center, path.points) <= self.tile_width
            for path in self.paths
        )
        in_public_area = any(
            location.kind in {"plaza", "park"} and location.bounds.contains(center)
            for location in self.locations
        )
        return 1 if on_authored_path or in_public_area else 4

    def tile_center(self, tile: MapPoint) -> MapPoint:
        return MapPoint(
            x=(tile.x * self.tile_width) + (self.tile_width // 2),
            y=(tile.y * self.tile_height) + (self.tile_height // 2),
        )

    def is_connected_to_authored_path(self, tile: MapPoint) -> bool:
        """Return whether a path reaches the tile edge-to-center.

        Tiled paths are authored on tile boundaries while navigation uses tile
        centers, so half a tile is the exact expected door-connection offset.
        """
        center = self.tile_center(tile)
        return any(
            _distance_to_polyline(center, path.points) <= self.tile_width / 2
            for path in self.paths
        )

    def find_path(
        self,
        start: MapPoint,
        goal: MapPoint,
        *,
        blocked_tiles: Collection[MapPoint] = (),
    ) -> list[MapPoint]:
        """Return a deterministic four-direction A* path in tile coordinates."""
        if not self.is_walkable_tile(
            start, blocked_tiles=blocked_tiles
        ) or not self.is_walkable_tile(goal, blocked_tiles=blocked_tiles):
            return []

        frontier: list[tuple[int, int, MapPoint]] = [(0, 0, start)]
        came_from: dict[MapPoint, MapPoint | None] = {start: None}
        cost_so_far: dict[MapPoint, int] = {start: 0}
        sequence = 0

        while frontier:
            _, _, current = heapq.heappop(frontier)
            if current == goal:
                break
            for neighbor in self._neighbors(current, blocked_tiles=blocked_tiles):
                new_cost = cost_so_far[current] + self.movement_cost(neighbor)
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

    def _neighbors(
        self,
        point: MapPoint,
        *,
        blocked_tiles: Collection[MapPoint] = (),
    ) -> tuple[MapPoint, ...]:
        candidates = (
            MapPoint(point.x, point.y - 1),
            MapPoint(point.x + 1, point.y),
            MapPoint(point.x, point.y + 1),
            MapPoint(point.x - 1, point.y),
        )
        return tuple(
            candidate
            for candidate in candidates
            if self.is_walkable_tile(candidate, blocked_tiles=blocked_tiles)
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
            aliases=tuple(
                alias.strip()
                for alias in str(_property(item, "aliases", "")).split(",")
                if alias.strip()
            ),
            bounds=_bounds(item),
            entrance=_optional_entrance(item),
            entrance_direction=MapPoint(
                x=_integer_property(item, "entrance_dx", 0),
                y=_integer_property(item, "entrance_dy", 1),
            ),
        )
        for item in _objects(layers, "locations")
    )
    paths = tuple(
        MapPath(
            id=str(item.get("id", "")),
            name=_string(item, "name"),
            points=_polyline_points(item),
        )
        for item in _objects(layers, "paths")
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

    world_map = WorldMap(
        id=str(map_properties.get("id", source_path.stem)),
        name=str(map_properties.get("name", source_path.stem)),
        width=_integer(raw, "width"),
        height=_integer(raw, "height"),
        tile_width=_integer(raw, "tilewidth"),
        tile_height=_integer(raw, "tileheight"),
        locations=locations,
        paths=paths,
        collisions=collisions,
        interactables=interactables,
        spawns=spawns,
    )
    _validate_home_access(world_map)
    return world_map


def _validate_home_access(world_map: WorldMap) -> None:
    """Require every home to use one authored, path-connected doorway.

    Home interiors are semantic dollhouse views rather than walkable outdoor
    tiles. The agent reaches the door tile, then the frontend projects it into
    an indoor activity slot. The solid tile immediately behind the door keeps
    outdoor A* from ever walking through a wall or across the house body.
    """
    for home in (
        location for location in world_map.locations if location.kind == "home"
    ):
        entrance = home.entrance
        if entrance is None:
            raise ValueError(f"home '{home.name}' must define an entrance tile")
        direction = home.entrance_direction
        if abs(direction.x) + abs(direction.y) != 1:
            raise ValueError(f"home '{home.name}' entrance direction must be cardinal")
        if not world_map.is_walkable_tile(entrance):
            raise ValueError(f"home '{home.name}' entrance must be walkable")
        if not world_map.is_connected_to_authored_path(entrance):
            raise ValueError(
                f"home '{home.name}' entrance must connect to an authored path"
            )
        wall_behind_door = MapPoint(
            x=entrance.x - direction.x,
            y=entrance.y - direction.y,
        )
        if world_map.is_walkable_tile(wall_behind_door):
            raise ValueError(
                f"home '{home.name}' wall behind entrance must remain solid"
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


def _integer_property(source: dict[str, object], name: str, default: int) -> int:
    value = _property(source, name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _optional_entrance(source: dict[str, object]) -> MapPoint | None:
    properties = _properties(source)
    x = properties.get("entrance_tile_x")
    y = properties.get("entrance_tile_y")
    if x is None and y is None:
        return None
    if (
        isinstance(x, bool)
        or not isinstance(x, int)
        or isinstance(y, bool)
        or not isinstance(y, int)
    ):
        raise ValueError("entrance_tile_x and entrance_tile_y must be integers")
    return MapPoint(x=x, y=y)


def _polyline_points(source: dict[str, object]) -> tuple[MapPoint, ...]:
    origin_x = _integer(source, "x")
    origin_y = _integer(source, "y")
    raw_points = _object_list(source.get("polyline", []), "polyline")
    points = tuple(
        MapPoint(
            x=origin_x + _integer(point, "x"),
            y=origin_y + _integer(point, "y"),
        )
        for point in raw_points
    )
    if len(points) < 2:
        raise ValueError("path polyline must contain at least two points")
    return points


def _distance_to_polyline(point: MapPoint, points: tuple[MapPoint, ...]) -> float:
    return min(
        _distance_to_segment(point, start, end)
        for start, end in zip(points, points[1:])
    )


def _distance_to_segment(point: MapPoint, start: MapPoint, end: MapPoint) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    if dx == 0 and dy == 0:
        return ((point.x - start.x) ** 2 + (point.y - start.y) ** 2) ** 0.5
    progress = max(
        0.0,
        min(
            1.0,
            ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy),
        ),
    )
    projection_x = start.x + progress * dx
    projection_y = start.y + progress * dy
    return ((point.x - projection_x) ** 2 + (point.y - projection_y) ** 2) ** 0.5


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


def _normalize_label(value: str) -> str:
    normalized_characters = (
        character.lower() if character.isalnum() else " " for character in value
    )
    return " ".join("".join(normalized_characters).split())


def _distance_to_bounds(*, x: int, y: int, bounds: MapBounds) -> int:
    horizontal = max(bounds.x - x, 0, x - (bounds.x + bounds.width - 1))
    vertical = max(bounds.y - y, 0, y - (bounds.y + bounds.height - 1))
    return horizontal + vertical
