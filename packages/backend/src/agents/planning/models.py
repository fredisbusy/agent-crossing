import datetime
from dataclasses import dataclass


def _is_exact_minute(value: datetime.datetime) -> bool:
    return value.second == 0 and value.microsecond == 0


def _duration_minutes_between(
    start_time: datetime.datetime, end_time: datetime.datetime
) -> int:
    return int((end_time - start_time).total_seconds() // 60)


def _validate_time_window(
    *,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    label: str,
) -> int:
    if not _is_exact_minute(start_time):
        raise ValueError(f"{label} start_time must use minute precision")
    if not _is_exact_minute(end_time):
        raise ValueError(f"{label} end_time must use minute precision")
    if end_time <= start_time:
        raise ValueError(f"{label} end_time must be later than start_time")
    return _duration_minutes_between(start_time, end_time)


@dataclass(frozen=True)
class DayPlanItem:
    """하루 계획의 단일 실행 항목."""

    """계획 시작 시각."""
    start_time: datetime.datetime

    """계획 종료 시각."""
    end_time: datetime.datetime

    """행동이 수행되는 위치."""
    location: str

    """수행할 행동 내용."""
    action_content: str

    def __post_init__(self) -> None:
        _ = _validate_time_window(
            start_time=self.start_time,
            end_time=self.end_time,
            label="day plan",
        )
        if not self.location.strip():
            raise ValueError("location must not be blank")
        if not self.action_content.strip():
            raise ValueError("action_content must not be blank")

    @property
    def duration_minutes(self) -> int:
        return _duration_minutes_between(self.start_time, self.end_time)


@dataclass(frozen=True)
class HourlyPlanItem:
    """시간 단위 계획의 단일 실행 항목."""

    """시간 단위 계획 시작 시각."""
    start_time: datetime.datetime

    """시간 단위 계획 종료 시각."""
    end_time: datetime.datetime

    """시간 단위 행동이 수행되는 위치."""
    location: str

    """시간 단위로 수행할 행동 내용."""
    action_content: str

    def __post_init__(self) -> None:
        _ = _validate_time_window(
            start_time=self.start_time,
            end_time=self.end_time,
            label="hourly plan",
        )
        if not self.location.strip():
            raise ValueError("location must not be blank")
        if not self.action_content.strip():
            raise ValueError("action_content must not be blank")

    @property
    def duration_minutes(self) -> int:
        return _duration_minutes_between(self.start_time, self.end_time)


@dataclass(frozen=True)
class MinutePlanItem:
    """분 단위 계획의 단일 실행 항목."""

    """분 단위 계획 시작 시각."""
    start_time: datetime.datetime

    """분 단위 계획 종료 시각."""
    end_time: datetime.datetime

    """분 단위 행동이 수행되는 위치."""
    location: str

    """즉시 실행할 분 단위 행동 내용."""
    action_content: str

    def __post_init__(self) -> None:
        duration_minutes = _validate_time_window(
            start_time=self.start_time,
            end_time=self.end_time,
            label="minute plan",
        )
        if duration_minutes < 5 or duration_minutes > 15:
            raise ValueError("minute plan duration_minutes must be in range [5, 15]")
        if not self.location.strip():
            raise ValueError("location must not be blank")
        if not self.action_content.strip():
            raise ValueError("action_content must not be blank")

    @property
    def duration_minutes(self) -> int:
        return _duration_minutes_between(self.start_time, self.end_time)


@dataclass(frozen=True)
class DayPlan:
    """하루 계획 전체를 나타내는 모델."""

    """하루 계획을 구성하는 항목 목록(5~8개)."""
    items: list[DayPlanItem]

    def __post_init__(self) -> None:
        if len(self.items) < 5 or len(self.items) > 8:
            raise ValueError("day plan must contain between 5 and 8 items")


@dataclass(frozen=True)
class HourlyPlan:
    """시간 단위 계획 전체를 나타내는 모델."""

    """시간 단위 계획 항목 목록."""
    items: list[HourlyPlanItem]


@dataclass(frozen=True)
class MinutePlan:
    """분 단위 실행 계획 전체를 나타내는 모델."""

    """분 단위 실행 항목 목록."""
    items: list[MinutePlanItem]


@dataclass(frozen=True)
class DayPlanBroadStrokesRequest:
    """하루 거시 계획 생성을 위한 입력 요청."""

    """계획을 생성할 에이전트 이름."""
    agent_name: str

    """에이전트 나이."""
    age: int

    """에이전트의 선천적 성향 목록."""
    innate_traits: list[str]

    """에이전트의 배경 설정 요약."""
    persona_background: str

    """어제 날짜를 나타내는 텍스트."""
    yesterday_date: datetime.datetime

    """어제 활동 요약."""
    yesterday_summary: str

    """오늘 날짜를 나타내는 텍스트."""
    today_date: datetime.datetime

    """전체 연속 커버리지를 강제할 authoritative planning-window 종료 시각."""
    planning_window_end: datetime.datetime | None = None

    def __post_init__(self) -> None:
        if not self.agent_name.strip():
            raise ValueError("agent_name must not be blank")
        if self.age <= 0:
            raise ValueError("age must be greater than 0")
        if not any(trait.strip() for trait in self.innate_traits):
            raise ValueError("innate_traits must contain at least one non-empty trait")
        if not self.persona_background.strip():
            raise ValueError("persona_background must not be blank")
        if not self.yesterday_date:
            raise ValueError("yesterday_date must not be blank")
        if not self.yesterday_summary.strip():
            raise ValueError("yesterday_summary must not be blank")
        if not self.today_date:
            raise ValueError("today_date must not be blank")
        if (
            self.planning_window_end is not None
            and self.planning_window_end <= self.today_date
        ):
            raise ValueError("planning_window_end must be later than today_date")


@dataclass(frozen=True)
class DayPlanBroadStrokes:
    """하루 거시 계획 결과를 표현하는 모델."""

    """하루 계획의 거시적 스트로크 목록(5~8개)."""
    items: list[str]

    def __post_init__(self) -> None:
        filtered_items = [item for item in self.items if item.strip()]
        if len(filtered_items) < 5 or len(filtered_items) > 8:
            raise ValueError("broad strokes must contain between 5 and 8 items")
