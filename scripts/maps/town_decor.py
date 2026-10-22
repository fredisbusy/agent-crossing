"""마을 맵의 실외 장식 배치 (SPEC §15, 에셋 계약 D절).

장식은 `decor` objectgroup으로만 나가고, 막는 장식은 collision 레이어에만 반영한다
(ground는 길·풀 그대로 둔다). 데이터만 만든다. 지도 쓰기는 generate_town_map.py가 맡는다.
"""

from collections.abc import Callable

Rect = tuple[int, int, int, int]  # 타일 단위 x, y, w, h
DecorItem = tuple[str, Rect]

# 이 이름의 객체는 collision에 막는다. 막는 칸은 기본적으로 사각형의 아래 한 줄(밑동)이다.
BLOCKING_DECOR = frozenset(
    {
        "fountain_0", "bench_h", "lamp_post", "signpost", "planter", "fence_h", "fence_post", "mailbox",
        "tomato_ripe", "sunflower_ripe", "scarecrow", "beehive", "keg",
    }
)  # fmt: skip
# 키 큰(1x2) 장식은 밑동 한 줄만 막는다.
TALL_DECOR = frozenset({"lamp_post", "signpost", "mailbox", "sunflower_ripe", "scarecrow", "beehive", "keg"})
FOUNTAIN_CELLS = 3

# 가로등 밑동 칸. 큰길(y16) 북쪽 가장자리와 아랫골목(y31). 문 x(9,23,40,52 / 4,19,31,43,56)와
# 우편함 x(6,21,33,58)를 피한다.
STREET_LAMPS = ((3, 16), (17, 16), (28, 16), (36, 16), (47, 16), (58, 16), (13, 31), (39, 31), (63, 31))


def lamp(x: int, base_y: int) -> list[DecorItem]:
    """가로등(16x32)과 같은 위치의 빛 객체(밑동 칸 16x16)."""
    return [("lamp_post", (x, base_y - 1, 1, 2)), ("light", (x, base_y, 1, 1))]


def square_decor() -> list[DecorItem]:
    """Town Square 포석 마당(29,9 7x7, 큰길 북쪽): 가운데 분수, 양옆 벤치, 위 모서리 가로등."""
    items: list[DecorItem] = [("fountain_0", (31, 10, FOUNTAIN_CELLS, FOUNTAIN_CELLS))]
    items += [("bench_h", (29, 13, 2, 1)), ("bench_h", (34, 13, 2, 1))]
    for x, base_y in ((29, 10), (35, 10)):
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
    if name in TALL_DECOR:
        return [(x, y + h - 1)]
    return [(xx, yy) for xx in range(x, x + w) for yy in range(y, y + h)]
