from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from agents.agent import AgentIdentity, AgentProfile

from .models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)
from persistence.contracts import PlanItemSave, PlanningStateSave

CANONICAL_LOCATIONS: tuple[str, ...] = (
    "브라이어 코브 > 지호의 집",
    "브라이어 코브 > 수진의 집",
    "브라이어 코브 > 허니컵 카페",
    "브라이어 코브 > 스토리하우스 도서관",
    "브라이어 코브 > 버드나무 시장",
    "브라이어 코브 > 달맞이꽃 공원",
    "브라이어 코브 > 마을 광장",
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


class PlanningGenerationError(RuntimeError):
    """Raised when an authoritative LLM plan cannot be generated or validated."""


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
        self._lock: threading.RLock = threading.RLock()

    def export_state(self, *, agent_id: str) -> PlanningStateSave | None:
        with self._lock:
            state = self._states.get(agent_id)
            if state is None:
                return None
            return PlanningStateSave(
                plan_date=state.plan_date,
                day_items=[_save_item(item) for item in state.day_items],
                hourly_items=[_save_item(item) for item in state.hourly_items],
                minute_items=[_save_item(item) for item in state.minute_items],
                hourly_parent_key=state.hourly_parent_key,
                minute_parent_key=state.minute_parent_key,
                last_replan_reason=state.last_replan_reason,
            )

    def restore_state(self, *, agent_id: str, state: PlanningStateSave) -> None:
        with self._lock:
            self._states[agent_id] = _AgentPlanState(
                plan_date=state.plan_date,
                day_items=[_restore_day_item(item) for item in state.day_items],
                hourly_items=[
                    _restore_hourly_item(item) for item in state.hourly_items
                ],
                minute_items=[
                    _restore_minute_item(item) for item in state.minute_items
                ],
                hourly_parent_key=state.hourly_parent_key,
                minute_parent_key=state.minute_parent_key,
                last_replan_reason=state.last_replan_reason,
            )

    def bootstrap(
        self, *, agent: LifeAgent, now: datetime.datetime
    ) -> AgentPlanSnapshot:
        """Generate the authoritative hierarchy without substituting fake plans."""
        return self.refresh_current(agent=agent, now=now)

    def refresh_current(
        self, *, agent: LifeAgent, now: datetime.datetime
    ) -> AgentPlanSnapshot:
        """Generate and install an authoritative LLM-authored hierarchy."""
        day_items = self.generate_day_plan(agent=agent, now=now)
        return self.install_day_plan(
            agent=agent,
            now=now,
            day_items=day_items,
            reason="llm_refresh",
        )

    def generate_day_plan(
        self, *, agent: LifeAgent, now: datetime.datetime
    ) -> list[DayPlanItem]:
        """Generate broad strokes without mutating live planning state."""
        planner = agent.brain.planner
        if planner is None:
            raise PlanningGenerationError(f"{agent.name}: planner is not configured")
        return self._generate_day_plan(planner=planner, agent=agent, now=now)

    def install_day_plan(
        self,
        *,
        agent: LifeAgent,
        now: datetime.datetime,
        day_items: list[DayPlanItem],
        reason: str,
    ) -> AgentPlanSnapshot:
        """Install generated broad strokes against the current world time."""
        with self._lock:
            planner = agent.brain.planner
            if planner is None:
                raise PlanningGenerationError(
                    f"{agent.name}: planner is not configured"
                )
            return self._install_hierarchy(
                agent=agent,
                planner=planner,
                now=now,
                day_items=day_items,
                reason=reason,
            )

    def _install_hierarchy(
        self,
        *,
        agent: LifeAgent,
        planner: LifePlanner,
        now: datetime.datetime,
        day_items: list[DayPlanItem],
        reason: str,
    ) -> AgentPlanSnapshot:
        active_day = _require_active(
            day_items, now, agent_name=agent.name, plan_level="day"
        )
        generated_hourly = planner.generate_hourly_plan(
            agent_name=agent.name,
            current_time=now,
            day_plan_item=active_day,
        )
        _require_canonical_locations(
            generated_hourly, agent_name=agent.name, plan_level="hourly"
        )
        hourly_items = _children_within(generated_hourly, active_day)
        if not hourly_items:
            raise PlanningGenerationError(
                f"{agent.name}: hourly plan is empty or outside its day-plan window"
            )
        active_hourly = _require_active(
            hourly_items, now, agent_name=agent.name, plan_level="hourly"
        )
        generated_minute = planner.generate_minute_plan(
            agent_name=agent.name,
            current_time=now,
            hourly_plan_item=active_hourly,
        )
        _require_canonical_locations(
            generated_minute, agent_name=agent.name, plan_level="minute"
        )
        minute_items = _children_within(generated_minute, active_hourly)
        if not minute_items:
            raise PlanningGenerationError(
                f"{agent.name}: minute plan is empty or outside its hourly-plan window"
            )
        _ = _require_active(
            minute_items, now, agent_name=agent.name, plan_level="minute"
        )
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
        with self._lock:
            return self._ensure_current(agent=agent, now=now, generate=generate)

    def _ensure_current(
        self,
        *,
        agent: LifeAgent,
        now: datetime.datetime,
        generate: bool,
    ) -> AgentPlanSnapshot:
        agent_id = str(agent.identity.id)
        state = self._states.setdefault(agent_id, _AgentPlanState())
        planner = agent.brain.planner
        if planner is None:
            raise RuntimeError(f"agent {agent_id} does not have a planner")

        if state.plan_date != now.date() or not state.day_items:
            if not generate:
                raise PlanningGenerationError(f"{agent.name}: day plan is unavailable")
            state.day_items = self._generate_day_plan(
                planner=planner, agent=agent, now=now
            )
            state.plan_date = now.date()
            state.hourly_items = []
            state.minute_items = []
            state.hourly_parent_key = None
            state.minute_parent_key = None
            state.last_replan_reason = "day_rollover"

        active_day = _require_active(
            state.day_items, now, agent_name=agent.name, plan_level="day"
        )
        day_key = (active_day.start_time, active_day.end_time)
        if state.hourly_parent_key != day_key or not state.hourly_items:
            if not generate:
                raise PlanningGenerationError(
                    f"{agent.name}: hourly plan is unavailable"
                )
            generated_hourly = planner.generate_hourly_plan(
                agent_name=agent.name,
                current_time=now,
                day_plan_item=active_day,
            )
            _require_canonical_locations(
                generated_hourly, agent_name=agent.name, plan_level="hourly"
            )
            state.hourly_items = [
                item
                for item in _children_within(generated_hourly, active_day)
                if item.duration_minutes >= 5
            ]
            if not state.hourly_items:
                raise PlanningGenerationError(
                    f"{agent.name}: hourly plan is empty or outside its day-plan window"
                )
            state.hourly_parent_key = day_key
            state.minute_items = []
            state.minute_parent_key = None
            state.last_replan_reason = "active_day_changed"

        active_hourly = _require_active(
            state.hourly_items, now, agent_name=agent.name, plan_level="hourly"
        )
        hourly_key = (active_hourly.start_time, active_hourly.end_time)
        active_minute = _active_or_none(state.minute_items, now)
        if state.minute_parent_key != hourly_key or active_minute is None:
            if not generate:
                raise PlanningGenerationError(
                    f"{agent.name}: minute plan is unavailable"
                )
            generated_minute = planner.generate_minute_plan(
                agent_name=agent.name,
                current_time=now,
                hourly_plan_item=active_hourly,
            )
            _require_canonical_locations(
                generated_minute, agent_name=agent.name, plan_level="minute"
            )
            state.minute_items = _children_within(generated_minute, active_hourly)
            if not state.minute_items:
                raise PlanningGenerationError(
                    f"{agent.name}: minute plan is empty or outside its hourly-plan window"
                )
            state.minute_parent_key = hourly_key
            state.last_replan_reason = "active_hour_changed"
            active_minute = _require_active(
                state.minute_items,
                now,
                agent_name=agent.name,
                plan_level="minute",
            )

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
        generated = planner.generate_day_plan(
            DayPlanBroadStrokesRequest(
                agent_name=agent.name,
                age=int(agent.identity.age),
                innate_traits=list(agent.identity.traits),
                persona_background=" | ".join(background_parts),
                yesterday_date=now - datetime.timedelta(days=1),
                yesterday_summary="평소 일과를 지키며 마을 사람들과 자연스럽게 교류했다.",
                today_date=now,
                planning_window_end=datetime.datetime.combine(
                    now.date() + datetime.timedelta(days=1), datetime.time.min
                ),
            )
        )
        if generated and all(
            item.location in CANONICAL_LOCATIONS and item.duration_minutes >= 5
            for item in generated
        ):
            return generated
        raise PlanningGenerationError(
            f"{agent.name}: day plan is empty or contains an invalid location/time window"
        )


def _snapshot(
    item: DayPlanItem | HourlyPlanItem | MinutePlanItem,
) -> PlanItemSnapshot:
    return PlanItemSnapshot(
        start_time=item.start_time,
        end_time=item.end_time,
        location=item.location,
        action_content=item.action_content,
    )


def _save_item(
    item: DayPlanItem | HourlyPlanItem | MinutePlanItem,
) -> PlanItemSave:
    return PlanItemSave(
        start_time=item.start_time,
        end_time=item.end_time,
        location=item.location,
        action_content=item.action_content,
    )


def _restore_day_item(item: PlanItemSave) -> DayPlanItem:
    return DayPlanItem(
        start_time=item.start_time,
        end_time=item.end_time,
        location=item.location,
        action_content=item.action_content,
    )


def _restore_hourly_item(item: PlanItemSave) -> HourlyPlanItem:
    return HourlyPlanItem(
        start_time=item.start_time,
        end_time=item.end_time,
        location=item.location,
        action_content=item.action_content,
    )


def _restore_minute_item(item: PlanItemSave) -> MinutePlanItem:
    return MinutePlanItem(
        start_time=item.start_time,
        end_time=item.end_time,
        location=item.location,
        action_content=item.action_content,
    )


def _state_snapshot(
    *, agent: LifeAgent, state: _AgentPlanState, now: datetime.datetime
) -> AgentPlanSnapshot:
    active_day = _require_active(
        state.day_items, now, agent_name=agent.name, plan_level="day"
    )
    active_hourly = _require_active(
        state.hourly_items, now, agent_name=agent.name, plan_level="hourly"
    )
    active_minute = _require_active(
        state.minute_items, now, agent_name=agent.name, plan_level="minute"
    )
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


def _require_active(
    items: list[PlanItemT],
    now: datetime.datetime,
    *,
    agent_name: str,
    plan_level: str,
) -> PlanItemT:
    active = _active_or_none(items, now)
    if active is None:
        raise PlanningGenerationError(
            f"{agent_name}: {plan_level} plan does not cover the current world time"
        )
    return active


def _children_within(
    items: list[PlanItemT],
    parent: DayPlanItem | HourlyPlanItem,
) -> list[PlanItemT]:
    return [
        item
        for item in items
        if item.start_time >= parent.start_time and item.end_time <= parent.end_time
    ]


def _require_canonical_locations(
    items: list[PlanItemT], *, agent_name: str, plan_level: str
) -> None:
    invalid_locations = sorted(
        {item.location for item in items if item.location not in CANONICAL_LOCATIONS}
    )
    if invalid_locations:
        raise PlanningGenerationError(
            f"{agent_name}: {plan_level} plan contains non-canonical locations: "
            + ", ".join(invalid_locations)
        )
