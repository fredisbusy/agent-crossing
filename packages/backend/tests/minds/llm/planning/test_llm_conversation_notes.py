import asyncio
import datetime

from llm_fakes import (
    DAY,
    CountingReflection,
    FixedPlanner,
    ListMemory,
    ScriptedClient,
    ctx,
    make_mind,
)
from minds.llm import LlmPersona
from minds.llm.planning import (
    MAX_PLAN_NOTES,
    PLAN_NOTE_LIFETIME,
    ConversationNotes,
    parse_notes,
    plan_request,
)
from minds.llm.recall import MemoryWriter
from minds.social import Slot
from world.contracts import ConversationView, SpeechAct, Utterance

MORNING = DAY.replace(hour=10)
NAMES = {"isabella": "Isabella", "maria": "Maria"}
NOTE_REPLY = {"memo": "Maria는 시험 때문에 바쁘다.", "plan_note": "내일 Maria에게 쿠키를 가져다준다."}


def _said(speaker: str, listener: str, text: str, minute: int = 0) -> Utterance:
    return Utterance(
        speaker_id=speaker,
        listener_ids=(listener,),
        text=text,
        acts=(SpeechAct(kind="smalltalk"),),
        spoken_at=MORNING + datetime.timedelta(minutes=minute),
    )


def _conv(*history: Utterance, cid: str = "c1") -> ConversationView:
    return ConversationView(
        conversation_id=cid, participant_ids=("isabella", "maria"), history=history
    )


def _notes(client: ScriptedClient) -> tuple[ConversationNotes, ListMemory]:
    memory = ListMemory()
    persona = LlmPersona(
        resident_id="isabella",
        display_name="Isabella",
        age=34,
        identity=("Loves making people feel welcome.",),
        home="Smallville > Hobbs Cafe > Counter",
        known_places=("Smallville > Hobbs Cafe > Counter",),
    )
    writer = MemoryWriter(memory, CountingReflection())
    return ConversationNotes(persona=persona, client=client, writer=writer), memory


def _digest(notes: ConversationNotes, now: datetime.datetime, current: str | None = None) -> None:
    slot = Slot(
        "Smallville > Hobbs Cafe > Counter",
        "카페를 정리한다",
        None,
        "idle",
        now,
        now + datetime.timedelta(hours=2),
    )
    notes.digest(now, current_conversation_id=current, summary="", remaining=[slot])


def test_finished_talk_becomes_memo_memory_and_plan_note() -> None:
    client = ScriptedClient(lambda _: NOTE_REPLY)
    notes, memory = _notes(client)
    hello = _said("isabella", "maria", "요즘 어때요?")
    notes.track(_conv(), "maria", NAMES, hello)
    notes.heard(_said("maria", "isabella", "시험 때문에 바빠요.", 1))
    notes.heard(_said("klaus", "maria", "지나가던 말", 1))

    _digest(notes, MORNING, current="c1")
    assert client.prompts == []
    _digest(notes, MORNING + datetime.timedelta(minutes=5))

    [prompt] = client.prompts
    assert "- Isabella: 요즘 어때요?\n- Maria: 시험 때문에 바빠요." in prompt
    assert "지나가던 말" not in prompt and "카페를 정리한다" in prompt
    assert memory.stored == [
        ("observation", "Isabella의 Maria와의 대화 메모: Maria는 시험 때문에 바쁘다."),
        ("plan", "Isabella는 Maria와 이야기한 뒤 이렇게 하기로 했다: 내일 Maria에게 쿠키를 가져다준다."),
    ]
    later = MORNING + datetime.timedelta(hours=20)
    assert notes.plan_lines(later) == ["Maria와 이야기한 뒤: 내일 Maria에게 쿠키를 가져다준다."]
    _digest(notes, later)
    assert len(client.prompts) == 1
    assert notes.plan_lines(MORNING + PLAN_NOTE_LIFETIME + datetime.timedelta(minutes=5)) == []


