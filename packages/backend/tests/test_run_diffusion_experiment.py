from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

import pytest
from agents.evaluation.diffusion import DiffusionResult
from agents.sim_agent import SimAgent
from run_diffusion_experiment import DiffusionExperimentReport, _require_agent


@dataclass
class DummyIdentity:
    id: str


def _agent(agent_id: str) -> SimAgent:
    return cast(SimAgent, SimpleNamespace(identity=DummyIdentity(id=agent_id)))


def test_require_agent_finds_matching_agent_id() -> None:
    agents = [_agent("jiho"), _agent("sujin")]
    runtime = SimpleNamespace(agents=agents)

    found = _require_agent(runtime, "sujin")

    assert found is agents[1]


def test_require_agent_raises_with_available_ids_on_miss() -> None:
    runtime = SimpleNamespace(agents=[_agent("jiho"), _agent("sujin")])

    with pytest.raises(ValueError, match="jiho.*sujin|sujin.*jiho"):
        _require_agent(runtime, "minji")


def test_report_to_json_flattens_diffusion_result() -> None:
    report = DiffusionExperimentReport(
        seed_holder_name="정우",
        seed_fact_content="하은이 전시를 연다는 소식",
        interview_question="하은이 전시를 연다는 걸 아는가?",
        run_duration_seconds=60.0,
        turns_elapsed=12,
        diffusion=DiffusionResult(aware_agent_names=["정우", "하은"], total_agent_count=6),
        per_agent_aware={"정우": True, "하은": True, "지호": False},
        per_agent_reason={"정우": "직접 들었다", "하은": "본인 일정이다", "지호": "들은 적 없다"},
    )

    payload = report.to_json()

    assert '"aware_count": 2' in payload
    assert '"total_agent_count": 6' in payload
    assert '"rate": ' in payload
    assert '"정우": true' in payload
