"""일정표: 시각·요일로 현재 항목을 고르고, 수락한 초대를 덮어쓰기로 얹는다."""

import datetime
from dataclasses import dataclass, field

from world.contracts import LocationPath

from .config import EntryAction, ScheduleEntry

OVERRIDE_LEAD = datetime.timedelta(minutes=30)
"""덮어쓰기 시작 전 미리 이동을 시작하는 시간 (SPEC §13)."""
OVERRIDE_DURATION = datetime.timedelta(minutes=60)
"""초대에 길이가 없으므로 쓰는 기본 행사 길이."""
_LOOKAHEAD_DAYS = 8


@dataclass(frozen=True)
class Slot:
    """지금 따라야 할 한 구간."""

    location_path: LocationPath
    description: str
    emoji: str | None
    action: EntryAction
    start: datetime.datetime
    end: datetime.datetime
    is_override: bool = False


@dataclass(frozen=True)
class Override:
    """수락한 초대 같은 일회성 항목."""

    event: str
    start: datetime.datetime
    end: datetime.datetime
    location_path: LocationPath


@dataclass
class Timetable:
    entries: tuple[ScheduleEntry, ...]
    overrides: list[Override] = field(default_factory=list)

    def add_override(
        self, event: str, start: datetime.datetime, location_path: LocationPath
    ) -> Override:
        override = Override(event, start, start + OVERRIDE_DURATION, location_path)
        self.overrides.append(override)
        self.overrides.sort(key=lambda o: (o.start, o.event))
        return override

    def conflicts(self, start: datetime.datetime) -> bool:
        end = start + OVERRIDE_DURATION
        return any(o.start < end and start < o.end for o in self.overrides)

    def slot_at(self, now: datetime.datetime) -> Slot:
        """덮어쓰기(시작 30분 전부터)가 있으면 그것, 없으면 일정표 항목."""
        self.overrides = [o for o in self.overrides if o.end > now]
        for o in self.overrides:
            if o.start - OVERRIDE_LEAD <= now < o.end:
                return Slot(
                    o.location_path,
                    o.event,
                    None,
                    "idle",
                    o.start - OVERRIDE_LEAD,
                    o.end,
                    True,
                )
        slot = self._table_slot(now)
        leads = [o.start - OVERRIDE_LEAD for o in self.overrides]
        upcoming = [t for t in leads if t > now]
        if upcoming and min(upcoming) < slot.end:
            slot = Slot(
                slot.location_path,
                slot.description,
                slot.emoji,
                slot.action,
                slot.start,
                min(upcoming),
            )
        return slot

    def _occurrences(
        self, now: datetime.datetime
    ) -> list[tuple[datetime.datetime, ScheduleEntry]]:
        found: list[tuple[datetime.datetime, ScheduleEntry]] = []
        for offset in range(-1, _LOOKAHEAD_DAYS):
            day = now.date() + datetime.timedelta(days=offset)
            midnight = datetime.datetime.combine(
                day, datetime.time(), tzinfo=now.tzinfo
            )
            for entry in self.entries:
                if entry.applies_on(day.weekday()):
                    start = midnight + datetime.timedelta(minutes=entry.minutes())
                    found.append((start, entry))
        found.sort(key=lambda item: item[0])
        return found

    def _table_slot(self, now: datetime.datetime) -> Slot:
        occurrences = self._occurrences(now)
        current = [item for item in occurrences if item[0] <= now]
        later = [item for item in occurrences if item[0] > now]
        if not current:
            raise ValueError("no schedule entry applies near the given time")
        start, entry = current[-1]
        end = later[0][0] if later else start + datetime.timedelta(days=1)
        return Slot(
            entry.location_path,
            entry.description,
            entry.emoji,
            entry.action,
            start,
            end,
        )
