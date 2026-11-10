"""delta 순수 함수와 스냅샷의 `current_plan_item`."""

import datetime

from world.contracts import ResidentSnapshot, TilePosition, WorldSnapshot
from world.town import diff_snapshots

NOW = datetime.datetime(2026, 11, 10, 8, 0)


def _resident(rid: str, x: int = 0, plan: str | None = None) -> ResidentSnapshot:
    return ResidentSnapshot(
        resident_id=rid,
        display_name=rid,
        tile=TilePosition(x=x, y=0),
        location_path="Town",
        current_plan_item=plan,
    )


def _snap(tick: int, *residents: ResidentSnapshot) -> WorldSnapshot:
    return WorldSnapshot(
        tick=tick, sim_time=NOW + datetime.timedelta(minutes=tick), residents=residents
    )


def test_no_change_gives_empty_residents_with_new_tick() -> None:
    before = _snap(1, _resident("a"), _resident("b"))
    after = _snap(2, _resident("a"), _resident("b"))
    delta = diff_snapshots(before, after)
    assert delta.residents == ()
    assert delta.tick == 2 and delta.sim_time == after.sim_time


def test_only_changed_residents_are_included_whole() -> None:
    before = _snap(1, _resident("a"), _resident("b"))
    after = _snap(2, _resident("a"), _resident("b", x=3, plan="장보기"))
    delta = diff_snapshots(before, after)
    assert delta.residents == (_resident("b", x=3, plan="장보기"),)


def test_plan_item_change_alone_counts() -> None:
    delta = diff_snapshots(_snap(1, _resident("a")), _snap(2, _resident("a", plan="산책")))
    assert [r.resident_id for r in delta.residents] == ["a"]

