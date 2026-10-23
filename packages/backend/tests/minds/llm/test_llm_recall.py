import asyncio

from llm_fakes import CAFE, ScriptedClient, ctx, make_mind, view
from test_llm_mind import MORNING, _conv, _said
from minds.llm import LLMMind
from world.contracts import Observation, SpeechAct, Utterance

REPLY = {"utterance": "그렇군요.", "acts": [{"kind": "smalltalk"}]}
MINE = 'Isabella가 Maria에게 말했다: "그렇군요."'


def _heard(text: str) -> Observation:
    return Observation(kind="event", text=text, observed_at=MORNING, location_path=CAFE)


def _speak_once(mind: LLMMind) -> Utterance | None:
    ctx_ = ctx("isabella", MORNING, nearby=(view("maria"),))
    return asyncio.run(mind.respond(ctx_, _conv()))


def test_own_utterance_is_not_stored_right_after_speaking() -> None:
    mind, memory = make_mind(ScriptedClient(lambda _: REPLY))
    assert _speak_once(mind) is not None
    assert all(content != MINE for _, content in memory.stored)
    assert memory.batches == []


def test_next_observe_stores_own_utterance_first_in_one_batch() -> None:
    mind, memory = make_mind(ScriptedClient(lambda _: REPLY))
    _speak_once(mind)
    asyncio.run(mind.observe((_heard("a"), _heard("b"))))
    assert memory.batches == [[MINE, "a", "b"]]


def test_pending_utterance_is_flushed_before_retrieval_without_observe() -> None:
    mind, memory = make_mind(ScriptedClient(lambda _: REPLY))
    _speak_once(mind)
    follow_up = _conv(_said("maria", "isabella", SpeechAct(kind="smalltalk")))
    asyncio.run(mind.respond(ctx("isabella", MORNING), follow_up))
    assert memory.batches[0] == [MINE]
    assert memory.stored_at_query[-1] >= 1
    assert any(content == MINE for _, content in memory.stored)


def test_seed_memories_are_stored_as_one_batch() -> None:
    mind, memory = make_mind(ScriptedClient(lambda _: {}))
    asyncio.run(mind.next_action(ctx("isabella", MORNING)))
    assert memory.batches == [["카페를 운영한다."]]
