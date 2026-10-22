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


def _combined_json(*, should_react: bool, utterance: str) -> str:
    return json.dumps(
        {
            "should_react": should_react,
            "reason": "r",
            "thought": "t",
            "critique": "c",
            "end_dialogue": False,
            "utterance": utterance,
        }
    )


def _history_input() -> ReactionDecisionInput:
    base = _input()
    return ReactionDecisionInput(
        agent_identity=base.agent_identity,
        current_time=base.current_time,
        observation_content=base.observation_content,
        dialogue_history=[("수진 씨, 오늘 테스트 어땠어요?", "none")],
        profile=base.profile,
        retrieved_memories=[],
        language="ko",
    )


def test_combined_response_finishes_in_one_llm_call() -> None:
    client = StubGenerationClient(
        responses=[_combined_json(should_react=True, utterance="안녕하세요, 지호예요.")]
    )
    runner = ReactionGraphRunner(generation_client=client, embedding_encoder=None)

    decision = runner.decide_reaction(_input())

    assert client.calls == 1
    assert decision.should_react is True
    assert decision.reaction == "안녕하세요, 지호예요."
    assert decision.thought == "t"
    assert decision.trace.combined_fallback_reason == ""


def test_combined_response_no_reaction_has_empty_utterance_in_one_call() -> None:
    client = StubGenerationClient(
        responses=[_combined_json(should_react=False, utterance="")]
    )
    runner = ReactionGraphRunner(generation_client=client, embedding_encoder=None)

    decision = runner.decide_reaction(_input())

    assert client.calls == 1
    assert decision.should_react is False
    assert decision.reaction == ""


def test_combined_parse_failure_falls_back_to_two_stage() -> None:
    client = StubGenerationClient(
        responses=[
            "not-json",
            _intent_json(should_react=True, reason="react"),
            _utterance_json(utterance="좋은 아침이에요.", reason="greet"),
        ]
    )
    runner = ReactionGraphRunner(generation_client=client, embedding_encoder=None)

    decision = runner.decide_reaction(_input())

    assert client.calls == 3
    assert decision.reaction == "좋은 아침이에요."
    assert decision.trace.combined_fallback_reason == "json_parse_error_or_non_object"


def test_combined_without_utterance_key_generates_utterance_separately() -> None:
    client = StubGenerationClient(
        responses=[
            _intent_json(should_react=True, reason="react"),
            _utterance_json(utterance="네, 들려주세요.", reason="respond"),
        ]
    )
    runner = ReactionGraphRunner(generation_client=client, embedding_encoder=None)

    decision = runner.decide_reaction(_input())

    assert client.calls == 2
    assert decision.reaction == "네, 들려주세요."
    assert decision.trace.combined_fallback_reason == ""


def test_retry_after_combined_empty_utterance_regenerates_utterance_only() -> None:
    prompts: list[str] = []

    class RecordingClient(StubGenerationClient):
        def generate(self, **kwargs: object) -> str:
            prompts.append(str(kwargs["prompt"]))
            return super().generate(**kwargs)

    client = RecordingClient(
        responses=[
            _combined_json(should_react=True, utterance=""),
            _utterance_json(utterance="좋아요, 더 들려주세요.", reason="respond"),
        ]
    )
    runner = ReactionGraphRunner(generation_client=client, embedding_encoder=None)

    decision = runner.decide_reaction(_history_input())

    assert client.calls == 2
    assert decision.reaction == "좋아요, 더 들려주세요."
    assert decision.trace.partner_retry_count == 1
    assert "empty when should_react is false" in prompts[0]
    assert "empty when should_react is false" not in prompts[1]
    assert '"utterance": "<string>"' in prompts[1]
