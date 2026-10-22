"""마을 건물 배치표 (SPEC §15, 큰길 + 골목 배치).

좌표는 월드 타일이다. 모든 건물은 문이 아래(남쪽)에 있고, 아래 세 줄이 앞벽(3/4 시점 정면)이다.
북쪽 줄은 큰길(y15..17)을, 남쪽 줄은 아랫골목(y31..32)을 바라본다.
데이터만 둔다. 지도 쓰기는 generate_town_map.py가 맡는다.
"""

from dataclasses import dataclass

Rect = tuple[int, int, int, int]  # x, y, w, h (타일)

FRONT_ROWS = 3
"""앞벽 두께(칸). 프런트는 이 세 줄 위에 건물 정면을 세운다."""


@dataclass(frozen=True)
class Building:
    """건물 하나. 바깥 문은 앞벽 세 줄을 뚫고, 방 이름 순서는 rooms 순서다."""

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
        (1, 3, 13, 11),
        9,
        (("Counter", (2, 4, 4, 7)), ("Seating", (7, 4, 6, 7))),
        walls=((6, 4, 1, 7),),
        inner_doors=((6, 9),),
    ),
    Building("The Willows Market", (18, 3, 11, 12), 23, (("Store", (19, 4, 9, 8)),)),
    Building("The Rose and Crown Pub", (36, 3, 10, 12), 40, (("Bar", (37, 4, 8, 8)),)),
    Building(
        "Oak Hill College",
        (48, 0, 15, 13),
        52,
        (("Classroom", (49, 1, 7, 9)), ("Library", (57, 1, 5, 9))),
        walls=((56, 1, 1, 9),),
        inner_doors=((56, 7),),
    ),
    # 남쪽 줄: 아랫골목을 바라보고, 큰길 쪽은 뒷마당이다.
    Building(
        "Moore Family House",
        (1, 21, 11, 10),
        4,
        (("Living Room", (2, 22, 4, 6)), ("Bedroom", (7, 22, 4, 6))),
        walls=((6, 22, 1, 6),),
        inner_doors=((6, 26),),
    ),
    Building("Isabella's Apartment", (14, 22, 11, 9), 19, (("Bedroom", (15, 23, 9, 5)),)),
    Building(
        "Dorm for Oak Hill College",
        (27, 18, 11, 13),
        31,
        (
            ("Klaus's Room", (28, 19, 4, 4)),
            ("Maria's Room", (33, 19, 4, 4)),
            ("Common Room", (28, 24, 9, 4)),
        ),
        walls=((32, 19, 1, 4), (28, 23, 9, 1)),
        inner_doors=((29, 23), (35, 23)),
    ),
    Building(
        "Artist's Co-living Space",
        (40, 20, 11, 11),
        43,
        (("Common Room", (41, 21, 4, 7)), ("Studio", (46, 21, 4, 7))),
        walls=((45, 21, 1, 7),),
        inner_doors=((45, 25),),
    ),
    Building(
        "Lin Family House",
        (53, 19, 11, 12),
        56,
        (("Kitchen", (54, 20, 4, 8)), ("Bedroom", (59, 20, 4, 8))),
        walls=((58, 20, 1, 8),),
        inner_doors=((58, 25),),
    ),
)
