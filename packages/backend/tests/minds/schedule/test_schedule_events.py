"""규칙 마음의 행사·기념일 행동: 초대하기, 소문 듣고 가기, 선물, 기념일 인사."""

import asyncio
import datetime
import random

from minds.schedule import (
    ScheduleConfig,
    ScheduleEntry,
    ScheduleMind,
    build_schedule_mind,
)
from minds.social import SocialSeed, event_act
from world.contracts import (
    BodyState,
    ConversationView,
    Holiday,
    MindContext,
    ResidentPublicView,
    SocialEvent,
    SpeechAct,
    TilePosition,
    Utterance,
)

NOW = datetime.datetime(2023, 2, 13, 12, 0)
CAFE = "Smallville > Hobbs Cafe > Seating"
PARTY = SocialEvent(
    name="밸런타인데이 파티",
    start_time=datetime.datetime(2023, 2, 14, 17, 0),
    end_time=datetime.datetime(2023, 2, 14, 19, 0),
    location_path=CAFE,
    host_id="isabella",
)
VALENTINE = Holiday(
    name="밸런타인데이", greetings=("해피 밸런타인데이!",), gift_item="초콜릿"
)


def _mind(resident_id: str, *, interest: float = 1.0) -> ScheduleMind:
    config = ScheduleConfig(
        entries=[
            ScheduleEntry(start="08:00", location_path=CAFE, description="일한다")
        ],
        event_interest=interest,
        share_probability=1.0,
        talkativeness=0.0,
        max_turns=6,
    )
    return build_schedule_mind(
        resident_id=resident_id,
        display_name=resident_id.title(),
        config=config,
        rng=random.Random(1),
    )


def _ctx(
    resident_id: str,
    now: datetime.datetime = NOW,
    holidays: tuple[Holiday, ...] = (),
    where: str = CAFE,
) -> MindContext:
    body = BodyState(
        resident_id=resident_id,
        display_name=resident_id.title(),
        tile=TilePosition(x=0, y=0),
        location_path=where,
    )
    return MindContext(now=now, self_state=body, holidays=holidays)


def _talk(a: ScheduleMind, b: ScheduleMind, ctx_a: MindContext, ctx_b: MindContext):
    """a가 먼저 말하고 둘이 번갈아 말한다. 대화 기록을 돌려 준다."""
    history: list[Utterance] = []
    speakers = [(a, ctx_a), (b, ctx_b)]
    for turn in range(12):
        mind, ctx = speakers[turn % 2]
        view = ConversationView(
            conversation_id="c1",
            participant_ids=(a.resident_id, b.resident_id),
            history=tuple(history),
        )
        said = asyncio.run(mind.respond(ctx, view))
        if said is None:
            break
        history.append(said)
    return history


def test_host_invites_and_guest_accepts_then_goes_to_party() -> None:
    isabella, maria = _mind("isabella"), _mind("maria")
    isabella.social.apply_seed(SocialSeed(hosting=(PARTY,)), NOW)
    history = _talk(isabella, maria, _ctx("isabella"), _ctx("maria"))
    kinds = [a.kind for u in history for a in u.acts]
    assert "invite" in kinds and "accept" in kinds
    invite = next(u for u in history if u.acts[0].kind == "invite")
    assert "내일 오후 5시" in invite.text and "Seating" in invite.text
    assert maria.social.agenda.is_committed(PARTY)
    before = PARTY.start_time - datetime.timedelta(minutes=20)
    away = _ctx("maria", before, where="Smallville > Town Square")
    action = asyncio.run(maria.next_action(away))
    assert action.kind == "move" and action.location_path == CAFE


def test_rumor_listener_decides_once_by_interest() -> None:
    rumor = event_act("share_fact", PARTY, topic=PARTY.name, fact="파티가 열린대")
    said = Utterance(
        speaker_id="maria",
        listener_ids=("eddy",),
        text="들었어?",
        acts=(rumor,),
        spoken_at=NOW,
    )
    view = ConversationView(
        conversation_id="c1", participant_ids=("eddy", "maria"), history=(said,)
    )
    keen = _mind("eddy", interest=1.0)
    reply = asyncio.run(keen.respond(_ctx("eddy"), view))
    assert reply is not None and reply.acts[0].kind == "accept"
    assert keen.social.agenda.is_committed(PARTY)
    shy = _mind("eddy", interest=0.0)
    reply = asyncio.run(shy.respond(_ctx("eddy"), view))
    assert reply is not None and reply.acts[0].kind == "smalltalk"
    assert not shy.social.agenda.is_committed(PARTY)


def test_holiday_greeting_and_gift_to_friend() -> None:
    maria, klaus = _mind("maria"), _mind("klaus")
    maria.social.friendship.add("klaus", 30)
    day = datetime.datetime(2023, 2, 14, 10, 0)
    holidays = (VALENTINE,)
    history = _talk(
        maria, klaus, _ctx("maria", day, holidays), _ctx("klaus", day, holidays)
    )
    assert history[0].text == "해피 밸런타인데이!"
    gift = next(u for u in history if u.acts[0].kind == "gift")
    assert "초콜릿" in gift.text
    thanks = history[history.index(gift) + 1]
    assert thanks.speaker_id == "klaus" and "고마" in thanks.text
    assert klaus.social.friendship.score("maria") >= 5


def test_long_time_no_see_greeting() -> None:
    maria, klaus = _mind("maria"), _mind("klaus")
    maria.social.friendship.record_conversation(
        "klaus", NOW - datetime.timedelta(days=5)
    )
    history = _talk(maria, klaus, _ctx("maria"), _ctx("klaus"))
    assert "오랜만" in history[0].text or "얼마 만" in history[0].text


def test_encounter_wants_to_talk_when_holding_an_invitation() -> None:
    isabella = _mind("isabella")
    maria = ResidentPublicView(
        resident_id="maria", display_name="Maria", location_path=CAFE
    )
    assert asyncio.run(isabella.on_encounter(_ctx("isabella"), maria)) == "pass_by"
    isabella.social.host(PARTY, NOW)
    assert asyncio.run(isabella.on_encounter(_ctx("isabella"), maria)) == "converse"


def test_invite_sent_with_farewell_is_still_answered() -> None:
    eddy = _mind("eddy")
    invite = Utterance(
        speaker_id="maria",
        listener_ids=("eddy",),
        text="파티 같이 가자, 그럼 안녕!",
        acts=(event_act("invite", PARTY), SpeechAct(kind="farewell")),
        spoken_at=NOW,
    )
    view = ConversationView(
        conversation_id="c1", participant_ids=("eddy", "maria"), history=(invite,)
    )
    reply = asyncio.run(eddy.respond(_ctx("eddy"), view))
    assert reply is not None and reply.acts[0].kind == "accept"
    assert eddy.social.agenda.is_committed(PARTY)
