"""마을 맵의 실외 장식 배치 (SPEC §15, 에셋 계약 D절).

장식은 `decor` objectgroup으로만 나가고, 막는 장식은 collision 레이어에만 반영한다
(ground는 길·풀 그대로 둔다). 데이터만 만든다. 지도 쓰기는 generate_town_map.py가 맡는다.
"""

from collections.abc import Callable

Rect = tuple[int, int, int, int]  # 타일 단위 x, y, w, h
DecorItem = tuple[str, Rect]

# 이 이름의 객체는 collision에 막는다. 막는 칸은 기본적으로 사각형의 아래 한 줄(밑동)이다.
BLOCKING_DECOR = frozenset({"fountain_0", "bench_h", "lamp_post", "signpost", "planter"})
FOUNTAIN_CELLS = 3

# 큰길 가로등 밑동 칸. 건물 문 앞 칸(문 x 4,19,28,43,52 / 4,19,31,40)을 피한다.
STREET_LAMPS = ((10, 19), (22, 19), (42, 19), (60, 19))


def lamp(x: int, base_y: int) -> list[DecorItem]:
    """가로등(16x32)과 같은 위치의 빛 객체(밑동 칸 16x16)."""
    return [("lamp_post", (x, base_y - 1, 1, 2)), ("light", (x, base_y, 1, 1))]


def square_decor() -> list[DecorItem]:
    """Town Square(27,18 10x4): 가운데 분수, 둘레 벤치와 가로등. 맨 아래 줄(y21)은 걷는 길로 둔다."""
    items: list[DecorItem] = [("fountain_0", (30, 18, FOUNTAIN_CELLS, FOUNTAIN_CELLS))]
    items += [("bench_h", (28, 19, 2, 1)), ("bench_h", (34, 19, 2, 1))]
    for x, base_y in ((27, 19), (36, 19), (27, 21), (36, 21)):
        items += lamp(x, base_y)
    for x, base_y in STREET_LAMPS:
        items += lamp(x, base_y)
    return items


def park_decor(is_free_grass: Callable[[int, int, int, int], bool]) -> list[DecorItem]:
    """Johnson Park(2,33 47x6)와 Garden(6,35 11x3), 연못(24,35 5x3) 장식.

    is_free_grass(x, y, w, h): 그 사각형이 전부 비어 있는 풀이면 True(나무·길·물 제외).
    """
    items: list[DecorItem] = []
    taken: set[tuple[int, int]] = set()

    def add(name: str, rect: Rect) -> None:
        x, y, w, h = rect
        if not is_free_grass(x, y, w, h):
            return
        cells = {(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)}
        if cells & taken:
            return
        taken.update(cells)
        items.append((name, rect))

    kinds = ("flower_bed_a", "flower_bed_b", "flower_bed_c")
    for i, x in enumerate(range(6, 17, 2)):  # Garden 위줄
        add(kinds[i % 3], (x, 35, 1, 1))
    for i, x in enumerate(range(7, 16, 2)):  # Garden 아래줄
        add(kinds[(i + 1) % 3], (x, 37, 1, 1))
    add("bench_h", (10, 36, 2, 1))
    add("planter", (6, 36, 1, 1))
    add("planter", (16, 36, 1, 1))
    for i, x in enumerate((19, 21, 31, 33, 40, 42, 44)):  # 공원 곳곳
        add(kinds[i % 3], (x, 34, 1, 1))
    add("bench_h", (31, 36, 2, 1))
    add("bench_h", (40, 36, 2, 1))
    add("signpost", (35, 34, 1, 2))
    return items


def pond_decor() -> list[DecorItem]:
    """연못(물 24..28, 35..37) 위 연꽃과 물가 갈대."""
    return [
        ("lily_pad", (25, 36, 1, 1)),
        ("lily_pad_b", (27, 36, 1, 1)),
        ("lily_pad", (26, 35, 1, 1)),
        ("lily_pad_b", (26, 37, 1, 1)),
        ("reeds", (24, 35, 1, 1)),
        ("reeds", (28, 36, 1, 1)),
        ("reeds", (24, 37, 1, 1)),
    ]


def blocked_cells(item: DecorItem) -> list[tuple[int, int]]:
    """막는 장식이 collision에 올리는 칸. 키 큰 장식은 밑동 한 줄만 막는다."""
    name, (x, y, w, h) = item
    if name not in BLOCKING_DECOR:
        return []
    if name in ("lamp_post", "signpost"):
        return [(x, y + h - 1)]
    return [(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)]
