"""지각: 누가 가까운지, 무엇을 관찰했는지 (SPEC §12 불가지 원칙).

관찰 문장은 상대 마음 종류와 무관한 한 형식이다.
"""

import datetime
from collections.abc import Sequence

from world.contracts import LOCATION_SEPARATOR, Observation, Utterance
from world.residents import Resident

DEFAULT_PERCEPTION_RADIUS = 4
BUILDING_DEPTH = 2
"""위치 경로 두 번째 단계(`Town > Building`)까지 같으면 같은 건물."""


def building_of(location_path: str) -> str | None:
    parts = location_path.split(LOCATION_SEPARATOR)
    if len(parts) < BUILDING_DEPTH:
        return None
    return LOCATION_SEPARATOR.join(parts[:BUILDING_DEPTH])


def is_near(a: Resident, b: Resident, radius: int) -> bool:
    """같은 건물(또는 같은 야외 구역) 안이면 가깝다. 건물 밖 길에서는 맨해튼 거리가
    `radius` 이하일 때만 가깝다. 벽 너머 다른 건물의 주민은 보지 못한다."""
    sa, sb = a.body.state, b.body.state
    building = building_of(sa.location_path)
    if building != building_of(sb.location_path):
        return False
    if building is not None:
        return True
    distance = abs(sa.tile.x - sb.tile.x) + abs(sa.tile.y - sb.tile.y)
    return distance <= radius


def near_pairs(
    residents: Sequence[Resident], radius: int
) -> set[tuple[str, str]]:
    """가까운 주민 쌍(id 사전순 정렬)."""
    pairs: set[tuple[str, str]] = set()
    for index, a in enumerate(residents):
        for b in residents[index + 1 :]:
            if is_near(a, b, radius):
                first, second = sorted((a.resident_id, b.resident_id))
                pairs.add((first, second))
    return pairs


def sight_text(other: Resident) -> str:
    view = other.public_view()
    doing = view.action_description or "서 있다"
    return f"{view.display_name}가 {view.location_path}에서 {doing}"


def sight_signature(other: Resident) -> tuple[str, str | None]:
    view = other.public_view()
    return (view.location_path, view.action_description)


def sight_observation(other: Resident, at: datetime.datetime, where: str) -> Observation:
    return Observation(
        kind="sight",
        text=sight_text(other),
        observed_at=at,
        location_path=where,
        subject_id=other.resident_id,
    )


def utterance_observation(
    utterance: Utterance, speaker_name: str, where: str
) -> Observation:
    return Observation(
        kind="utterance",
        text=f'{speaker_name}가 말했다: "{utterance.text}"',
        observed_at=utterance.spoken_at,
        location_path=where,
        subject_id=utterance.speaker_id,
        utterance=utterance,
    )
