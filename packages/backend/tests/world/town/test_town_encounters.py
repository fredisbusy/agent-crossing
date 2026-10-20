import asyncio
import datetime

from town_fakes import CAFE, GARDEN, SQUARE, ScriptedMind, make_sim, stay
from world.contracts import ActionIntent, MindContext


def minutes_since_start(ctx: MindContext) -> int:
    return int((ctx.now - datetime.datetime(2025, 2, 13, 8, 0)).total_seconds() // 60)


def shuttle(ctx: MindContext) -> ActionIntent:
    """10분 광장, 10분 카페, 50분 광장, 이후 카페."""
    m = minutes_since_start(ctx)
    where = CAFE if 10 <= m < 20 or m >= 70 else SQUARE
    return ActionIntent(
        kind="move",
        description="걸어간다",
        location_path=where,
        until=ctx.now + datetime.timedelta(minutes=1),
    )


def test_newly_near_pair_is_asked_once_and_both_converse_starts_conversation() -> None:
    ann = ScriptedMind(encounter="converse", replies=["안녕", None])
    bob = ScriptedMind(encounter="converse", replies=["반가워", None])
    sim = make_sim({"ann": (CAFE, ann), "bob": (CAFE, bob)})
    asyncio.run(sim.tick())
    assert ann.encounter_with == ["bob"] and bob.encounter_with == ["ann"]
    assert all(r.body.conversation_id for r in sim.residents)
    asyncio.run(sim.run_minutes(10))
    assert ann.encounter_with == ["bob"]
    assert all(r.body.conversation_id is None for r in sim.residents)


def test_one_side_passing_by_prevents_conversation() -> None:
    ann = ScriptedMind(encounter="converse", replies=["안녕"])
    bob = ScriptedMind(encounter="pass_by")
    sim = make_sim({"ann": (CAFE, ann), "bob": (CAFE, bob)})
    asyncio.run(sim.run_minutes(3))
    assert ann.respond_calls == 0 and bob.respond_calls == 0


def test_conversation_alternates_and_ends_on_none() -> None:
    ann = ScriptedMind(encounter="converse", replies=["하나", "셋", None])
    bob = ScriptedMind(encounter="converse", replies=["둘", None])
    sim = make_sim({"ann": (CAFE, ann), "bob": (CAFE, bob)}, seed=1)
    asyncio.run(sim.run_minutes(10))
    # 첫 화자는 시드로 정해지며, 번갈아 말하다 한쪽이 None을 내면 끝난다.
    assert ann.respond_calls + bob.respond_calls <= 5
    assert ann.respond_calls >= 1 and bob.respond_calls >= 1
    heard_by_ann = [o for o in ann.observed if o.kind == "utterance"]
    assert heard_by_ann
    assert all(o.subject_id == "bob" for o in heard_by_ann)


def test_conversation_stops_at_max_turns() -> None:
    chatter = ["말"] * 20
    ann = ScriptedMind(encounter="converse", replies=chatter)
    bob = ScriptedMind(encounter="converse", replies=chatter)
    sim = make_sim({"ann": (CAFE, ann), "bob": (CAFE, bob)}, max_turns=3)
    asyncio.run(sim.run_minutes(10))
    assert ann.respond_calls + bob.respond_calls == 3
    assert all(r.body.conversation_id is None for r in sim.residents)


def test_one_turn_per_game_minute_and_bodies_frozen_during_conversation() -> None:
    chatter = ["말"] * 20
    ann = ScriptedMind(encounter="converse", replies=chatter, plan=stay(600))
    bob = ScriptedMind(encounter="converse", replies=chatter, plan=stay(600))
    sim = make_sim({"ann": (CAFE, ann), "bob": (CAFE, bob)}, max_turns=8)
    asyncio.run(sim.run_minutes(4))
    assert ann.respond_calls + bob.respond_calls == 4
    assert sim.text_state().count('"in_conversation":true') == 2


def test_bystander_in_same_building_hears_utterance_but_other_area_does_not() -> None:
    ann = ScriptedMind(encounter="converse", replies=["비밀 이야기", None])
    bob = ScriptedMind(encounter="converse", replies=["그래", None])
    near = ScriptedMind(encounter="pass_by", plan=stay(10, where=CAFE))
    far = ScriptedMind(plan=stay(600, where=GARDEN))
    sim = make_sim(
        {
            "ann": (CAFE, ann),
            "bob": (CAFE, bob),
            "cat": (CAFE, near),
            "dan": (GARDEN, far),
        }
    )
    asyncio.run(sim.run_minutes(12))
    heard = [o for o in near.observed if o.kind == "utterance"]
    assert sorted(o.utterance.text for o in heard if o.utterance) == ["그래", "비밀 이야기"]
    assert {o.subject_id for o in heard} == {"ann", "bob"}
    assert not [o for o in far.observed if o.kind == "utterance"]


def test_pair_cooldown_blocks_reencounter_within_sixty_minutes() -> None:
    ann = ScriptedMind(plan=stay(1))
    bob = ScriptedMind(plan=shuttle)
    sim = make_sim({"ann": (CAFE, ann), "bob": (CAFE, bob)})
    asyncio.run(sim.run_minutes(60))
    assert ann.encounter_with == ["bob"]
    asyncio.run(sim.run_minutes(40))
    assert ann.encounter_with == ["bob", "bob"]


def test_busy_resident_is_not_asked_for_second_encounter() -> None:
    ann = ScriptedMind(encounter="converse", replies=["하나", "둘", "셋", None])
    bob = ScriptedMind(encounter="converse", replies=["넷", "다섯", None])
    cat = ScriptedMind(encounter="converse", replies=["여섯"])
    sim = make_sim({"ann": (CAFE, ann), "bob": (CAFE, bob), "cat": (CAFE, cat)})
    asyncio.run(sim.tick())
    assert cat.respond_calls == 0
    members = [r for r in sim.residents if r.body.conversation_id]
    assert len(members) == 2
