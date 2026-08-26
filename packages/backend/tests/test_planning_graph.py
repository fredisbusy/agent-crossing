import datetime
import json

from pydantic import BaseModel

from agents.planning.graph import PlanningGraphRunner
from agents.planning.models import (
    DayPlanBroadStrokesRequest,
    DayPlanItem,
    HourlyPlanItem,
)
from agents.planning.planner import Planner
from llm.clients.types import LlmGenerateOptions


class StubPlanningClient:
    def __init__(self) -> None:
        self.call_labels: list[str] = []
        self.prompts: list[str] = []
        self.options: list[LlmGenerateOptions] = []
        self.response_models: list[type[BaseModel]] = []
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
                                "duration_minutes": 10,
                                "action_content": "Sketch the first phrase.",
                            },
                            {"duration_minutes": 10, "action_content": "Revise."},
                            {"duration_minutes": 10, "action_content": "Compare."},
                            {"duration_minutes": 10, "action_content": "Polish."},
                            {"duration_minutes": 10, "action_content": "Review."},
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
        response_model: type[BaseModel],
    ) -> str:
        assert issubclass(response_model, BaseModel)
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
        self.prompts.append(prompt)
        self.options.append(options)
        self.response_models.append(response_model)
        return self.responses_by_label[label].pop(0)


def _day_plan_request() -> DayPlanBroadStrokesRequest:
    return DayPlanBroadStrokesRequest(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="Studied harmony and practiced composition in the evening.",
        today_date=datetime.datetime(2026, 2, 13, 8),
        planning_window_end=datetime.datetime(2026, 2, 13, 21),
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
    assert len(minute_items) == 5
    assert client.call_labels == ["day", "hour", "minute"]
    assert client.options[0].num_predict == 4096
    assert client.options[0].reasoning_effort is None


def test_minute_plan_fits_a_non_five_minute_remaining_window() -> None:
    client = StubPlanningClient()
    graph = PlanningGraphRunner(planning_client=client)
    hourly_item = HourlyPlanItem(
        start_time=datetime.datetime(2026, 2, 13, 8),
        end_time=datetime.datetime(2026, 2, 13, 9),
        location="Town > Home > Desk",
        action_content="Draft composition motifs.",
    )

    items = graph.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 1),
        hourly_plan_item=hourly_item,
    )

    assert [item.duration_minutes for item in items] == [10, 10, 10, 10, 19]
    assert items[0].start_time == datetime.datetime(2026, 2, 13, 8, 1)
    assert items[-1].end_time == hourly_item.end_time


def test_minute_plan_allows_a_short_tail_at_the_parent_boundary() -> None:
    client = StubPlanningClient()
    graph = PlanningGraphRunner(planning_client=client)
    hourly_item = HourlyPlanItem(
        start_time=datetime.datetime(2026, 2, 13, 8),
        end_time=datetime.datetime(2026, 2, 13, 9),
        location="Town > Home > Desk",
        action_content="Draft composition motifs.",
    )

    items = graph.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 57),
        hourly_plan_item=hourly_item,
    )

    assert [item.duration_minutes for item in items] == [3]
    assert items[-1].end_time == hourly_item.end_time


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


def test_day_plan_repairs_provider_start_to_cover_authoritative_window() -> None:
    client = StubPlanningClient()

    def day_response(start: str) -> str:
        return json.dumps(
            {
                "items": [
                    {
                        "start_time": start,
                        "end_time": "2026-02-13T09:00:00",
                        "location": "Town > Home > Desk",
                        "action_content": "아침 준비를 한다.",
                    },
                    {
                        "start_time": "2026-02-13T09:00:00",
                        "end_time": "2026-02-13T12:00:00",
                        "location": "Town > College > Studio",
                        "action_content": "오전 작업을 한다.",
                    },
                    {
                        "start_time": "2026-02-13T12:00:00",
                        "end_time": "2026-02-13T15:00:00",
                        "location": "Town > Cafe > Patio",
                        "action_content": "점심 일정을 보낸다.",
                    },
                    {
                        "start_time": "2026-02-13T15:00:00",
                        "end_time": "2026-02-13T18:00:00",
                        "location": "Town > Cafe > Patio",
                        "action_content": "오후 일정을 보낸다.",
                    },
                    {
                        "start_time": "2026-02-13T18:00:00",
                        "end_time": "2026-02-13T21:00:00",
                        "location": "Town > Home > Desk",
                        "action_content": "저녁 활동을 한다.",
                    },
                    {
                        "start_time": "2026-02-13T21:00:00",
                        "end_time": "2026-02-14T00:00:00",
                        "location": "Town > Home > Desk",
                        "action_content": "하루를 정리하고 쉰다.",
                    },
                ]
            }
        )

    client.responses_by_label["day"] = [day_response("2026-02-13T06:30:00")]
    request = _day_plan_request()
    request = DayPlanBroadStrokesRequest(
        agent_name=request.agent_name,
        age=request.age,
        innate_traits=request.innate_traits,
        persona_background=request.persona_background,
        yesterday_date=request.yesterday_date,
        yesterday_summary=request.yesterday_summary,
        today_date=datetime.datetime(2026, 2, 13, 6, 25),
        planning_window_end=datetime.datetime(2026, 2, 14),
    )

    items = PlanningGraphRunner(planning_client=client).generate_day_plan(request)

    assert client.call_labels == ["day"]
    assert items[0].start_time == datetime.datetime(2026, 2, 13, 6, 25)
    assert items[-1].end_time == datetime.datetime(2026, 2, 14)


