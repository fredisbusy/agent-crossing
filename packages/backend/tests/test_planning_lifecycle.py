import datetime
from dataclasses import dataclass

import pytest

from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona
from agents.planning.lifecycle import PlanningCoordinator, PlanningGenerationError
from agents.planning.models import DayPlanItem, HourlyPlanItem, MinutePlanItem


class FakePlanner:
    def __init__(self) -> None:
        self.day_calls = 0
        self.hourly_calls = 0
        self.minute_calls = 0

    def generate_day_plan(self, request):
        self.day_calls += 1
        date = request.today_date.date()
        return [
            DayPlanItem(
                start_time=datetime.datetime.combine(date, datetime.time(6)),
                end_time=datetime.datetime.combine(date, datetime.time(12)),
                location="Briar Cove > Story House",
                action_content="도서관 오전 업무를 한다.",
            ),
            DayPlanItem(
                start_time=datetime.datetime.combine(date, datetime.time(12)),
                end_time=datetime.datetime.combine(date, datetime.time(18)),
                location="Briar Cove > Town Square",
                action_content="오후 일과를 보낸다.",
            ),
        ]

    def generate_hourly_plan(self, *, agent_name, current_time, day_plan_item):
        _ = agent_name, current_time
        self.hourly_calls += 1
        return [
            HourlyPlanItem(
                start_time=day_plan_item.start_time,
                end_time=day_plan_item.end_time,
                location=day_plan_item.location,
                action_content="현재 broad stroke를 수행한다.",
            )
        ]

    def generate_minute_plan(self, *, agent_name, current_time, hourly_plan_item):
        _ = agent_name, current_time
        self.minute_calls += 1
        return [
            MinutePlanItem(
                start_time=hourly_plan_item.start_time,
                end_time=hourly_plan_item.start_time + datetime.timedelta(minutes=15),
                location=hourly_plan_item.location,
                action_content="책 반납함을 정리한다.",
            )
        ]


@dataclass
class FakeBrain:
    planner: FakePlanner


@dataclass
class FakeAgent:
    identity: AgentIdentity
    profile: AgentProfile
    brain: FakeBrain

    @property
    def name(self) -> str:
        return self.identity.name


def test_planning_coordinator_generates_hierarchy_just_in_time_and_caches() -> None:
    planner = FakePlanner()
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=["Story House의 사서다."]),
            extended=ExtendedPersona(
                lifestyle_and_routine=["아침에 출근한다."], current_plan_context=[]
            ),
        ),
        brain=FakeBrain(planner=planner),
    )
    coordinator = PlanningCoordinator()
    now = datetime.datetime(2026, 8, 24, 6, 5)

    first = coordinator.ensure_current(agent=agent, now=now)
    second = coordinator.ensure_current(
        agent=agent, now=now + datetime.timedelta(minutes=5)
    )

    assert first.active_minute.action_content == "책 반납함을 정리한다."
    assert second.active_day.location == "Briar Cove > Story House"
    assert (planner.day_calls, planner.hourly_calls, planner.minute_calls) == (1, 1, 1)
    assert agent.profile.extended.current_plan_context[0] == "책 반납함을 정리한다."


def test_planning_coordinator_uses_half_open_boundaries() -> None:
    planner = FakePlanner()
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )

    snapshot = PlanningCoordinator().ensure_current(
        agent=agent,
        now=datetime.datetime(2026, 8, 24, 12, 0),
    )

    assert snapshot.active_day.location == "Briar Cove > Town Square"
    assert planner.hourly_calls == 1


def test_bootstrap_uses_generated_plan_instead_of_a_fallback() -> None:
    planner = FakePlanner()
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )
    snapshot = PlanningCoordinator().bootstrap(
        agent=agent, now=datetime.datetime(2026, 8, 24, 6, 5)
    )

    assert snapshot.active_day.action_content == "도서관 오전 업무를 한다."
    assert snapshot.active_hourly.action_content == "현재 broad stroke를 수행한다."
    assert snapshot.active_minute.action_content == "책 반납함을 정리한다."
    assert (planner.day_calls, planner.hourly_calls, planner.minute_calls) == (1, 1, 1)


def test_invalid_generated_day_plan_raises_instead_of_installing_fallback() -> None:
    planner = FakePlanner()

    def invalid_day_plan(request):
        date = request.today_date.date()
        return [
            DayPlanItem(
                start_time=datetime.datetime.combine(date, datetime.time(6)),
                end_time=datetime.datetime.combine(date, datetime.time(12)),
                location="Unknown Place",
                action_content="알 수 없는 장소에서 일한다.",
            )
        ]

    planner.generate_day_plan = invalid_day_plan
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )

    with pytest.raises(PlanningGenerationError, match="invalid location/time"):
        PlanningCoordinator().bootstrap(
            agent=agent, now=datetime.datetime(2026, 8, 24, 6, 5)
        )
