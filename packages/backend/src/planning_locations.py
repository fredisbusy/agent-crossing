from typing import Literal, TypeAlias, get_args, cast


CanonicalLocation: TypeAlias = Literal[
    "브라이어 코브 > 지호의 집",
    "브라이어 코브 > 수진의 집",
    "브라이어 코브 > 허니컵 카페",
    "브라이어 코브 > 스토리하우스 도서관",
    "브라이어 코브 > 버드나무 시장",
    "브라이어 코브 > 달맞이꽃 공원",
    "브라이어 코브 > 마을 광장",
]

CANONICAL_LOCATIONS: tuple[str, ...] = cast(
    tuple[str, ...], get_args(CanonicalLocation)
)

