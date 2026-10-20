"""ScheduleMind 설정 스키마 (SPEC §12)."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from world.contracts import LocationPath

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

EntryAction = Literal["idle", "use_object", "sleep"]
Tone = Literal["polite", "casual"]


class ScheduleEntry(BaseModel):
    """일과 항목. 다음 항목이 시작하기 전까지 지속된다."""

    model_config = ConfigDict(frozen=True)

    start: str
    """시작 시각 `HH:MM`."""
    location_path: LocationPath
    description: str
    emoji: str | None = None
    action: EntryAction = "idle"
    """장소에 도착한 뒤 하는 행동 종류. 밤 시간은 `sleep`."""
    weekdays: list[int] | None = None
    """적용 요일(0=월 ... 6=일). None이면 매일."""

    @field_validator("start")
    @classmethod
    def _check_start(cls, value: str) -> str:
        if not _HHMM.match(value):
            raise ValueError(f"start must be HH:MM, got {value!r}")
        return value

    @field_validator("weekdays")
    @classmethod
    def _check_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and (not value or any(d < 0 or d > 6 for d in value)):
            raise ValueError("weekdays must be a non-empty list of 0..6")
        return value

    def minutes(self) -> int:
        """자정 기준 시작 분."""
        hour, minute = self.start.split(":")
        return int(hour) * 60 + int(minute)

    def applies_on(self, weekday: int) -> bool:
        return self.weekdays is None or weekday in self.weekdays


class ScheduleConfig(BaseModel):
    """규칙 NPC 한 명의 일정·성향 설정."""

    model_config = ConfigDict(frozen=True)

    entries: list[ScheduleEntry] = Field(min_length=1)
    talkativeness: float = Field(default=0.5, ge=0.0, le=1.0)
    """조우 시 대화를 시작할 확률."""
    share_probability: float = Field(default=0.5, ge=0.0, le=1.0)
    """전할 사실이 있을 때 `share_fact`를 섞는 확률."""
    min_friendship_to_accept_invite: int = 0
    max_turns: int = Field(default=4, ge=1)
    """한 대화에서 내가 말하는 최대 횟수. 마지막 말은 `farewell`."""
    tone: Tone = "polite"
