"""관찰에 대한 반응 판정과 지금 이후 재계획 (SPEC §7, TODO 3-B)."""

import asyncio
import datetime
import json

from agents.planning.models import DayPlanBroadStrokesRequest, DayPlanItem
from llm_fakes import (
    CAFE,
    DAY,
    HOME,
    PARK,
    SQUARE,
    FixedPlanner,
    ScriptedClient,
    ctx,
    make_mind,
)
from minds.llm import LLMMind
from minds.llm.planning.reaction import REACTION_LOG_SIZE, parse_verdict
from minds.social import SocialSeed
from world.contracts import MindContext, Observation, SocialEvent, Utterance

HOME_CAFE = CAFE
MARKER = "반응해야 하는가"
FORBIDDEN = ("npc", "agent", "rule")
REACTION = {
    "react": True,
    "reason": "도와야 한다",
    "reaction": {
        "description": "광장에서 소란을 살핀다",
        "location": "Town Square",
        "minutes": 30,
    },
}


def at(hour: int, minute: int = 0) -> datetime.datetime:
    return DAY.replace(hour=hour, minute=minute)


class ReplanPlanner(FixedPlanner):
    """첫 호출은 9~12시 산책, 이후 호출은 정해진 재계획(또는 실패)."""

    def __init__(self, later: list[tuple[int, int, str]] | None) -> None:
        super().__init__()
        self._later = later

    def generate_day_plan(
        self, request: DayPlanBroadStrokesRequest
    ) -> list[DayPlanItem]:
        if not self.requests:
            return super().generate_day_plan(request)
        self.requests.append(request)
        if self._later is None:
            raise RuntimeError("llm down")
        return [
            DayPlanItem(at(start), at(end), "Hobbs Cafe Seating", text)
            for start, end, text in self._later
        ]


def sight(text: str, now: datetime.datetime, who: str = "maria") -> Observation:
    return Observation(
        kind="sight", text=text, observed_at=now, location_path=CAFE, subject_id=who
    )


def woken(
    now: datetime.datetime,
    *obs: Observation,
    where: str = CAFE,
) -> MindContext:
    return ctx("isabella", now, where=where).model_copy(update={"observations": obs})


def _client(reply: object = REACTION) -> ScriptedClient:
    return ScriptedClient(
        lambda prompt: (
            reply if MARKER in prompt else {"summary": "친절한 카페 주인이다"}
        )
    )


def _judged(client: ScriptedClient) -> list[str]:
    return [p for p in client.prompts if MARKER in p]


def _start(mind: LLMMind) -> None:
    asyncio.run(mind.next_action(ctx("isabella", at(9, 30), where=PARK)))


def _plan(mind: LLMMind) -> list[tuple[str, str, str, str]]:
    return [
        (f"{s.start:%H:%M}", f"{s.end:%H:%M}", s.location_path, s.description)
        for s in mind.routine.slots(DAY.date())
    ]


def test_no_judgement_without_new_sights_or_while_asleep() -> None:
    client = _client()
    mind, _ = make_mind(client)
    _start(mind)
    talk = Utterance(
        speaker_id="maria", listener_ids=("isabella",), text="안녕", spoken_at=at(10)
    )
    heard = Observation(
        kind="utterance",
        text="Maria: 안녕",
        observed_at=at(10),
        location_path=CAFE,
        utterance=talk,
        subject_id="maria",
    )
    mine = sight("Isabella가 커피를 내린다", at(10), who="isabella")
    for obs in ((), (heard,), (mine,)):
        asyncio.run(mind.next_action(woken(at(10), *obs)))
    asyncio.run(
        mind.next_action(woken(at(3), sight("누가 지나간다", at(3)), where=HOME))
    )
    assert _judged(client) == []
    assert mind.reaction_log == ()


