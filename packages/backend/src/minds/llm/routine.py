"""LLM 마음의 평소 일과: 하루 계획(SPEC §7)을 지도 장소 구간으로 옮긴다.

약속 덮어쓰기는 규칙 마음과 같은 `minds.social.Agenda`가 한다.
"""

import datetime
from collections.abc import Sequence

from agents.planning.models import DayPlanBroadStrokesRequest, DayPlanItem
from minds.social import (
    Commitment,
    Slot,
    SlotAction,
    describe_event,
    josa,
    place_name,
)
from world.contracts import LOCATION_SEPARATOR, Holiday, LocationPath

from .contracts import LlmPersona

WAKE_HOUR = 7
"""계획이 없을 때 일어나는 시각."""
SLEEP_HOUR = 23
"""계획이 없을 때 잠드는 시각."""
_SLEEP_WORDS = ("잠", "취침", "잔다", "자기", "sleep", "bed")


class PlannedRoutine:
    """날짜별 계획 구간. 계획이 비는 시간은 집에서 쉬거나 잔다."""

    def __init__(self, persona: LlmPersona) -> None:
        self._persona = persona
        self._plans: dict[datetime.date, tuple[Slot, ...]] = {}

    def has_plan(self, day: datetime.date) -> bool:
        return day in self._plans

    def set_plan(
        self, day: datetime.date, items: Sequence[DayPlanItem]
    ) -> tuple[Slot, ...]:
        slots = sorted(
            (
                Slot(
                    resolve_place(item.location, self._persona),
                    item.action_content.strip(),
                    None,
                    slot_action(item.action_content),
                    item.start_time.replace(tzinfo=None),
                    item.end_time.replace(tzinfo=None),
                )
                for item in items
            ),
            key=lambda slot: slot.start,
        )
        self._plans[day] = tuple(slots)
        return self._plans[day]

    def slot_at(self, now: datetime.datetime) -> Slot:
        slots = self._plans.get(now.date(), ())
        for slot in slots:
            if slot.start <= now < slot.end:
                return slot
        later = [slot.start for slot in slots if slot.start > now]
        return self._rest_slot(now, min(later) if later else None)

    def _rest_slot(
        self, now: datetime.datetime, next_start: datetime.datetime | None
    ) -> Slot:
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour < WAKE_HOUR or now.hour >= SLEEP_HOUR:
            wake = day.replace(hour=WAKE_HOUR)
            if now.hour >= SLEEP_HOUR:
                wake += datetime.timedelta(days=1)
            end = min(wake, next_start) if next_start else wake
            return Slot(self._persona.home, "잠든다", "😴", "sleep", now, end)
        bedtime = day.replace(hour=SLEEP_HOUR)
        end = min(bedtime, next_start) if next_start else bedtime
        return Slot(self._persona.home, "집에서 쉰다", "🏠", "idle", now, end)


def resolve_place(text: str, persona: LlmPersona) -> LocationPath:
    """계획의 장소 문장을 아는 위치 경로로. 가장 구체적으로 맞는 경로, 없으면 집."""
    wanted = text.strip().lower()
    places = persona.known_places
    for path in places:
        if path.lower() == wanted or place_name(path).lower() == wanted:
            return path
    korean = [p for p in places if place_name(p).lower() in wanted]
    if korean:
        return max(korean, key=lambda p: (len(place_name(p)), -len(p)))
    best: tuple[tuple[int, int, int], LocationPath] | None = None
    for path in places:
        segments = [seg.lower() for seg in path.split(LOCATION_SEPARATOR)[1:]]
        hits = [i for i, seg in enumerate(segments) if seg in wanted]
        if not hits:
            continue
        score = (len(hits), max(hits), -len(segments))
        if best is None or score > best[0]:
            best = (score, path)
    return best[1] if best else persona.home


def slot_action(content: str) -> SlotAction:
    lowered = content.lower()
    return "sleep" if any(word in lowered for word in _SLEEP_WORDS) else "idle"


def plan_request(
    persona: LlmPersona,
    now: datetime.datetime,
    *,
    commitments: Sequence[Commitment],
    holidays: Sequence[Holiday],
    yesterday: str,
    summary: str = "",
) -> DayPlanBroadStrokesRequest:
    """하루 계획 요청. 갈 수 있는 장소·오늘 약속·기념일을 배경에 함께 싣는다."""
    lines = [summary] if summary and summary != " ".join(persona.identity) else []
    lines += persona.identity
    places = ", ".join(_plan_places(persona))
    lines.append(
        f"Use exactly one of these place names as each item's location: {places}."
    )
    lines.append("Write every action_content in natural Korean (한국어로 쓴다).")
    for holiday in holidays:
        today_is = josa(holiday.name, "이다", "다")
        lines.append(f"오늘은 {today_is}. {' '.join(holiday.customs)}".strip())
    today = [c for c in commitments if c.event.start_time.date() == now.date()]
    for commitment in today:
        role = "연다" if commitment.role == "host" else "참석하기로 했다"
        lines.append(f"약속: {describe_event(commitment.event, now)} ({role})")
    return DayPlanBroadStrokesRequest(
        agent_name=persona.display_name,
        age=persona.age,
        innate_traits=list(persona.identity[:1]) or [persona.display_name],
        persona_background=" ".join(lines),
        yesterday_date=now - datetime.timedelta(days=1),
        yesterday_summary=yesterday or "평소처럼 하루를 보냈다.",
        today_date=now,
    )


def _plan_places(persona: LlmPersona) -> tuple[str, ...]:
    """계획 프롬프트에 싣는 장소 이름(방 단계까지, 중복 제거)."""
    names: list[str] = []
    for path in persona.known_places:
        parts = path.split(LOCATION_SEPARATOR)
        if 2 <= len(parts) <= 3:
            name = place_name(path)
            if name not in names:
                names.append(name)
    return tuple(names)
