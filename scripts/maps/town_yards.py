"""마을 마당·텃밭·골목 장식과 나무 자리 (SPEC §15, 큰길 + 골목 배치).

집마다 문앞(우편함)과 뒷마당(울타리·텃밭·꽃밭·벌통)을 달리 꾸며 같은 상자로 보이지 않게 한다.
데이터만 둔다. 지도 쓰기는 generate_town_map.py가 맡는다.
"""

Rect = tuple[int, int, int, int]  # 타일 단위 x, y, w, h
DecorItem = tuple[str, Rect]

TERRACE: Rect = (14, 10, 3, 6)
"""카페 옆 나무 데크 테라스(바닥 FLOOR, 장소 사각형 밖)."""

TERRACE_FURNITURE: tuple[tuple[str, Rect], ...] = (
    ("furn_table_round", (15, 11, 1, 1)),
    ("furn_chair_down", (15, 10, 1, 1)),
    ("furn_chair_up", (15, 12, 1, 1)),
    ("furn_chair_right", (14, 11, 1, 1)),
    ("furn_table_round", (15, 14, 1, 1)),
    ("furn_chair_down", (15, 13, 1, 1)),
    ("furn_chair_right", (14, 14, 1, 1)),
)

# 나무(TREE gid) 밑동 칸. 건물 옆은 프런트가 덤불로 낮춘다.
TREES: tuple[tuple[int, int], ...] = (
    # 북쪽 숲 가장자리
    (1, 2), (4, 1), (7, 3), (10, 1), (13, 2), (16, 3), (19, 1), (22, 2), (25, 3), (28, 1),
    (31, 2), (34, 1), (37, 3), (40, 1), (43, 2), (46, 3), (50, 0), (55, 1), (60, 0),
    (15, 7), (46, 8), (47, 11),
    # 남쪽 집 사이 틈
    (12, 24), (13, 28), (38, 23), (39, 28),
    # 공원 가장자리
    (2, 38), (5, 39), (19, 38), (22, 39), (30, 38), (34, 39), (45, 38), (47, 35), (50, 38),
    (53, 35), (56, 38), (59, 35), (62, 38),
)  # fmt: skip


def _fence_row(x0: int, x1: int, y: int) -> list[DecorItem]:
    """x0..x1 가로 울타리. 양끝은 기둥."""
    return [("fence_post" if x in (x0, x1) else "fence_h", (x, y, 1, 1)) for x in range(x0, x1 + 1)]


def _plot(x0: int, x1: int, y0: int, y1: int) -> list[DecorItem]:
    """갈아 둔 밭(바닥에 굽는다)."""
    return [("tilled", (x, y, 1, 1)) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def moore_yard() -> list[DecorItem]:
    """무어네 뒷마당: 큰길 쪽 울타리, 토마토·해바라기 텃밭, 허수아비."""
    items = _fence_row(1, 11, 19) + _plot(3, 8, 20, 21)
    items += [("tomato_ripe", (x, 21, 1, 1)) for x in (3, 4, 5)]
    items += [("sunflower_ripe", (7, 20, 1, 2)), ("sunflower_ripe", (8, 20, 1, 2))]
    items.append(("scarecrow", (10, 20, 1, 2)))
    return items


def isabella_yard() -> list[DecorItem]:
    """이사벨라네 앞뜰 같은 뒷마당: 꽃밭 한 줄과 벤치, 화분."""
    kinds = ("flower_bed_a", "flower_bed_b", "flower_bed_c")
    items: list[DecorItem] = [(kinds[i % 3], (x, 20, 1, 1)) for i, x in enumerate(range(15, 19))]
    items += [("bench_h", (19, 21, 2, 1)), ("planter", (22, 20, 1, 1)), ("signpost", (24, 19, 1, 2))]
    return items


def artist_yard() -> list[DecorItem]:
    """예술가 공동주택 뒷마당: 벌통 둘과 꽃밭."""
    return [
        ("beehive", (42, 19, 1, 2)),
        ("beehive", (44, 19, 1, 2)),
        ("flower_bed_b", (47, 20, 1, 1)),
        ("flower_bed_a", (48, 20, 1, 1)),
    ]


def fronts() -> list[DecorItem]:
    """문앞: 집은 우편함, 가게는 화분·꽃, 술집은 술통, 대학 앞 잔디길은 꽃밭."""
    items: list[DecorItem] = [("mailbox", (x, 30, 1, 2)) for x in (6, 21, 33, 58)]
    items += [("flower_bed_a", (8, 15, 1, 1)), ("flower_bed_c", (10, 15, 1, 1))]
    items += [("planter", (21, 16, 1, 1)), ("planter", (25, 16, 1, 1))]
    items.append(("keg", (46, 14, 1, 2)))
    kinds = ("flower_bed_b", "flower_bed_c")
    items += [(kinds[i % 2], (x, y, 1, 1)) for i, (x, y) in enumerate(((51, 14), (53, 14), (51, 15), (53, 15)))]
    return items


def yard_decor() -> list[DecorItem]:
    return moore_yard() + isabella_yard() + artist_yard() + fronts()