def test_declining_keeps_plan_and_judges_once_per_wake() -> None:
    client = _client({"react": False, "reason": "하던 일이 낫다"})
    planner = ReplanPlanner([])
    mind, _ = make_mind(client, planner=planner)
    _start(mind)
    before = _plan(mind)
    obs = (sight("Maria가 걸어온다", at(10)), sight("Eddy가 노래한다", at(10), "eddy"))
    action = asyncio.run(mind.next_action(woken(at(10), *obs, where=PARK)))
    assert len(_judged(client)) == 1
    assert _plan(mind) == before and len(planner.requests) == 1
    assert action.location_path == PARK and action.until == at(12)
    (record,) = mind.reaction_log
    assert not record.react and record.reason == "하던 일이 낫다"
    assert "Maria가 걸어온다" in record.observations


def test_reacting_replaces_only_the_rest_of_the_day() -> None:
    client = _client()
    planner = ReplanPlanner([])
    mind, memory = make_mind(client, planner=planner)
    _start(mind)
    dropped: list[datetime.datetime | None] = []
    original = mind._decomposer.invalidate  # pyright: ignore[reportPrivateUsage]

    def spy(since: datetime.datetime | None = None) -> None:
        dropped.append(since)
        original(since)

    mind._decomposer.invalidate = spy  # pyright: ignore[reportPrivateUsage]
    # 반응 끝(10:30) 전에 끝나는 항목은 버리고, 걸친 항목은 10:30에서 자르며, 같은 시각에 구간이 둘 생기지 않게 겹친 항목은 버린다.
    planner._later = [  # pyright: ignore[reportPrivateUsage]
        (10, 11, "짧은 일"),
        (10, 11, "정리"),
        (11, 13, "점심"),
    ]
    action = asyncio.run(
        mind.next_action(woken(at(10), sight("광장이 소란스럽다", at(10)), where=PARK))
    )
    assert _plan(mind) == [
        ("09:00", "10:00", PARK, "공원을 산책한다"),
        ("10:00", "10:30", SQUARE, "광장에서 소란을 살핀다"),
        ("10:30", "11:00", HOME_CAFE, "짧은 일"),
        ("11:00", "13:00", HOME_CAFE, "점심"),
    ]
    assert action.kind == "move" and action.location_path == SQUARE
    assert action.until == at(10, 30)
    assert dropped == [at(10)]
    note = planner.requests[-1].persona_background
    assert (
        "10:00" in note
        and "광장에서 소란을 살핀다" in note
        and "공원을 산책한다" in note
    )
    assert any(
        kind == "plan" and "광장이 소란스럽다" in text and "보고" in text
        for kind, text in memory.stored
    )
    (record,) = mind.reaction_log
    assert record.react and record.at == at(10)
    # 반응 구간은 다시 쪼개지 않는다.
    assert planner.hourly_calls[-1][1].action_content != "광장에서 소란을 살핀다"


def test_failed_replan_only_cuts_the_reaction_window() -> None:
    mind, _ = make_mind(_client(), planner=ReplanPlanner(None))
    _start(mind)
    asyncio.run(mind.next_action(woken(at(10), sight("광장이 소란스럽다", at(10)))))
    assert _plan(mind) == [
        ("09:00", "10:00", PARK, "공원을 산책한다"),
        ("10:00", "10:30", SQUARE, "광장에서 소란을 살핀다"),
        ("10:30", "12:00", PARK, "공원을 산책한다"),
    ]


def test_unknown_place_falls_back_to_here_and_minutes_are_clamped() -> None:
    reply = {
        "react": True,
        "reason": "r",
        "reaction": {"description": "구경한다", "location": "달나라", "minutes": 1},
    }
    mind, _ = make_mind(_client(reply), planner=ReplanPlanner(None))
    _start(mind)
    action = asyncio.run(
        mind.next_action(woken(at(10), sight("무언가 보인다", at(10)), where=CAFE))
    )
    assert action.description == "구경한다" and action.location_path == CAFE
    assert action.until == at(10, 5)


