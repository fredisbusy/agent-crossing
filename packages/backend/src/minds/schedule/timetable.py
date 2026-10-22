"""일정표: 시각·요일로 현재 항목을 고른다."""

import datetime
from dataclasses import dataclass

from minds.social import Slot

from .config import ScheduleEntry

_LOOKAHEAD_DAYS = 8


@dataclass
class Timetable:
    """규칙 마음의 평소 일과(`Routine`). 약속 덮어쓰기는 `minds.social.Agenda`가 한다."""

    entries: tuple[ScheduleEntry, ...]

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

    def slot_at(self, now: datetime.datetime) -> Slot:
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