def test_day_plan_uses_single_tail_item_for_last_five_minutes() -> None:
    client = StubPlanningClient()
    client.responses_by_label["day"] = [
        json.dumps(
            {
                "items": [
                    {
                        "start_time": "2026-08-25T23:55:00",
                        "end_time": "2026-08-26T00:00:00",
                        "location": "브라이어 코브 > 지호의 집",
                        "action_content": "잠들기 전 하루를 정리한다.",
                    }
                ]
            },
            ensure_ascii=False,
        )
    ]
    request = DayPlanBroadStrokesRequest(
        agent_name="Jiho Park",
        age=31,
        innate_traits=["차분함"],
        persona_background="브라이어 코브 주민",
        yesterday_date=datetime.datetime(2026, 8, 24, 23, 55),
        yesterday_summary="평소 일과를 보냈다.",
        today_date=datetime.datetime(2026, 8, 25, 23, 55),
        planning_window_end=datetime.datetime(2026, 8, 26),
    )

    items = PlanningGraphRunner(planning_client=client).generate_day_plan(request)

    assert len(items) == 1
    assert "Return exactly 1 plan items" in client.prompts[0]
    items_schema = client.response_models[0].model_json_schema()["properties"][
        "items"
    ]
    assert items_schema["minItems"] == 1
    assert items_schema["maxItems"] == 1


def test_day_plan_compacts_oversized_legacy_draft_to_eight_items() -> None:
    client = StubPlanningClient()
    boundaries = [index * 90 for index in range(17)]

    def timestamp(minutes: int) -> str:
        return (
            datetime.datetime(2026, 8, 25) + datetime.timedelta(minutes=minutes)
        ).isoformat()

    client.responses_by_label["day"] = [
        json.dumps(
            {
                "items": [
                    {
                        "start_time": timestamp(start),
                        "end_time": timestamp(end),
                        "location": "브라이어 코브 > 마을 광장",
                        "action_content": f"일과 {index + 1}을 수행한다.",
                    }
                    for index, (start, end) in enumerate(
                        zip(boundaries, boundaries[1:])
                    )
                ]
            },
            ensure_ascii=False,
        )
    ]
    request = DayPlanBroadStrokesRequest(
        agent_name="Jiho Park",
        age=31,
        innate_traits=["차분함"],
        persona_background="브라이어 코브 주민",
        yesterday_date=datetime.datetime(2026, 8, 24),
        yesterday_summary="평소 일과를 보냈다.",
        today_date=datetime.datetime(2026, 8, 25),
        planning_window_end=datetime.datetime(2026, 8, 26),
    )

    items = PlanningGraphRunner(planning_client=client).generate_day_plan(request)

    assert len(items) == 8
    assert items[0].start_time == request.today_date
    assert items[-1].end_time == request.planning_window_end
    assert all(
        first.end_time == second.start_time
        for first, second in zip(items, items[1:])
    )
    items_schema = client.response_models[0].model_json_schema()["properties"][
        "items"
    ]
    assert items_schema["maxItems"] == 8


def test_day_plan_repairs_gap_and_overlap_when_item_count_is_feasible() -> None:
    client = StubPlanningClient()
    boundaries = [
        ("06:00", "09:00"),
        ("09:10", "12:10"),
        ("12:00", "15:00"),
        ("15:00", "18:00"),
        ("18:00", "21:00"),
        ("21:00", "00:00"),
    ]
    client.responses_by_label["day"] = [
        json.dumps(
            {
                "items": [
                    {
                        "start_time": f"2026-08-25T{start}:00",
                        "end_time": (
                            "2026-08-26T00:00:00"
                            if end == "00:00"
                            else f"2026-08-25T{end}:00"
                        ),
                        "location": "브라이어 코브 > 마을 광장",
                        "action_content": f"일과 {index + 1}을 수행한다.",
                    }
                    for index, (start, end) in enumerate(boundaries)
                ]
            },
            ensure_ascii=False,
        )
    ]
    request = DayPlanBroadStrokesRequest(
        agent_name="Jiho Park",
        age=31,
        innate_traits=["차분함"],
        persona_background="브라이어 코브 주민",
        yesterday_date=datetime.datetime(2026, 8, 24, 6),
        yesterday_summary="평소 일과를 보냈다.",
        today_date=datetime.datetime(2026, 8, 25, 6),
        planning_window_end=datetime.datetime(2026, 8, 26),
    )

    items = PlanningGraphRunner(planning_client=client).generate_day_plan(request)

    assert client.call_labels == ["day"]
    assert items[0].start_time == request.today_date
    assert items[-1].end_time == request.planning_window_end
    assert all(item.duration_minutes == 180 for item in items)
    assert all(
        first.end_time == second.start_time
        for first, second in zip(items, items[1:])
    )


