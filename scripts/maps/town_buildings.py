"""마을 건물 배치표 (SPEC §15, 큰길 + 골목 배치).

좌표는 월드 타일이다. 모든 건물은 문이 아래(남쪽)에 있고, 아래 두 줄이 앞벽(3/4 시점 정면)이다.
북쪽 줄은 큰길(y16..18)을, 남쪽 줄은 아랫골목(y31..32)을 바라본다.
데이터만 둔다. 지도 쓰기는 generate_town_map.py가 맡는다.
"""

from dataclasses import dataclass

Rect = tuple[int, int, int, int]  # x, y, w, h (타일)

FRONT_ROWS = 2
"""앞벽 두께(칸). 프런트는 이 두 줄 위에 건물 정면을 세운다."""


@dataclass(frozen=True)
class Building:
    """건물 하나. 바깥 문은 앞벽 두 줄을 뚫고, 방 이름 순서는 rooms 순서다."""

    name: str
    rect: Rect
    door_x: int
    rooms: tuple[tuple[str, Rect], ...]
    walls: tuple[Rect, ...] = ()
    inner_doors: tuple[tuple[int, int], ...] = ()

    @property
    def front(self) -> Rect:
        x, y, w, h = self.rect
        return (x, y + h - FRONT_ROWS, w, FRONT_ROWS)


BUILDINGS: tuple[Building, ...] = (
    # 북쪽 줄: 큰길을 바라본다. 카페와 대학은 한두 칸 물러서 앞마당을 둔다.
    Building(
        "Hobbs Cafe",
        (1, 5, 13, 10),
        9,
        (("Counter", (2, 6, 4, 7)), ("Seating", (7, 6, 6, 7))),
        walls=((6, 6, 1, 7),),
        inner_doors=((6, 11),),
    ),
    Building("The Willows Market", (18, 5, 11, 11), 23, (("Store", (19, 6, 9, 8)),)),
    Building("The Rose and Crown Pub", (36, 5, 10, 11), 40, (("Bar", (37, 6, 8, 8)),)),
    Building(
        "Oak Hill College",
        (48, 2, 15, 12),
        52,
        (("Classroom", (49, 3, 7, 9)), ("Library", (57, 3, 5, 9))),
        walls=((56, 3, 1, 9),),
        inner_doors=((56, 9),),
    ),
    # 남쪽 줄: 아랫골목을 바라보고, 큰길 쪽은 뒷마당이다.
    Building(
        "Moore Family House",
        (1, 22, 11, 9),
        4,
        (("Living Room", (2, 23, 4, 6)), ("Bedroom", (7, 23, 4, 6))),
        walls=((6, 23, 1, 6),),
        inner_doors=((6, 27),),
    ),
    Building("Isabella's Apartment", (14, 23, 11, 8), 19, (("Bedroom", (15, 24, 9, 5)),)),
    Building(
        "Dorm for Oak Hill College",
        (27, 19, 11, 12),
        31,
        (
            ("Klaus's Room", (28, 20, 4, 4)),
            ("Maria's Room", (33, 20, 4, 4)),
            ("Common Room", (28, 25, 9, 4)),
        ),
        walls=((32, 20, 1, 4), (28, 24, 9, 1)),
        inner_doors=((29, 24), (35, 24)),
    ),
    Building(
        "Artist's Co-living Space",
        (40, 21, 11, 10),
        43,
        (("Common Room", (41, 22, 4, 7)), ("Studio", (46, 22, 4, 7))),
        walls=((45, 22, 1, 7),),
        inner_doors=((45, 26),),
    ),
    Building(
        "Lin Family House",
        (53, 20, 11, 11),
        56,
        (("Kitchen", (54, 21, 4, 8)), ("Bedroom", (59, 21, 4, 8))),
        walls=((58, 21, 1, 8),),
        inner_doors=((58, 26),),
    ),
)
