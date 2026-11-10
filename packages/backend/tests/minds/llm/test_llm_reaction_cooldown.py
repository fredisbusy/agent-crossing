"""같은 주민을 보고 연달아 재계획하지 않는다 (SPEC §7 연속 재계획 방지)."""

import asyncio
import datetime

from llm_fakes import CAFE, DAY, PARK, FixedPlanner, ScriptedClient, ctx, make_mind
from minds.llm import LLMMind
from minds.llm.planning import REACTION_COOLDOWN_MINUTES
from world.contracts import MindContext, Observation

MARKER = "반응해야 하는가"
REACT = {
    "react": True,
    "reason": "반갑다",
    "reaction": {"description": "인사한다", "location": "", "minutes": 5},
}
START = DAY.replace(hour=13)


def after(minutes: int) -> datetime.datetime:
    return START + datetime.timedelta(minutes=minutes)


def seen(who: str | None, now: datetime.datetime, text: str = "지나간다") -> Observation:
    return Observation(
        kind="sight" if who else "event",
        text=f"{who or '마을'}: {text}",
        observed_at=now,
        location_path=CAFE,
        subject_id=who,
    )


def woken(now: datetime.datetime, *obs: Observation) -> MindContext:
    return ctx("isabella", now).model_copy(update={"observations": obs})


def make(reply: object = REACT) -> tuple[LLMMind, ScriptedClient, FixedPlanner]:
    client = ScriptedClient(
        lambda prompt: reply if MARKER in prompt else {"summary": "카페 주인이다"}
    )
    planner = FixedPlanner()
    mind, _ = make_mind(client, planner=planner)
    asyncio.run(mind.next_action(ctx("isabella", DAY.replace(hour=9, minute=30), where=PARK)))
    return mind, client, planner


def judged(client: ScriptedClient) -> list[str]:
    return [p for p in client.prompts if MARKER in p]


def test_same_resident_is_not_judged_again_within_the_cooldown() -> None:
    mind, client, planner = make()
    plans = len(planner.requests)
    asyncio.run(mind.next_action(woken(after(0), seen("maria", after(0)))))
    assert len(judged(client)) == 1 and len(planner.requests) == plans + 1
    for minutes in (5, 35, REACTION_COOLDOWN_MINUTES - 1):
        now = after(minutes)
        asyncio.run(mind.next_action(woken(now, seen("maria", now, "돌아온다"))))
    assert len(judged(client)) == 1 and len(planner.requests) == plans + 1
    assert len(mind.reaction_log) == 1
    now = after(REACTION_COOLDOWN_MINUTES)
    asyncio.run(mind.next_action(woken(now, seen("maria", now, "돌아온다"))))
    assert len(judged(client)) == 2 and len(planner.requests) == plans + 2


def test_only_fresh_subjects_and_subjectless_events_reach_the_judge() -> None:
    mind, client, _ = make()
    asyncio.run(mind.next_action(woken(after(0), seen("maria", after(0)))))
    now = after(5)
    asyncio.run(
        mind.next_action(
            woken(
                now,
                seen("maria", now, "다시 온다"),
                seen("john", now, "들어온다"),
                seen(None, now, "종이 울린다"),
            )
        )
    )
    last = judged(client)[-1]
    assert len(judged(client)) == 2
    assert "john: 들어온다" in last and "마을: 종이 울린다" in last
    assert "maria: 다시 온다" not in last


def test_declined_judgement_does_not_start_a_cooldown() -> None:
    mind, client, planner = make({"react": False, "reason": "그대로"})
    plans = len(planner.requests)
    for minutes in (0, 5):
        now = after(minutes)
        asyncio.run(mind.next_action(woken(now, seen("maria", now))))
    assert len(judged(client)) == 2 and len(planner.requests) == plans
