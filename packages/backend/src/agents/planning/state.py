import datetime
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Generic, Protocol, TypeVar, overload

from agents.agent import AgentIdentity, AgentProfile

from .models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)


class PlanWindow(Protocol):
    @property
    def start_time(self) -> datetime.datetime: ...

    @property
    def end_time(self) -> datetime.datetime: ...

    @property
    def location(self) -> str: ...

    @property
    def action_content(self) -> str: ...


class MutablePlanWindow(Protocol):
    start_time: datetime.datetime
    end_time: datetime.datetime
    location: str
    action_content: str


PlanItemT = TypeVar("PlanItemT", bound=PlanWindow)


@dataclass(frozen=True)
class PlanSelection(Generic[PlanItemT]):
    active: PlanItemT | None
    current: PlanItemT | None
    next: PlanItemT | None


class PlanningRunner(Protocol):
    def generate_day_plan(
        self,
        request: DayPlanBroadStrokesRequest,
    ) -> list[DayPlanItem]: ...

    def generate_hourly_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]: ...

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]: ...


@dataclass
class AgentPlanState:
    day_items: list[DayPlanItem] = field(default_factory=list)
    hourly_items: list[HourlyPlanItem] = field(default_factory=list)
    minute_items: list[MinutePlanItem] = field(default_factory=list)
    active_day_key: tuple[datetime.datetime, datetime.datetime] | None = None
    active_hour_key: tuple[datetime.datetime, datetime.datetime] | None = None


@dataclass(frozen=True)
class PlanTickContext:
    current_plan_item: MinutePlanItem | None
    next_plan_item: MinutePlanItem | None
    plan_updated: bool
    replan_reason: str


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


def select_day_plan(
    items: list[DayPlanItem],
    *,
    current_time: datetime.datetime,
) -> PlanSelection[DayPlanItem]:
    return select_plan_items(items, current_time=current_time)


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


def current_minute_plan_context(
    selection: PlanSelection[MinutePlanItem],
) -> list[str]:
    context: list[str] = []
    if selection.current is not None:
        context.append(selection.current.action_content)
    if (
        selection.next is not None
        and selection.current is not None
        and selection.next.action_content != selection.current.action_content
    ):
        context.append(selection.next.action_content)
    return context


def format_plan_memory_content(
    *,
    agent_name: str,
    current_time: datetime.datetime,
    day_item: DayPlanItem | None,
    hourly_item: HourlyPlanItem | None,
    minute_item: MinutePlanItem | None,
) -> str:
    lines = [
        f"time={current_time.isoformat()}",
        f"agent={agent_name}",
    ]
    if day_item is not None:
        lines.append("active_day_plan=" + _format_plan_window(day_item))
    if hourly_item is not None:
        lines.append("active_hourly_plan=" + _format_plan_window(hourly_item))
    if minute_item is not None:
        lines.append("current_minute_plan=" + _format_plan_window(minute_item))
    return "\n".join(lines)


@overload
def select_active_item(
    items: list[DayPlanItem],
    current_time: datetime.datetime,
) -> DayPlanItem | None: ...


@overload
def select_active_item(
    items: list[HourlyPlanItem],
    current_time: datetime.datetime,
) -> HourlyPlanItem | None: ...


@overload
def select_active_item(
    items: list[MinutePlanItem],
    current_time: datetime.datetime,
) -> MinutePlanItem | None: ...


def select_active_item(
    items: list[DayPlanItem] | list[HourlyPlanItem] | list[MinutePlanItem],
    current_time: datetime.datetime,
) -> DayPlanItem | HourlyPlanItem | MinutePlanItem | None:
    if not items:
        return None

    ordered_items = sorted(items, key=lambda item: item.start_time)
    for item in ordered_items:
        if item.start_time <= current_time < item.end_time:
            return item

    for item in ordered_items:
        if current_time < item.start_time:
            return item

    return ordered_items[-1]


def select_next_item(
    items: list[MinutePlanItem],
    current_time: datetime.datetime,
) -> MinutePlanItem | None:
    for item in sorted(items, key=lambda value: value.start_time):
        if item.start_time > current_time:
            return item
    return None


