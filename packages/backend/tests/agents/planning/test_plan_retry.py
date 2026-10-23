import datetime
import json

from agents.planning.graph import MAX_PARSE_RETRIES, PlanningGraphRunner
from agents.planning.models import DayPlanItem, HourlyPlanItem
from llm.clients.types import LlmGenerateOptions

NOW = datetime.datetime(2026, 2, 13, 9, 0)
DAY_ITEM = DayPlanItem(
    start_time=NOW,
    end_time=NOW + datetime.timedelta(hours=2),
    location="Town > Cafe",
    action_content="coffee",
)


class ScriptedClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.prompts: list[str] = []

    def complete_planning_prompt(self, *, prompt: str, options: LlmGenerateOptions) -> str:
        self.prompts.append(prompt)
        index = min(len(self.prompts) - 1, len(self.responses) - 1)
        return self.responses[index]


def _valid_hourly_response() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "start_time": NOW.isoformat(),
                    "end_time": (NOW + datetime.timedelta(hours=1)).isoformat(),
                    "location": "Town > Cafe",
                    "action_content": "order coffee",
                }
            ]
        }
    )


def _run_hourly(client: ScriptedClient) -> list[HourlyPlanItem]:
    runner = PlanningGraphRunner(planning_client=client)
    return runner.generate_hourly_plan(
        agent_name="Eddy", current_time=NOW, day_plan_item=DAY_ITEM
    )


def test_gives_up_with_empty_list_after_max_calls() -> None:
    client = ScriptedClient(["not json"])

    assert _run_hourly(client) == []
    assert len(client.prompts) == MAX_PARSE_RETRIES + 1 == 3


def test_empty_items_response_triggers_retry() -> None:
    client = ScriptedClient([json.dumps({"items": []}), _valid_hourly_response()])

    items = _run_hourly(client)

    assert len(items) == 1
    assert len(client.prompts) == 2


def test_retry_prompt_carries_failure_reason_and_truncated_previous_response() -> None:
    bad_response = "x" * 300
    client = ScriptedClient([bad_response, _valid_hourly_response()])

    _run_hourly(client)

    retry_prompt = client.prompts[1]
    assert retry_prompt.startswith(client.prompts[0])
    assert "Failure reason:" in retry_prompt
    assert "required hourly plan JSON schema" in retry_prompt
    assert repr("x" * 180) in retry_prompt
    assert "x" * 181 not in retry_prompt
