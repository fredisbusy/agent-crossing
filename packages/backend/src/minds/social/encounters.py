"""조우 판정의 공통 규칙과 진단 기록 (TODO 3-C).

대화 쿨다운과 꺼낼 이야깃거리는 두 마음이 같은 규칙으로 본다(SPEC §12).
그 밖의 판단(규칙 마음은 확률, LLM 마음은 모델)만 마음이 따로 정한다.
기록은 진단용이며 행동 결과(`EncounterChoice`)에는 섞지 않는다(AGENTS.md §9).
"""

import datetime
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from world.contracts import EncounterChoice, Holiday, ResidentId

from .state import SocialState

ENCOUNTER_LOG_SIZE = 20
"""마음이 보관하는 최근 조우 판정 수."""

EncounterBasis = Literal["cooldown", "talking_point", "judged", "chance"]
"""판정 근거: 대화 쿨다운 / 꺼낼 이야깃거리 / LLM 판정 / 규칙 마음의 확률."""


@dataclass(frozen=True)
class EncounterRecord:
    """조우 판정 한 번의 진단 기록."""

    at: datetime.datetime
    other_id: ResidentId
    choice: EncounterChoice
    basis: EncounterBasis
    friendship: int
    """판정 시점의 우호도(0~100)."""
    last_talk: datetime.datetime | None
    reason: str = ""
    """근거 설명. LLM 판정이면 모델이 쓴 이유, 규칙이면 걸린 이야깃거리 종류."""


class EncounterLog:
    """최근 조우 판정을 `ENCOUNTER_LOG_SIZE`개까지 보관한다."""

    def __init__(self) -> None:
        self._records: deque[EncounterRecord] = deque(maxlen=ENCOUNTER_LOG_SIZE)

    @property
    def records(self) -> tuple[EncounterRecord, ...]:
        return tuple(self._records)

    def add(
        self,
        social: SocialState,
        other_id: ResidentId,
        now: datetime.datetime,
        choice: EncounterChoice,
        basis: EncounterBasis,
        reason: str = "",
    ) -> EncounterChoice:
        """판정을 기록하고 그 선택을 그대로 돌려준다."""
        self._records.append(
            EncounterRecord(
                at=now,
                other_id=other_id,
                choice=choice,
                basis=basis,
                friendship=social.friendship.score(other_id),
                last_talk=social.friendship.last_talk(other_id),
                reason=reason,
            )
        )
        return choice


def rule_choice(
    social: SocialState,
    other_id: ResidentId,
    now: datetime.datetime,
    holidays: Sequence[Holiday],
) -> tuple[EncounterChoice, EncounterBasis, str] | None:
    """두 마음 공통 규칙으로 정해지면 (선택, 근거, 설명), 아니면 None."""
    if social.friendship.in_cooldown(other_id, now):
        return "pass_by", "cooldown", "방금 이야기한 상대다"
    points = social.talking_points(other_id, now, holidays)
    if points:
        kinds = ", ".join(dict.fromkeys(point.kind for point in points))
        return "converse", "talking_point", f"꺼낼 이야깃거리: {kinds}"
    return None
