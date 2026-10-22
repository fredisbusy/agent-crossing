"""마을 맵(Tiled 1.10 JSON) 결정론적 생성기 (SPEC §15).

사용: python3 scripts/maps/generate_town_map.py [출력 경로]
기본 출력은 packages/shared/maps/town.json. 외부 의존 없음.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from town_decor import DecorItem, blocked_cells, park_decor, pond_decor, square_decor  # noqa: E402
from town_furniture import (  # noqa: E402
    FRAME_CELLS,
    ROOM_FURNITURE,
    WALKABLE_FRAMES,
)

WIDTH = 64
HEIGHT = 40
TILE = 16
GRASS, ROAD, FLOOR, WALL, WATER, FURNITURE, DOOR, TREE = range(1, 9)
BLOCKING = {WALL, WATER, FURNITURE, TREE}
TOWN = "Smallville"
SEP = " > "
BUILDING_W = 11
BUILDING_H = 10
NORTH_Y = 8
SOUTH_Y = 22
ROAD_Y0, ROAD_Y1 = 18, 21
BUILDING_XS = (2, 14, 26, 38, 50)
CONNECTOR_X = 37

Rect = tuple[int, int, int, int]  # x, y, w, h (타일; 건물 로컬 또는 월드)


@dataclass(frozen=True)
class Layout:
    """건물 내부 배치. 로컬 좌표는 바깥 문이 아래(ly=BUILDING_H-1)에 있는 기준."""

    walls: tuple[Rect, ...]
    doors: tuple[tuple[int, int], ...]
    rooms: tuple[Rect, ...]  # 방 이름 순서와 대응


SINGLE = Layout((), ((5, 9),), ((1, 1, 9, 8),))
TWO = Layout(((5, 1, 1, 8),), ((5, 7), (2, 9)), ((1, 1, 4, 8), (6, 1, 4, 8)))
THREE = Layout(
    ((5, 1, 1, 4), (1, 5, 9, 1)),
    ((2, 5), (8, 5), (5, 9)),
    ((1, 1, 4, 4), (6, 1, 4, 4), (1, 6, 9, 3)),
)

# (건물 이름, 배치, 방 이름들)
NORTH = (
    ("Hobbs Cafe", TWO, ("Counter", "Seating")),
    ("The Willows Market", SINGLE, ("Store",)),
    ("Oak Hill College", TWO, ("Classroom", "Library")),
    ("The Rose and Crown Pub", SINGLE, ("Bar",)),
    ("Lin Family House", TWO, ("Kitchen", "Bedroom")),
)
SOUTH = (
    ("Moore Family House", TWO, ("Living Room", "Bedroom")),
    ("Dorm for Oak Hill College", THREE, ("Klaus's Room", "Maria's Room", "Common Room")),
    ("Isabella's Apartment", SINGLE, ("Bedroom",)),
    ("Artist's Co-living Space", TWO, ("Common Room", "Studio")),
)


class Canvas:
    def __init__(self) -> None:
        self.ground = [GRASS] * (WIDTH * HEIGHT)
        self.regions: list[tuple[str, Rect]] = []
        self.furniture: list[tuple[str, Rect]] = []
        self.decor: list[DecorItem] = []
        self.extra_block: set[tuple[int, int]] = set()

    def put(self, x: int, y: int, gid: int) -> None:
        self.ground[y * WIDTH + x] = gid

    def fill(self, rect: Rect, gid: int) -> None:
        x, y, w, h = rect
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, gid)

    def region(self, path: str, rect: Rect) -> None:
        self.regions.append((path, rect))


def place_furniture(canvas: Canvas, frame: str, rect: Rect) -> None:
    """가구 객체를 기록하고, 막는 가구는 ground에 FURNITURE gid를 칠한다."""
    canvas.furniture.append((frame, rect))
    if frame not in WALKABLE_FRAMES:
        canvas.fill(rect, FURNITURE)


def place_building(
    canvas: Canvas,
    x: int,
    y: int,
    flip: bool,
    name: str,
    layout: Layout,
    rooms: tuple[str, ...],
) -> None:
    """flip이면 세로로 뒤집어 문이 위쪽 벽에 오게 한다."""

    def world(lx: int, ly: int) -> tuple[int, int]:
        return x + lx, y + (BUILDING_H - 1 - ly if flip else ly)

    def world_rect(rect: Rect) -> Rect:
        lx, ly, w, h = rect
        wx, wy = world(lx, ly)
        return (wx, wy - (h - 1) if flip else wy, w, h)

    canvas.fill((x, y, BUILDING_W, BUILDING_H), WALL)
    canvas.fill(world_rect((1, 1, BUILDING_W - 2, BUILDING_H - 2)), FLOOR)
    for wall in layout.walls:
        canvas.fill(world_rect(wall), WALL)
    for lx, ly in layout.doors:
        canvas.put(*world(lx, ly), DOOR)
    for lx, ly in layout.doors:
        if ly == BUILDING_H - 1:  # 바깥 문: 안쪽 칸에 문 매트
            place_furniture(canvas, "mat_door", world_rect((lx, ly - 1, 1, 1)))
    building_path = TOWN + SEP + name
    canvas.region(building_path, (x, y, BUILDING_W, BUILDING_H))
    for room_name, room in zip(rooms, layout.rooms, strict=True):
        rx, ry, _, _ = world_rect(room)
        for frame, lx, ly in ROOM_FURNITURE[(name, room_name)]:
            fw, fh = FRAME_CELLS[frame]
            place_furniture(canvas, frame, world_rect((lx, ly, fw, fh)))
        canvas.region(building_path + SEP + room_name, world_rect(room))


def scatter_trees(canvas: Canvas) -> None:
    for i in range(48):
        x = (i * 37 + 11) % WIDTH
        y = (i * 17 + 5) % 7 + 1 if i % 2 == 0 else 34 + (i * 5) % 5
        if CONNECTOR_X - 1 <= x <= CONNECTOR_X + 1:
            continue
        if 6 <= x <= 16 and 35 <= y <= 37:  # Garden은 비워 둔다
            continue
        if 24 <= x <= 28 and 35 <= y <= 37:  # 연못 자리
            continue
        if canvas.ground[y * WIDTH + x] == GRASS:
            canvas.put(x, y, TREE)


def build() -> Canvas:
    canvas = Canvas()
    canvas.fill((0, ROAD_Y0, WIDTH, ROAD_Y1 - ROAD_Y0 + 1), ROAD)
    canvas.fill((CONNECTOR_X, SOUTH_Y, 1, 12), ROAD)
    scatter_trees(canvas)
    for x, (name, layout, rooms) in zip(BUILDING_XS, NORTH, strict=False):
        place_building(canvas, x, NORTH_Y, False, name, layout, rooms)
    for x, (name, layout, rooms) in zip(BUILDING_XS, SOUTH, strict=False):
        place_building(canvas, x, SOUTH_Y, True, name, layout, rooms)
    canvas.fill((24, 35, 5, 3), WATER)
    canvas.region(TOWN + SEP + "Town Square", (27, ROAD_Y0, 10, ROAD_Y1 - ROAD_Y0 + 1))
    canvas.region(TOWN + SEP + "Johnson Park", (2, 33, 47, 6))
    canvas.region(TOWN + SEP + "Johnson Park" + SEP + "Garden", (6, 35, 11, 3))
    add_decor(canvas)
    return canvas


def add_decor(canvas: Canvas) -> None:
    def is_free_grass(x: int, y: int, w: int, h: int) -> bool:
        return all(
            canvas.ground[yy * WIDTH + xx] == GRASS
            for yy in range(y, y + h)
            for xx in range(x, x + w)
        )

    canvas.decor = square_decor() + park_decor(is_free_grass) + pond_decor()
    for item in canvas.decor:
        canvas.extra_block.update(blocked_cells(item))


def object_group(layer_id: int, name: str, objects: list[dict[str, object]]) -> dict[str, object]:
    return {
        "draworder": "topdown",
        "id": layer_id,
        "name": name,
        "objects": objects,
        "opacity": 1,
        "type": "objectgroup",
        "visible": True,
        "x": 0,
        "y": 0,
    }


def rect_objects(items: list[tuple[str, Rect]], first_id: int) -> list[dict[str, object]]:
    return [
        {
            "height": h * TILE,
            "id": first_id + i,
            "name": name,
            "rotation": 0,
            "type": "",
            "visible": True,
            "width": w * TILE,
            "x": x * TILE,
            "y": y * TILE,
        }
        for i, (name, (x, y, w, h)) in enumerate(items)
    ]


def tile_layer(layer_id: int, name: str, data: list[int]) -> dict[str, object]:
    return {
        "data": data,
        "height": HEIGHT,
        "id": layer_id,
        "name": name,
        "opacity": 1,
        "type": "tilelayer",
        "visible": True,
        "width": WIDTH,
        "x": 0,
        "y": 0,
    }


def to_tiled(canvas: Canvas) -> dict[str, object]:
    collision = [
        1 if gid in BLOCKING or (i % WIDTH, i // WIDTH) in canvas.extra_block else 0
        for i, gid in enumerate(canvas.ground)
    ]
    objects = []
    for index, (path, (x, y, w, h)) in enumerate(canvas.regions, start=1):
        objects.append(
            {
                "height": h * TILE,
                "id": index,
                "name": path.split(SEP)[-1],
                "properties": [{"name": "location_path", "type": "string", "value": path}],
                "rotation": 0,
                "type": "",
                "visible": True,
                "width": w * TILE,
                "x": x * TILE,
                "y": y * TILE,
            }
        )
    locations = object_group(3, "locations", objects)
    furniture_objects = rect_objects(canvas.furniture, len(objects) + 1)
    decor_objects = rect_objects(canvas.decor, len(objects) + len(furniture_objects) + 1)
    tileset = {
        "columns": 8,
        "firstgid": 1,
        "image": "town-tiles.png",
        "imageheight": 16,
        "imagewidth": 128,
        "margin": 0,
        "name": "town-tiles",
        "spacing": 0,
        "tilecount": 8,
        "tileheight": TILE,
        "tilewidth": TILE,
    }
    return {
        "compressionlevel": -1,
        "height": HEIGHT,
        "infinite": False,
        "layers": [
            tile_layer(1, "ground", canvas.ground),
            tile_layer(2, "collision", collision),
            locations,
            object_group(4, "furniture", furniture_objects),
            object_group(5, "decor", decor_objects),
        ],
        "nextlayerid": 6,
        "nextobjectid": len(objects) + len(furniture_objects) + len(decor_objects) + 1,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.10.2",
        "tileheight": TILE,
        "tilesets": [tileset],
        "tilewidth": TILE,
        "type": "map",
        "version": "1.10",
        "width": WIDTH,
    }


def render(tiled: dict[str, object]) -> str:
    """키마다 한 줄로 쓴 JSON. 같은 입력이면 항상 같은 바이트."""
    lines = [f"{json.dumps(k)}:{json.dumps(v, separators=(',', ':'))}" for k, v in tiled.items()]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def main() -> None:
    default = Path(__file__).resolve().parents[2] / "packages/shared/maps/town.json"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(to_tiled(build())), encoding="utf-8")


if __name__ == "__main__":
    main()
