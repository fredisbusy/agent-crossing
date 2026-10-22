"""마을 맵의 장소별 가구 배치표 (SPEC §15, 에셋 계약 D절).

좌표는 방 로컬(방 사각형 왼쪽 위 = 0,0) 타일이다. 항목은 (프레임 이름, rx, ry)이며
크기는 FRAME_CELLS에서 찾는다. 모든 건물은 문이 아래(남쪽)에 있어 뒤집지 않는다.
데이터만 둔다. 지도 쓰기는 generate_town_map.py가 맡는다.
"""

# 프레임 이름 -> (너비, 높이) 타일 수. 에셋 계약 A절 + 기존 가구 프레임.
FRAME_CELLS: dict[str, tuple[int, int]] = {
    "furn_shelf": (2, 1),
    "furn_counter": (2, 1),
    "furn_cabinet": (2, 1),
    "furn_plant": (1, 1),
    "furn_bed": (1, 2),
    "furn_bed_double": (2, 2),
    "furn_table_round": (1, 1),
    "furn_chair_down": (1, 1),
    "furn_chair_up": (1, 1),
    "furn_chair_right": (1, 1),
    "furn_dining_table": (2, 1),
    "furn_desk": (2, 1),
    "furn_sofa": (2, 1),
    "furn_cafe_counter": (2, 1),
    "furn_pastry_case": (2, 1),
    "furn_bar_counter": (2, 1),
    "furn_bottle_shelf": (2, 1),
    "furn_keg": (1, 1),
    "furn_chalkboard": (2, 1),
    "furn_easel": (1, 2),
    "furn_canvas_stack": (1, 1),
    "furn_stove": (1, 1),
    "furn_fridge": (1, 2),
    "furn_market_shelf": (2, 1),
    "furn_crate": (1, 1),
    "furn_register": (1, 1),
    "rug_a": (2, 2),
    "rug_b": (3, 2),
    "mat_door": (1, 1),
}

# 막지 않는 프레임: 깔개, 문 매트, 의자(앉는 자리라 걸어서 닿아야 한다).
WALKABLE_FRAMES = frozenset(
    {"rug_a", "rug_b", "mat_door", "furn_chair_down", "furn_chair_up", "furn_chair_right"}
)

Item = tuple[str, int, int]

_BEDROOM_A: tuple[Item, ...] = (
    ("furn_bed", 0, 0),
    ("furn_cabinet", 2, 0),
    ("rug_a", 1, 1),
)
_BEDROOM_B: tuple[Item, ...] = (
    ("furn_bed", 3, 0),
    ("furn_cabinet", 0, 0),
    ("rug_a", 1, 1),
)
_LIVING: tuple[Item, ...] = (
    ("furn_sofa", 0, 0),
    ("furn_plant", 3, 0),
    ("rug_b", 0, 2),
    ("furn_table_round", 1, 2),
)

# (건물 이름, 방 이름) -> 가구 목록
ROOM_FURNITURE: dict[tuple[str, str], tuple[Item, ...]] = {
    ("Hobbs Cafe", "Counter"): (
        ("furn_cafe_counter", 0, 0),
        ("furn_pastry_case", 2, 0),
        ("furn_register", 3, 2),
    ),
    ("Hobbs Cafe", "Seating"): (
        ("furn_table_round", 1, 1),
        ("furn_chair_down", 1, 0),
        ("furn_chair_up", 1, 2),
        ("furn_chair_right", 0, 1),
        ("furn_table_round", 2, 4),
        ("furn_chair_down", 2, 3),
        ("furn_chair_up", 2, 5),
        ("furn_chair_right", 1, 4),
    ),
    ("The Willows Market", "Store"): (
        ("furn_market_shelf", 0, 0),
        ("furn_market_shelf", 2, 0),
        ("furn_market_shelf", 4, 0),
        ("furn_market_shelf", 6, 0),
        ("furn_crate", 8, 0),
        ("furn_market_shelf", 2, 3),
        ("furn_market_shelf", 5, 3),
        ("furn_crate", 8, 3),
        ("furn_crate", 0, 6),
        ("furn_register", 8, 6),
    ),
    ("Oak Hill College", "Classroom"): (
        ("furn_chalkboard", 1, 0),
        ("furn_desk", 0, 2),
        ("furn_desk", 2, 4),
        ("furn_desk", 0, 6),
    ),
    ("Oak Hill College", "Library"): (
        ("furn_shelf", 0, 0),
        ("furn_shelf", 2, 0),
        ("furn_shelf", 1, 3),
        ("furn_desk", 2, 5),
        ("furn_chair_up", 2, 6),
    ),
    ("The Rose and Crown Pub", "Bar"): (
        ("furn_keg", 1, 0),
        ("furn_bottle_shelf", 2, 0),
        ("furn_bottle_shelf", 4, 0),
        ("furn_keg", 6, 0),
        ("furn_keg", 7, 0),
        ("furn_bar_counter", 2, 2),
        ("furn_bar_counter", 4, 2),
        ("furn_table_round", 1, 5),
        ("furn_chair_right", 0, 5),
        ("furn_chair_down", 1, 4),
        ("furn_chair_up", 1, 6),
        ("furn_table_round", 7, 5),
        ("furn_chair_right", 6, 5),
        ("furn_chair_down", 7, 4),
        ("furn_chair_up", 7, 6),
    ),
    ("Lin Family House", "Kitchen"): (
        ("furn_stove", 0, 0),
        ("furn_counter", 1, 0),
        ("furn_fridge", 3, 0),
        ("furn_dining_table", 1, 4),
        ("furn_chair_down", 1, 3),
        ("furn_chair_down", 2, 3),
        ("furn_chair_up", 1, 5),
        ("furn_chair_up", 2, 5),
    ),
    ("Lin Family House", "Bedroom"): (
        ("furn_bed", 3, 0),
        ("furn_cabinet", 0, 0),
        ("rug_a", 1, 3),
    ),
    ("Moore Family House", "Living Room"): _LIVING,
    ("Moore Family House", "Bedroom"): (
        ("furn_bed_double", 1, 0),
        ("furn_cabinet", 2, 3),
        ("rug_a", 0, 3),
    ),
    ("Dorm for Oak Hill College", "Klaus's Room"): _BEDROOM_A,
    ("Dorm for Oak Hill College", "Maria's Room"): _BEDROOM_B,
    ("Dorm for Oak Hill College", "Common Room"): (
        ("rug_b", 0, 1),
        ("furn_table_round", 1, 1),
        ("furn_sofa", 6, 1),
        ("furn_plant", 8, 0),
    ),
    ("Isabella's Apartment", "Bedroom"): (
        ("furn_cabinet", 0, 0),
        ("furn_bed_double", 6, 0),
        ("furn_plant", 8, 0),
        ("rug_a", 2, 2),
    ),
    ("Artist's Co-living Space", "Common Room"): _LIVING,
    ("Artist's Co-living Space", "Studio"): (
        ("furn_canvas_stack", 0, 0),
        ("furn_easel", 1, 0),
        ("furn_plant", 2, 0),
        ("furn_easel", 3, 0),
    ),
}
