import datetime
from typing import Literal, Protocol, cast

from pydantic import BaseModel

from ..graph_support import GRAPH_END, GRAPH_START, GRAPH_STATE_FACTORY
from llm import prompt_builders
from llm.clients.types import LlmGenerateOptions
from llm.governance import (
    DayPlanParseError,
    HourPlanParseError,
    MinutePlanParseError,
    try_parse_day_plan,
    try_parse_hour_plan_decomposition,
    try_parse_minute_task_decomposition,
)
from llm.structured_outputs import (
    HourlyPlanOutput,
    MinutePlanOutput,
    day_plan_output_model,
)
from typing_extensions import TypedDict

from .models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
    MinutePlanItem,
)

DAY_PLAN_GENERATE_OPTIONS = LlmGenerateOptions(
    temperature=0.0,
    top_p=1.0,
    # A daily plan has up to eight timestamped items. Give its complete structured
    # JSON document room to finish, while leaving Qwen thinking disabled by default.
    num_predict=4096,
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


def _truncate_to_minute(moment: datetime.datetime) -> datetime.datetime:
    """Drop sub-minute precision so window prompts and validation always agree.

    Prompts render planning-window timestamps with minute precision, so any
    sub-minute component on the simulation clock would make the LLM's
    exact-boundary output un-matchable against the validator's full-precision
    comparison. Truncating here keeps both sides on the same footing regardless
    of the world runtime's tick size.
    """
    return moment.replace(second=0, microsecond=0)


def _day_plan_item_bounds(
    request: DayPlanBroadStrokesRequest,
) -> tuple[int, int]:
    if request.planning_window_end is None:
        return 5, 8

    planning_end = request.planning_window_end
    remaining_five_minute_slots = max(
        1, int((planning_end - request.today_date).total_seconds() // 300)
    )
    max_items = min(8, remaining_five_minute_slots)
    minimum_for_duration = max(
        1,
        (remaining_five_minute_slots * 5 + 180 - 1) // 180,
    )
    return min(max_items, max(min(5, max_items), minimum_for_duration)), max_items


class PlanningGraphError(RuntimeError):
    """Raised after structured planning output exhausts its parse retries."""


MAX_PARSE_RETRIES = 2


class PlanningGraphBuilder(Protocol):
    def add_node(self, node: str, action: object) -> None: ...

    def add_edge(self, start_key: object, end_key: object) -> None: ...

    def add_conditional_edges(
        self,
        source: str,
        path: object,
        path_map: dict[str, object],
    ) -> None: ...

    def compile(self) -> "PlanningGraphInvoker": ...


class PlanningGraphInvoker(Protocol):
    def invoke(self, input: object) -> object: ...


class StateGraphFactory(Protocol):
    def __call__(self, state_schema: type[object]) -> PlanningGraphBuilder: ...


STATE_GRAPH = cast(StateGraphFactory, GRAPH_STATE_FACTORY)


class PlanningCompletionClient(Protocol):
    def complete_planning_prompt(
        self,
        *,
        prompt: str,
        options: LlmGenerateOptions,
        response_model: type[BaseModel],
    ) -> str: ...


class DayPlanningGraphState(TypedDict):
    request: DayPlanBroadStrokesRequest
    base_prompt: str
    current_prompt: str
    response_text: str
    attempt_count: int
    plan_items: list[DayPlanItem]
    parse_error: str


class HourlyPlanningGraphState(TypedDict):
    agent_name: str
    current_time: datetime.datetime
    day_plan_item: DayPlanItem
    base_prompt: str
    current_prompt: str
    response_text: str
    attempt_count: int
    plan_items: list[HourlyPlanItem]
    parse_error: str


class MinutePlanningGraphState(TypedDict):
    agent_name: str
    current_time: datetime.datetime
    hourly_plan_item: HourlyPlanItem
    base_prompt: str
    current_prompt: str
    response_text: str
    attempt_count: int
    plan_items: list[MinutePlanItem]
    parse_error: str


class PlanningGraphRunner:
    def __init__(self, *, planning_client: PlanningCompletionClient):
        self.planning_client: PlanningCompletionClient = planning_client
        self.day_plan_graph: PlanningGraphInvoker = self._build_day_plan_graph()
        self.hourly_plan_graph: PlanningGraphInvoker = self._build_hourly_plan_graph()
        self.minute_plan_graph: PlanningGraphInvoker = self._build_minute_plan_graph()

    def generate_day_plan(
        self,
        request: DayPlanBroadStrokesRequest,
    ) -> list[DayPlanItem]:
        final_state = cast(
            DayPlanningGraphState,
            self.day_plan_graph.invoke(
                DayPlanningGraphState(
                    request=request,
                    base_prompt="",
                    current_prompt="",
                    response_text="",
                    attempt_count=0,
                    plan_items=[],
                    parse_error="",
                )
            ),
        )
        if not final_state["plan_items"]:
            raise PlanningGraphError(
                f"day plan parse failed: {final_state['parse_error'] or 'empty output'}"
            )
        return final_state["plan_items"]

    def generate_hourly_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        day_plan_item: DayPlanItem,
    ) -> list[HourlyPlanItem]:
        final_state = cast(
            HourlyPlanningGraphState,
            self.hourly_plan_graph.invoke(
                HourlyPlanningGraphState(
                    agent_name=agent_name,
                    current_time=_truncate_to_minute(current_time),
                    day_plan_item=day_plan_item,
                    base_prompt="",
                    current_prompt="",
                    response_text="",
                    attempt_count=0,
                    plan_items=[],
                    parse_error="",
                )
            ),
        )
        if not final_state["plan_items"]:
            raise PlanningGraphError(
                f"hourly plan parse failed: {final_state['parse_error'] or 'empty output'}"
            )
        return final_state["plan_items"]

    def generate_minute_plan(
        self,
        *,
        agent_name: str,
        current_time: datetime.datetime,
        hourly_plan_item: HourlyPlanItem,
    ) -> list[MinutePlanItem]:
        current_time = _truncate_to_minute(current_time)
        window_start = max(current_time, hourly_plan_item.start_time)
        window_duration_minutes = int(
            (hourly_plan_item.end_time - window_start).total_seconds() // 60
        )
        if window_duration_minutes < 1:
            raise PlanningGraphError(
                "minute planning window must contain at least one minute"
            )
        final_state = cast(
            MinutePlanningGraphState,
            self.minute_plan_graph.invoke(
                MinutePlanningGraphState(
                    agent_name=agent_name,
                    current_time=current_time,
                    hourly_plan_item=hourly_plan_item,
                    base_prompt="",
                    current_prompt="",
                    response_text="",
                    attempt_count=0,
                    plan_items=[],
                    parse_error="",
                )
            ),
        )
        if not final_state["plan_items"]:
            raise PlanningGraphError(
                f"minute plan parse failed: {final_state['parse_error'] or 'empty output'}"
            )
        return final_state["plan_items"]

    def _build_day_plan_graph(self) -> PlanningGraphInvoker:
        builder = STATE_GRAPH(DayPlanningGraphState)
        builder.add_node("build_prompt", self._build_day_plan_prompt)
        builder.add_node("generate_response", self._generate_day_plan_response)
        builder.add_node("parse_response", self._parse_day_plan_response)
        builder.add_node("prepare_retry", self._prepare_day_plan_retry)
        builder.add_edge(GRAPH_START, "build_prompt")
        builder.add_edge("build_prompt", "generate_response")
        builder.add_edge("generate_response", "parse_response")
        builder.add_conditional_edges(
            "parse_response",
            self._route_day_plan_after_parse,
            {
                "prepare_retry": "prepare_retry",
                "__end__": GRAPH_END,
            },
        )
        builder.add_edge("prepare_retry", "generate_response")
        return builder.compile()

    def _build_hourly_plan_graph(self) -> PlanningGraphInvoker:
        builder = STATE_GRAPH(HourlyPlanningGraphState)
        builder.add_node("build_prompt", self._build_hourly_plan_prompt)
        builder.add_node("generate_response", self._generate_hourly_plan_response)
        builder.add_node("parse_response", self._parse_hourly_plan_response)
        builder.add_node("prepare_retry", self._prepare_hourly_plan_retry)
        builder.add_edge(GRAPH_START, "build_prompt")
        builder.add_edge("build_prompt", "generate_response")
        builder.add_edge("generate_response", "parse_response")
        builder.add_conditional_edges(
            "parse_response",
            self._route_hourly_plan_after_parse,
            {
                "prepare_retry": "prepare_retry",
                "__end__": GRAPH_END,
            },
        )
        builder.add_edge("prepare_retry", "generate_response")
        return builder.compile()

    def _build_minute_plan_graph(self) -> PlanningGraphInvoker:
        builder = STATE_GRAPH(MinutePlanningGraphState)
        builder.add_node("build_prompt", self._build_minute_plan_prompt)
        builder.add_node("generate_response", self._generate_minute_plan_response)
        builder.add_node("parse_response", self._parse_minute_plan_response)
        builder.add_node("prepare_retry", self._prepare_minute_plan_retry)
        builder.add_edge(GRAPH_START, "build_prompt")
        builder.add_edge("build_prompt", "generate_response")
        builder.add_edge("generate_response", "parse_response")
        builder.add_conditional_edges(
            "parse_response",
            self._route_minute_plan_after_parse,
            {
                "prepare_retry": "prepare_retry",
                "__end__": GRAPH_END,
            },
        )
        builder.add_edge("prepare_retry", "generate_response")
        return builder.compile()

    def _build_day_plan_prompt(
        self,
        state: DayPlanningGraphState,
    ) -> dict[str, str]:
        request = state["request"]
        min_items, max_items = _day_plan_item_bounds(request)
        prompt = prompt_builders.build_day_plan_prompt(
            agent_name=request.agent_name,
            age=request.age,
            innate_traits=request.innate_traits,
            persona_background=request.persona_background,
            yesterday_date=request.yesterday_date,
            yesterday_summary=request.yesterday_summary,
            today_date=request.today_date,
            planning_window_end=request.planning_window_end,
            min_items=min_items,
            max_items=max_items,
        )
        return {"base_prompt": prompt, "current_prompt": prompt}

    def _generate_day_plan_response(
        self,
        state: DayPlanningGraphState,
    ) -> dict[str, str]:
        min_items, max_items = _day_plan_item_bounds(state["request"])
        return {
            "response_text": self.planning_client.complete_planning_prompt(
                prompt=state["current_prompt"],
                options=DAY_PLAN_GENERATE_OPTIONS,
                response_model=day_plan_output_model(
                    min_items=min_items,
                    max_items=max_items,
                ),
            )
        }

    def _parse_day_plan_response(
        self,
        state: DayPlanningGraphState,
    ) -> dict[str, object]:
        try:
            min_items, max_items = _day_plan_item_bounds(state["request"])
            parsed = try_parse_day_plan(
                state["response_text"],
                min_items=min_items,
                max_items=min(8, max_items),
                min_duration=5,
                reference_date=state["request"].today_date.date(),
                repair_excessive_duration=state["attempt_count"] >= MAX_PARSE_RETRIES,
                fixed_window=(
                    (state["request"].today_date, state["request"].planning_window_end)
                    if state["request"].planning_window_end is not None
                    else None
                ),
            )
            planning_end = state["request"].planning_window_end
            if planning_end is not None:
                window_error = _continuous_window_error(
                    parsed.items,
                    window_start=state["request"].today_date,
                    window_end=planning_end,
                )
                if window_error:
                    raise DayPlanParseError(window_error)
            return {"plan_items": parsed.items, "parse_error": ""}
        except DayPlanParseError as exc:
            return {"plan_items": [], "parse_error": exc.reason}

    def _route_day_plan_after_parse(
        self,
        state: DayPlanningGraphState,
    ) -> Literal["prepare_retry", "__end__"]:
        if state["plan_items"]:
            return "__end__"
        if state["attempt_count"] >= MAX_PARSE_RETRIES:
            return "__end__"
        return "prepare_retry"

    def _prepare_day_plan_retry(
        self,
        state: DayPlanningGraphState,
    ) -> dict[str, object]:
        duration_repair = ""
        if state["parse_error"] == "day_plan_item_duration_exceeds_maximum":
            duration_repair = (
                "\n\nCRITICAL REPAIR: Every day-plan item must be 180 minutes "
                "or shorter. Replace any workday-sized block with separate morning, "
                "midday, afternoon, and evening items; include a break or errand at a "
                "different canonical location between long work periods."
            )
        elif state["parse_error"] == "planning_window_not_repairable_for_item_count":
            duration_repair = (
                "\n\nCRITICAL REPAIR: Return enough items for the fixed window: "
                "each item may cover at most 180 minutes, and all items together "
                "must be able to span the complete start-to-end duration."
            )
        return {
            "attempt_count": state["attempt_count"] + 1,
            "current_prompt": _build_plan_retry_prompt(
                base_prompt=state["base_prompt"],
                plan_name="day-plan",
                json_shape=prompt_builders.DAY_PLAN_JSON_SHAPE,
                previous_error=state["parse_error"],
                previous_response=state["response_text"],
            )
            + duration_repair,
        }

    def _build_hourly_plan_prompt(
        self,
        state: HourlyPlanningGraphState,
    ) -> dict[str, str]:
        prompt = prompt_builders.build_hourly_plan_prompt(
            agent_name=state["agent_name"],
            current_time=state["current_time"],
            day_plan_item=state["day_plan_item"],
        )
        return {"base_prompt": prompt, "current_prompt": prompt}

    def _generate_hourly_plan_response(
        self,
        state: HourlyPlanningGraphState,
    ) -> dict[str, str]:
        return {
            "response_text": self.planning_client.complete_planning_prompt(
                prompt=state["current_prompt"],
                options=HOURLY_PLAN_GENERATE_OPTIONS,
                response_model=HourlyPlanOutput,
            )
        }

    def _parse_hourly_plan_response(
        self,
        state: HourlyPlanningGraphState,
    ) -> dict[str, object]:
        try:
            parsed = try_parse_hour_plan_decomposition(
                state["response_text"],
                authoritative_location=state["day_plan_item"].location,
                reference_date=state["current_time"].date(),
            )
            window_error = _continuous_window_error(
                parsed.items,
                window_start=max(
                    state["current_time"], state["day_plan_item"].start_time
                ),
                window_end=state["day_plan_item"].end_time,
                containing_start=state["day_plan_item"].start_time,
            )
            if window_error:
                raise HourPlanParseError(window_error)
            return {"plan_items": parsed.items, "parse_error": ""}
        except HourPlanParseError as exc:
            return {"plan_items": [], "parse_error": exc.reason}

    def _route_hourly_plan_after_parse(
        self,
        state: HourlyPlanningGraphState,
    ) -> Literal["prepare_retry", "__end__"]:
        if state["plan_items"]:
            return "__end__"
        if state["attempt_count"] >= MAX_PARSE_RETRIES:
            return "__end__"
        return "prepare_retry"

    def _prepare_hourly_plan_retry(
        self,
        state: HourlyPlanningGraphState,
    ) -> dict[str, object]:
        return {
            "attempt_count": state["attempt_count"] + 1,
            "current_prompt": _build_plan_retry_prompt(
                base_prompt=state["base_prompt"],
                plan_name="hourly plan",
                json_shape=prompt_builders.HOURLY_PLAN_JSON_SHAPE,
                previous_error=state["parse_error"],
                previous_response=state["response_text"],
            ),
        }

    def _build_minute_plan_prompt(
        self,
        state: MinutePlanningGraphState,
    ) -> dict[str, str]:
        prompt = prompt_builders.build_minute_plan_prompt(
            agent_name=state["agent_name"],
            current_time=state["current_time"],
            hourly_plan_item=state["hourly_plan_item"],
        )
        return {"base_prompt": prompt, "current_prompt": prompt}

    def _generate_minute_plan_response(
        self,
        state: MinutePlanningGraphState,
    ) -> dict[str, str]:
        return {
            "response_text": self.planning_client.complete_planning_prompt(
                prompt=state["current_prompt"],
                options=MINUTE_PLAN_GENERATE_OPTIONS,
                response_model=MinutePlanOutput,
            )
        }

    def _parse_minute_plan_response(
        self,
        state: MinutePlanningGraphState,
    ) -> dict[str, object]:
        window_start = max(state["current_time"], state["hourly_plan_item"].start_time)
        expected_duration_minutes = int(
            (state["hourly_plan_item"].end_time - window_start).total_seconds() // 60
        )
        try:
            parsed = try_parse_minute_task_decomposition(
                state["response_text"],
                expected_duration_minutes=expected_duration_minutes,
            )
            cursor = window_start
            plan_items: list[MinutePlanItem] = []
            for item in parsed.items:
                end_time = cursor + datetime.timedelta(minutes=item.duration_minutes)
                plan_items.append(
                    MinutePlanItem(
                        start_time=cursor,
                        end_time=end_time,
                        location=state["hourly_plan_item"].location,
                        action_content=item.action_content,
                    )
                )
                cursor = end_time
            return {"plan_items": plan_items, "parse_error": ""}
        except MinutePlanParseError as exc:
            return {"plan_items": [], "parse_error": exc.reason}

    def _route_minute_plan_after_parse(
        self,
        state: MinutePlanningGraphState,
    ) -> Literal["prepare_retry", "__end__"]:
        if state["plan_items"]:
            return "__end__"
        if state["attempt_count"] >= MAX_PARSE_RETRIES:
            return "__end__"
        return "prepare_retry"

    def _prepare_minute_plan_retry(
        self,
        state: MinutePlanningGraphState,
    ) -> dict[str, object]:
        return {
            "attempt_count": state["attempt_count"] + 1,
            "current_prompt": _build_plan_retry_prompt(
                base_prompt=state["base_prompt"],
                plan_name="minute plan",
                json_shape=prompt_builders.MINUTE_PLAN_JSON_SHAPE,
                previous_error=state["parse_error"],
                previous_response=state["response_text"],
            ),
        }


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
        f"Do not repeat this invalid output: {previous_response[:4000]!r}"
    )


def _continuous_window_error(
    items: list[DayPlanItem] | list[HourlyPlanItem],
    *,
    window_start: datetime.datetime,
    window_end: datetime.datetime,
    containing_start: datetime.datetime | None = None,
) -> str:
    """Return a semantic error unless items continuously cover a fixed window."""
    if window_end <= window_start:
        return "invalid_planning_window"

    lower_bound = containing_start or window_start
    relevant = [item for item in items if item.end_time > window_start]
    if not relevant:
        return "plan_does_not_cover_window_start"
    if relevant[0].start_time < lower_bound or relevant[0].start_time > window_start:
        return "plan_does_not_cover_window_start"

    cursor = relevant[0].end_time
    if cursor <= window_start:
        return "plan_does_not_cover_window_start"
    if cursor > window_end:
        return "plan_exceeds_fixed_window"

    for item in relevant[1:]:
        if cursor == window_end:
            return "plan_exceeds_fixed_window"
        if item.start_time != cursor:
            return "plan_contains_gap_or_overlap"
        if item.end_time > window_end:
            return "plan_exceeds_fixed_window"
        cursor = item.end_time

    if cursor != window_end:
        return "plan_does_not_cover_window_end"
    return ""
