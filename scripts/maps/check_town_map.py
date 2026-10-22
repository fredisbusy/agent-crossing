"""마을 맵(Tiled 1.10 JSON) 검증기 (SPEC §15). 맵의 정본은 Tiled에서 직접 고친 town.json이다.

사용: python3 scripts/maps/check_town_map.py [--fix] [맵 경로]
- 배치와 무관한 규칙만 본다: 레이어·타일 값, 객체 이름·크기, 장소 트리, 주민이 쓰는 장소,
  길에서 모든 장소·의자·문 매트까지 걸어서 닿는지, collision이 ground·장식에서 나온 값과 같은지,
  건물마다 정면(`facades`)이 건물 아래 세 줄에 붙어 있는지.
- `--fix`(옛 이름 `--fix-collision`): 저장 전 정리. 가구·장식 그림 타일셋을 넣고, 사각형 가구·장식을
  그림 타일 객체로 바꾸고, Tiled에서 새로 놓아 이름이 빈 타일 객체에 프레임 이름을 채우고,
  collision 레이어를 ground + 막는 장식으로 다시 계산한다(손으로 칠하지 않는다).
외부 의존 없음. 문제가 있으면 목록을 찍고 1로 끝난다.
"""

import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from town_buildings import FRONT_ROWS  # noqa: E402
from town_decor import DECOR_FRAMES, DecorItem, blocked_cells  # noqa: E402
from town_furniture import FRAME_CELLS, WALKABLE_FRAMES  # noqa: E402
from town_object_tiles import NAME as OBJECT_TILESET, frame_of_gid, tileset_json, to_tile_object, top_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP = ROOT / "packages/shared/maps/town.json"
RESIDENTS_DIR = ROOT / "packages/backend/residents"
TILE = 16
TOWN = "Smallville"
SEP = " > "
GRASS, ROAD, FLOOR, WALL, WATER, FURNITURE, DOOR, TREE = range(1, 9)
BLOCKING_GIDS = frozenset({WALL, WATER, FURNITURE, TREE})
# 장소의 걸을 수 있는 칸 중 길에서 닿아야 하는 비율(가구 뒤 구석은 봐준다).
REACHABLE_RATIO = 0.9
PATH_PATTERN = re.compile(r'"(Smallville(?: > [^"]+)*)"')

Raw = dict[str, Any]
Cell = tuple[int, int]


def layer(raw: Raw, name: str, kind: str) -> Raw | None:
    return next((g for g in raw.get("layers", []) if g.get("name") == name and g.get("type") == kind), None)


