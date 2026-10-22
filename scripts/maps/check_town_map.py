"""마을 맵(Tiled 1.10 JSON) 검증기 (SPEC §15). 맵의 정본은 Tiled에서 직접 고친 town.json이다.

사용: python3 scripts/maps/check_town_map.py [--fix-collision] [맵 경로]
- 배치와 무관한 규칙만 본다: 레이어·타일 값, 객체 이름·크기, 장소 트리, 주민이 쓰는 장소,
  길에서 모든 장소·의자·문 매트까지 걸어서 닿는지, collision이 ground·장식에서 나온 값과 같은지.
- `--fix-collision`: collision 레이어를 ground + 막는 장식으로 다시 계산해 저장한다(손으로 칠하지 않는다).
외부 의존 없음. 문제가 있으면 목록을 찍고 1로 끝난다.
"""

import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from town_decor import DECOR_FRAMES, DecorItem, blocked_cells  # noqa: E402
from town_furniture import FRAME_CELLS, WALKABLE_FRAMES  # noqa: E402

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
    x0, y0 = obj["x"] // TILE, obj["y"] // TILE
    return [(x, y) for y in range(y0, y0 + obj["height"] // TILE) for x in range(x0, x0 + obj["width"] // TILE)]


def rect_of(obj: Raw) -> tuple[int, int, int, int]:
    return obj["x"] // TILE, obj["y"] // TILE, obj["width"] // TILE, obj["height"] // TILE


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
    by_path = check_locations(raw, errors)
    collision = derive_collision(raw)
    if layer(raw, "collision", "tilelayer")["data"] != collision:  # type: ignore[index]
        errors.append("collision이 ground·장식과 맞지 않는다. --fix-collision으로 다시 계산한다.")
    check_reachability(raw, collision, by_path, errors)
    return errors


def render(raw: Raw) -> str:
    """키마다 한 줄로 쓴 JSON(생성기와 같은 모양). Tiled에서 다시 저장해도 읽힌다."""
    lines = [f"{json.dumps(k)}:{json.dumps(v, separators=(',', ':'), ensure_ascii=False)}" for k, v in raw.items()]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def main(argv: list[str]) -> int:
    fix = "--fix-collision" in argv
    rest = [a for a in argv if a != "--fix-collision"]
    path = Path(rest[0]) if rest else DEFAULT_MAP
    raw = json.loads(path.read_text(encoding="utf-8"))
    if fix and layer(raw, "collision", "tilelayer") and layer(raw, "decor", "objectgroup"):
        layer(raw, "collision", "tilelayer")["data"] = derive_collision(raw)  # type: ignore[index]
        path.write_text(render(raw), encoding="utf-8")
        print(f"collision을 다시 계산해 저장했다: {path}")
    errors = check(raw)
    for error in errors:
        print(f"- {error}")
    print(f"{path.name}: {'문제 ' + str(len(errors)) + '개' if errors else '통과'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
