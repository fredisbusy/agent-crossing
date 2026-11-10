import asyncio
import datetime

from llm_fakes import CAFE, DAY, ScriptedClient, ctx, make_mind, view
from world.contracts import SocialEvent

MORNING = DAY.replace(hour=10)
PARTY = SocialEvent(
    name="밸런타인데이 파티",
    start_time=datetime.datetime(2023, 2, 14, 17, 0),
    end_time=datetime.datetime(2023, 2, 14, 19, 0),
    location_path=CAFE,
)


def _meet(mind: object, now: datetime.datetime = MORNING) -> str:
    return asyncio.run(mind.on_encounter(ctx("isabella", now), view("maria")))  # type: ignore[attr-defined]


def test_model_judgement_is_logged_with_its_reason() -> None:
    client = ScriptedClient(lambda _: {"converse": True, "reason": "오랜 단골이라 반갑다"})
    mind, _ = make_mind(client)

    assert _meet(mind) == "converse"

    [record] = mind.encounter_log
    assert (record.other_id, record.choice, record.basis) == ("maria", "converse", "judged")
    assert record.reason == "오랜 단골이라 반갑다" and record.at == MORNING
    assert record.friendship == 0 and record.last_talk is None


def test_unreadable_judgement_passes_by_and_says_so() -> None:
    mind, _ = make_mind(ScriptedClient(lambda _: "not json"))

    assert _meet(mind) == "pass_by"
    assert mind.encounter_log[0].reason == "판정 응답을 읽지 못했다"


def test_rule_decisions_are_logged_without_calling_the_model() -> None:
    client = ScriptedClient(lambda _: {"converse": False})
    mind, _ = make_mind(client)
    mind.social.host(PARTY, MORNING)

    assert _meet(mind) == "converse"
    mind.social.join_conversation("c1", "maria", MORNING)
    assert _meet(mind, MORNING + datetime.timedelta(hours=1)) == "pass_by"

    talking, cooldown = mind.encounter_log
    assert (talking.basis, talking.reason) == ("talking_point", "꺼낼 이야깃거리: invite")
    assert cooldown.basis == "cooldown" and cooldown.friendship > 0
    assert client.prompts == []
