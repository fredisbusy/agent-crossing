import datetime
import json
from typing import cast

import numpy as np
from agents.memory.memory_object import MemoryObject, NodeType
from agents.planning.models import DayPlanItem, HourlyPlanItem
from agents.llm_gateway import LlmGateway
from llm_gateway_helpers import (
    StubGenerationClient,
)


def test_generate_salient_questions_requests_json_format() -> None:
    client = StubGenerationClient(
        responses=[
            json.dumps(
                {
                    "questions": [
                        "What should Eddy focus on first today?",
                        "Who can help Eddy improve the composition?",
                        "Which task gives the highest progress today?",
                    ]
                }
            )
        ]
    )
    service = LlmGateway(client)
    memory = MemoryObject(
        id=2,
        node_type=NodeType.OBSERVATION,
        citations=None,
        content="Eddy wants to spend more hours on composition work.",
        created_at=datetime.datetime(2026, 2, 27, 10, 0, 0),
        last_accessed_at=datetime.datetime(2026, 2, 27, 10, 0, 0),
        importance=5,
        embedding=np.asarray([0.2, 0.3], dtype=np.float32),
    )

    questions = service.generate_salient_high_level_questions(
        agent_name="Eddy Lin",
        memories=[memory],
    )

    assert len(questions) == 3
    assert client.call_kwargs[0].get("format_json") is True


def test_generate_hour_plan_parses_json_items() -> None:
    service = LlmGateway(
        StubGenerationClient(
            responses=[
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2026-02-13T08:00:00",
                                "end_time": "2026-02-13T10:00:00",
                                "location": "Town > Home > Kitchen",
                                "action_content": "Review composition notes over breakfast.",
                            },
                            {
                                "start_time": "2026-02-13T10:00:00",
                                "end_time": "2026-02-13T11:00:00",
                                "location": "Town > College > Theory Room",
                                "action_content": "Attend morning music theory class.",
                            },
                        ]
                    }
                )
            ]
        )
    )

    items = service.generate_hour_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
        day_plan_item=DayPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 10, 0, 0),
            location="Town > Home > Kitchen",
            action_content="Review composition notes and plan",
        ),
    )

    assert len(items) == 2
    assert items[0].duration_minutes == 120
    assert items[0].start_time == datetime.datetime(2026, 2, 13, 8, 0, 0)


def test_generate_hour_plan_prompt_uses_single_day_plan_item() -> None:
    client = StubGenerationClient(
        responses=[
            json.dumps({"items": []}),
            json.dumps({"items": []}),
            json.dumps({"items": []}),
        ]
    )
    service = LlmGateway(client)

    _ = service.generate_hour_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 45, 0),
        day_plan_item=DayPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 7, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 9, 0, 0),
            location="Town > Home > Kitchen",
            action_content="Morning routine",
        ),
    )

    prompt = cast(str, client.call_kwargs[0]["prompt"])
    assert "Morning routine" in prompt
    assert "Attend lecture" not in prompt
    assert "Independent study" not in prompt


def test_generate_day_plan_coerces_year_to_today_when_month_day_match() -> None:
    service = LlmGateway(
        StubGenerationClient(
            responses=[
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2023-02-13T08:00:00",
                                "end_time": "2023-02-13T09:00:00",
                                "location": "Town > Home > Room",
                                "action_content": "Wake up and stretch.",
                            },
                            {
                                "start_time": "2023-02-13T09:00:00",
                                "end_time": "2023-02-13T10:00:00",
                                "location": "Town > Home > Kitchen",
                                "action_content": "Eat breakfast.",
                            },
                            {
                                "start_time": "2023-02-13T10:00:00",
                                "end_time": "2023-02-13T12:00:00",
                                "location": "Town > College > Theory Room",
                                "action_content": "Attend class.",
                            },
                            {
                                "start_time": "2023-02-13T12:00:00",
                                "end_time": "2023-02-13T13:00:00",
                                "location": "Town > Cafe > Patio",
                                "action_content": "Lunch with classmates.",
                            },
                            {
                                "start_time": "2023-02-13T13:00:00",
                                "end_time": "2023-02-13T15:00:00",
                                "location": "Town > Home > Desk",
                                "action_content": "Revise composition notes.",
                            },
                        ]
                    }
                )
            ]
        )
    )

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="Studied harmony and practiced composition in the evening.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert len(items) == 5
    assert all(item.start_time.year == 2026 for item in items)
    assert all(item.end_time.year == 2026 for item in items)


def test_generate_hour_plan_coerces_year_to_current_date_when_month_day_match() -> None:
    service = LlmGateway(
        StubGenerationClient(
            responses=[
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2023-02-13T08:00:00",
                                "end_time": "2023-02-13T10:00:00",
                                "location": "Town > Home > Kitchen",
                                "action_content": "Review composition notes over breakfast.",
                            },
                            {
                                "start_time": "2023-02-13T10:00:00",
                                "end_time": "2023-02-13T11:00:00",
                                "location": "Town > College > Theory Room",
                                "action_content": "Attend morning music theory class.",
                            },
                        ]
                    }
                )
            ]
        )
    )

    items = service.generate_hour_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
        day_plan_item=DayPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 10, 0, 0),
            location="Town > Home > Kitchen",
            action_content="Review composition notes and plan",
        ),
    )

    assert len(items) == 2
    assert all(item.start_time.year == 2026 for item in items)
    assert all(item.end_time.year == 2026 for item in items)


