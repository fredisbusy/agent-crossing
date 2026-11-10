"""LLM 마음의 평소 일과: 하루 계획(SPEC §7)을 지도 장소 구간으로 옮긴다.

약속 덮어쓰기는 규칙 마음과 같은 `minds.social.Agenda`가 한다.
"""

import datetime
from collections.abc import Sequence
from dataclasses import replace

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

from ..contracts import LlmPersona

WAKE_HOUR = 7
"""계획이 없을 때 일어나는 시각."""
SLEEP_HOUR = 23
"""계획이 없을 때 잠드는 시각."""
_SLEEP_WORDS = ("잠", "취침", "잔다", "자기", "sleep", "bed")


class PlannedRoutine:
    """날짜별 계획 구간. 계획이 비는 시간은 집에서 쉬거나 잔다."""

    def __init__(self, persona: LlmPersona) -> None:
        self._persona = persona
        self._entries: dict[datetime.date, tuple[tuple[Slot, DayPlanItem], ...]] = {}
        """날짜별 (구간, 그 구간을 낳은 하루 계획 항목). 시간 순."""

    def has_plan(self, day: datetime.date) -> bool:
        return day in self._entries

    def set_plan(
        self, day: datetime.date, items: Sequence[DayPlanItem]
    ) -> tuple[Slot, ...]:
        entries = sorted(
            (
                (
                    Slot(
                        resolve_place(item.location, self._persona),
                        item.action_content.strip(),
                        None,
                        slot_action(item.action_content),
                        item.start_time.replace(tzinfo=None),
                        item.end_time.replace(tzinfo=None),
                    ),
                    item,
                )
                for item in items
            ),
            key=lambda entry: entry[0].start,
        )
        self._entries[day] = tuple(entries)
        return self.slots(day)

    def slots(self, day: datetime.date) -> tuple[Slot, ...]:
        return tuple(slot for slot, _ in self._entries.get(day, ()))

    def item_for(self, slot: Slot) -> DayPlanItem | None:
        """이 구간을 낳은 하루 계획 항목. 약속·쉬기·잠 구간이면 None.

        약속 때문에 끝이 잘린 구간도 시작·장소·설명이 같으면 같은 구간으로 본다.
        """
        if slot.is_commitment:
            return None
        for planned, item in self._entries.get(slot.start.date(), ()):
            if (
                planned.start == slot.start
                and planned.location_path == slot.location_path
                and planned.description == slot.description
            ):
                return item
        return None

    def replace_from(
        self, now: datetime.datetime, items: Sequence[DayPlanItem]
    ) -> tuple[Slot, ...]:
        """지금 이후 구간을 새 항목으로 바꾼다. 이미 지난 구간은 두고 걸친 구간은 지금에서 자른다.

        관찰에 반응해 계획을 다시 세울 때 쓴다. 바뀐 항목의 분해 캐시는 `Decomposer.invalidate`로 비운다.
        """
        floor = now.replace(second=0, microsecond=0)
        kept: list[DayPlanItem] = []
        for slot, item in self._entries.get(now.date(), ()):
            if slot.end <= now:
                kept.append(item)
            elif slot.start < floor:
                kept.append(replace(item, start_time=slot.start, end_time=floor))
        for item in items:
            start = max(item.start_time.replace(tzinfo=None), floor)
            if item.end_time.replace(tzinfo=None) > start:
                kept.append(
                    replace(
                        item,
                        start_time=start,
                        end_time=item.end_time.replace(tzinfo=None),
                    )
                )
        return self.set_plan(now.date(), kept)

    def slot_at(self, now: datetime.datetime) -> Slot:
        slots = self.slots(now.date())
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
    return find_place(text, persona) or persona.home


def find_place(text: str, persona: LlmPersona) -> LocationPath | None:
    """`resolve_place`와 같되 아는 장소를 못 찾으면 집 대신 None."""
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
    return best[1] if best else None


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
    talk_notes: Sequence[str] = (),
    close_friends: Sequence[tuple[str, int]] = (),
) -> DayPlanBroadStrokesRequest:
    """하루 계획 요청. 갈 수 있는 장소·오늘 약속·기념일을 배경에 함께 싣는다.

    `talk_notes`는 대화 뒤에 정한 일, `close_friends`는 (이름, 우호도)로 가까운 사람이다(TODO 3-C).
    """
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
    for note in talk_notes:
        lines.append(f"대화에서 정한 일: {note}")
    if close_friends:
        friends = ", ".join(f"{name}(친밀도 {score}/100)" for name, score in close_friends)
        lines.append(
            f"가까운 사람: {friends}. 시간이 맞으면 이들과 보내는 시간을 계획에 넣어도 좋다."
        )
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
