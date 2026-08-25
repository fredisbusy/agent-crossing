import datetime
import json

from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona
from agents.planning.react_gate import PlanDisruptionGate, PlanDisruptionInput


class StubGenerationClient:
    def __init__(self, response: str) -> None:
        self.response: str = response
        self.calls: int = 0
        self.last_prompt: str = ""

    def generate(self, *, prompt: str, **_: object) -> str:
        self.calls += 1
        self.last_prompt = prompt
        return self.response


def _input(observation: str) -> PlanDisruptionInput:
    return PlanDisruptionInput(
        agent_identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["차분함"]),
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=["도서관 사서다."]),
            extended=ExtendedPersona(
                lifestyle_and_routine=[], current_plan_context=["그림을 그리는 중이다."]
            ),
        ),
        current_time=datetime.datetime(2026, 8, 24, 10, 0),
        agent_status="이젤 앞에서 그림을 그리는 중",
        observation_content=observation,
    )


def test_plan_disruption_gate_continues_when_observation_is_ordinary() -> None:
    client = StubGenerationClient(
        json.dumps({"should_react": False, "reason": "이젤은 평소와 같은 배경 사물이다."})
    )
    gate = PlanDisruptionGate(generation_client=client)

    decision = gate.evaluate(_input("근처에 이젤이 놓여 있다."))

    assert decision.should_react is False
    assert "이젤" in decision.reason
    assert "[Agent's Summary Description]" in client.last_prompt
    assert "It is 2026-08-24T10:00:00." in client.last_prompt


def test_plan_disruption_gate_reacts_when_observation_disrupts_plan() -> None:
    client = StubGenerationClient(
        json.dumps({"should_react": True, "reason": "아이가 위험한 상황에 처했다."})
    )
    gate = PlanDisruptionGate(generation_client=client)

    decision = gate.evaluate(_input("아들이 도로로 뛰어드는 것을 목격했다."))

    assert decision.should_react is True
    assert decision.trace.parse_success is True


def test_plan_disruption_gate_defaults_to_continue_on_parse_failure() -> None:
    client = StubGenerationClient("not json")
    gate = PlanDisruptionGate(generation_client=client)

    decision = gate.evaluate(_input("아들이 도로로 뛰어드는 것을 목격했다."))

    assert decision.should_react is False
    assert decision.trace.parse_success is False


def test_plan_disruption_gate_skips_llm_call_for_empty_observation() -> None:
    client = StubGenerationClient(json.dumps({"should_react": True, "reason": "n/a"}))
    gate = PlanDisruptionGate(generation_client=client)

    decision = gate.evaluate(_input("   "))

    assert decision.should_react is False
    assert client.calls == 0
