"""하루 계획 → 시간 → 5~15분 단위의 just-in-time 분해 (논문 §4.3, SPEC §7, §12).

마음이 깨어날 때 지금 시각이 속한 하루 계획 항목만 내려간다.
- 시간 단위 계획: 하루 계획 항목당 1회 만들어 캐시한다.
- 분 단위 계획: 시간 단위 항목당 만들어 캐시하고, 계획 범위를 지나쳤는데 아직 그 항목 안이면 지금부터 다시 만든다.
- 생성이 실패해도(빈 결과 포함) 캐시해서 같은 항목을 매 틱 다시 부르지 않는다. 실패하면 하루 계획 구간 그대로 쓴다.
결과는 기억에 저장하지 않는다(논문 구현도 scratch에만 둔다).
"""

import datetime
from dataclasses import dataclass, replace
from typing import TypeVar

from agents.planning import (
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
    select_hourly_plan,
    select_minute_plan,
)
from minds.social import Slot
from world.contracts import LOCATION_SEPARATOR, LocationPath

from ..contracts import DayPlanner, LlmPersona
from .routine import find_place

HOURLY_CALLS_PER_DAY_ITEM = 1
"""하루 계획 항목 하나를 시간 단위로 쪼개는 호출 수."""
MINUTE_CALLS_PER_HOURLY_ITEM = 2
"""시간 단위 항목 하나(60~90분)를 분 단위로 쪼개는 호출 수. 분 계획은 앞으로 60~90분을 낸다."""
MAX_MINUTE_CALLS_PER_HOURLY_ITEM = 3
"""한 시간 단위 항목에서 분 계획을 만드는 호출 수의 상한. 넘으면 하루 계획 구간으로 대체한다."""
BUILDING_DEPTH = 2
"""같은 건물로 보는 위치 경로 앞부분 단계 수 (마을 > 건물)."""
_NaiveT = TypeVar("_NaiveT", DayPlanItem, HourlyPlanItem, MinutePlanItem)
_RECOVERABLE = (RuntimeError, TimeoutError, ValueError)


@dataclass
class _MinuteCache:
    items: list[MinutePlanItem]
    covered_until: datetime.datetime
    calls: int


class Decomposer:
    """동기 호출을 한다. `asyncio.to_thread` 안에서 부른다."""

    def __init__(self, planner: DayPlanner, persona: LlmPersona) -> None:
        self._planner = planner
        self._persona = persona
        self._hourly: dict[DayPlanItem, list[HourlyPlanItem]] = {}
        self._minutes: dict[HourlyPlanItem, _MinuteCache] = {}

    def refine(self, slot: Slot, item: DayPlanItem, now: datetime.datetime) -> Slot:
        """하루 계획 구간을 지금의 분 단위 행동 구간으로 좁힌다. 못 하면 구간 그대로."""
        item = _naive(item)
        self._drop_before(now.date())
        block = select_hourly_plan(
            self._hourly_items(item, now), current_time=now
        ).current
        if block is None:
            return slot
        if block.start_time > now:
            return _until(slot, block.start_time)
        minutes = self._minute_items(block, now).items
        selection = select_minute_plan(minutes, current_time=now)
        step = selection.active
        if step is None:
            nxt = selection.next
            return _until(slot, nxt.start_time if nxt else block.end_time)
        return Slot(
            self._place(step.location, slot),
            step.action_content.strip(),
            slot.emoji,
            slot.action,
            step.start_time,
            min(step.end_time, slot.end),
        )

    def invalidate(self, since: datetime.datetime | None = None) -> None:
        """분해 캐시를 비운다. `since`를 주면 그 시각 이후에 끝나는 항목만 비운다.

        계획을 다시 세운 뒤(`PlannedRoutine.replace_from`) 낡은 분해를 버릴 때 쓴다.
        """
        since = since.replace(tzinfo=None) if since else None
        if since is None:
            self._hourly.clear()
            self._minutes.clear()
            return
        self._hourly = {k: v for k, v in self._hourly.items() if k.end_time <= since}
        self._minutes = {k: v for k, v in self._minutes.items() if k.end_time <= since}

    # --- 생성·캐시 --------------------------------------------------------------

    def _hourly_items(
        self, item: DayPlanItem, now: datetime.datetime
    ) -> list[HourlyPlanItem]:
        if item not in self._hourly:
            self._hourly[item] = self._generate_hourly(
                item, max(now, item.start_time.replace(tzinfo=None))
            )
        return self._hourly[item]

    def _generate_hourly(
        self, item: DayPlanItem, at: datetime.datetime
    ) -> list[HourlyPlanItem]:
        try:
            made = self._planner.generate_hourly_plan(
                agent_name=self._persona.display_name,
                current_time=at,
                day_plan_item=item,
            )
        except _RECOVERABLE:
            return []
        items = [_naive(h) for h in made]
        return sorted(
            (
                h
                for h in items
                if h.end_time > item.start_time and h.start_time < item.end_time
            ),
            key=lambda h: h.start_time,
        )

    def _minute_items(
        self, block: HourlyPlanItem, now: datetime.datetime
    ) -> _MinuteCache:
        cache = self._minutes.get(block)
        if cache is None:
            cache = self._generate_minutes(block, max(now, block.start_time), 0)
        elif (
            now >= cache.covered_until
            and now < block.end_time
            and cache.calls < MAX_MINUTE_CALLS_PER_HOURLY_ITEM
        ):
            cache = self._generate_minutes(block, now, cache.calls)
        self._minutes[block] = cache
        return cache

    def _generate_minutes(
        self, block: HourlyPlanItem, at: datetime.datetime, calls: int
    ) -> _MinuteCache:
        try:
            made = self._planner.generate_minute_plan(
                agent_name=self._persona.display_name,
                current_time=at,
                hourly_plan_item=block,
            )
        except _RECOVERABLE:
            made = []
        items = sorted(
            (
                m
                for m in map(_naive, made)
                if m.end_time > block.start_time and m.start_time < block.end_time
            ),
            key=lambda m: m.start_time,
        )
        covered = max((m.end_time for m in items), default=block.end_time)
        if covered <= at:
            covered = block.end_time
        return _MinuteCache(items, covered, calls + 1)

    # --- 위치 -------------------------------------------------------------------

    def _place(self, text: str, slot: Slot) -> LocationPath:
        """분 단위 장소가 하루 계획 구간과 같은 건물 안의 아는 장소일 때만 쓴다."""
        found = find_place(text, self._persona)
        if found is not None and _building(found) == _building(slot.location_path):
            return found
        return slot.location_path

    def _drop_before(self, day: datetime.date) -> None:
        """지난 날짜 항목의 캐시를 버린다."""
        self._hourly = {
            k: v for k, v in self._hourly.items() if k.end_time.date() >= day
        }
        self._minutes = {
            k: v for k, v in self._minutes.items() if k.end_time.date() >= day
        }


def _building(path: LocationPath) -> str:
    return LOCATION_SEPARATOR.join(path.split(LOCATION_SEPARATOR)[:BUILDING_DEPTH])


def _until(slot: Slot, limit: datetime.datetime) -> Slot:
    """구간을 limit까지로 줄인다(그때 다시 깨어나 분해한다)."""
    return replace(slot, end=min(slot.end, limit)) if limit > slot.start else slot


def _naive(item: _NaiveT) -> _NaiveT:
    return replace(
        item,
        start_time=item.start_time.replace(tzinfo=None),
        end_time=item.end_time.replace(tzinfo=None),
    )
