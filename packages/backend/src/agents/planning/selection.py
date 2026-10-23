"""계획 항목 목록에서 지금 진행 중인(active)·다음(next) 항목을 고르는 순수 함수."""

import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .models import HourlyPlanItem, MinutePlanItem


class PlanWindow(Protocol):
    @property
    def start_time(self) -> datetime.datetime: ...

    @property
    def end_time(self) -> datetime.datetime: ...

    @property
    def location(self) -> str: ...

    @property
    def action_content(self) -> str: ...


PlanItemT = TypeVar("PlanItemT", bound=PlanWindow)


@dataclass(frozen=True)
class PlanSelection(Generic[PlanItemT]):
    active: PlanItemT | None
    current: PlanItemT | None
    next: PlanItemT | None


def select_plan_items(
    items: Sequence[PlanItemT],
    *,
    current_time: datetime.datetime,
) -> PlanSelection[PlanItemT]:
    ordered_items = sorted(items, key=lambda item: item.start_time)
    active: PlanItemT | None = None
    next_item: PlanItemT | None = None

    for item in ordered_items:
        if item.start_time <= current_time < item.end_time:
            active = item
            continue
        if item.start_time > current_time and next_item is None:
            next_item = item

    current = active if active is not None else next_item
    if active is not None:
        next_item = _find_next_plan_item(ordered_items, after=active)
    return PlanSelection(active=active, current=current, next=next_item)


def select_hourly_plan(
    items: list[HourlyPlanItem],
    *,
    current_time: datetime.datetime,
) -> PlanSelection[HourlyPlanItem]:
    return select_plan_items(items, current_time=current_time)


def select_minute_plan(
    items: list[MinutePlanItem],
    *,
    current_time: datetime.datetime,
) -> PlanSelection[MinutePlanItem]:
    return select_plan_items(items, current_time=current_time)


def _find_next_plan_item(
    items: Sequence[PlanItemT],
    *,
    after: PlanItemT,
) -> PlanItemT | None:
    for item in items:
        if item.start_time >= after.end_time:
            return item
    return None
