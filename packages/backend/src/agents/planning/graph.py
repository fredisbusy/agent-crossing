import datetime
from typing import Callable, Protocol, TypeVar

from llm.clients.types import LlmGenerateOptions

from . import plan_prompts
from .models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)
from .plan_parsing import (
    DayPlanParseError,
    HourPlanParseError,
    MinutePlanParseError,
    try_parse_day_plan,
    try_parse_hour_plan,
    try_parse_minute_plan,
)

DAY_PLAN_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=1024,
)

HOURLY_PLAN_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=1024,
)

MINUTE_PLAN_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    num_predict=3072,
)

MAX_PARSE_RETRIES = 2
"""첫 호출이 파싱에 실패했을 때 재시도 프롬프트로 다시 부르는 최대 횟수."""

TPlanItem = TypeVar("TPlanItem")


class PlanningCompletionClient(Protocol):
    def complete_planning_prompt(
        self,
        *,
        prompt: str,
        options: LlmGenerateOptions,
    ) -> str: ...


class PlanningGraphRunner:
    """프롬프트 → 생성 → 파싱 → 실패 시 재시도 프롬프트 루프로 계획을 만든다."""

    def __init__(self, *, planning_client: PlanningCompletionClient):
        self.planning_client: PlanningCompletionClient = planning_client

    def generate_day_plan(
        self,
        request: DayPlanBroadStrokesRequest,
    ) -> list[DayPlanItem]:
        base_prompt = plan_prompts.build_day_plan_prompt(
            agent_name=request.agent_name,
            age=request.age,
            innate_traits=request.innate_traits,
            persona_background=request.persona_background,
            yesterday_date=request.yesterday_date,
            yesterday_summary=request.yesterday_summary,
            today_date=request.today_date,
        )

        def parse(text: str) -> list[DayPlanItem]:
            return try_parse_day_plan(
                text, reference_date=request.today_date.date()
            ).items

        return self._generate_with_retries(
            base_prompt=base_prompt,
            options=DAY_PLAN_GENERATE_OPTIONS,
            plan_name="day-plan",
            json_shape=plan_prompts.DAY_PLAN_JSON_SHAPE,
            parse=parse,
            parse_error=DayPlanParseError,
        )

    def generate_hourly_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]:
        base_prompt = plan_prompts.build_hourly_plan_prompt(
            agent_name=agent_name,
            current_time=current_time,
            day_plan_item=day_plan_item,
        )

        def parse(text: str) -> list[HourlyPlanItem]:
            return try_parse_hour_plan(text, reference_date=current_time.date()).items

        return self._generate_with_retries(
            base_prompt=base_prompt,
            options=HOURLY_PLAN_GENERATE_OPTIONS,
            plan_name="hourly plan",
            json_shape=plan_prompts.HOURLY_PLAN_JSON_SHAPE,
            parse=parse,
            parse_error=HourPlanParseError,
        )

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]:
        base_prompt = plan_prompts.build_minute_plan_prompt(
            agent_name=agent_name,
            current_time=current_time,
            hourly_plan_item=hourly_plan_item,
        )

        def parse(text: str) -> list[MinutePlanItem]:
            return try_parse_minute_plan(text, reference_date=current_time.date()).items

        return self._generate_with_retries(
            base_prompt=base_prompt,
            options=MINUTE_PLAN_GENERATE_OPTIONS,
            plan_name="minute plan",
            json_shape=plan_prompts.MINUTE_PLAN_JSON_SHAPE,
            parse=parse,
            parse_error=MinutePlanParseError,
        )

    def _generate_with_retries(
        self,
        *,
        base_prompt: str,
        options: LlmGenerateOptions,
        plan_name: str,
        json_shape: str,
        parse: Callable[[str], list[TPlanItem]],
        parse_error: type[ValueError],
    ) -> list[TPlanItem]:
        """빈 결과나 파싱 실패면 재시도 프롬프트로 최대 MAX_PARSE_RETRIES번 더 부른다."""
        prompt = base_prompt
        items: list[TPlanItem] = []
        for attempt in range(MAX_PARSE_RETRIES + 1):
            response_text = self.planning_client.complete_planning_prompt(
                prompt=prompt,
                options=options,
            )
            error_reason = ""
            try:
                items = parse(response_text)
            except parse_error as exc:
                items = []
                error_reason = str(getattr(exc, "reason", exc))
            if items or attempt >= MAX_PARSE_RETRIES:
                return items
            prompt = _build_plan_retry_prompt(
                base_prompt=base_prompt,
                plan_name=plan_name,
                json_shape=json_shape,
                previous_error=error_reason,
                previous_response=response_text,
            )
        return items


def _build_plan_retry_prompt(
    *,
    base_prompt: str,
    plan_name: str,
    json_shape: str,
    previous_error: str,
    previous_response: str,
) -> str:
    return (
        f"{base_prompt}\n\n"
        f"The previous response did not match the required {plan_name} JSON schema.\n"
        f"Failure reason: {previous_error}.\n\n"
        f"Return strict JSON only with this exact shape and no extra text: {json_shape}\n"
        f"Do not repeat this invalid output: {previous_response[:180]!r}"
    )
