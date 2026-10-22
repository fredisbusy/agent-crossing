"""주민 간 동시 실행과 겹치는 조우 쌍 처리 (결과·순서는 순차 실행과 같아야 한다)."""

import asyncio
from collections.abc import Sequence

from town_fakes import CAFE, SQUARE, ScriptedMind, make_sim
from world.contracts import (
    ActionIntent,
    ConversationView,
    EncounterChoice,
    MindContext,
    Observation,
    ResidentPublicView,
    Utterance,
)

Log = list[tuple[str, str]]


class TracedMind(ScriptedMind):
    """await 중에 양보하며 시작/끝을 공용 로그에 남기는 가짜 마음."""

    def __init__(
        self,
        name: str,
        log: Log,
        *,
        encounter: EncounterChoice = "pass_by",
        replies: Sequence[str | None] = (),
    ) -> None:
        super().__init__(encounter=encounter, replies=replies)
        self.name = name
        self.log = log

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        self.log.append(("next_action:start", self.name))
        await asyncio.sleep(0)
        intent = await super().next_action(ctx)
        self.log.append(("next_action:end", self.name))
        return intent

    async def on_encounter(
        self, ctx: MindContext, other: ResidentPublicView
    ) -> EncounterChoice:
        self.log.append(("on_encounter:start", self.name))
        await asyncio.sleep(0)
        choice = await super().on_encounter(ctx, other)
        self.log.append(("on_encounter:end", self.name))
        return choice

    async def respond(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        self.log.append(("respond:start", self.name))
        await asyncio.sleep(0)
        utterance = await super().respond(ctx, conversation)
        self.log.append(("respond:end", self.name))
        return utterance

    async def observe(self, observations: tuple[Observation, ...]) -> None:
        self.log.append(("observe:start", self.name))
        await asyncio.sleep(0)
        await super().observe(observations)
        self.log.append(("observe:end", self.name))


def starts_before_first_end(log: Log, phase: str) -> set[str]:
    names: set[str] = set()
    for event, name in log:
        if event == f"{phase}:end":
            break
        if event == f"{phase}:start":
            names.add(name)
    return names


def test_wake_and_respond_and_encounters_run_residents_concurrently() -> None:
    log: Log = []
    minds = {
        n: TracedMind(n, log, encounter="converse", replies=["안녕", None])
        for n in ("ann", "bob", "cat", "dan")
    }
    sim = make_sim(
        {
            "ann": (CAFE, minds["ann"]),
            "bob": (CAFE, minds["bob"]),
            "cat": (SQUARE, minds["cat"]),
            "dan": (SQUARE, minds["dan"]),
        }
    )
    asyncio.run(sim.tick())
    everyone = {"ann", "bob", "cat", "dan"}
    assert starts_before_first_end(log, "next_action") == everyone
    # 떨어진 두 쌍은 같은 묶음에서 네 마음이 동시에 판정된다.
    assert starts_before_first_end(log, "on_encounter") == everyone
    # 두 대화의 화자 둘이 동시에 응답을 시작한다.
    assert len(starts_before_first_end(log, "respond")) == 2
    assert sum(sim.mind_calls.values()) == 4 + 4 + 2


def test_overlapping_pairs_skip_resident_already_in_conversation() -> None:
    log: Log = []
    minds = {
        n: TracedMind(n, log, encounter="converse", replies=["안녕", None])
        for n in ("ann", "bob", "cat")
    }
    sim = make_sim({n: (CAFE, m) for n, m in minds.items()}, seed=3)
    asyncio.run(sim.tick())
    # (ann,bob)이 먼저 대화를 시작하므로 (ann,cat)·(bob,cat)은 can_talk에서 걸러진다.
    assert minds["cat"].encounter_with == []
    assert minds["ann"].encounter_with == ["bob"]
    assert minds["bob"].encounter_with == ["ann"]
    assert {r.resident_id for r in sim.residents if r.body.conversation_id} == {"ann", "bob"}


def test_overlapping_pairs_are_serialized_when_earlier_pair_passes_by() -> None:
    log: Log = []
    minds = {n: TracedMind(n, log) for n in ("ann", "bob", "cat")}
    sim = make_sim({n: (CAFE, m) for n, m in minds.items()})
    asyncio.run(sim.tick())
    # 세 쌍이 모두 판정된다: 순서 (ann,bob) → (ann,cat) → (bob,cat), 겹치는 쌍끼리는 순차.
    assert minds["ann"].encounter_with == ["bob", "cat"]
    assert minds["bob"].encounter_with == ["ann", "cat"]
    assert minds["cat"].encounter_with == ["ann", "bob"]
    encounter_log = [e for e in log if e[0].startswith("on_encounter")]
    assert encounter_log[:4] == [
        ("on_encounter:start", "ann"),
        ("on_encounter:start", "bob"),
        ("on_encounter:end", "ann"),
        ("on_encounter:end", "bob"),
    ]


def test_same_seed_gives_same_outcome() -> None:
    def run() -> list[str]:
        minds = {
            n: ScriptedMind(encounter="converse", replies=["안녕", None])
            for n in ("ann", "bob", "cat", "dan")
        }
        sim = make_sim(
            {
                "ann": (CAFE, minds["ann"]),
                "bob": (CAFE, minds["bob"]),
                "cat": (SQUARE, minds["cat"]),
                "dan": (SQUARE, minds["dan"]),
            },
            seed=7,
        )
        asyncio.run(sim.run_minutes(3))
        return [sim.text_state()] + [f"{n}:{m.respond_calls}" for n, m in minds.items()]

    assert run() == run()
