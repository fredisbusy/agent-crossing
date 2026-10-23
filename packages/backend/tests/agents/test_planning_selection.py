import datetime

from agents.planning import (
    HourlyPlanItem,
    MinutePlanItem,
    select_hourly_plan,
    select_minute_plan,
)

DAY = datetime.datetime(2023, 2, 13)


def _hour(h: int) -> HourlyPlanItem:
    return HourlyPlanItem(
        start_time=DAY.replace(hour=h),
        end_time=DAY.replace(hour=h + 1),
        location="Cafe",
        action_content=f"{h}시",
    )


def test_active_current_and_next() -> None:
    items = [_hour(11), _hour(9), _hour(10)]
    sel = select_hourly_plan(items, current_time=DAY.replace(hour=9, minute=30))
    assert sel.active == _hour(9) and sel.current == _hour(9)
    assert sel.next == _hour(10)


def test_gap_picks_the_nearest_next_as_current() -> None:
    sel = select_hourly_plan(
        [_hour(9), _hour(11)], current_time=DAY.replace(hour=10, minute=10)
    )
    assert sel.active is None and sel.current == _hour(11) and sel.next == _hour(11)


def test_nothing_left_after_the_last_item() -> None:
    sel = select_hourly_plan([_hour(9)], current_time=DAY.replace(hour=12))
    assert (sel.active, sel.current, sel.next) == (None, None, None)


def test_minute_selection_uses_half_open_windows() -> None:
    first = MinutePlanItem(
        start_time=DAY.replace(hour=9),
        end_time=DAY.replace(hour=9, minute=10),
        location="Cafe",
        action_content="a",
    )
    second = MinutePlanItem(
        start_time=DAY.replace(hour=9, minute=10),
        end_time=DAY.replace(hour=9, minute=20),
        location="Cafe",
        action_content="b",
    )
    sel = select_minute_plan(
        [first, second], current_time=DAY.replace(hour=9, minute=10)
    )
    assert sel.active == second and sel.next is None
