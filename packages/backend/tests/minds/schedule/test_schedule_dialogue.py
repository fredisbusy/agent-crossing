import asyncio
import datetime
import random

from minds.schedule import ScheduleConfig, ScheduleEntry, build_schedule_mind
from minds.schedule.lines import all_templates
from world.contracts import (
    BodyState,
    ConversationView,
    MindContext,
    Observation,
    ResidentPublicView,
    SpeechAct,
    TilePosition,
    Utterance,
)

CAFE = "Smallville > Hobbs Cafe > Counter"
SQUARE = "Smallville > Town Square"
MONDAY = datetime.datetime(2026, 10, 19, 12, 0)
PARTY_START = datetime.datetime(2026, 10, 19, 17, 0)
META_WORDS = ("NPC", "npc", "agent", "Agent", "에이전트", "규칙", "AI", "rule", "봇")


def _mind(
    *,
    seed: int = 1,
    min_friendship: int = 0,
    share: float = 1.0,
    max_turns: int = 4,
    talkativeness: float = 0.0,
):
    config = ScheduleConfig(
        entries=[
            ScheduleEntry(start="08:00", location_path=CAFE, description="일한다")
        ],
        min_friendship_to_accept_invite=min_friendship,
        share_probability=share,
        max_turns=max_turns,
        talkativeness=talkativeness,
    )
    return build_schedule_mind(
        resident_id="isabella",
        display_name="Isabella",
        config=config,
        rng=random.Random(seed),
    )


def _ctx(now: datetime.datetime = MONDAY) -> MindContext:
    body = BodyState(
        resident_id="isabella",
        display_name="Isabella",
        tile=TilePosition(x=0, y=0),
        location_path=CAFE,
    )
    return MindContext(now=now, self_state=body)


def _said(text: str, *acts: SpeechAct, speaker: str = "klaus") -> Utterance:
    return Utterance(
        speaker_id=speaker,
        listener_ids=("isabella",) if speaker != "isabella" else ("klaus",),
        text=text,
        acts=acts,
        spoken_at=MONDAY,
    )


def _conv(*history: Utterance, cid: str = "c1") -> ConversationView:
    return ConversationView(
        conversation_id=cid, participant_ids=("isabella", "klaus"), history=history
    )


def _respond(
    mind, *history: Utterance, cid: str = "c1", now: datetime.datetime = MONDAY
):
    return asyncio.run(mind.respond(_ctx(now), _conv(*history, cid=cid)))


def _invite() -> SpeechAct:
    return SpeechAct(
        kind="invite",
        event="밸런타인 파티",
        start_time=PARTY_START,
        location_path=SQUARE,
    )


def test_opens_with_greet_when_history_empty() -> None:
    reply = _respond(_mind())
    assert reply is not None and [a.kind for a in reply.acts] == ["greet"]
    assert reply.listener_ids == ("klaus",)


def test_greet_is_answered_with_greet() -> None:
    reply = _respond(_mind(), _said("안녕", SpeechAct(kind="greet")))
    assert reply is not None and reply.acts[0].kind == "greet"


def test_invite_accept_adds_override_and_moves_there() -> None:
    mind = _mind()
    reply = _respond(mind, _said("초대", _invite()))
    assert reply is not None and reply.acts[0].kind == "accept"
    assert reply.acts[0].start_time == PARTY_START
    assert "오후 5시" in reply.text and "Town Square" in reply.text
    ctx = _ctx(PARTY_START - datetime.timedelta(minutes=20))
    action = asyncio.run(mind.next_action(ctx))
    assert action.kind == "move" and action.location_path == SQUARE
    assert mind.friendship.score("klaus") == 3  # 대화 +2, 수락 +1


def test_invite_declined_on_conflict_or_low_friendship() -> None:
    mind = _mind()
    mind.timetable.add_override("다른 약속", PARTY_START, CAFE)
    reply = _respond(mind, _said("초대", _invite()))
    assert reply is not None and reply.acts[0].kind == "decline"
    picky = _mind(min_friendship=10)
    reply = _respond(picky, _said("초대", _invite()))
    assert reply is not None and reply.acts[0].kind == "decline"
    assert picky.timetable.overrides == []


