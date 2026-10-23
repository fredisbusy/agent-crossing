import datetime
import json

from agents.planning.graph import PlanningGraphRunner
from agents.planning.models import (
    DayPlanBroadStrokesRequest,
)
from agents.planning.planner import Planner
from llm.clients.types import LlmGenerateOptions


class StubPlanningClient:
    def __init__(self) -> None:
        self.call_labels: list[str] = []
        self.responses_by_label: dict[str, list[str]] = {
            "day": [
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2026-02-13T08:00:00",
                                "end_time": "2026-02-13T09:00:00",
                                "location": "Town > Home > Desk",
                                "action_content": "Plan the morning composition session.",
                            },
                            {
                                "start_time": "2026-02-13T09:00:00",
                                "end_time": "2026-02-13T10:00:00",
                                "location": "Town > College > Studio",
                                "action_content": "Review harmony exercises.",
                            },
                            {
                                "start_time": "2026-02-13T10:00:00",
                                "end_time": "2026-02-13T11:00:00",
                                "location": "Town > Cafe > Patio",
                                "action_content": "Meet classmates to compare notes.",
                            },
                            {
                                "start_time": "2026-02-13T11:00:00",
                                "end_time": "2026-02-13T12:00:00",
                                "location": "Town > Home > Desk",
                                "action_content": "Sketch melodic ideas.",
                            },
                            {
                                "start_time": "2026-02-13T12:00:00",
                                "end_time": "2026-02-13T13:00:00",
                                "location": "Town > Home > Kitchen",
                                "action_content": "Eat lunch and rest.",
                            },
                        ]
                    }
                )
            ],
            "hour": [
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2026-02-13T08:00:00",
                                "end_time": "2026-02-13T09:00:00",
                                "location": "Town > Home > Desk",
                                "action_content": "Draft composition motifs.",
                            }
                        ]
                    }
                )
            ],
            "minute": [
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2026-02-13T08:00:00",
                                "end_time": "2026-02-13T08:10:00",
                                "location": "Town > Home > Desk",
                                "action_content": "Sketch the first phrase.",
                            }
                        ]
                    }
                )
            ],
        }

    def complete_planning_prompt(
        self,
        *,
        prompt: str,
        options: LlmGenerateOptions,
    ) -> str:
        normalized_prompt = prompt.lower()
        if options.num_predict == 3072:
            label = "minute"
        elif "hourly plan" in normalized_prompt:
            label = "hour"
        elif "day plan" in normalized_prompt:
            label = "day"
        else:
            raise AssertionError(f"Unknown planning prompt: {prompt[:120]!r}")
        self.call_labels.append(label)
        return self.responses_by_label[label].pop(0)


def _day_plan_request() -> DayPlanBroadStrokesRequest:
    return DayPlanBroadStrokesRequest(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="Studied harmony and practiced composition in the evening.",
        today_date=datetime.datetime(2026, 2, 13),
    )


def test_planning_graph_runner_parses_day_hour_and_minute_plans() -> None:
    client = StubPlanningClient()
    graph = PlanningGraphRunner(planning_client=client)

    day_items = graph.generate_day_plan(_day_plan_request())
    hourly_items = graph.generate_hourly_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 30, 0),
        day_plan_item=day_items[0],
    )
    minute_items = graph.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 10, 0),
        hourly_plan_item=hourly_items[0],
    )

    assert len(day_items) == 5
    assert len(hourly_items) == 1
    assert len(minute_items) == 1
    assert client.call_labels == ["day", "hour", "minute"]


def test_planning_graph_runner_retries_invalid_day_plan_once() -> None:
    client = StubPlanningClient()
    client.responses_by_label["day"] = [
        '{"items": [{"start_time": "2026-02-13T08:00:00"}',
        client.responses_by_label["day"][0],
    ]
    graph = PlanningGraphRunner(planning_client=client)

    items = graph.generate_day_plan(_day_plan_request())

    assert len(items) == 5
    assert client.call_labels == ["day", "day"]


def test_planner_uses_planning_graph_for_existing_entrypoints() -> None:
    client = StubPlanningClient()
    planner = Planner(client)

    day_items = planner.generate_day_plan(_day_plan_request())
    hourly_items = planner.generate_hourly_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 30, 0),
        day_plan_item=day_items[0],
    )
    minute_items = planner.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 10, 0),
        hourly_plan_item=hourly_items[0],
    )

    assert len(day_items) == 5
    assert len(hourly_items) == 1
    assert len(minute_items) == 1
    assert client.call_labels == ["day", "hour", "minute"]