def test_bad_replies_and_errors_mean_no_reaction() -> None:
    for reply in ("깨진 응답", {"react": True}, {"react": True, "reaction": {}}):
        mind, _ = make_mind(_client(reply), planner=ReplanPlanner([]))
        _start(mind)
        before = _plan(mind)
        asyncio.run(mind.next_action(woken(at(10), sight("누가 보인다", at(10)))))
        assert _plan(mind) == before
        assert not mind.reaction_log[-1].react

    def boom(prompt: str) -> object:
        if MARKER in prompt:
            raise TimeoutError("slow")
        return {}

    mind, _ = make_mind(ScriptedClient(boom))
    _start(mind)
    before = _plan(mind)
    asyncio.run(mind.next_action(woken(at(10), sight("누가 보인다", at(10)))))
    assert _plan(mind) == before


def test_prompt_carries_summary_observations_memories_without_forbidden_words() -> None:
    client = _client({"react": False})
    mind, _ = make_mind(client)
    _start(mind)
    obs = (sight("Maria가 걸어온다", at(10)), sight("Eddy가 노래한다", at(10), "eddy"))
    asyncio.run(mind.next_action(woken(at(10), *obs, where=PARK)))
    (prompt,) = _judged(client)
    assert "친절한 카페 주인이다" in prompt
    assert "1. Maria가 걸어온다" in prompt and "2. Eddy가 노래한다" in prompt
    assert "카페를 운영한다." in prompt
    assert "오전 10시" in prompt and "존슨 공원" in prompt
    assert "공원을 산책한다" in prompt
    assert not any(word in prompt.lower() for word in FORBIDDEN)


def test_pending_speech_is_flushed_before_retrieval() -> None:
    mind, memory = make_mind(_client({"react": False}))
    _start(mind)
    mind._writer.defer("Isabella가 말했다", at(10))  # pyright: ignore[reportPrivateUsage]
    asyncio.run(mind.next_action(woken(at(10), sight("Maria가 걸어온다", at(10)))))
    assert memory.queries[-1] == "Maria가 걸어온다"
    assert memory.stored_at_query[-1] == len(memory.stored)


def test_reaction_log_keeps_only_the_most_recent_records() -> None:
    mind, _ = make_mind(_client({"react": False, "reason": "그대로"}))
    _start(mind)
    for i in range(REACTION_LOG_SIZE + 5):
        when = at(10, i)
        asyncio.run(mind.next_action(woken(when, sight(f"소식 {i}", when))))
    log = mind.reaction_log
    assert len(log) == REACTION_LOG_SIZE
    assert log[-1].observations == f"소식 {REACTION_LOG_SIZE + 4}"
    assert log[0].observations == "소식 5"


def test_no_judgement_during_a_commitment() -> None:
    client = _client()
    mind, _ = make_mind(client)
    party = SocialEvent(
        name="파티",
        start_time=at(16),
        end_time=at(18),
        location_path=CAFE,
    )
    mind.social.apply_seed(SocialSeed(hosting=(party,)), at(9))
    _start(mind)
    asyncio.run(
        mind.next_action(woken(at(16, 30), sight("Maria가 들어온다", at(16, 30))))
    )
    assert _judged(client) == [] and mind.reaction_log == ()


def _by_minutes(*minutes: int) -> ScriptedClient:
    queue = list(minutes)

    def reply(prompt: str) -> object:
        if MARKER not in prompt:
            return {"summary": "친절한 카페 주인이다"}
        if not queue:
            return {"react": False}
        count = queue.pop(0)
        return {
            "react": True,
            "reason": "r",
            "reaction": {
                "description": f"반응{count}",
                "location": "Town Square",
                "minutes": count,
            },
        }

    return ScriptedClient(reply)


