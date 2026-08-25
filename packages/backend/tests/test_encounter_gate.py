import datetime
import json

from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona
from agents.reaction.encounter import EncounterDecisionInput, EncounterGate


class StubGenerationClient:
    def __init__(self, response: str) -> None:
        self.response: str = response
        self.calls: int = 0
        self.last_prompt: str = ""

    def generate(self, *, prompt: str, **_: object) -> str:
        self.calls += 1
        self.last_prompt = prompt
        return self.response


def _input() -> EncounterDecisionInput:
    return EncounterDecisionInput(
        self_identity=AgentIdentity(id="jiho", name="Jiho Park", age=29, traits=["다정함"]),
        other_identity=AgentIdentity(id="sujin", name="Sujin Lee", age=27, traits=["활발함"]),
        self_profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=["Sujin을 좋아한다."]),
            extended=ExtendedPersona(lifestyle_and_routine=[], current_plan_context=[]),
        ),
        current_time=datetime.datetime(2026, 8, 24, 10, 0),
        retrieved_memories=[],
    )


def test_encounter_gate_returns_converse_decision() -> None:
    client = StubGenerationClient(
        json.dumps(
            {
                "should_converse": True,
                "relationship_summary": "Jiho는 Sujin에게 호감이 있다.",
                "context_summary": "둘 다 한가한 시간에 마주쳤다.",
                "reason": "대화할 여유가 있다.",
            }
        )
    )
    gate = EncounterGate(generation_client=client)

    decision = gate.evaluate(_input())

    assert decision.should_converse is True
    assert decision.relationship_summary
    assert decision.context_summary
    assert "[Agent's Summary Description]" in client.last_prompt


def test_encounter_gate_returns_pass_by_decision() -> None:
    client = StubGenerationClient(
        json.dumps(
            {
                "should_converse": False,
                "relationship_summary": "아직 서로 잘 모른다.",
                "context_summary": "둘 다 바쁜 업무 중이다.",
                "reason": "지금은 대화할 시점이 아니다.",
            }
        )
    )
    gate = EncounterGate(generation_client=client)

    decision = gate.evaluate(_input())

    assert decision.should_converse is False


def test_encounter_gate_defaults_to_converse_on_parse_failure() -> None:
    client = StubGenerationClient("not json")
    gate = EncounterGate(generation_client=client)

    decision = gate.evaluate(_input())

    assert decision.should_converse is True
    assert decision.trace.parse_success is False
