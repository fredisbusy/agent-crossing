import asyncio
import datetime

from llm_fakes import CAFE, DAY, HOME, PARK, ScriptedClient, ctx, make_mind, view
from minds.llm.routine import plan_request
from minds.social import SocialSeed, event_act
from world.contracts import (
    ConversationView,
    Observation,
    SocialEvent,
    SpeechAct,
    Utterance,
)

PARTY = SocialEvent(
    name="밸런타인데이 파티",
    start_time=datetime.datetime(2023, 2, 14, 17, 0),
    end_time=datetime.datetime(2023, 2, 14, 19, 0),
    location_path=CAFE,
)
MORNING = DAY.replace(hour=10)


def _conv(
    *history: Utterance, me: str = "isabella", other: str = "maria"
) -> ConversationView:
    return ConversationView(
        conversation_id="c1", participant_ids=(me, other), history=history
    )


def _said(
    speaker: str, listener: str, *acts: SpeechAct, text: str = "안녕"
) -> Utterance:
    return Utterance(
        speaker_id=speaker,
        listener_ids=(listener,),
        text=text,
        acts=acts,
        spoken_at=MORNING,
    )


def test_follows_day_plan_and_sleeps_at_home_outside_it() -> None:
    mind, memory = make_mind(ScriptedClient(lambda _: {}))
    action = asyncio.run(mind.next_action(ctx("isabella", MORNING, where=HOME)))
    assert action.kind == "move" and action.location_path == PARK
    assert action.until == DAY.replace(hour=12)
    night = asyncio.run(
        mind.next_action(ctx("isabella", DAY.replace(hour=3), where=HOME))
    )
    assert night.kind == "sleep" and night.until == DAY.replace(hour=7)
    assert any(kind == "plan" for kind, _ in memory.stored)
    assert ("observation", "카페를 운영한다.") in memory.stored


def test_commitment_overrides_plan_like_any_other_mind() -> None:
    mind, memory = make_mind(ScriptedClient(lambda _: {}))
    mind.social.apply_seed(SocialSeed(hosting=(PARTY,)), MORNING)
    prep = asyncio.run(
        mind.next_action(ctx("isabella", PARTY.start_time.replace(hour=16, minute=10)))
    )
    assert prep.location_path == CAFE and "준비" in prep.description
    asyncio.run(mind.next_action(ctx("isabella", MORNING)))
    assert any(PARTY.name in content for _, content in memory.stored)


def test_invite_times_come_from_the_known_event_not_the_model() -> None:
    reply = {
        "utterance": "내일 파티 와 줄래요?",
        "acts": [
            {"kind": "invite", "event": PARTY.name, "start_time": "2023-02-20T09:00:00"}
        ],
        "end_conversation": False,
    }
    client = ScriptedClient(lambda _: reply)
    mind, _ = make_mind(client)
    mind.social.host(PARTY, MORNING)
    said = asyncio.run(
        mind.respond(ctx("isabella", MORNING, nearby=(view("maria"),)), _conv())
    )
    assert said is not None and said.text == "내일 파티 와 줄래요?"
    [invite] = said.acts
    assert invite.start_time == PARTY.start_time and invite.end_time == PARTY.end_time
    assert mind.social.talking_points("maria", MORNING) == ()
    prompt = client.prompts[-1]
    assert "밸런타인데이 파티에 초대하기" in prompt and "Maria" in prompt
    assert "Loves making people feel welcome." in prompt and "Seating" in prompt


def test_accepting_a_heard_invite_commits_through_shared_state() -> None:
    reply = {
        "utterance": "좋아요, 갈게요!",
        "acts": [{"kind": "accept", "event": PARTY.name}],
    }
    mind, _ = make_mind(ScriptedClient(lambda _: reply), resident_id="maria")
    hosted = PARTY.model_copy(update={"host_id": "isabella"})
    invite = _said("isabella", "maria", event_act("invite", hosted), text="파티 와요")
    conv = _conv(invite, me="maria", other="isabella")
    said = asyncio.run(mind.respond(ctx("maria", MORNING), conv))
    assert said is not None and said.acts[0].kind == "accept"
    [commitment] = mind.social.agenda.commitments
    assert commitment.role == "guest" and commitment.event.host_id == "isabella"


