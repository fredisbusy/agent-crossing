"""마을 맵의 장소별 가구 배치표 (SPEC §15, 에셋 계약 D절).

좌표는 건물 로컬(바깥 문이 아래쪽 벽 ly=9에 있는 기준) 타일이다. 항목은 (프레임 이름, lx, ly)이며
크기는 FRAME_CELLS에서 찾는다. 남쪽 건물은 생성기가 세로로 뒤집어 적용한다.
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
    ("furn_bed", 1, 1),
    ("furn_cabinet", 3, 1),
    ("rug_a", 2, 2),
)
_BEDROOM_B: tuple[Item, ...] = (
    ("furn_bed", 9, 1),
    ("furn_cabinet", 6, 1),
    ("rug_a", 7, 2),
)
_LIVING: tuple[Item, ...] = (
    ("furn_sofa", 1, 1),
    ("furn_plant", 4, 1),
    ("rug_b", 1, 3),
    ("furn_table_round", 2, 3),
)

# (건물 이름, 방 이름) -> 가구 목록
ROOM_FURNITURE: dict[tuple[str, str], tuple[Item, ...]] = {
    ("Hobbs Cafe", "Counter"): (
        ("furn_cafe_counter", 1, 1),
        ("furn_pastry_case", 3, 1),
        ("furn_register", 4, 3),
    ),
    ("Hobbs Cafe", "Seating"): (
        ("furn_table_round", 7, 2),
        ("furn_chair_down", 7, 1),
        ("furn_chair_up", 7, 3),
        ("furn_chair_right", 6, 2),
        ("furn_table_round", 8, 5),
        ("furn_chair_down", 8, 4),
        ("furn_chair_up", 8, 6),
        ("furn_chair_right", 7, 5),
    ),
    ("The Willows Market", "Store"): (
        ("furn_market_shelf", 1, 1),
        ("furn_market_shelf", 3, 1),
        ("furn_market_shelf", 5, 1),
        ("furn_market_shelf", 7, 1),
        ("furn_crate", 9, 1),
        ("furn_market_shelf", 3, 4),
        ("furn_market_shelf", 6, 4),
        ("furn_crate", 9, 4),
        ("furn_crate", 1, 7),
        ("furn_register", 9, 7),
    ),
    ("Oak Hill College", "Classroom"): (
        ("furn_chalkboard", 2, 1),
        ("furn_desk", 1, 3),
        ("furn_desk", 3, 5),
        ("furn_desk", 1, 7),
    ),
    ("Oak Hill College", "Library"): (
        ("furn_shelf", 6, 1),
        ("furn_shelf", 8, 1),
        ("furn_shelf", 7, 4),
        ("furn_desk", 8, 6),
        ("furn_chair_up", 8, 7),
    ),
    ("The Rose and Crown Pub", "Bar"): (
        ("furn_keg", 2, 1),
        ("furn_bottle_shelf", 3, 1),
        ("furn_bottle_shelf", 5, 1),
        ("furn_keg", 7, 1),
        ("furn_keg", 8, 1),
        ("furn_bar_counter", 3, 3),
        ("furn_bar_counter", 5, 3),
        ("furn_table_round", 2, 6),
        ("furn_chair_right", 1, 6),
        ("furn_chair_down", 2, 5),
        ("furn_chair_up", 2, 7),
        ("furn_table_round", 8, 6),
        ("furn_chair_right", 7, 6),
        ("furn_chair_down", 8, 5),
        ("furn_chair_up", 8, 7),
    ),
    ("Lin Family House", "Kitchen"): (
        ("furn_stove", 1, 1),
        ("furn_counter", 2, 1),
        ("furn_fridge", 4, 1),
        ("furn_dining_table", 2, 5),
        ("furn_chair_down", 2, 4),
        ("furn_chair_down", 3, 4),
        ("furn_chair_up", 2, 6),
        ("furn_chair_up", 3, 6),
    ),
    ("Lin Family House", "Bedroom"): (
        ("furn_bed", 9, 1),
        ("furn_cabinet", 6, 1),
        ("rug_a", 7, 4),
    ),
    ("Moore Family House", "Living Room"): _LIVING,
    ("Moore Family House", "Bedroom"): (
        ("furn_bed_double", 7, 1),
        ("furn_cabinet", 8, 4),
        ("rug_a", 6, 4),
    ),
    ("Dorm for Oak Hill College", "Klaus's Room"): _BEDROOM_A,
    ("Dorm for Oak Hill College", "Maria's Room"): _BEDROOM_B,
    ("Dorm for Oak Hill College", "Common Room"): (
        ("rug_b", 1, 7),
        ("furn_table_round", 2, 7),
        ("furn_sofa", 7, 7),
        ("furn_plant", 9, 6),
    ),
    ("Isabella's Apartment", "Bedroom"): (
        ("furn_cabinet", 1, 1),
        ("furn_bed_double", 7, 1),
        ("furn_plant", 9, 1),
        ("rug_a", 3, 3),
    ),
    ("Artist's Co-living Space", "Common Room"): _LIVING,
    ("Artist's Co-living Space", "Studio"): (
        ("furn_canvas_stack", 6, 1),
        ("furn_easel", 7, 1),
        ("furn_plant", 8, 1),
        ("furn_easel", 9, 1),
    ),
}
