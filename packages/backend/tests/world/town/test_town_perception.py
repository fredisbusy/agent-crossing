import asyncio
import datetime

from town_fakes import CAFE, GARDEN, ScriptedMind, make_sim, stay
from world.contracts import ActionIntent, MindContext


def walk_to_hall(ctx: MindContext) -> ActionIntent:
    return ActionIntent(
        kind="move",
        description="홉스 카페 홀 쪽으로 이동한다",
        location_path=CAFE,
        until=ctx.now + datetime.timedelta(minutes=30),
    )


def test_sight_of_someone_moving_inside_the_place_names_it_once() -> None:
    watcher = ScriptedMind(plan=stay(minutes=1))
    walker = ScriptedMind(plan=walk_to_hall)
    sim = make_sim({"ann": (CAFE, watcher), "bob": (GARDEN, walker)})
    asyncio.run(sim.run_minutes(8))
    texts = [o.text for o in watcher.observed if o.kind == "sight"]
    assert "Bob이 홉스 카페 홀 안에서 자리를 옮긴다" in texts
    assert not any("홉스 카페 홀에서 홉스 카페 홀" in text for text in texts)