def test_unparseable_reply_ends_and_bad_acts_fall_back_to_smalltalk() -> None:
    silent, _ = make_mind(ScriptedClient(lambda _: "잘 모르겠어요"))
    assert asyncio.run(silent.respond(ctx("isabella", MORNING), _conv())) is None
    reply = {
        "utterance": "그렇군요.",
        "acts": [{"kind": "accept", "event": "없는 행사"}],
    }
    vague, _ = make_mind(ScriptedClient(lambda _: reply))
    said = asyncio.run(vague.respond(ctx("isabella", MORNING), _conv()))
    assert said is not None and [a.kind for a in said.acts] == ["smalltalk"]
    assert vague.social.agenda.commitments == []


def test_last_allowed_turn_ends_with_farewell() -> None:
    reply = {"utterance": "그렇네요.", "acts": [{"kind": "smalltalk"}]}
    mind, _ = make_mind(ScriptedClient(lambda _: reply), max_turns=1)
    said = asyncio.run(mind.respond(ctx("isabella", MORNING), _conv()))
    assert said is not None and [a.kind for a in said.acts] == ["smalltalk", "farewell"]
    after = _conv(said, _said("maria", "isabella", SpeechAct(kind="farewell")))
    assert asyncio.run(mind.respond(ctx("isabella", MORNING), after)) is None


def test_observe_remembers_and_learns_rumors() -> None:
    mind, memory = make_mind(ScriptedClient(lambda _: {}), resident_id="eddy")
    rumor = event_act("share_fact", PARTY, topic=PARTY.name, fact="파티가 열린대")
    heard = Utterance(
        speaker_id="maria",
        listener_ids=("klaus",),
        text="파티 한대",
        acts=(rumor,),
        spoken_at=MORNING,
    )
    obs = Observation(
        kind="utterance",
        text='Maria가 말했다: "파티 한대"',
        observed_at=MORNING,
        location_path=CAFE,
        subject_id="maria",
        utterance=heard,
    )
    asyncio.run(mind.observe((obs,)))
    assert mind.social.facts.get(PARTY.name) is not None
    assert ("observation", obs.text) in memory.stored


def test_encounter_skips_the_model_when_there_is_something_to_say() -> None:
    client = ScriptedClient(lambda _: {"converse": False})
    mind, _ = make_mind(client)
    assert (
        asyncio.run(mind.on_encounter(ctx("isabella", MORNING), view("maria")))
        == "pass_by"
    )
    assert len(client.prompts) == 1
    mind.social.host(PARTY, MORNING)
    assert (
        asyncio.run(mind.on_encounter(ctx("isabella", MORNING), view("maria")))
        == "converse"
    )
    assert len(client.prompts) == 1


def test_partner_farewell_makes_this_turn_the_last() -> None:
    reply = {"utterance": "네, 또 봬요.", "acts": [{"kind": "smalltalk"}]}
    client = ScriptedClient(lambda _: reply)
    mind, _ = make_mind(client)
    bye = _said("maria", "isabella", SpeechAct(kind="farewell"), text="그럼 갈게요")
    said = asyncio.run(mind.respond(ctx("isabella", MORNING), _conv(bye)))
    assert said is not None and said.acts[-1].kind == "farewell"
    assert "이번 말로 대화를 마무리한다." in client.prompts[-1]


def test_repeated_invite_from_the_model_is_dropped_and_partner_notes_shown() -> None:
    reply = {
        "utterance": "내일 파티 꼭 와요!",
        "acts": [
            {"kind": "invite", "event": PARTY.name},
            {"kind": "accept", "event": PARTY.name},
        ],
    }
    client = ScriptedClient(lambda _: reply)
    mind, _ = make_mind(client)
    mind.social.host(PARTY, MORNING)
    first = asyncio.run(mind.respond(ctx("isabella", MORNING), _conv()))
    assert first is not None and [a.kind for a in first.acts] == ["invite"]
    second = asyncio.run(
        mind.respond(
            ctx("isabella", MORNING),
            _conv(first, _said("maria", "isabella", SpeechAct(kind="smalltalk"))),
        )
    )
    assert second is not None and [a.kind for a in second.acts] == ["smalltalk"]
    assert "Maria를 밸런타인데이 파티에 이미 초대했다." in client.prompts[-1]


def test_day_plan_is_requested_in_korean() -> None:
    mind, _ = make_mind(ScriptedClient(lambda _: {}))
    request = plan_request(
        mind.persona, MORNING, commitments=(), holidays=(), yesterday=""
    )
    assert "한국어" in request.persona_background
