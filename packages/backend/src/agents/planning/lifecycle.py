from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from agents.agent import AgentIdentity, AgentProfile

from .models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)

CANONICAL_LOCATIONS: tuple[str, ...] = (
    "Briar Cove > Rose Cottage",
    "Briar Cove > Sage Cottage",
    "Briar Cove > The Honey Cup",
    "Briar Cove > Story House",
    "Briar Cove > Willow Market",
    "Briar Cove > Moonflower Park",
    "Briar Cove > Town Square",
)


class LifePlanner(Protocol):
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


class LifeAgent(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def identity(self) -> AgentIdentity: ...

    @property
    def profile(self) -> AgentProfile: ...

    @property
    def brain(self) -> "LifeBrain": ...


class LifeBrain(Protocol):
    planner: LifePlanner | None


@dataclass(frozen=True)
class PlanItemSnapshot:
    start_time: datetime.datetime
    end_time: datetime.datetime
    location: str
    action_content: str


@dataclass(frozen=True)
class AgentPlanSnapshot:
    agent_id: str
    day_plan: tuple[PlanItemSnapshot, ...]
    active_day: PlanItemSnapshot
    active_hourly: PlanItemSnapshot
    active_minute: PlanItemSnapshot
    last_replan_reason: str


@dataclass
class _AgentPlanState:
    plan_date: datetime.date | None = None
    day_items: list[DayPlanItem] = field(default_factory=list)
    hourly_items: list[HourlyPlanItem] = field(default_factory=list)
    minute_items: list[MinutePlanItem] = field(default_factory=list)
    hourly_parent_key: tuple[datetime.datetime, datetime.datetime] | None = None
    minute_parent_key: tuple[datetime.datetime, datetime.datetime] | None = None
    last_replan_reason: str = "initial_day"


PlanItemT = TypeVar("PlanItemT", DayPlanItem, HourlyPlanItem, MinutePlanItem)


class PlanningCoordinator:
    """Owns the live day/hour/minute schedule for every simulation agent."""

    def __init__(self) -> None:
        self._states: dict[str, _AgentPlanState] = {}

    def bootstrap(
        self, *, agent: LifeAgent, now: datetime.datetime
    ) -> AgentPlanSnapshot:
        """Install a deterministic schedule so the world never waits for an LLM."""
        agent_id = str(agent.identity.id)
        day_items = _fallback_day_plan(agent_id=agent_id, date=now.date())
        return self._install_hierarchy(
            agent=agent,
            now=now,
            day_items=day_items,
            reason="deterministic_bootstrap",
        )

    def refresh_current(
        self, *, agent: LifeAgent, now: datetime.datetime
    ) -> AgentPlanSnapshot:
        """Generate an LLM-authored hierarchy and atomically replace the fallback."""
        planner = agent.brain.planner
        if planner is None:
            return self.bootstrap(agent=agent, now=now)
        day_items = self._generate_day_plan(planner=planner, agent=agent, now=now)
        active_day = _active_or_next(day_items, now)
        hourly_items = _fallback_hourly(active_day)
        active_hourly = _active_or_next(hourly_items, now)
        minute_items = _fallback_minute(active_hourly)
        state = _AgentPlanState(
            plan_date=now.date(),
            day_items=day_items,
            hourly_items=hourly_items,
            minute_items=minute_items,
            hourly_parent_key=(active_day.start_time, active_day.end_time),
            minute_parent_key=(active_hourly.start_time, active_hourly.end_time),
            last_replan_reason="llm_refresh",
        )
        self._states[str(agent.identity.id)] = state
        return _state_snapshot(agent=agent, state=state, now=now)

    def _install_hierarchy(
        self,
        *,
        agent: LifeAgent,
        now: datetime.datetime,
        day_items: list[DayPlanItem],
        reason: str,
    ) -> AgentPlanSnapshot:
        active_day = _active_or_next(day_items, now)
        hourly_items = _fallback_hourly(active_day)
        active_hourly = _active_or_next(hourly_items, now)
        minute_items = _fallback_minute(active_hourly)
        state = _AgentPlanState(
            plan_date=now.date(),
            day_items=day_items,
            hourly_items=hourly_items,
            minute_items=minute_items,
            hourly_parent_key=(active_day.start_time, active_day.end_time),
            minute_parent_key=(active_hourly.start_time, active_hourly.end_time),
            last_replan_reason=reason,
        )
        self._states[str(agent.identity.id)] = state
        return _state_snapshot(agent=agent, state=state, now=now)

    def ensure_current(
        self,
        *,
        agent: LifeAgent,
        now: datetime.datetime,
        generate: bool = True,
    ) -> AgentPlanSnapshot:
        agent_id = str(agent.identity.id)
        state = self._states.setdefault(agent_id, _AgentPlanState())
        planner = agent.brain.planner
        if planner is None:
            raise RuntimeError(f"agent {agent_id} does not have a planner")

        if state.plan_date != now.date() or not state.day_items:
            state.day_items = (
                self._generate_day_plan(planner=planner, agent=agent, now=now)
                if generate
                else _fallback_day_plan(agent_id=agent_id, date=now.date())
            )
            state.plan_date = now.date()
            state.hourly_items = []
            state.minute_items = []
            state.hourly_parent_key = None
            state.minute_parent_key = None
            state.last_replan_reason = "day_rollover"

        active_day = _active_or_next(state.day_items, now)
        day_key = (active_day.start_time, active_day.end_time)
        if state.hourly_parent_key != day_key or not state.hourly_items:
            try:
                if not generate:
                    raise RuntimeError("synchronous generation disabled")
                generated_hourly = planner.generate_hourly_plan(
                    agent_name=agent.name,
                    current_time=now,
                    day_plan_item=active_day,
                )
            except Exception:
                generated_hourly = []
            state.hourly_items = [
                item
                for item in _children_within(generated_hourly, active_day)
                if item.duration_minutes >= 5
            ]
            if not state.hourly_items:
                state.hourly_items = _fallback_hourly(active_day)
            state.hourly_parent_key = day_key
            state.minute_items = []
            state.minute_parent_key = None
            state.last_replan_reason = "active_day_changed"

        active_hourly = _active_or_next(state.hourly_items, now)
        hourly_key = (active_hourly.start_time, active_hourly.end_time)
        active_minute = _active_or_none(state.minute_items, now)
        if state.minute_parent_key != hourly_key or active_minute is None:
            try:
                if not generate:
                    raise RuntimeError("synchronous generation disabled")
                generated_minute = planner.generate_minute_plan(
                    agent_name=agent.name,
                    current_time=now,
                    hourly_plan_item=active_hourly,
                )
            except Exception:
                generated_minute = []
            state.minute_items = _children_within(generated_minute, active_hourly)
            if not state.minute_items:
                state.minute_items = _fallback_minute(active_hourly)
            state.minute_parent_key = hourly_key
            state.last_replan_reason = "active_hour_changed"
            active_minute = _active_or_next(state.minute_items, now)

        return _state_snapshot(agent=agent, state=state, now=now)

    def _generate_day_plan(
        self,
        *,
        planner: LifePlanner,
        agent: LifeAgent,
        now: datetime.datetime,
    ) -> list[DayPlanItem]:
        background_parts = [
            *agent.profile.fixed.identity_stable_set,
            *agent.profile.extended.lifestyle_and_routine,
        ]
        background_parts.append(
            "사용 가능한 장소는 다음뿐이다: " + ", ".join(CANONICAL_LOCATIONS)
        )
        try:
            generated = planner.generate_day_plan(
                DayPlanBroadStrokesRequest(
                    agent_name=agent.name,
                    age=int(agent.identity.age),
                    innate_traits=list(agent.identity.traits),
                    persona_background=" | ".join(background_parts),
                    yesterday_date=now - datetime.timedelta(days=1),
                    yesterday_summary="평소 일과를 지키며 마을 사람들과 자연스럽게 교류했다.",
                    today_date=now,
                )
            )
        except Exception:
            generated = []
        if generated and all(
            item.location in CANONICAL_LOCATIONS and item.duration_minutes >= 5
            for item in generated
        ):
            return generated
        return _fallback_day_plan(agent_id=str(agent.identity.id), date=now.date())


def _snapshot(
    item: DayPlanItem | HourlyPlanItem | MinutePlanItem,
) -> PlanItemSnapshot:
    return PlanItemSnapshot(
        start_time=item.start_time,
        end_time=item.end_time,
        location=item.location,
        action_content=item.action_content,
    )


def _state_snapshot(
    *, agent: LifeAgent, state: _AgentPlanState, now: datetime.datetime
) -> AgentPlanSnapshot:
    active_day = _active_or_next(state.day_items, now)
    active_hourly = _active_or_next(state.hourly_items, now)
    active_minute = _active_or_next(state.minute_items, now)
    agent.profile.extended.current_plan_context = [
        active_minute.action_content,
        active_hourly.action_content,
        active_day.action_content,
    ]
    return AgentPlanSnapshot(
        agent_id=str(agent.identity.id),
        day_plan=tuple(_snapshot(item) for item in state.day_items),
        active_day=_snapshot(active_day),
        active_hourly=_snapshot(active_hourly),
        active_minute=_snapshot(active_minute),
        last_replan_reason=state.last_replan_reason,
    )


def _active_or_none(items: list[PlanItemT], now: datetime.datetime) -> PlanItemT | None:
    return next(
        (item for item in items if item.start_time <= now < item.end_time),
        None,
    )


def _active_or_next(items: list[PlanItemT], now: datetime.datetime) -> PlanItemT:
    active = _active_or_none(items, now)
    if active is not None:
        return active
    future = next((item for item in items if item.start_time > now), None)
    if future is not None:
        return future
    if not items:
        raise ValueError("plan items must not be empty")
    return items[-1]


def _children_within(
    items: list[PlanItemT],
    parent: DayPlanItem | HourlyPlanItem,
) -> list[PlanItemT]:
    return [
        item
        for item in items
        if item.start_time >= parent.start_time and item.end_time <= parent.end_time
    ]


def _fallback_hourly(parent: DayPlanItem) -> list[HourlyPlanItem]:
    items: list[HourlyPlanItem] = []
    cursor = parent.start_time
    while cursor < parent.end_time:
        end = min(cursor + datetime.timedelta(minutes=60), parent.end_time)
        items.append(
            HourlyPlanItem(
                start_time=cursor,
                end_time=end,
                location=parent.location,
                action_content=parent.action_content,
            )
        )
        cursor = end
    return items


def _fallback_minute(parent: HourlyPlanItem) -> list[MinutePlanItem]:
    items: list[MinutePlanItem] = []
    cursor = parent.start_time
    while cursor < parent.end_time:
        remaining = int((parent.end_time - cursor).total_seconds() // 60)
        duration = min(15, remaining)
        if duration < 5:
            if items:
                previous = items.pop()
                combined_minutes = int(
                    (parent.end_time - previous.start_time).total_seconds() // 60
                )
                first_duration = combined_minutes // 2
                split_time = previous.start_time + datetime.timedelta(
                    minutes=first_duration
                )
                items.append(
                    MinutePlanItem(
                        start_time=previous.start_time,
                        end_time=split_time,
                        location=previous.location,
                        action_content=previous.action_content,
                    )
                )
                items.append(
                    MinutePlanItem(
                        start_time=split_time,
                        end_time=parent.end_time,
                        location=previous.location,
                        action_content=previous.action_content,
                    )
                )
            break
        end = cursor + datetime.timedelta(minutes=duration)
        items.append(
            MinutePlanItem(
                start_time=cursor,
                end_time=end,
                location=parent.location,
                action_content=parent.action_content,
            )
        )
        cursor = end
    return items


def _fallback_day_plan(*, agent_id: str, date: datetime.date) -> list[DayPlanItem]:
    is_jiho = agent_id.lower() == "jiho"
    home = "Briar Cove > Rose Cottage" if is_jiho else "Briar Cove > Sage Cottage"
    work = "Briar Cove > Story House" if is_jiho else "Briar Cove > The Honey Cup"
    schedule = [
        (0, 0, 6, 0, home, "집에서 잠을 자며 하루를 준비한다."),
        (6, 0, 8, 0, home, "아침을 준비하고 오늘 할 일을 차분히 정리한다."),
        (8, 0, 12, 0, work, "오전 업무를 집중해서 수행한다."),
        (12, 0, 13, 0, "Briar Cove > Town Square", "점심을 먹고 광장을 산책한다."),
        (13, 0, 18, 0, work, "오후 업무를 마치고 저녁 일정을 준비한다."),
        (
            18,
            0,
            20,
            0,
            "Briar Cove > The Honey Cup",
            "수진과 편안하게 시간을 보내며 마음을 서두르지 않고 대화한다."
            if is_jiho
            else "지호와 친구로서 편안하게 이야기하며 카페를 정리한다.",
        ),
        (20, 0, 0, 0, home, "집에서 하루를 돌아보고 쉬다가 잠자리에 든다."),
    ]
    return [
        DayPlanItem(
            start_time=datetime.datetime.combine(
                date, datetime.time(start_hour, start_minute)
            ),
            end_time=(
                datetime.datetime.combine(date, datetime.time(end_hour, end_minute))
                if end_hour != 0 or end_minute != 0
                else datetime.datetime.combine(
                    date + datetime.timedelta(days=1), datetime.time()
                )
            ),
            location=location,
            action_content=action,
        )
        for start_hour, start_minute, end_hour, end_minute, location, action in schedule
    ]