def test_generate_hour_plan_retries_once_on_truncated_json() -> None:
    client = StubGenerationClient(
        responses=[
            '{"items": [{"start_time": "2026-02-13T08:00:00", "end_time": "2026-02-13T09:30:00"',
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "2026-02-13T08:00:00",
                            "end_time": "2026-02-13T10:00:00",
                            "location": "Town > Home > Kitchen",
                            "action_content": "Review composition notes over breakfast.",
                        },
                        {
                            "start_time": "2026-02-13T10:00:00",
                            "end_time": "2026-02-13T11:00:00",
                            "location": "Town > College > Theory Room",
                            "action_content": "Attend morning music theory class.",
                        },
                    ]
                }
            ),
        ]
    )
    service = LlmGateway(client)

    items = service.generate_hour_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13),
        day_plan_item=DayPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 10, 0, 0),
            location="Town > Home > Kitchen",
            action_content="Review composition notes and plan",
        ),
    )

    assert len(items) == 2
    assert client.calls == 2


def test_generate_hour_plan_returns_empty_after_retry_exhaustion() -> None:
    client = StubGenerationClient(
        responses=[
            "not-json",
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "bad-time",
                            "end_time": "2026-02-13T08:30:00",
                            "location": "Town > Home > Kitchen",
                            "action_content": "Wake up",
                        }
                    ]
                }
            ),
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "also-bad",
                            "end_time": "2026-02-13T09:30:00",
                            "location": "Town > Home > Kitchen",
                            "action_content": "Breakfast",
                        }
                    ]
                }
            ),
        ]
    )
    service = LlmGateway(client)

    items = service.generate_hour_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
        day_plan_item=DayPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 8, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 10, 0, 0),
            location="Town > Home > Kitchen",
            action_content="Review composition notes and plan",
        ),
    )

    assert items == []
    assert client.calls == 3


def test_generate_minute_plan_parses_json_items() -> None:
    service = LlmGateway(
        StubGenerationClient(
            responses=[
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2026-02-13T12:00:00",
                                "end_time": "2026-02-13T12:10:00",
                                "location": "Town > Home > Study",
                                "action_content": "Review motif variations.",
                            },
                            {
                                "start_time": "2026-02-13T12:10:00",
                                "end_time": "2026-02-13T12:15:00",
                                "location": "Town > Home > Study",
                                "action_content": "Write transition phrase.",
                            },
                        ]
                    }
                )
            ]
        )
    )

    items = service.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
        hourly_plan_item=HourlyPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 13, 0, 0),
            location="Town > Home > Study",
            action_content="Draft project outline",
        ),
    )

    assert len(items) == 2
    assert items[1].duration_minutes == 5
    assert items[0].action_content == "Review motif variations."


def test_generate_minute_plan_prompt_uses_single_hourly_plan_item() -> None:
    client = StubGenerationClient(
        responses=[
            json.dumps({"items": []}),
            json.dumps({"items": []}),
            json.dumps({"items": []}),
        ]
    )
    service = LlmGateway(client)

    _ = service.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 12, 20, 0),
        hourly_plan_item=HourlyPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 13, 0, 0),
            location="Town > Home > Study",
            action_content="Draft project outline",
        ),
    )

    prompt = cast(str, client.call_kwargs[0]["prompt"])
    assert "Draft project outline" in prompt
    assert "Take lunch break" not in prompt
    assert "Resume focused writing" not in prompt


def test_generate_minute_plan_coerces_year_to_current_date_when_month_day_match() -> (
    None
):
    service = LlmGateway(
        StubGenerationClient(
            responses=[
                json.dumps(
                    {
                        "items": [
                            {
                                "start_time": "2023-02-13T12:00:00",
                                "end_time": "2023-02-13T12:10:00",
                                "location": "Town > Home > Study",
                                "action_content": "Review motif variations.",
                            },
                            {
                                "start_time": "2023-02-13T12:10:00",
                                "end_time": "2023-02-13T12:15:00",
                                "location": "Town > Home > Study",
                                "action_content": "Write transition phrase.",
                            },
                        ]
                    }
                )
            ]
        )
    )

    items = service.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
        hourly_plan_item=HourlyPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 13, 0, 0),
            location="Town > Home > Study",
            action_content="Draft project outline",
        ),
    )

    assert len(items) == 2
    assert all(item.start_time.year == 2026 for item in items)
    assert all(item.end_time.year == 2026 for item in items)


def test_generate_minute_plan_retries_once_on_schema_validation_error() -> None:
    client = StubGenerationClient(
        responses=[
            json.dumps({"items": "invalid-format"}),
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "2026-02-13T12:00:00",
                            "end_time": "2026-02-13T12:12:00",
                            "location": "Town > Home > Study",
                            "action_content": "Review motif variations.",
                        }
                    ]
                }
            ),
        ]
    )
    service = LlmGateway(client)

    items = service.generate_minute_plan(
        agent_name="Eddy Lin",
        current_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
        hourly_plan_item=HourlyPlanItem(
            start_time=datetime.datetime(2026, 2, 13, 12, 0, 0),
            end_time=datetime.datetime(2026, 2, 13, 13, 0, 0),
            location="Town > Home > Study",
            action_content="Draft project outline",
        ),
    )

    assert len(items) == 1
    assert items[0].duration_minutes == 12
    assert client.calls == 2
