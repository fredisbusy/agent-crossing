import asyncio

from llm_fakes import DAY, FixedPlanner, ScriptedClient, ctx, make_mind, view
from test_llm_mind import MORNING, _conv
from minds.llm.summary import summary_queries

SUMMARY = "이사벨라는 따뜻한 카페 주인으로, 요즘 손님맞이에 바쁘고 삶에 만족한다."
SPEECH = {"utterance": "안녕하세요!", "acts": [{"kind": "greet"}]}


def _reply(prompt: str) -> object:
    if "요약을 쓴다" in prompt:
        return {"summary": SUMMARY}
    if "converse" in prompt:
        return {"converse": True}
    return SPEECH


def _summary_prompts(client: ScriptedClient) -> list[str]:
    return [p for p in client.prompts if "요약을 쓴다" in p]


def test_summary_is_built_once_a_day_from_three_queries() -> None:
    client = ScriptedClient(_reply)
    mind, memory = make_mind(client)
    asyncio.run(mind.next_action(ctx("isabella", MORNING)))
    asyncio.run(mind.next_action(ctx("isabella", MORNING.replace(hour=11))))
    assert len(_summary_prompts(client)) == 1
    for query in summary_queries("Isabella"):
        assert query in memory.queries
    next_day = MORNING.replace(day=DAY.day + 1)
    asyncio.run(mind.next_action(ctx("isabella", next_day)))
    assert len(_summary_prompts(client)) == 2


def test_summary_goes_into_plan_encounter_and_speech_prompts() -> None:
    client = ScriptedClient(_reply)
    mind, _ = make_mind(client)
    planner = FixedPlanner()
    mind._planner = planner  # noqa: SLF001
    asyncio.run(mind.next_action(ctx("isabella", MORNING)))
    assert SUMMARY in planner.requests[0].persona_background
    nearby = ctx("isabella", MORNING, nearby=(view("maria"),))
    asyncio.run(mind.on_encounter(nearby, view("maria")))
    assert SUMMARY in client.prompts[-1]
    asyncio.run(mind.respond(nearby, _conv()))
    assert SUMMARY in client.prompts[-1]


def test_summary_failure_falls_back_to_identity_sentences() -> None:
    client = ScriptedClient(lambda _: "깨진 응답")
    mind, _ = make_mind(client)
    planner = FixedPlanner()
    mind._planner = planner  # noqa: SLF001
    asyncio.run(mind.next_action(ctx("isabella", MORNING)))
    identity = "Loves making people feel welcome."
    assert planner.requests[0].persona_background.count(identity) == 1
    nearby = ctx("isabella", MORNING, nearby=(view("maria"),))
    asyncio.run(mind.respond(nearby, _conv()))
    assert client.prompts[-1].count(identity) == 1


def test_summary_prompts_avoid_simulation_jargon() -> None:
    client = ScriptedClient(_reply)
    mind, _ = make_mind(client)
    asyncio.run(mind.next_action(ctx("isabella", MORNING)))
    prompt = _summary_prompts(client)[0]
    assert not any(word in prompt for word in ("NPC", "agent", "rule"))
