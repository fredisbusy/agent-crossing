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
        self.last_day_plan_request = None

    def generate_day_plan(self, request):
        self.day_calls += 1
        self.last_day_plan_request = request
        date = request.today_date.date()
        return [
            DayPlanItem(
                start_time=datetime.datetime.combine(date, datetime.time(6)),
                end_time=datetime.datetime.combine(date, datetime.time(12)),
                location="브라이어 코브 > 스토리하우스 도서관",
                action_content="도서관 오전 업무를 한다.",
            ),
            DayPlanItem(
                start_time=datetime.datetime.combine(date, datetime.time(12)),
                end_time=datetime.datetime.combine(date, datetime.time(18)),
                location="브라이어 코브 > 마을 광장",
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
            fixed=FixedPersona(identity_stable_set=["스토리하우스 도서관의 사서다."]),
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
    assert second.active_day.location == "브라이어 코브 > 스토리하우스 도서관"
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

    assert snapshot.active_day.location == "브라이어 코브 > 마을 광장"
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


def test_future_minute_plan_raises_instead_of_resetting_progress_to_zero() -> None:
    planner = FakePlanner()

    def future_minute_plan(*, agent_name, current_time, hourly_plan_item):
        _ = agent_name, current_time
        return [
            MinutePlanItem(
                start_time=hourly_plan_item.start_time + datetime.timedelta(minutes=30),
                end_time=hourly_plan_item.start_time + datetime.timedelta(minutes=40),
                location=hourly_plan_item.location,
                action_content="아직 시작하지 않은 다음 일정을 수행한다.",
            )
        ]

    planner.generate_minute_plan = future_minute_plan
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )

    with pytest.raises(
        PlanningGenerationError,
        match="minute plan does not cover the current world time",
    ):
        PlanningCoordinator().bootstrap(
            agent=agent, now=datetime.datetime(2026, 8, 24, 6, 5)
        )


def test_shortened_minute_location_raises_instead_of_losing_destination() -> None:
    planner = FakePlanner()

    def shortened_minute_plan(*, agent_name, current_time, hourly_plan_item):
        _ = agent_name, current_time
        return [
            MinutePlanItem(
                start_time=hourly_plan_item.start_time,
                end_time=hourly_plan_item.start_time + datetime.timedelta(minutes=15),
                location="브라이어 코브",
                action_content="집에서 아침을 준비한다.",
            )
        ]

    planner.generate_minute_plan = shortened_minute_plan
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )

    with pytest.raises(
        PlanningGenerationError, match="minute plan contains non-canonical locations"
    ):
        PlanningCoordinator().bootstrap(
            agent=agent, now=datetime.datetime(2026, 8, 24, 6, 5)
        )


def test_react_replan_regenerates_only_current_and_future_segments() -> None:
    """TODO.md §3-B: react 시 day plan(과 canonical 시간창)은 보존하고
    hourly/minute만 현재 시점 이후로 재수립한다."""
    planner = FakePlanner()
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )
    coordinator = PlanningCoordinator()
    now = datetime.datetime(2026, 8, 24, 6, 5)

    before = coordinator.ensure_current(agent=agent, now=now)

    def disrupted_minute_plan(*, agent_name, current_time, hourly_plan_item):
        _ = agent_name, current_time
        return [
            MinutePlanItem(
                start_time=hourly_plan_item.start_time,
                end_time=hourly_plan_item.start_time + datetime.timedelta(minutes=15),
                location=hourly_plan_item.location,
                action_content="예상치 못한 사건에 대응한다.",
            )
        ]

    planner.generate_minute_plan = disrupted_minute_plan

    after = coordinator.react_replan(agent=agent, now=now, reason="tick_react:테스트")

    assert after.active_minute.action_content == "예상치 못한 사건에 대응한다."
    assert after.day_plan == before.day_plan
    assert after.active_day.location == before.active_day.location
    assert after.last_replan_reason == "tick_react:테스트"


def test_no_disruption_tick_does_not_regenerate_plan() -> None:
    """TODO.md §3-B 회귀: 방해 없는 tick에서는 기존 계획이 재생성되지 않는다."""
    planner = FakePlanner()
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )
    coordinator = PlanningCoordinator()
    now = datetime.datetime(2026, 8, 24, 6, 5)

    coordinator.ensure_current(agent=agent, now=now)
    calls_before = (planner.day_calls, planner.hourly_calls, planner.minute_calls)

    coordinator.ensure_current(agent=agent, now=now + datetime.timedelta(minutes=1))

    assert (planner.day_calls, planner.hourly_calls, planner.minute_calls) == calls_before


class FakeMemory:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeMemoryService:
    def __init__(self, memories: list[FakeMemory]) -> None:
        self._memories = memories
        self.last_query: str | None = None

    def get_retrieval_memories(self, query, *, current_time, top_k=3):
        _ = current_time, top_k
        self.last_query = query
        return self._memories


def test_day_plan_generation_includes_retrieved_memories() -> None:
    """TODO.md §3-C: 대화에서 저장된 정보가 다음 day plan 생성 시 retrieval
    후보로 포함된다."""
    planner = FakePlanner()
    memory_service = FakeMemoryService(
        [FakeMemory("수진이 발렌타인 파티에 초대했다: 8월 30일 저녁 카페에서.")]
    )
    agent = FakeAgent(
        identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=FakeBrain(planner=planner),
    )
    agent.memory_service = memory_service

    PlanningCoordinator().bootstrap(agent=agent, now=datetime.datetime(2026, 8, 24, 6, 5))

    assert planner.last_day_plan_request is not None
    assert "발렌타인 파티" in planner.last_day_plan_request.persona_background
