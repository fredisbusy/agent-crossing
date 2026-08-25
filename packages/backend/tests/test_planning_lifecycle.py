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


class NotifiableBrain:
    """§4.3.1/§4.3.2 pattern: dialogue observations land directly in the
    agent's memory stream (via ``queue_observation``), which is the only
    channel the paper specifies for relationship/context influence — there
    is no separate numeric relationship-weight formula (see SPEC.md)."""

    def __init__(self, *, planner: FakePlanner, memory_service: FakeMemoryService) -> None:
        self.planner = planner
        self._memory_service = memory_service

    def queue_observation(self, *, content, now, profile, **_ignored) -> None:
        _ = now, profile
        self._memory_service._memories.append(FakeMemory(content))


def test_event_notification_via_conversation_flows_into_next_day_plan() -> None:
    """TODO.md §3-C 통합 재현: A가 B에게 이벤트를 알림(대화) -> B의 memory에
    observation으로 저장 -> B의 다음 day plan 생성 프롬프트에 반영 -> (LLM 응답
    mock을 통해) 실제 계획에 해당 시간/장소 항목이 포함된다.

    논문 §4.3.1/§4.3.2는 관계/맥락 영향을 별도 수치 가중치가 아니라
    "What is [observer]'s relationship with [entity]?" /
    "[entity] is [status]" 두 retrieval 질의의 요약을 프롬프트에 넣는 방식으로만
    명시한다. 이 테스트는 그 요약이 실제로 흘러가는 배선(plumbing)이 동작함을
    검증하는 것이지, 새로운 가중치 메커니즘을 요구하지 않는다.
    """
    from world.session import WorldConversationSession

    day = datetime.date(2026, 8, 30)
    invite_text = (
        "지호가 8월 30일 저녁 6시에 허니컵 카페에서 만나자고 초대했다."
    )

    # --- A(지호)가 B(수진)에게 대화로 이벤트를 알린다 ---
    planner_b = FakePlanner()

    def day_plan_with_invited_event(request):
        planner_b.day_calls += 1
        planner_b.last_day_plan_request = request
        return [
            DayPlanItem(
                start_time=datetime.datetime.combine(day, datetime.time(6)),
                end_time=datetime.datetime.combine(day, datetime.time(18)),
                location="브라이어 코브 > 스토리하우스 도서관",
                action_content="평소처럼 도서관 업무를 한다.",
            ),
            DayPlanItem(
                start_time=datetime.datetime.combine(day, datetime.time(18)),
                end_time=datetime.datetime.combine(day, datetime.time(20)),
                location="브라이어 코브 > 허니컵 카페",
                action_content="지호와 만나기로 한 약속에 간다.",
            ),
        ]

    planner_b.generate_day_plan = day_plan_with_invited_event

    memory_service_b = FakeMemoryService([])
    brain_b = NotifiableBrain(planner=planner_b, memory_service=memory_service_b)

    agent_a = FakeAgent(
        identity=AgentIdentity(id="jiho", name="지호", age=29, traits=["다정함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=NotifiableBrain(planner=FakePlanner(), memory_service=FakeMemoryService([])),
    )
    agent_b = FakeAgent(
        identity=AgentIdentity(id="sujin", name="수진", age=27, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=[]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        brain=brain_b,
    )
    agent_b.memory_service = memory_service_b

    session = WorldConversationSession(agents=[agent_a, agent_b], dialogue_turn_window=None)
    session.broadcast_reply(
        speaker=agent_a,
        reply=invite_text,
        now=datetime.datetime(2026, 8, 24, 18, 0),
        language="ko",
    )

    assert memory_service_b._memories, "대화 내용이 B의 memory stream에 저장돼야 한다"
    assert invite_text in memory_service_b._memories[0].content

    # --- B의 다음 day plan 생성 사이클 ---
    coordinator = PlanningCoordinator()
    result = coordinator.bootstrap(
        agent=agent_b, now=datetime.datetime.combine(day, datetime.time(6, 5))
    )

    assert planner_b.last_day_plan_request is not None
    assert invite_text in planner_b.last_day_plan_request.persona_background

    invited_items = [
        item for item in result.day_plan if item.location == "브라이어 코브 > 허니컵 카페"
    ]
    assert invited_items, "생성된 day plan에 초대받은 시간/장소 항목이 포함돼야 한다"
    assert invited_items[0].start_time == datetime.datetime.combine(day, datetime.time(18))
