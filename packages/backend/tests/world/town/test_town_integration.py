"""실제 맵 + 실제 주민 데이터 + ScheduleMind로 마을을 돌리는 통합 테스트."""

import asyncio
import datetime
import random

from world.contracts import (
    ActionIntent,
    ConversationView,
    MindContext,
    Observation,
    ResidentPublicView,
    SpeechAct,
    Utterance,
)
from world.residents import (
    Resident,
    ResidentConfig,
    ResidentMindFactory,
    apply_mind_selection,
    load_resident_configs,
)
from world.space import load_town_space
from world.town import SimClock, TownSimulation

START = datetime.datetime(2026, 2, 13, 8, 30)
PARTY_AT = datetime.datetime(2026, 2, 13, 10, 0)
CAFE_COUNTER = "Smallville > Hobbs Cafe > Counter"
SQUARE = "Smallville > Town Square"


class Inviter:
    """카페에 머물며 만난 사람을 10시 광장 파티에 초대하고, 수락을 들으면 대화를 끝낸다."""

    kind = "llm"

    async def next_action(self, ctx: MindContext) -> ActionIntent:
        return ActionIntent(
            kind="idle",
            description="커피를 마신다",
            location_path=CAFE_COUNTER,
            until=ctx.now + datetime.timedelta(hours=8),
        )

    async def on_encounter(self, ctx: MindContext, other: ResidentPublicView) -> str:
        return "converse"

    async def respond(
        self, ctx: MindContext, conversation: ConversationView
    ) -> Utterance | None:
        acts = [act.kind for u in conversation.history for act in u.acts]
        if "accept" in acts or "decline" in acts:
            return None
        me = ctx.self_state.resident_id
        return Utterance(
            speaker_id=me,
            listener_ids=tuple(p for p in conversation.participant_ids if p != me),
            text="10시에 광장에서 파티 해요. 올래요?",
            acts=(
                SpeechAct(
                    kind="invite",
                    event="파티",
                    start_time=PARTY_AT,
                    location_path=SQUARE,
                ),
            ),
            spoken_at=ctx.now,
        )

    async def observe(self, observations: tuple[Observation, ...]) -> None:
        return None


class InviterAwareFactory:
    def __init__(self) -> None:
        self._schedule = ResidentMindFactory(start_time=START, seed=0)

    def build(self, config: ResidentConfig):  # noqa: ANN201 - Mind 프로토콜
        if config.resident_id == "guest":
            return Inviter()
        return self._schedule.build(config)


def isabella_with_guest() -> tuple[TownSimulation, Resident]:
    space = load_town_space()
    isabella = next(
        c for c in load_resident_configs() if c.resident_id == "isabella_rodriguez"
    ).model_copy(update={"mind": "schedule"})
    guest = isabella.model_copy(
        update={"resident_id": "guest", "display_name": "Guest", "mind": "llm"}
    )
    factory = InviterAwareFactory()
    residents = [Resident(isabella, space, factory), Resident(guest, space, factory)]
    sim = TownSimulation(
        space=space,
        residents=residents,
        clock=SimClock(START),
        rng=random.Random(0),
    )
    return sim, residents[0]


def test_accepted_invite_takes_resident_to_the_party() -> None:
    sim, isabella = isabella_with_guest()
    asyncio.run(sim.run_minutes(95))
    assert isabella.body.state.location_path.startswith(SQUARE)


def test_whole_town_of_schedule_minds_runs_a_day_deterministically() -> None:
    def run() -> list[str]:
        space = load_town_space()
        configs = apply_mind_selection(load_resident_configs(), agent_count=0)
        factory = ResidentMindFactory(start_time=datetime.datetime(2026, 2, 13, 6, 0), seed=3)
        residents = [Resident(c, space, factory) for c in configs]
        sim = TownSimulation(
            space=space,
            residents=residents,
            clock=SimClock(datetime.datetime(2026, 2, 13, 6, 0)),
            rng=random.Random(3),
        )
        states: list[str] = []
        for _ in range(18):
            asyncio.run(sim.run_minutes(60))
            states.append(sim.text_state())
        calls_per_resident_day = sim.mind_calls["schedule"] / len(residents)
        assert calls_per_resident_day < 80
        return states

    first = run()
    assert first == run()
    assert any("Hobbs Cafe" in state for state in first)
