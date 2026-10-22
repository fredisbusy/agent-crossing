"""마을 맵(Tiled 1.10 JSON) 결정론적 생성기 (SPEC §15).

사용: python3 scripts/maps/generate_town_map.py [출력 경로]
기본 출력은 packages/shared/maps/town.json. 외부 의존 없음.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from town_buildings import BUILDINGS, Building  # noqa: E402
from town_decor import DecorItem, blocked_cells, park_decor, pond_decor, square_decor  # noqa: E402
from town_furniture import FRAME_CELLS, ROOM_FURNITURE, WALKABLE_FRAMES  # noqa: E402
from town_yards import TERRACE, TERRACE_FURNITURE, TREES, yard_decor  # noqa: E402

WIDTH = 64
HEIGHT = 40
TILE = 16
GRASS, ROAD, FLOOR, WALL, WATER, FURNITURE, DOOR, TREE = range(1, 9)
BLOCKING = {WALL, WATER, FURNITURE, TREE}
TOWN = "Smallville"
SEP = " > "
Rect = tuple[int, int, int, int]  # x, y, w, h (월드 타일)
MAIN_ROAD: Rect = (0, 15, WIDTH, 3)
LOWER_LANE: Rect = (0, 31, WIDTH, 2)
SIDE_LANES: tuple[Rect, ...] = ((25, 18, 2, 13), (51, 18, 2, 13))
# 북쪽 건물 앞마당을 큰길까지 잇는 한 칸 길(카페·대학 문 아래).
FRONT_PATHS: tuple[Rect, ...] = ((9, 14, 1, 1), (52, 13, 1, 2))
SQUARE: Rect = (29, 8, 7, 10)
SQUARE_PLAZA: Rect = (29, 8, 7, 7)
POND: Rect = (24, 35, 5, 3)
PARK: Rect = (0, 33, WIDTH, 7)
GARDEN: Rect = (6, 35, 11, 3)


class Canvas:
    def __init__(self) -> None:
        self.ground = [GRASS] * (WIDTH * HEIGHT)
        self.regions: list[tuple[str, Rect]] = []
        self.furniture: list[tuple[str, Rect]] = []
        self.decor: list[DecorItem] = []
        self.facades: list[tuple[str, Rect]] = []
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


def place_building(canvas: Canvas, building: Building) -> None:
    """벽(위·옆 한 칸, 앞 두 칸)과 바닥, 칸막이, 문, 방별 가구를 놓는다."""
    x, y, w, h = building.rect
    fx, fy, _, fh = building.front
    canvas.fill(building.rect, WALL)
    canvas.fill((x + 1, y + 1, w - 2, fy - y - 1), FLOOR)
    for wall in building.walls:
        canvas.fill(wall, WALL)
    for door in building.inner_doors:
        canvas.put(*door, DOOR)
    canvas.fill((building.door_x, fy, 1, fh), DOOR)
    place_furniture(canvas, "mat_door", (building.door_x, fy - 1, 1, 1))
    path = TOWN + SEP + building.name
    canvas.region(path, building.rect)
    canvas.facades.append((building.name, building.front))
    for room_name, room in building.rooms:
        rx, ry, _, _ = room
        for frame, ox, oy in ROOM_FURNITURE[(building.name, room_name)]:
            cw, ch = FRAME_CELLS[frame]
            place_furniture(canvas, frame, (rx + ox, ry + oy, cw, ch))
        canvas.region(path + SEP + room_name, room)


def build() -> Canvas:
    canvas = Canvas()
    for road in (MAIN_ROAD, LOWER_LANE, *SIDE_LANES, *FRONT_PATHS, SQUARE_PLAZA):
        canvas.fill(road, ROAD)
    for tx, ty in TREES:
        canvas.put(tx, ty, TREE)
    for building in BUILDINGS:
        place_building(canvas, building)
    canvas.fill(TERRACE, FLOOR)
    for frame, rect in TERRACE_FURNITURE:
        place_furniture(canvas, frame, rect)
    canvas.fill(POND, WATER)
    canvas.region(TOWN + SEP + "Town Square", SQUARE)
    canvas.region(TOWN + SEP + "Johnson Park", PARK)
    canvas.region(TOWN + SEP + "Johnson Park" + SEP + "Garden", GARDEN)
    add_decor(canvas)
    return canvas


def add_decor(canvas: Canvas) -> None:
    def is_free_grass(x: int, y: int, w: int, h: int) -> bool:
        return all(
            canvas.ground[yy * WIDTH + xx] == GRASS
            for yy in range(y, y + h)
            for xx in range(x, x + w)
        )

    canvas.decor = square_decor() + park_decor(is_free_grass) + pond_decor() + yard_decor()
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
    facade_objects = rect_objects(canvas.facades, len(objects) + len(furniture_objects) + len(decor_objects) + 1)
    next_id = len(objects) + len(furniture_objects) + len(decor_objects) + len(facade_objects) + 1
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
            object_group(6, "facades", facade_objects),
        ],
        "nextlayerid": 7,
        "nextobjectid": next_id,
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