def test_event_observation_without_subject_is_judged() -> None:
    client = _client({"react": False, "reason": "그대로"})
    mind, _ = make_mind(client)
    _start(mind)
    holiday = Observation(
        kind="event", text="오늘은 기념일이다", observed_at=at(10), location_path=CAFE
    )
    asyncio.run(mind.next_action(woken(at(10), holiday)))
    assert len(_judged(client)) == 1


def test_nested_reaction_with_failed_replan_is_not_decomposed() -> None:
    planner = ReplanPlanner(None)
    mind, _ = make_mind(_by_minutes(120, 10), planner=planner)
    _start(mind)
    asyncio.run(mind.next_action(woken(at(10), sight("소란", at(10)))))
    asyncio.run(mind.next_action(woken(at(10, 20), sight("또 소란", at(10, 20)))))
    calls = len(planner.hourly_calls)
    action = asyncio.run(mind.next_action(ctx("isabella", at(10, 35), where=SQUARE)))
    assert action.description == "반응120" and action.until == at(12)
    assert len(planner.hourly_calls) == calls


def test_reaction_stops_at_midnight_without_replanning() -> None:
    class LatePlanner(ReplanPlanner):
        def generate_day_plan(
            self, request: DayPlanBroadStrokesRequest
        ) -> list[DayPlanItem]:
            self.requests.append(request)
            return [DayPlanItem(at(22), at(23, 59), "Town Square", "책을 읽는다")]

    planner = LatePlanner([])
    mind, _ = make_mind(_by_minutes(120), planner=planner)
    asyncio.run(mind.next_action(ctx("isabella", at(22, 10))))
    action = asyncio.run(mind.next_action(woken(at(23, 30), sight("소란", at(23, 30)))))
    midnight = DAY + datetime.timedelta(days=1)
    assert action.until == midnight and len(planner.requests) == 1
    assert not mind.routine.has_plan(midnight.date())


def test_timezone_aware_replan_results_are_normalized() -> None:
    zone = datetime.timezone(datetime.timedelta(hours=9))

    class AwarePlanner(ReplanPlanner):
        def generate_day_plan(
            self, request: DayPlanBroadStrokesRequest
        ) -> list[DayPlanItem]:
            if not self.requests:
                return super().generate_day_plan(request)
            self.requests.append(request)
            return [
                DayPlanItem(
                    at(10, 15).replace(tzinfo=zone),
                    at(13).replace(tzinfo=zone),
                    "Hobbs Cafe Seating",
                    "점심",
                )
            ]

    mind, _ = make_mind(_client(), planner=AwarePlanner([]))
    _start(mind)
    asyncio.run(mind.next_action(woken(at(10), sight("소란", at(10)))))
    assert _plan(mind) == [
        ("09:00", "10:00", PARK, "공원을 산책한다"),
        ("10:00", "10:30", SQUARE, "광장에서 소란을 살핀다"),
        ("10:30", "13:00", CAFE, "점심"),
    ]


def test_minutes_accept_floats_and_numeric_strings() -> None:
    def parsed(value: object) -> int:
        reply = {"react": True, "reaction": {"description": "가본다", "minutes": value}}
        verdict = parse_verdict(json.dumps(reply))
        assert verdict.reaction is not None
        return verdict.reaction.minutes

    assert parsed(30.0) == 30 and parsed("30") == 30 and parsed(" 45.4 ") == 45
    assert parsed("곧") == 0 and parsed(True) == 0 and parsed(None) == 0


def test_stale_reaction_items_are_dropped_on_a_new_day() -> None:
    mind, _ = make_mind(_by_minutes(30), planner=ReplanPlanner([]))
    _start(mind)
    asyncio.run(mind.next_action(woken(at(10), sight("소란", at(10)))))
    reactor = mind._reactor  # pyright: ignore[reportPrivateUsage]
    assert len(reactor.items) == 1
    tomorrow = at(10) + datetime.timedelta(days=1)
    asyncio.run(mind.next_action(woken(tomorrow, sight("소란", tomorrow))))
    assert reactor.items == set()
