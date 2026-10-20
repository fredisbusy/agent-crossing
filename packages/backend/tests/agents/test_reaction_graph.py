import datetime
import json

from agents.agent import AgentIdentity, AgentProfile, ExtendedPersona, FixedPersona
from agents.reaction import (
    ReactionDecisionInput,
    ReactionGraphRunner,
)


class StubGenerationClient:
    def __init__(self, responses: list[str]):
        self.responses: list[str] = list(responses)
        self.calls: int = 0

    def generate(self, **_: object) -> str:
        index = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        return self.responses[index]


def _intent_json(*, should_react: bool, reason: str) -> str:
    return json.dumps({"should_react": should_react, "reason": reason})


def _utterance_json(*, utterance: str, reason: str) -> str:
    return json.dumps({"utterance": utterance, "reason": reason})


def _input() -> ReactionDecisionInput:
    return ReactionDecisionInput(
        agent_identity=AgentIdentity(
            id="jiho",
            name="Jiho Park",
            age=29,
            traits=["kind"],
        ),
        current_time=datetime.datetime(2026, 2, 27, 14, 0, 0),
        observation_content="Jiho encountered Sujin near the cafe.",
        dialogue_history=[],
        profile=AgentProfile(
            fixed=FixedPersona(identity_stable_set=["Jiho helps neighbors."]),
            extended=ExtendedPersona(
                lifestyle_and_routine=["Morning library routine."],
                current_plan_context=["Finish workbook."],
            ),
        ),
        retrieved_memories=[],
        language="ko",
    )


def test_reaction_graph_runner_finishes_without_utterance_when_intent_rejects() -> None:
    runner = ReactionGraphRunner(
        generation_client=StubGenerationClient(
            responses=[_intent_json(should_react=False, reason="stay_silent")]
        ),
        embedding_encoder=None,
    )

    decision = runner.decide_reaction(_input())

    assert decision.should_react is False
    assert decision.reason == "stay_silent"
    assert decision.trace.partner_retry_count == 0


def test_reaction_graph_runner_retries_partner_nudge_once() -> None:
    runner = ReactionGraphRunner(
        generation_client=StubGenerationClient(
            responses=[
                _intent_json(should_react=True, reason="react"),
                _utterance_json(utterance="", reason="silent"),
                _utterance_json(utterance="좋아요, 더 들려주세요.", reason="respond"),
            ]
        ),
        embedding_encoder=None,
    )

    result = runner.decide_reaction(
        ReactionDecisionInput(
            agent_identity=_input().agent_identity,
            current_time=_input().current_time,
            observation_content=_input().observation_content,
            dialogue_history=[("수진 씨, 오늘 테스트 어땠어요?", "none")],
            profile=_input().profile,
            retrieved_memories=[],
            language="ko",
        )
    )

    assert result.should_react is True
    assert result.reaction == "좋아요, 더 들려주세요."
    assert result.trace.partner_retry_count == 1