def ensure_tick_plan_context(
    *,
    state: AgentPlanState,
    planner: PlanningRunner | None,
    agent_identity: AgentIdentity,
    profile: AgentProfile,
    current_time: datetime.datetime,
) -> PlanTickContext:
    if not state.day_items:
        state.day_items = _generate_day_items(
            planner=planner,
            agent_identity=agent_identity,
            profile=profile,
            current_time=current_time,
        )

    active_day = select_active_item(state.day_items, current_time)
    if active_day is None:
        _sync_profile_plan_context(profile=profile, current_plan_item=None)
        return PlanTickContext(
            current_plan_item=None,
            next_plan_item=None,
            plan_updated=False,
            replan_reason="no_day_plan",
        )

    day_key = _plan_key(active_day)
    if not state.hourly_items or state.active_day_key != day_key:
        state.hourly_items = _generate_hourly_items(
            planner=planner,
            agent_name=agent_identity.name,
            current_time=current_time,
            day_plan_item=active_day,
        )
        state.active_day_key = day_key

    active_hour = select_active_item(state.hourly_items, current_time)
    if active_hour is None:
        _sync_profile_plan_context(profile=profile, current_plan_item=None)
        return PlanTickContext(
            current_plan_item=None,
            next_plan_item=None,
            plan_updated=False,
            replan_reason="no_hourly_plan",
        )

    hour_key = _plan_key(active_hour)
    if not state.minute_items or state.active_hour_key != hour_key:
        state.minute_items = _generate_minute_items(
            planner=planner,
            agent_name=agent_identity.name,
            current_time=current_time,
            hourly_plan_item=active_hour,
        )
        state.active_hour_key = hour_key

    current_plan_item = select_active_item(state.minute_items, current_time)
    next_plan_item = select_next_item(state.minute_items, current_time)
    _sync_profile_plan_context(profile=profile, current_plan_item=current_plan_item)
    return PlanTickContext(
        current_plan_item=current_plan_item,
        next_plan_item=next_plan_item,
        plan_updated=False,
        replan_reason="",
    )


def update_current_plan_for_dialogue(
    *,
    state: AgentPlanState,
    profile: AgentProfile,
    current_time: datetime.datetime,
    partner_name: str | None,
    latest_partner_utterance: str | None,
) -> PlanTickContext:
    if not latest_partner_utterance or not latest_partner_utterance.strip():
        current_plan_item = select_active_item(state.minute_items, current_time)
        next_plan_item = select_next_item(state.minute_items, current_time)
        _sync_profile_plan_context(profile=profile, current_plan_item=current_plan_item)
        return PlanTickContext(
            current_plan_item=current_plan_item,
            next_plan_item=next_plan_item,
            plan_updated=False,
            replan_reason="",
        )

    start_time = _floor_to_minute(current_time)
    end_time = start_time + datetime.timedelta(minutes=10)
    current_plan_item = select_active_item(state.minute_items, current_time)
    location = (
        current_plan_item.location
        if current_plan_item is not None
        else "Town > Morning Dew Cafe > Counter"
    )
    partner_text = partner_name or "the conversation partner"
    replacement_item = MinutePlanItem(
        start_time=start_time,
        end_time=end_time,
        location=location,
        action_content=(
            f"Continue the open conversation with {partner_text}, respond to the "
            "new information, and let it shape the next few minutes."
        ),
    )
    state.minute_items = [
        item for item in state.minute_items if item.end_time <= start_time
    ]
    state.minute_items.append(replacement_item)
    next_plan_item = select_next_item(state.minute_items, current_time)
    _sync_profile_plan_context(profile=profile, current_plan_item=replacement_item)
    return PlanTickContext(
        current_plan_item=replacement_item,
        next_plan_item=next_plan_item,
        plan_updated=True,
        replan_reason="dialogue_partner_utterance",
    )


def format_plan_item(item: MinutePlanItem | None) -> str:
    if item is None:
        return ""
    return (
        f"{item.start_time.isoformat()} -> {item.end_time.isoformat()} | "
        f"{item.location} | {item.action_content}"
    )


