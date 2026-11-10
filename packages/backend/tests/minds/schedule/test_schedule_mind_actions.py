import asyncio
import datetime
import random

from minds.schedule import ScheduleConfig, ScheduleEntry, build_schedule_mind
from world.contracts import BodyState, MindContext, ResidentPublicView, TilePosition

BED = "Smallville > Lin Family House > Bedroom"
CAFE = "Smallville > Hobbs Cafe > Counter"
SQUARE = "Smallville > Town Square"
MONDAY = datetime.datetime(2026, 10, 19)


def _config(talkativeness: float = 0.5) -> ScheduleConfig:
    return ScheduleConfig(
        talkativeness=talkativeness,
        entries=[
            ScheduleEntry(
                start="22:00", location_path=BED, description="잠든다", action="sleep"
            ),
            ScheduleEntry(
                start="08:00",
                location_path=CAFE,
                description="커피를 내린다",
                action="use_object",
                emoji="☕",
            ),
        ],
    )


def _ctx(now: datetime.datetime, location: str) -> MindContext:
    body = BodyState(
        resident_id="isabella",
        display_name="Isabella",
        tile=TilePosition(x=0, y=0),
        location_path=location,
    )
    return MindContext(now=now, self_state=body)


def _mind(talkativeness: float = 0.5):
    return build_schedule_mind(
        resident_id="isabella",
        display_name="Isabella",
        config=_config(talkativeness),
        rng=random.Random(1),
    )


def test_moves_when_not_at_entry_location() -> None:
    now = MONDAY.replace(hour=9)
    action = asyncio.run(_mind().next_action(_ctx(now, SQUARE)))
    assert action.kind == "move"
    assert action.location_path == CAFE
    assert action.until == MONDAY.replace(hour=22)


def test_performs_entry_action_when_in_place() -> None:
    now = MONDAY.replace(hour=9)
    action = asyncio.run(_mind().next_action(_ctx(now, CAFE)))
    assert (action.kind, action.description, action.emoji) == (
        "use_object",
        "커피를 내린다",
        "☕",
    )
    assert action.until == MONDAY.replace(hour=22)


def test_sleep_action_across_midnight() -> None:
    now = MONDAY.replace(hour=1)
    action = asyncio.run(_mind().next_action(_ctx(now, BED)))
    assert action.kind == "sleep"
    assert action.until == MONDAY.replace(hour=8)


def test_encounter_follows_talkativeness_and_is_deterministic() -> None:
    other = ResidentPublicView(
        resident_id="klaus", display_name="Klaus", location_path=SQUARE
    )
    now = MONDAY.replace(hour=12)
    ctx = _ctx(now, SQUARE)
    assert asyncio.run(_mind(1.0).on_encounter(ctx, other)) == "converse"
    assert asyncio.run(_mind(0.0).on_encounter(ctx, other)) == "pass_by"
    first = [asyncio.run(_mind(0.5).on_encounter(ctx, other)) for _ in range(3)]
    assert first == [asyncio.run(_mind(0.5).on_encounter(ctx, other)) for _ in range(3)]


def test_encounter_log_records_the_chance_decision() -> None:
    other = ResidentPublicView(
        resident_id="klaus", display_name="Klaus", location_path=SQUARE
    )
    now = MONDAY.replace(hour=12)
    mind = _mind(1.0)

    asyncio.run(mind.on_encounter(_ctx(now, SQUARE), other))

    [record] = mind.encounter_log
    assert (record.other_id, record.choice, record.basis) == ("klaus", "converse", "chance")
    assert record.reason == "수다 확률 1.00" and record.at == now
