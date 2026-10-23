"""하루 계획 → 시간 → 분 단위 just-in-time 분해 (SPEC §7, §12)."""

import asyncio
import datetime

from agents.planning.models import DayPlanItem
from llm_fakes import DAY, HOME, PARK, ScriptedClient, ctx, make_mind
from minds.llm import LLMMind
from minds.llm.planning import (
    HOURLY_CALLS_PER_DAY_ITEM,
    MAX_MINUTE_CALLS_PER_HOURLY_ITEM,
    MINUTE_CALLS_PER_HOURLY_ITEM,
)
from minds.social import SocialSeed
from plan_fakes import LayeredPlanner
from world.contracts import ActionIntent, SocialEvent

BUILDING = "Smallville > Johnson Park"


def at(hour: int, minute: int = 0) -> datetime.datetime:
    return DAY.replace(hour=hour, minute=minute)


def _mind(planner: LayeredPlanner) -> LLMMind:
    mind, _ = make_mind(ScriptedClient(lambda _: {}), planner=planner)
    return mind


def _act(mind: LLMMind, now: datetime.datetime, where: str = PARK) -> ActionIntent:
    return asyncio.run(mind.next_action(ctx("isabella", now, where=where)))


def test_minute_action_ends_at_the_minute_item_end() -> None:
    planner = LayeredPlanner()
    action = _act(_mind(planner), at(9, 20))
    assert action.description == "09:20 걷는다"
    assert action.until == at(9, 35)
    assert action.kind == "idle" and action.location_path == PARK
    [(called_at, block)] = planner.minute_calls
    assert called_at == at(9, 20) and block.start_time == at(9)


def test_cached_plans_are_not_regenerated() -> None:
    planner = LayeredPlanner()
    mind = _mind(planner)
    for now in (at(9, 20), at(9, 35), at(9, 50)):
        _act(mind, now)
    assert len(planner.hourly_calls) == 1
    assert len(planner.minute_calls) == 1
    _act(mind, at(10, 5))
    assert len(planner.hourly_calls) == 1
    assert len(planner.minute_calls) == 2
    assert planner.minute_calls[1][1].start_time == at(10)


def test_minute_plan_is_regenerated_after_its_range_runs_out() -> None:
    planner = LayeredPlanner(horizon_minutes=30)
    mind = _mind(planner)
    _act(mind, at(9, 5))
    again = _act(mind, at(9, 40))
    assert [c for c, _ in planner.minute_calls] == [at(9, 5), at(9, 40)]
    assert again.description == "09:40 걷는다" and again.until == at(9, 55)
    assert len(planner.hourly_calls) == 1


def test_commitment_and_rest_slots_are_not_decomposed() -> None:
    planner = LayeredPlanner()
    mind = _mind(planner)
    party = SocialEvent(
        name="파티", start_time=at(17), end_time=at(19), location_path=HOME
    )
    mind.social.apply_seed(SocialSeed(hosting=(party,)), at(8))
    assert "준비" in _act(mind, at(16, 10), HOME).description
    assert _act(mind, at(14), HOME).description == "집에서 쉰다"
    assert _act(mind, at(3), HOME).kind == "sleep"
    assert planner.hourly_calls == [] and planner.minute_calls == []


def test_hourly_failure_falls_back_to_the_day_slot_without_retry_storm() -> None:
    planner = LayeredPlanner(empty_hourly=True)
    mind = _mind(planner)
    for now in (at(9, 20), at(9, 40), at(10, 30)):
        action = _act(mind, now)
        assert action.description == "공원을 산책한다" and action.until == at(12)
    assert len(planner.hourly_calls) == 1 and planner.minute_calls == []


def test_minute_failure_falls_back_once_per_hourly_item() -> None:
    planner = LayeredPlanner(fail_minutes=True)
    mind = _mind(planner)
    for now in (at(9, 10), at(9, 20), at(9, 50), at(10, 10), at(10, 20)):
        action = _act(mind, now)
        assert action.description == "공원을 산책한다" and action.until == at(12)
    assert len(planner.hourly_calls) == 1
    assert len(planner.minute_calls) == 2


def test_other_building_location_is_ignored() -> None:
    action = _act(_mind(LayeredPlanner(minute_location="Town Square")), at(9, 20))
    assert action.description == "09:20 걷는다" and action.location_path == PARK


def test_same_building_location_is_used() -> None:
    mind = _mind(LayeredPlanner(minute_location="Johnson Park"))
    action = _act(mind, at(9, 20), where=PARK)
    assert action.description == "09:20 걷는다"
    assert action.location_path == BUILDING


def test_minute_end_never_passes_the_day_slot_end() -> None:
    planner = LayeredPlanner(horizon_minutes=90)
    action = _act(_mind(planner), at(11, 50))
    assert action.until == at(12)


def test_next_hourly_item_is_used_when_now_falls_in_a_gap() -> None:
    class GapPlanner(LayeredPlanner):
        def generate_hourly_plan(self, **kwargs):  # type: ignore[no-untyped-def]
            items = super().generate_hourly_plan(**kwargs)
            return [i for i in items if i.start_time.hour != 9]

    planner = GapPlanner()
    action = _act(_mind(planner), at(9, 20))
    assert action.description == "공원을 산책한다" and action.until == at(10)
    assert planner.minute_calls == []


def test_call_counts_for_one_day_item_stay_within_the_cost_cap() -> None:
    planner = LayeredPlanner(horizon_minutes=45)
    mind = _mind(planner)
    now = at(9)
    while now < at(12):
        now = _act(mind, now).until
    hourly_blocks = 3
    assert len(planner.hourly_calls) == HOURLY_CALLS_PER_DAY_ITEM
    assert len(planner.minute_calls) <= hourly_blocks * MINUTE_CALLS_PER_HOURLY_ITEM
    assert MINUTE_CALLS_PER_HOURLY_ITEM <= MAX_MINUTE_CALLS_PER_HOURLY_ITEM


def test_minute_calls_per_hourly_item_are_capped() -> None:
    planner = LayeredPlanner(horizon_minutes=5)
    mind = _mind(planner)
    now = at(9)
    while now < at(10):
        now = _act(mind, now).until
    calls = [b.start_time for _, b in planner.minute_calls]
    assert len(calls) == MAX_MINUTE_CALLS_PER_HOURLY_ITEM
    assert set(calls) == {at(9)}


def test_routine_replace_from_keeps_past_and_swaps_future() -> None:
    mind = _mind(LayeredPlanner())
    _act(mind, at(9, 20))
    new = DayPlanItem(
        start_time=at(9, 40),
        end_time=at(11),
        location="Johnson Park Garden",
        action_content="벤치에서 책을 읽는다",
    )
    slots = mind.routine.replace_from(at(9, 30), [new])
    assert [(s.start, s.end, s.description) for s in slots] == [
        (at(9), at(9, 30), "공원을 산책한다"),
        (at(9, 40), at(11), "벤치에서 책을 읽는다"),
    ]
    assert mind.routine.item_for(slots[1]) == new
    assert mind.routine.slot_at(at(9, 35)).description == "집에서 쉰다"


def test_invalidate_drops_decompositions_after_the_replan() -> None:
    planner = LayeredPlanner()
    mind = _mind(planner)
    _act(mind, at(9, 20))
    mind._decomposer.invalidate(at(9, 30))  # noqa: SLF001
    _act(mind, at(9, 40))
    assert len(planner.hourly_calls) == 2 and len(planner.minute_calls) == 2
