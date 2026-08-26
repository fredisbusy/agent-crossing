from typing import Literal, TypeAlias, get_args, cast


CanonicalLocation: TypeAlias = Literal[
    "브라이어 코브 > 지호의 집",
    "브라이어 코브 > 수진의 집",
    "브라이어 코브 > 민지의 집",
    "브라이어 코브 > 정우의 집",
    "브라이어 코브 > 하은의 집",
    "브라이어 코브 > 태오의 집",
    "브라이어 코브 > 우식의 집",
    "브라이어 코브 > 용준의 집",
    "브라이어 코브 > 병용의 집",
    "브라이어 코브 > 원준의 집",
    "브라이어 코브 > 허니컵 카페",
    "브라이어 코브 > 스토리하우스 도서관",
    "브라이어 코브 > 버드나무 시장",
    "브라이어 코브 > 달맞이꽃 공원",
    "브라이어 코브 > 마을 광장",
    "브라이어 코브 > 별빛 주점",
]

CANONICAL_LOCATIONS: tuple[str, ...] = cast(
    tuple[str, ...], get_args(CanonicalLocation)
)

HOME_LOCATIONS: tuple[str, ...] = tuple(
    location for location in CANONICAL_LOCATIONS if location.endswith("의 집")
)

PUBLIC_LOCATION_ACTIVITIES: dict[str, str] = {
    "브라이어 코브 > 별빛 주점": (
        "저녁에 음료와 간단한 안주를 주문하고, 다트·카드게임·음악을 즐기며 "
        "주민들과 어울릴 수 있는 공공 장소"
    ),
}
