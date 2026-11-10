import datetime
import random

from minds.schedule import ScheduleConfig, ScheduleEntry, build_schedule_mind

CAFE = "Smallville > Hobbs Cafe > Counter"
MONDAY = datetime.datetime(2026, 10, 19)


def test_plan_item_is_current_timetable_description() -> None:
    config = ScheduleConfig(
        talkativeness=0.5,
        entries=[
            ScheduleEntry(
                start="08:00",
                location_path=CAFE,
                description="커피를 내린다",
                action="use_object",
            )
        ],
    )
    mind = build_schedule_mind(
        resident_id="isabella",
        display_name="Isabella",
        config=config,
        rng=random.Random(0),
    )
    assert mind.plan_item_at(MONDAY.replace(hour=9)) == "커피를 내린다"