def test_one_line_talk_and_unreadable_reply_leave_nothing() -> None:
    client = ScriptedClient(lambda _: "not json")
    notes, memory = _notes(client)

    notes.track(_conv(), "maria", NAMES, _said("isabella", "maria", "안녕"))
    _digest(notes, MORNING)
    assert client.prompts == []

    notes.track(_conv(_said("maria", "isabella", "안녕"), cid="c2"), "maria", NAMES, _said("isabella", "maria", "네"))
    _digest(notes, MORNING)
    assert len(client.prompts) == 1 and memory.stored == [] and notes.plan_lines(MORNING) == []


def test_plan_lines_keep_only_recent_notes() -> None:
    notes, _ = _notes(ScriptedClient(lambda _: NOTE_REPLY))
    for index in range(MAX_PLAN_NOTES + 2):
        history = _said("maria", "isabella", f"말 {index}")
        notes.track(_conv(history, cid=f"c{index}"), "maria", NAMES, _said("isabella", "maria", "네"))
        _digest(notes, MORNING + datetime.timedelta(minutes=index))

    assert len(notes.plan_lines(MORNING + datetime.timedelta(hours=1))) == MAX_PLAN_NOTES


def test_parse_notes_tolerates_missing_fields_and_trailing_text() -> None:
    assert parse_notes('{"memo": " 메모 ", "plan_note": ""}</final') == ("메모", "")
    assert parse_notes('{"plan_note": 3}') == ("", "")
    assert parse_notes("[]") == ("", "")


def test_mind_feeds_talk_notes_and_close_friends_into_the_next_plan() -> None:
    def reply(prompt: str) -> object:
        if "이 대화를 정리한다" in prompt:
            return NOTE_REPLY
        if "## 대화" in prompt or "utterance" in prompt:
            return {"utterance": "그렇군요.", "acts": [{"kind": "smalltalk"}], "end_conversation": False}
        return {}

    planner = FixedPlanner()
    mind, memory = make_mind(ScriptedClient(reply), planner=planner)
    mind.social.friendship.add("maria", 30)
    asyncio.run(mind.next_action(ctx("isabella", MORNING)))
    heard = _said("maria", "isabella", "시험 때문에 바빠요.")

    asyncio.run(mind.respond(ctx("isabella", MORNING), _conv(heard)))
    asyncio.run(mind.next_action(ctx("isabella", MORNING + datetime.timedelta(minutes=10))))

    assert ("plan", "Isabella는 Maria와 이야기한 뒤 이렇게 하기로 했다: 내일 Maria에게 쿠키를 가져다준다.") in memory.stored
    asyncio.run(mind.next_action(ctx("isabella", MORNING + datetime.timedelta(hours=21))))
    background = planner.requests[-1].persona_background
    assert "대화에서 정한 일: Maria와 이야기한 뒤: 내일 Maria에게 쿠키를 가져다준다." in background
    assert "가까운 사람: Maria(친밀도 32/100)" in background


def test_plan_request_omits_relationship_lines_when_empty() -> None:
    mind, _ = make_mind(ScriptedClient(lambda _: {}))
    request = plan_request(mind.persona, MORNING, commitments=(), holidays=(), yesterday="")
    assert "가까운 사람" not in request.persona_background
    assert "대화에서 정한 일" not in request.persona_background


def test_repeated_partner_words_and_known_events_reach_the_prompt() -> None:
    client = ScriptedClient(lambda _: NOTE_REPLY)
    notes, _ = _notes(client)
    first = _said("maria", "isabella", "네")
    notes.track(_conv(first), "maria", NAMES, _said("isabella", "maria", "내일 봐요", 1))
    last = _said("maria", "isabella", "네", 2)
    notes.heard(last)
    notes.heard(last)

    notes.digest(
        MORNING + datetime.timedelta(minutes=5),
        current_conversation_id=None,
        summary="",
        remaining=[],
        events=["내가 여는 행사: 밸런타인데이 파티"],
    )

    [prompt] = client.prompts
    assert "- Maria: 네\n- Isabella: 내일 봐요\n- Maria: 네" in prompt
    assert prompt.count("- Maria: 네") == 2
    assert "- 내가 여는 행사: 밸런타인데이 파티" in prompt
