import datetime

from minds.schedule.config import ScheduleEntry
from minds.schedule.timetable import Timetable

MONDAY = datetime.datetime(2026, 10, 19)
SUNDAY = datetime.datetime(2026, 10, 25)
HOME = "Smallville > Lin Family House > Kitchen"
BED = "Smallville > Lin Family House > Bedroom"
CAFE = "Smallville > Hobbs Cafe > Counter"
PARK = "Smallville > Johnson Park > Garden"
SQUARE = "Smallville > Town Square"


def _table() -> Timetable:
    return Timetable(
        entries=(
            ScheduleEntry(
                start="22:00", location_path=BED, description="잠든다", action="sleep"
            ),
            ScheduleEntry(start="07:00", location_path=HOME, description="아침"),
            ScheduleEntry(
                start="09:00",
                location_path=CAFE,
                description="일한다",
                weekdays=[0, 1, 2, 3, 4],
            ),
            ScheduleEntry(
                start="09:00", location_path=PARK, description="쉰다", weekdays=[5, 6]
            ),
        )
    )


def at(base: datetime.datetime, hour: int, minute: int = 0) -> datetime.datetime:
    return base.replace(hour=hour, minute=minute)


def test_fixture_dates_are_expected_weekdays() -> None:
    assert MONDAY.weekday() == 0
    assert SUNDAY.weekday() == 6


def test_selects_entry_by_time_and_weekday() -> None:
    table = _table()
    assert table.slot_at(at(MONDAY, 10)).location_path == CAFE
    assert table.slot_at(at(SUNDAY, 10)).location_path == PARK
    slot = table.slot_at(at(MONDAY, 7, 30))
    assert slot.location_path == HOME
    assert slot.end == at(MONDAY, 9)


def test_midnight_wraps_previous_day_entry() -> None:
    table = _table()
    slot = table.slot_at(at(MONDAY, 1))
    assert slot.location_path == BED and slot.action == "sleep"
    assert slot.end == at(MONDAY, 7)
    late = table.slot_at(at(MONDAY, 23))
    assert late.end == at(MONDAY, 7) + datetime.timedelta(days=1)


def test_weekday_boundary_uses_next_days_entry_for_end() -> None:
    table = _table()
    friday_evening = datetime.datetime(2026, 10, 23, 20, 0)
    slot = table.slot_at(friday_evening)
    assert slot.location_path == CAFE
    assert slot.end == friday_evening.replace(hour=22)