def test_day_plan_rebuckets_oversized_schema_ignoring_response() -> None:
    client = StubPlanningClient()
    start = datetime.datetime(2026, 8, 25, 6)
    client.responses_by_label["day"] = [
        json.dumps(
            {
                "items": [
                    {
                        "start_time": (
                            start + datetime.timedelta(minutes=index * 120)
                        ).isoformat(),
                        "end_time": (
                            start + datetime.timedelta(minutes=(index + 1) * 120)
                        ).isoformat(),
                        "location": "브라이어 코브 > 마을 광장",
                        "action_content": f"일과 {index + 1}을 수행한다.",
                    }
                    for index in range(9)
                ]
            },
            ensure_ascii=False,
        )
    ]
    request = DayPlanBroadStrokesRequest(
        agent_name="Jiho Park",
        age=31,
        innate_traits=["차분함"],
        persona_background="브라이어 코브 주민",
        yesterday_date=datetime.datetime(2026, 8, 24, 6),
        yesterday_summary="평소 일과를 보냈다.",
        today_date=start,
        planning_window_end=datetime.datetime(2026, 8, 26),
    )

    items = PlanningGraphRunner(planning_client=client).generate_day_plan(request)

    assert len(items) == 8
    assert items[0].start_time == request.today_date
    assert items[-1].end_time == request.planning_window_end
    assert all(item.duration_minutes == 135 for item in items)
    assert all(
        first.end_time == second.start_time
        for first, second in zip(items, items[1:])
    )


def test_hourly_plan_retries_when_it_misses_the_current_world_time() -> None:
    client = StubPlanningClient()
    client.responses_by_label["hour"] = [
        json.dumps(
            {
                "items": [
                    {
                        "start_time": "2026-02-13T09:00:00",
                        "end_time": "2026-02-13T10:00:00",
                        "location": "Town > Home > Desk",
                        "action_content": "늦게 시작한다.",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "items": [
                    {
                        "start_time": "2026-02-13T08:00:00",
                        "end_time": "2026-02-13T10:00:00",
                        "location": "Town > Home > Desk",
                        "action_content": "현재 작업을 이어간다.",
                    }
                ]
            }
        ),
    ]
    parent = DayPlanItem(
        start_time=datetime.datetime(2026, 2, 13, 8),
        end_time=datetime.datetime(2026, 2, 13, 10),
        location="Town > Home > Desk",
        action_content="오전 작업",
    )

    items = PlanningGraphRunner(planning_client=client).generate_hourly_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 45),
        day_plan_item=parent,
    )

    assert client.call_labels == ["hour", "hour"]
    assert items[0].start_time <= datetime.datetime(2026, 2, 13, 8, 45)
    assert items[-1].end_time == parent.end_time


def test_hourly_plan_retries_when_one_item_exceeds_three_hours() -> None:
    client = StubPlanningClient()
    client.responses_by_label["hour"] = [
        json.dumps(
            {
                "items": [
                    {
                        "start_time": "2026-02-13T08:00:00",
                        "end_time": "2026-02-13T12:00:00",
                        "action_content": "오전 작업 전체를 한 번에 수행한다.",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "items": [
                    {
                        "start_time": "2026-02-13T08:00:00",
                        "end_time": "2026-02-13T10:00:00",
                        "action_content": "오전 전반 작업을 수행한다.",
                    },
                    {
                        "start_time": "2026-02-13T10:00:00",
                        "end_time": "2026-02-13T12:00:00",
                        "action_content": "오전 후반 작업을 수행한다.",
                    },
                ]
            }
        ),
    ]
    parent = DayPlanItem(
        start_time=datetime.datetime(2026, 2, 13, 8),
        end_time=datetime.datetime(2026, 2, 13, 12),
        location="Town > Home > Desk",
        action_content="오전 작업",
    )

    items = PlanningGraphRunner(planning_client=client).generate_hourly_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8),
        day_plan_item=parent,
    )

    assert [item.duration_minutes for item in items] == [120, 120]
    assert client.call_labels == ["hour", "hour"]
    assert items[-1].end_time == parent.end_time


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
    assert len(minute_items) == 5
    assert client.call_labels == ["day", "hour", "minute"]
