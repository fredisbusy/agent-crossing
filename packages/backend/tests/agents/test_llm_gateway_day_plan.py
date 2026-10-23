import datetime
import json

from agents.llm_gateway import LlmGateway
from llm_gateway_helpers import (
    StubGenerationClient,
)


def test_generate_day_plan_parses_json_items() -> None:
    client = StubGenerationClient(
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
                            "end_time": "2026-02-13T12:00:00",
                            "location": "Town > College > Theory Room",
                            "action_content": "Attend morning music theory class.",
                        },
                        {
                            "start_time": "2026-02-13T12:00:00",
                            "end_time": "2026-02-13T14:00:00",
                            "location": "Town > College > Studio",
                            "action_content": "Draft harmonic progression for project.",
                        },
                        {
                            "start_time": "2026-02-13T15:00:00",
                            "end_time": "2026-02-13T16:00:00",
                            "location": "Town > Cafe > Patio",
                            "action_content": "Meet classmate for feedback session.",
                        },
                        {
                            "start_time": "2026-02-13T17:00:00",
                            "end_time": "2026-02-13T19:00:00",
                            "location": "Town > Home > Desk",
                            "action_content": "Revise composition and annotate changes.",
                        },
                    ]
                }
            )
        ]
    )
    service = LlmGateway(client)

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="woke up at 7:00 am and got ready to sleep around 10 pm.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert len(items) == 5
    assert items[0].action_content == "Review composition notes over breakfast."
    assert items[0].location == "Town > Home > Kitchen"
    assert items[0].start_time == datetime.datetime(2026, 2, 13, 8, 0, 0)


def test_generate_day_plan_returns_empty_on_parse_failure() -> None:
    client = StubGenerationClient(responses=["not-json"])
    service = LlmGateway(client)

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="woke up at 7:00 am and got ready to sleep around 10 pm.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert items == []


def test_generate_day_plan_returns_empty_if_too_few_items() -> None:
    client = StubGenerationClient(
        responses=[
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "2026-02-13T08:00:00",
                            "end_time": "2026-02-13T09:00:00",
                            "location": "Town > Home > Room",
                            "action_content": "Wake up and brush teeth.",
                        },
                        {
                            "start_time": "2026-02-13T09:00:00",
                            "end_time": "2026-02-13T10:00:00",
                            "location": "Town > Home > Kitchen",
                            "action_content": "Have breakfast.",
                        },
                        {
                            "start_time": "2026-02-13T10:00:00",
                            "end_time": "2026-02-13T11:00:00",
                            "location": "Town > Street > Bus Stop",
                            "action_content": "Head to class.",
                        },
                    ]
                }
            )
        ]
    )
    service = LlmGateway(client)

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="woke up at 7:00 am and got ready to sleep around 10 pm.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert items == []


def test_generate_day_plan_dedupes_and_truncates_to_max() -> None:
    client = StubGenerationClient(
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
                            "start_time": "2026-02-13T08:00:00",
                            "end_time": "2026-02-13T10:00:00",
                            "location": "Town > Home > Kitchen",
                            "action_content": "Review composition notes over breakfast. ",
                        },
                        {
                            "start_time": "2026-02-13T10:00:00",
                            "end_time": "2026-02-13T11:00:00",
                            "location": "Town > College > Theory Room",
                            "action_content": "Attend morning music theory class.",
                        },
                        {
                            "start_time": "2026-02-13T12:00:00",
                            "end_time": "2026-02-13T14:00:00",
                            "location": "Town > College > Studio",
                            "action_content": "Draft harmonic progression for project.",
                        },
                        {
                            "start_time": "2026-02-13T14:00:00",
                            "end_time": "2026-02-13T15:00:00",
                            "location": "Town > Cafe > Patio",
                            "action_content": "Meet classmate for feedback session.",
                        },
                        {
                            "start_time": "2026-02-13T16:00:00",
                            "end_time": "2026-02-13T18:00:00",
                            "location": "Town > Home > Desk",
                            "action_content": "Revise composition and annotate changes.",
                        },
                        {
                            "start_time": "2026-02-13T18:00:00",
                            "end_time": "2026-02-13T19:00:00",
                            "location": "Town > Cafe > Table",
                            "action_content": "Take lunch with classmate.",
                        },
                        {
                            "start_time": "2026-02-13T20:00:00",
                            "end_time": "2026-02-13T21:00:00",
                            "location": "Town > Home > Practice Room",
                            "action_content": "Practice instrument for 30 minutes.",
                        },
                        {
                            "start_time": "2026-02-13T21:00:00",
                            "end_time": "2026-02-13T22:00:00",
                            "location": "Town > Home > Desk",
                            "action_content": "Log today's notes in planner.",
                        },
                    ]
                }
            )
        ]
    )
    service = LlmGateway(client)

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="woke up at 7:00 am and got ready to sleep around 10 pm.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert len(items) == 8
    assert items[0].action_content == "Review composition notes over breakfast."
    assert items[1].action_content == "Attend morning music theory class."
    assert items[-1].action_content == "Log today's notes in planner."