def _generate_day_items(
    *,
    planner: PlanningRunner | None,
    agent_identity: AgentIdentity,
    profile: AgentProfile,
    current_time: datetime.datetime,
) -> list[DayPlanItem]:
    if planner is not None:
        persona_background = " | ".join(profile.extended.lifestyle_and_routine)
        if not persona_background.strip():
            persona_background = "No background summary available."
        generated = planner.generate_day_plan(
            DayPlanBroadStrokesRequest(
                agent_name=agent_identity.name,
                age=agent_identity.age,
                innate_traits=list(agent_identity.traits),
                persona_background=persona_background,
                yesterday_date=current_time - datetime.timedelta(days=1),
                yesterday_summary="No recorded activity summary.",
                today_date=current_time,
            )
        )
        if generated:
            return generated

    return [_synthetic_day_item(profile=profile, current_time=current_time)]


def _generate_hourly_items(
    *,
    planner: PlanningRunner | None,
    agent_name: str,
    current_time: datetime.datetime,
    day_plan_item: DayPlanItem,
) -> list[HourlyPlanItem]:
    if planner is not None:
        generated = planner.generate_hourly_plan(
            agent_name=agent_name,
            current_time=current_time,
            day_plan_item=day_plan_item,
        )
        if generated:
            return generated

    return [
        HourlyPlanItem(
            start_time=day_plan_item.start_time,
            end_time=day_plan_item.end_time,
            location=day_plan_item.location,
            action_content=day_plan_item.action_content,
        )
    ]


def _generate_minute_items(
    *,
    planner: PlanningRunner | None,
    agent_name: str,
    current_time: datetime.datetime,
    hourly_plan_item: HourlyPlanItem,
) -> list[MinutePlanItem]:
    if planner is not None:
        generated = planner.generate_minute_plan(
            agent_name=agent_name,
            current_time=current_time,
            hourly_plan_item=hourly_plan_item,
        )
        if generated:
            return generated

    start_time = max(_floor_to_minute(current_time), hourly_plan_item.start_time)
    end_time = min(start_time + datetime.timedelta(minutes=10), hourly_plan_item.end_time)
    if (end_time - start_time).total_seconds() < 5 * 60:
        end_time = start_time + datetime.timedelta(minutes=10)
    return [
        MinutePlanItem(
            start_time=start_time,
            end_time=end_time,
            location=hourly_plan_item.location,
            action_content=hourly_plan_item.action_content,
        )
    ]


def _synthetic_day_item(
    *, profile: AgentProfile, current_time: datetime.datetime
) -> DayPlanItem:
    start_time = _floor_to_minute(current_time)
    action_content = (
        profile.extended.current_plan_context[0]
        if profile.extended.current_plan_context
        else "Continue the current routine."
    )
    return DayPlanItem(
        start_time=start_time,
        end_time=start_time + datetime.timedelta(hours=1),
        location="Town > Morning Dew Cafe > Counter",
        action_content=action_content,
    )


def _sync_profile_plan_context(
    *, profile: AgentProfile, current_plan_item: MinutePlanItem | None
) -> None:
    if current_plan_item is None:
        return
    if profile.extended.current_plan_context:
        profile.extended.current_plan_context[0] = current_plan_item.action_content
    else:
        profile.extended.current_plan_context.append(current_plan_item.action_content)


def _plan_key(
    item: DayPlanItem | HourlyPlanItem | MinutePlanItem,
) -> tuple[datetime.datetime, datetime.datetime]:
    return (item.start_time, item.end_time)


def _floor_to_minute(value: datetime.datetime) -> datetime.datetime:
    return value.replace(second=0, microsecond=0)


def _find_next_plan_item(
    items: list[PlanItemT],
    *,
    after: PlanItemT,
) -> PlanItemT | None:
    for item in items:
        if item.start_time >= after.end_time:
            return item
    return None


def _format_plan_window(item: PlanWindow) -> str:
    return (
        f"{item.start_time.isoformat()}..{item.end_time.isoformat()} "
        f"@ {item.location}: {item.action_content}"
    )
