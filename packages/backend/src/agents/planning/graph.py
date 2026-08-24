import datetime
from typing import Literal, Protocol, cast

from ..graph_support import GRAPH_END, GRAPH_START, GRAPH_STATE_FACTORY
from llm import prompt_builders
from llm.clients.types import LlmGenerateOptions
from llm.governance import (
    DayPlanParseError,
    HourPlanParseError,
    MinutePlanParseError,
    try_parse_day_plan,
    try_parse_hour_plan,
    try_parse_minute_plan,
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
                    current_time=current_time,
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
        prompt = prompt_builders.build_day_plan_prompt(
            agent_name=request.agent_name,
            age=request.age,
            innate_traits=request.innate_traits,
            persona_background=request.persona_background,
            yesterday_date=request.yesterday_date,
            yesterday_summary=request.yesterday_summary,
            today_date=request.today_date,
        )
        return {"base_prompt": prompt, "current_prompt": prompt}

    def _generate_day_plan_response(
        self,
        state: DayPlanningGraphState,
    ) -> dict[str, str]:
        return {
            "response_text": self.planning_client.complete_planning_prompt(
                prompt=state["current_prompt"],
                options=DAY_PLAN_GENERATE_OPTIONS,
            )
        }

    def _parse_day_plan_response(
        self,
        state: DayPlanningGraphState,
    ) -> dict[str, object]:
        try:
            parsed = try_parse_day_plan(
                state["response_text"],
                reference_date=state["request"].today_date.date(),
            )
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
        return {
            "attempt_count": state["attempt_count"] + 1,
            "current_prompt": _build_plan_retry_prompt(
                base_prompt=state["base_prompt"],
                plan_name="day-plan",
                json_shape=prompt_builders.DAY_PLAN_JSON_SHAPE,
                previous_error=state["parse_error"],
                previous_response=state["response_text"],
            ),
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
            )
        }

    def _parse_hourly_plan_response(
        self,
        state: HourlyPlanningGraphState,
    ) -> dict[str, object]:
        try:
            parsed = try_parse_hour_plan(
                state["response_text"],
                reference_date=state["current_time"].date(),
            )
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
            )
        }

    def _parse_minute_plan_response(
        self,
        state: MinutePlanningGraphState,
    ) -> dict[str, object]:
        try:
            parsed = try_parse_minute_plan(
                state["response_text"],
                reference_date=state["current_time"].date(),
            )
            return {"plan_items": parsed.items, "parse_error": ""}
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
        f"Do not repeat this invalid output: {previous_response[:180]!r}"
    )
