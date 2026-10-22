import asyncio
import datetime

from town_fakes import CAFE, START, ScriptedMind, make_sim
from world.contracts import ActionIntent, Holiday, MindContext
from world.town import TownCalendar

SEEN: list[tuple[datetime.datetime, tuple[Holiday, ...]]] = []


def hourly(ctx: MindContext) -> ActionIntent:
    SEEN.append((ctx.now, ctx.holidays))
    return ActionIntent(
        kind="idle",
        description="머문다",
        location_path=CAFE,
        until=ctx.now + datetime.timedelta(hours=1),
    )


def test_calendar_knows_valentines_day_only_on_feb_14() -> None:
    calendar = TownCalendar()
    [valentine] = calendar.holidays_on(datetime.date(2025, 2, 14))
    assert valentine.name == "밸런타인데이" and valentine.gift_item == "초콜릿"
    assert calendar.holidays_on(datetime.date(2025, 2, 13)) == ()


def test_holiday_is_announced_once_to_every_mind_and_in_context() -> None:
    SEEN.clear()
    schedule, llm = (
        ScriptedMind("schedule", plan=hourly),
        ScriptedMind("llm", plan=hourly),
    )
    sim = make_sim({"a": (CAFE, schedule), "b": (CAFE, llm)})
    until_next_day = int(
        (datetime.datetime(2025, 2, 14, 2, 0) - START).total_seconds() // 60
    )
    asyncio.run(sim.run_minutes(until_next_day))
    for mind in (schedule, llm):
        events = [o for o in mind.observed if o.kind == "event"]
        assert [o.text for o in events] == [
            "오늘은 밸런타인데이다. 좋아하는 사람이나 고마운 이웃에게 초콜릿을 건네며 마음을 전한다."
        ]
    assert all(not holidays for now, holidays in SEEN if now.day == 13)
    assert any(
        holidays and holidays[0].name == "밸런타인데이" for now, holidays in SEEN
    )