def test_generate_day_plan_retries_once_on_truncated_json() -> None:
    client = StubGenerationClient(
        responses=[
            '{"items": [{"start_time": "2026-02-13T08:00:00", "end_time": "2026-02-13T08:20:00"',
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "2026-02-13T08:00:00",
                            "end_time": "2026-02-13T09:00:00",
                            "location": "Town > Home > Room",
                            "action_content": "Wake up",
                        },
                        {
                            "start_time": "2026-02-13T09:00:00",
                            "end_time": "2026-02-13T10:00:00",
                            "location": "Town > Home > Kitchen",
                            "action_content": "Eat breakfast",
                        },
                        {
                            "start_time": "2026-02-13T10:00:00",
                            "end_time": "2026-02-13T11:00:00",
                            "location": "Town > College > Theory Room",
                            "action_content": "Class",
                        },
                        {
                            "start_time": "2026-02-13T11:00:00",
                            "end_time": "2026-02-13T12:00:00",
                            "location": "Town > Home > Practice Room",
                            "action_content": "Practice",
                        },
                        {
                            "start_time": "2026-02-13T12:00:00",
                            "end_time": "2026-02-13T13:00:00",
                            "location": "Town > Home > Desk",
                            "action_content": "Review",
                        },
                        {
                            "start_time": "2026-02-13T13:00:00",
                            "end_time": "2026-02-13T14:00:00",
                            "location": "Town > Park > Bench",
                            "action_content": "Reflect",
                        },
                    ]
                }
            ),
        ]
    )
    service = LlmGateway(client)

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="woke up at 7:00 am and got ready to sleep around 10 pm.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert len(items) == 6
    assert items[0].action_content == "Wake up"
    assert client.calls == 2


def test_generate_day_plan_retries_once_on_schema_validation_error() -> None:
    client = StubGenerationClient(
        responses=[
            json.dumps({"items": "invalid-format"}),
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
                        {
                            "start_time": "2026-02-13T12:00:00",
                            "end_time": "2026-02-13T14:00:00",
                            "location": "Town > College > Studio",
                            "action_content": "Draft harmonic progression for project.",
                        },
                        {
                            "start_time": "2026-02-13T14:00:00",
                            "end_time": "2026-02-13T15:00:00",
                            "location": "Town > Cafe > Patio",
                            "action_content": "Meet classmate for feedback session.",
                        },
                        {
                            "start_time": "2026-02-13T16:00:00",
                            "end_time": "2026-02-13T18:00:00",
                            "location": "Town > Home > Desk",
                            "action_content": "Revise composition and annotate changes.",
                        },
                    ]
                }
            ),
        ]
    )
    service = LlmGateway(client)

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="woke up at 7:00 am and got ready to sleep around 10 pm.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert len(items) == 5
    assert client.calls == 2


def test_generate_day_plan_returns_empty_after_retry_exhaustion() -> None:
    client = StubGenerationClient(
        responses=[
            "not-json",
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "2026-02-13T08:00:00",
                            "end_time": "2026-02-13T08:30:00",
                            "location": "Town > Home > Room",
                            "action_content": "Too few",
                        },
                        {
                            "start_time": "2026-02-13T08:40:00",
                            "end_time": "2026-02-13T09:00:00",
                            "location": "Town > Home > Kitchen",
                            "action_content": "items",
                        },
                    ]
                }
            ),
            json.dumps(
                {
                    "items": [
                        {
                            "start_time": "bad-time",
                            "end_time": "2026-02-13T08:20:00",
                            "location": "Town > Home > Room",
                            "action_content": "Wake",
                        },
                        {
                            "start_time": "bad-time",
                            "end_time": "2026-02-13T08:20:00",
                            "location": "Town > Home > Room",
                            "action_content": "Eat",
                        },
                        {
                            "start_time": "bad-time",
                            "end_time": "2026-02-13T08:20:00",
                            "location": "Town > Home > Room",
                            "action_content": "Class",
                        },
                        {
                            "start_time": "bad-time",
                            "end_time": "2026-02-13T08:20:00",
                            "location": "Town > Home > Room",
                            "action_content": "Practice",
                        },
                        {
                            "start_time": "bad-time",
                            "end_time": "2026-02-13T08:20:00",
                            "location": "Town > Home > Room",
                            "action_content": "Review",
                        },
                    ]
                }
            ),
        ]
    )
    service = LlmGateway(client)

    items = service.generate_day_plan(
        agent_name="Eddy Lin",
        age=19,
        innate_traits=["friendly", "outgoing", "hospitable"],
        persona_background="Music theory student focusing on composition.",
        yesterday_date=datetime.datetime(2026, 2, 12),
        yesterday_summary="woke up at 7:00 am and got ready to sleep around 10 pm.",
        today_date=datetime.datetime(2026, 2, 13),
    )

    assert items == []
    assert client.calls == 3