def test_share_fact_is_stored_then_answered_with_smalltalk() -> None:
    mind = _mind()
    fact = SpeechAct(kind="share_fact", topic="파티", fact="토요일에 열린대요")
    reply = _respond(mind, _said("들었어?", fact))
    assert reply is not None and reply.acts[0].kind == "smalltalk"
    stored = mind.facts.get("파티")
    assert stored is not None and stored.source_resident_id == "klaus"
    newer = SpeechAct(kind="share_fact", topic="파티", fact="일요일로 바뀌었대요")
    _respond(mind, _said("바뀜", newer), cid="c2")
    updated = mind.facts.get("파티")
    assert updated is not None and updated.fact == "일요일로 바뀌었대요"


def test_ask_answers_known_fact_else_smalltalk() -> None:
    mind = _mind()
    ask = SpeechAct(kind="ask", topic="파티")
    unknown = _respond(mind, _said("파티?", ask))
    assert unknown is not None and unknown.acts[0].kind == "smalltalk"
    assert "파티" in unknown.text
    mind.facts.learn("파티", "토요일", "maria", MONDAY)
    known = _respond(mind, _said("파티?", ask), cid="c2")
    assert known is not None and known.acts[0].kind == "share_fact"
    assert known.acts[0].fact == "토요일" and "토요일" in known.text


def test_farewell_is_answered_then_conversation_ends() -> None:
    mind = _mind()
    bye = _said("안녕히", SpeechAct(kind="farewell"))
    reply = _respond(mind, bye)
    assert reply is not None and reply.acts[0].kind == "farewell"
    assert _respond(mind, bye, reply, bye) is None


def test_max_turns_forces_farewell() -> None:
    mind = _mind(max_turns=2)
    first = _respond(mind)
    assert first is not None
    talk = _said("그렇죠", SpeechAct(kind="smalltalk"))
    second = _respond(mind, first, talk)
    assert second is not None and second.acts[0].kind == "farewell"


def test_unshared_fact_is_shared_once_per_listener_deterministically() -> None:
    def run(seed: int) -> list[str]:
        mind = _mind(seed=seed)
        mind.facts.learn("파티", "토요일", "maria", MONDAY)
        talk = _said("그렇죠", SpeechAct(kind="smalltalk"))
        kinds = []
        for i in range(3):
            reply = _respond(mind, talk, cid=f"c{i}")
            assert reply is not None
            kinds.append(reply.acts[0].kind)
        return kinds

    assert run(7) == run(7)
    assert run(7) == ["share_fact", "smalltalk", "smalltalk"]


def test_encounter_prefers_conversation_when_fact_pending_and_respects_cooldown() -> (
    None
):
    mind = _mind(talkativeness=0.0)
    other = ResidentPublicView(
        resident_id="klaus", display_name="Klaus", location_path=CAFE
    )
    assert asyncio.run(mind.on_encounter(_ctx(), other)) == "pass_by"
    mind.facts.learn("파티", "토요일", "maria", MONDAY)
    assert asyncio.run(mind.on_encounter(_ctx(), other)) == "converse"
    _respond(mind, cid="c1")  # 대화 기록 -> 쿨다운 시작
    soon = MONDAY + datetime.timedelta(hours=2, minutes=59)
    later = MONDAY + datetime.timedelta(hours=3)
    assert asyncio.run(mind.on_encounter(_ctx(soon), other)) == "pass_by"
    assert asyncio.run(mind.on_encounter(_ctx(later), other)) == "converse"


def test_observe_stores_overheard_share_fact() -> None:
    mind = _mind()
    utterance = Utterance(
        speaker_id="klaus",
        listener_ids=("maria",),
        text="들었어?",
        acts=(SpeechAct(kind="share_fact", topic="시장", fact="내일 쉰대요"),),
        spoken_at=MONDAY,
    )
    obs = Observation(
        kind="utterance",
        text="Klaus가 말했다",
        observed_at=MONDAY,
        location_path=CAFE,
        subject_id="klaus",
        utterance=utterance,
    )
    asyncio.run(mind.observe((obs,)))
    stored = mind.facts.get("시장")
    assert (
        stored is not None
        and stored.fact == "내일 쉰대요"
        and stored.learned_at == MONDAY
    )


def test_templates_and_replies_have_no_meta_words() -> None:
    for text in all_templates():
        assert not any(word in text for word in META_WORDS), text
    mind = _mind()
    reply = _respond(mind, _said("초대", _invite()))
    assert reply is not None
    assert not any(word in reply.text for word in META_WORDS)
