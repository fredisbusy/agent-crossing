"""마을 마당·텃밭·골목 장식과 나무 자리 (SPEC §15, 큰길 + 골목 배치).

집마다 문앞(우편함)과 뒷마당(울타리·텃밭·꽃밭·벌통)을 달리 꾸며 같은 상자로 보이지 않게 한다.
데이터만 둔다. 지도 쓰기는 generate_town_map.py가 맡는다.
"""

Rect = tuple[int, int, int, int]  # 타일 단위 x, y, w, h
DecorItem = tuple[str, Rect]

TERRACE: Rect = (14, 9, 3, 6)
"""카페 옆 나무 데크 테라스(바닥 FLOOR, 장소 사각형 밖)."""

TERRACE_FURNITURE: tuple[tuple[str, Rect], ...] = (
    ("furn_table_round", (15, 10, 1, 1)),
    ("furn_chair_down", (15, 9, 1, 1)),
    ("furn_chair_up", (15, 11, 1, 1)),
    ("furn_chair_right", (14, 10, 1, 1)),
    ("furn_table_round", (15, 13, 1, 1)),
    ("furn_chair_down", (15, 12, 1, 1)),
    ("furn_chair_right", (14, 13, 1, 1)),
)

# 나무(TREE gid) 밑동 칸. 건물 옆은 프런트가 덤불로 낮춘다.
TREES: tuple[tuple[int, int], ...] = (
    # 북쪽 숲 가장자리(대학은 지도 위끝까지 닿는다)
    (1, 1), (4, 0), (7, 1), (10, 0), (13, 1), (16, 1), (19, 0), (22, 1), (25, 1), (28, 0),
    (31, 1), (34, 0), (37, 1), (40, 0), (43, 1), (46, 1),
    (15, 6), (46, 7), (47, 10),
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
    items = _fence_row(1, 11, 18) + _plot(3, 8, 19, 20)
    items += [("tomato_ripe", (x, 20, 1, 1)) for x in (3, 4, 5)]
    items += [("sunflower_ripe", (7, 19, 1, 2)), ("sunflower_ripe", (8, 19, 1, 2))]
    items.append(("scarecrow", (10, 19, 1, 2)))
    return items


def isabella_yard() -> list[DecorItem]:
    """이사벨라네 앞뜰 같은 뒷마당: 꽃밭 한 줄과 벤치, 화분."""
    kinds = ("flower_bed_a", "flower_bed_b", "flower_bed_c")
    items: list[DecorItem] = [(kinds[i % 3], (x, 19, 1, 1)) for i, x in enumerate(range(15, 19))]
    items += [("bench_h", (19, 20, 2, 1)), ("planter", (22, 19, 1, 1)), ("signpost", (24, 18, 1, 2))]
    return items


def artist_yard() -> list[DecorItem]:
    """예술가 공동주택 뒷마당: 벌통 둘과 꽃밭."""
    return [
        ("beehive", (42, 18, 1, 2)),
        ("beehive", (44, 18, 1, 2)),
        ("flower_bed_b", (47, 19, 1, 1)),
        ("flower_bed_a", (48, 19, 1, 1)),
    ]


def fronts() -> list[DecorItem]:
    """문앞: 집마다 다르게(무어·린 우편함, 이사벨라 화분 한 쌍, 기숙사 벤치, 예술가 해바라기), 가게는 화분·꽃,
    술집은 술통, 대학 앞 잔디길은 꽃밭. 아랫골목 소품은 골목 위 줄(y31)만 막아 아래 줄은 늘 지나간다."""
    items: list[DecorItem] = [("mailbox", (6, 30, 1, 2)), ("mailbox", (58, 30, 1, 2)), ("flower_bed_b", (54, 31, 1, 1))]
    items += [("planter", (18, 31, 1, 1)), ("planter", (20, 31, 1, 1))]
    items += [("bench_h", (33, 31, 2, 1))]
    items += [("sunflower_ripe", (41, 30, 1, 2)), ("flower_bed_c", (45, 31, 1, 1))]
    items += [("flower_bed_a", (8, 14, 1, 1)), ("flower_bed_c", (10, 14, 1, 1))]
    items += [("planter", (21, 15, 1, 1)), ("planter", (25, 15, 1, 1))]
    items.append(("keg", (46, 13, 1, 2)))
    kinds = ("flower_bed_b", "flower_bed_c")
    items += [(kinds[i % 2], (x, y, 1, 1)) for i, (x, y) in enumerate(((51, 13), (53, 13), (51, 14), (53, 14)))]
    return items


def yard_decor() -> list[DecorItem]:
    return moore_yard() + isabella_yard() + artist_yard() + fronts()