def cells_of(obj: Raw) -> list[Cell]:
    x0, y0 = obj["x"] // TILE, top_of(obj) // TILE
    return [(x, y) for y in range(y0, y0 + obj["height"] // TILE) for x in range(x0, x0 + obj["width"] // TILE)]


def rect_of(obj: Raw) -> tuple[int, int, int, int]:
    return obj["x"] // TILE, top_of(obj) // TILE, obj["width"] // TILE, obj["height"] // TILE


def path_of(obj: Raw) -> str | None:
    props = {p.get("name"): p.get("value") for p in obj.get("properties", [])}
    value = props.get("location_path")
    return value if isinstance(value, str) and value else None


def derive_collision(raw: Raw) -> list[int]:
    """ground의 막는 타일 + 막는 장식의 밑동 칸 = collision."""
    width = raw["width"]
    ground = layer(raw, "ground", "tilelayer")["data"]  # type: ignore[index]
    blocked = {i for i, gid in enumerate(ground) if gid in BLOCKING_GIDS}
    for obj in layer(raw, "decor", "objectgroup")["objects"]:  # type: ignore[index]
        item: DecorItem = (obj["name"], rect_of(obj))
        blocked.update(y * width + x for x, y in blocked_cells(item))
    return [1 if i in blocked else 0 for i in range(len(ground))]


def check_structure(raw: Raw, errors: list[str]) -> bool:
    if raw.get("tilewidth") != TILE or raw.get("tileheight") != TILE:
        errors.append(f"타일 크기는 {TILE}px이어야 한다.")
    size = raw.get("width", 0) * raw.get("height", 0)
    for name, kind in (("ground", "tilelayer"), ("collision", "tilelayer"), ("locations", "objectgroup"),
                       ("furniture", "objectgroup"), ("decor", "objectgroup")):  # fmt: skip
        found = layer(raw, name, kind)
        if found is None:
            errors.append(f"{kind} 레이어 '{name}'이(가) 없다.")
        elif kind == "tilelayer" and len(found.get("data", [])) != size:
            errors.append(f"'{name}' 칸 수가 {size}가 아니다(Tiled에서 CSV 인코딩으로 저장).")
    if errors:
        return False
    bad = sorted({gid for gid in layer(raw, "ground", "tilelayer")["data"] if not GRASS <= gid <= TREE})  # type: ignore[index]
    if bad:
        errors.append(f"ground에 1~8 밖의 타일 값이 있다: {bad} (빈 칸은 풀(1)로 칠한다)")
    objects = [o for g in raw["layers"] if g["type"] == "objectgroup" for o in g["objects"]]
    ids = [o["id"] for o in objects]
    if len(ids) != len(set(ids)) or (ids and raw.get("nextobjectid", 0) <= max(ids)):
        errors.append("객체 id가 겹치거나 nextobjectid가 작다.")
    for o in objects:
        if any(o[k] % TILE for k in ("x", "y", "width", "height")) or not o["width"] or not o["height"]:
            errors.append(f"객체 '{o['name']}'(id {o['id']})가 칸에 맞지 않는다(스냅 켜고 다시 그리기).")
    return not errors


def check_object_tiles(raw: Raw, errors: list[str]) -> None:
    """가구·장식은 그림 타일 객체여야 Tiled에서 보인다. gid가 가리키는 그림과 이름이 같아야 한다."""
    if not any(t.get("name") == OBJECT_TILESET for t in raw.get("tilesets", [])):
        errors.append(f"타일셋 '{OBJECT_TILESET}'이 없다. --fix로 넣는다.")
    for name in ("furniture", "decor"):
        for o in layer(raw, name, "objectgroup")["objects"]:  # type: ignore[index]
            if not o.get("gid"):
                errors.append(f"'{o['name']}'(id {o['id']})가 그림 없는 사각형이다. --fix로 그림 타일 객체로 바꾼다.")
            elif frame_of_gid(int(o["gid"])) != o.get("name"):
                errors.append(f"객체 id {o['id']}의 이름 '{o.get('name')}'이 그림({frame_of_gid(int(o['gid']))})과 다르다.")


def check_objects(raw: Raw, errors: list[str]) -> None:
    width = raw["width"]
    ground = layer(raw, "ground", "tilelayer")["data"]  # type: ignore[index]
    for o in layer(raw, "furniture", "objectgroup")["objects"]:  # type: ignore[index]
        size = FRAME_CELLS.get(o["name"])
        if size is None:
            errors.append(f"모르는 가구 프레임 '{o['name']}'(id {o['id']}).")
            continue
        if (o["width"] // TILE, o["height"] // TILE) != size:
            errors.append(f"가구 '{o['name']}'(id {o['id']}) 크기는 {size[0]}x{size[1]}칸이어야 한다.")
        blocking = o["name"] not in WALKABLE_FRAMES
        for x, y in cells_of(o):
            if blocking and ground[y * width + x] != FURNITURE:
                errors.append(f"막는 가구 '{o['name']}'(id {o['id']}) 아래 ({x},{y})를 가구 타일(6)로 칠한다.")
    for o in layer(raw, "decor", "objectgroup")["objects"]:  # type: ignore[index]
        size = DECOR_FRAMES.get(o["name"])
        if size is None:
            errors.append(f"모르는 장식 프레임 '{o['name']}'(id {o['id']}).")
        elif (o["width"] // TILE, o["height"] // TILE) != size:
            errors.append(f"장식 '{o['name']}'(id {o['id']}) 크기는 {size[0]}x{size[1]}칸이어야 한다.")


def resident_paths() -> set[str]:
    found: set[str] = set()
    for file in RESIDENTS_DIR.rglob("*.json"):
        found.update(PATH_PATTERN.findall(file.read_text(encoding="utf-8")))
    return found


def check_locations(raw: Raw, errors: list[str]) -> dict[str, Raw]:
    by_path: dict[str, Raw] = {}
    for o in layer(raw, "locations", "objectgroup")["objects"]:  # type: ignore[index]
        path = path_of(o)
        if path is None:
            errors.append(f"장소 객체 '{o['name']}'(id {o['id']})에 location_path 속성이 없다.")
        elif not path.startswith(TOWN + SEP):
            errors.append(f"'{path}'는 '{TOWN} > '로 시작해야 한다.")
        elif path in by_path:
            errors.append(f"장소 '{path}'가 두 번 있다.")
        else:
            by_path[path] = o
    for path, o in by_path.items():
        parent = path.rsplit(SEP, 1)[0]
        if parent == TOWN:
            continue
        if parent not in by_path:
            errors.append(f"'{path}'의 부모 장소 '{parent}'가 없다.")
        elif not set(cells_of(o)) <= set(cells_of(by_path[parent])):
            errors.append(f"'{path}'가 부모 '{parent}' 사각형 밖으로 나간다.")
    for path in sorted(resident_paths() - set(by_path) - {TOWN}):
        errors.append(f"주민 데이터가 쓰는 장소 '{path}'가 맵에 없다.")
    return by_path


def check_facades(raw: Raw, by_path: dict[str, Raw], errors: list[str]) -> None:
    """`facades`(있으면): 이름 = 벽이 있는 건물, 사각형 = 건물 아래 FRONT_ROWS줄, 아래 줄에 바깥 문 하나."""
    facades = layer(raw, "facades", "objectgroup")
    if facades is None:
        return
    width = raw["width"]
    ground = layer(raw, "ground", "tilelayer")["data"]  # type: ignore[index]
    buildings = {
        path.split(SEP)[1]: o
        for path, o in by_path.items()
        if path.count(SEP) == 1 and any(ground[y * width + x] == WALL for x, y in cells_of(o))
    }
    seen: set[str] = set()
    for f in facades.get("objects", []):
        name = f["name"]
        building = buildings.get(name)
        if building is None:
            errors.append(f"정면 '{name}'(id {f['id']})에 맞는 건물(벽이 있는 장소)이 없다.")
            continue
        seen.add(name)
        bx, by, bw, bh = rect_of(building)
        if rect_of(f) != (bx, by + bh - FRONT_ROWS, bw, FRONT_ROWS):
            errors.append(f"정면 '{name}'은 건물 사각형의 아래 {FRONT_ROWS}줄이어야 한다(건물을 옮겼으면 정면도 옮긴다).")
            continue
        bottom = by + bh - 1
        doors = [x for x in range(bx, bx + bw) if ground[bottom * width + x] == DOOR]
        if len(doors) != 1:
            errors.append(f"정면 '{name}' 아래 줄에 바깥 문(7)이 하나여야 하는데 {len(doors)}개다.")
    for name in sorted(set(buildings) - seen):
        errors.append(f"건물 '{name}'에 정면(facades 객체)이 없다.")


def reachable_from_roads(raw: Raw, collision: list[int]) -> tuple[set[Cell], int] | None:
    """첫 길 칸에서 걸어서 닿는 칸들과, 거기서 끊긴 길 칸 수. 길이 없으면 None."""
    width, height = raw["width"], raw["height"]
    ground = layer(raw, "ground", "tilelayer")["data"]  # type: ignore[index]
    roads = [(i % width, i // width) for i, gid in enumerate(ground) if gid == ROAD and not collision[i]]
    if not roads:
        return None
    seen = {roads[0]}
    queue = deque([roads[0]])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height and not collision[ny * width + nx] and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen, len([c for c in roads if c not in seen])


def check_reachability(raw: Raw, collision: list[int], by_path: dict[str, Raw], errors: list[str]) -> None:
    width = raw["width"]
    result = reachable_from_roads(raw, collision)
    if result is None:
        errors.append("길 타일(2)이 하나도 없다.")
        return
    reached, cut = result
    if cut:
        errors.append(f"서로 이어지지 않은 길 칸이 {cut}개 있다.")
    for path, o in by_path.items():
        free = [c for c in cells_of(o) if not collision[c[1] * width + c[0]]]
        ratio = len([c for c in free if c in reached]) / len(free) if free else 0.0
        if ratio < REACHABLE_RATIO:
            errors.append(f"'{path}'의 걸을 수 있는 칸 중 길에서 닿는 비율이 {ratio:.0%}다(문이 막혔는지 확인).")
    for o in layer(raw, "furniture", "objectgroup")["objects"]:  # type: ignore[index]
        if o["name"] in WALKABLE_FRAMES and not o["name"].startswith("rug") and cells_of(o)[0] not in reached:
            errors.append(f"'{o['name']}'(id {o['id']})에 걸어서 닿지 못한다.")


def check(raw: Raw) -> list[str]:
    errors: list[str] = []
    if not check_structure(raw, errors):
        return errors
    check_objects(raw, errors)
    check_object_tiles(raw, errors)
    by_path = check_locations(raw, errors)
    collision = derive_collision(raw)
    if layer(raw, "collision", "tilelayer")["data"] != collision:  # type: ignore[index]
        errors.append("collision이 ground·장식과 맞지 않는다. --fix-collision으로 다시 계산한다.")
    check_reachability(raw, collision, by_path, errors)
    check_facades(raw, by_path, errors)
    return errors


def render(raw: Raw) -> str:
    """키마다 한 줄로 쓴 JSON(생성기와 같은 모양). Tiled에서 다시 저장해도 읽힌다."""
    lines = [f"{json.dumps(k)}:{json.dumps(v, separators=(',', ':'), ensure_ascii=False)}" for k, v in raw.items()]
    return "{\n" + ",\n".join(lines) + "\n}\n"


FIX_FLAGS = ("--fix", "--fix-collision")


def fix(raw: Raw) -> None:
    """그림 타일셋 넣기 → 가구·장식을 그림 타일 객체로 → 빈 이름 채우기 → collision 다시 계산."""
    tilesets = [t for t in raw.get("tilesets", []) if t.get("name") != OBJECT_TILESET]
    raw["tilesets"] = tilesets + [tileset_json()]
    for name in ("furniture", "decor"):
        for o in layer(raw, name, "objectgroup")["objects"]:  # type: ignore[index]
            to_tile_object(o)
    layer(raw, "collision", "tilelayer")["data"] = derive_collision(raw)  # type: ignore[index]


def main(argv: list[str]) -> int:
    fixing = any(a in FIX_FLAGS for a in argv)
    rest = [a for a in argv if a not in FIX_FLAGS]
    path = Path(rest[0]) if rest else DEFAULT_MAP
    raw = json.loads(path.read_text(encoding="utf-8"))
    if fixing and all(layer(raw, n, k) for n, k in (("collision", "tilelayer"), ("furniture", "objectgroup"),
                                                     ("decor", "objectgroup"))):  # fmt: skip
        fix(raw)
        path.write_text(render(raw), encoding="utf-8")
        print(f"그림 타일 객체·collision을 정리해 저장했다: {path}")
    errors = check(raw)
    for error in errors:
        print(f"- {error}")
    print(f"{path.name}: {'문제 ' + str(len(errors)) + '개' if errors else '통과'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
