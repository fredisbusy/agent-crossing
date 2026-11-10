import asyncio
import datetime
import json
import re

from town_fakes import CAFE, GARDEN, ISLAND, SQUARE, START, ScriptedMind, make_sim, stay
from world.contracts import ActionIntent, MindContext

META_WORDS = re.compile(r"NPC|에이전트|AI|규칙|agent|rule", re.IGNORECASE)


def move_to(where: str, minutes: int = 1):
    def plan(ctx: MindContext) -> ActionIntent:
        return ActionIntent(
            kind="move",
            description="걸어간다",
            location_path=where,
            until=ctx.now + datetime.timedelta(minutes=minutes),
        )

    return plan


def test_clock_advances_one_minute_per_tick() -> None:
    sim = make_sim({"ann": (CAFE, ScriptedMind())})
    asyncio.run(sim.run_minutes(5))
    assert sim.tick_count == 5
    assert sim.clock.now == START + datetime.timedelta(minutes=5)


def test_mind_not_called_while_action_in_progress() -> None:
    mind = ScriptedMind(plan=stay(minutes=30))
    sim = make_sim({"ann": (CAFE, mind)})
    asyncio.run(sim.run_minutes(30))
    assert mind.next_action_calls == 1
    assert sim.mind_calls["schedule"] == 1
    asyncio.run(sim.run_minutes(1))
    assert mind.next_action_calls == 2


def test_mind_call_counts_split_by_kind() -> None:
    llm = ScriptedMind("llm", plan=stay(minutes=60))
    npc = ScriptedMind("schedule", plan=stay(minutes=60, where=SQUARE))
    sim = make_sim({"ann": (CAFE, llm), "bob": (SQUARE, npc)})
    asyncio.run(sim.run_minutes(10))
    assert sim.mind_calls["llm"] == 1
    assert sim.mind_calls["schedule"] == 1


def test_sight_does_not_wake_running_action_but_arrives_at_next_wake() -> None:
    watcher = ScriptedMind(plan=stay(minutes=600, where=SQUARE))
    walker = ScriptedMind(plan=move_to(SQUARE, minutes=600))
    sim = make_sim({"ann": (SQUARE, watcher), "bob": (CAFE, walker)})
    asyncio.run(sim.run_minutes(30))
    assert watcher.next_action_calls == 1
    assert watcher.observed == []

    patient = ScriptedMind(plan=stay(minutes=20, where=SQUARE))
    walker = ScriptedMind(plan=move_to(SQUARE, minutes=600))
    sim = make_sim({"ann": (SQUARE, patient), "bob": (CAFE, walker)})
    asyncio.run(sim.run_minutes(30))
    assert patient.next_action_calls == 2
    assert any("Bob" in o.text for o in patient.observed)


def test_sight_text_format_and_no_meta_words() -> None:
    watcher = ScriptedMind(plan=stay(minutes=2))
    reader = ScriptedMind(plan=stay(minutes=600, description="책을 읽는다"))
    sim = make_sim({"ann": (CAFE, watcher), "bob": (CAFE, reader)})
    asyncio.run(sim.run_minutes(4))
    sights = [o for o in watcher.observed if o.kind == "sight"]
    assert sights
    assert any(o.text == "Bob이 홉스 카페 홀에서 책을 읽는다" for o in sights)
    for observation in watcher.observed + reader.observed:
        assert not META_WORDS.search(observation.text)


def test_far_residents_do_not_perceive_each_other() -> None:
    a = ScriptedMind(plan=stay(minutes=600))
    b = ScriptedMind(plan=stay(minutes=600, where=SQUARE))
    sim = make_sim({"ann": (CAFE, a), "bob": (SQUARE, b)})
    asyncio.run(sim.run_minutes(5))
    assert a.observed == [] and b.observed == []


def test_unreachable_destination_leaves_resident_idle_with_observation() -> None:
    mind = ScriptedMind(plan=move_to(ISLAND, minutes=5))
    sim = make_sim({"ann": (CAFE, mind)})
    asyncio.run(sim.run_minutes(2))
    assert any("갈 수 없었다" in o.text for o in mind.observed)
    state = sim.snapshot().residents[0]
    assert state.location_path == CAFE


def test_snapshot_hides_nothing_needed_and_text_state_is_short_json() -> None:
    sim = make_sim({"ann": (CAFE, ScriptedMind("llm")), "bob": (GARDEN, ScriptedMind())})
    asyncio.run(sim.run_minutes(2))
    snapshot = sim.snapshot()
    assert snapshot.tick == 2
    assert [r.mind_kind for r in snapshot.residents] == ["llm", "schedule"]
    data = json.loads(sim.text_state())
    assert data["tick"] == 2
    assert data["residents"][0] == {
        "id": "ann",
        "location": CAFE,
        "action": "책을 읽는다",
        "in_conversation": False,
    }


def _run_states(seed: int) -> list[str]:
    ann = ScriptedMind("llm", encounter="converse", replies=["안녕", "잘 지내?", None])
    bob = ScriptedMind(plan=move_to(SQUARE, minutes=3), encounter="converse", replies=["안녕", None])
    cat = ScriptedMind(plan=move_to(GARDEN, minutes=2), encounter="converse")
    sim = make_sim(
        {"ann": (CAFE, ann), "bob": (CAFE, bob), "cat": (SQUARE, cat)}, seed=seed
    )
    states: list[str] = []

    async def go() -> None:
        for _ in range(60):
            await sim.tick()
            states.append(sim.text_state())

    asyncio.run(go())
    return states


def test_same_seed_gives_identical_text_state_sequence() -> None:
    first = _run_states(seed=7)
    second = _run_states(seed=7)
    assert first == second
    assert len(set(first)) > 5
