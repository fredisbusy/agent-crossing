import datetime

from agents.planning.models import DayPlanItem, MinutePlanItem
from agents.planning.state import current_minute_plan_context, select_day_plan, select_minute_plan


def test_select_day_plan_returns_active_current_and_next_items() -> None:
    first = DayPlanItem(
        start_time=datetime.datetime(2026, 3, 3, 9, 0, 0),
        end_time=datetime.datetime(2026, 3, 3, 11, 0, 0),
        location="Town > Home > Desk",
        action_content="Draft composition ideas.",
    )
    second = DayPlanItem(
        start_time=datetime.datetime(2026, 3, 3, 11, 0, 0),
        end_time=datetime.datetime(2026, 3, 3, 13, 0, 0),
        location="Town > Cafe > Table",
        action_content="Review notes with classmates.",
    )

    selection = select_day_plan(
        [second, first],
        current_time=datetime.datetime(2026, 3, 3, 10, 30, 0),
    )

    assert selection.active == first
    assert selection.current == first
    assert selection.next == second


def test_select_minute_plan_uses_next_item_when_between_windows() -> None:
    first = MinutePlanItem(
        start_time=datetime.datetime(2026, 3, 3, 12, 0, 0),
        end_time=datetime.datetime(2026, 3, 3, 12, 10, 0),
        location="Town > Home > Desk",
        action_content="Sketch phrase A.",
    )
    second = MinutePlanItem(
        start_time=datetime.datetime(2026, 3, 3, 12, 15, 0),
        end_time=datetime.datetime(2026, 3, 3, 12, 25, 0),
        location="Town > Home > Desk",
        action_content="Sketch phrase B.",
    )

    selection = select_minute_plan(
        [first, second],
        current_time=datetime.datetime(2026, 3, 3, 12, 12, 0),
    )

    assert selection.active is None
    assert selection.current == second
    assert selection.next == second
    assert current_minute_plan_context(selection) == ["Sketch phrase B."]
