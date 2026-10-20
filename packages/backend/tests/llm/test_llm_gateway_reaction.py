from typing import cast

from llm.guardrails.similarity import EmbeddingEncoder
from llm.llm_gateway import LlmGateway
from llm_gateway_helpers import (
    StubEmbeddingEncoder,
    StubGenerationClient,
    build_reaction_input,
    intent_json,
    reaction_json,
)


def test_decide_reaction_retries_when_first_output_is_repetitive() -> None:
    client = StubGenerationClient(
        responses=[
            intent_json(should_react=True, reason="react"),
            reaction_json(
                should_react=True,
                reaction="안녕하세요 오늘 연습 문제를 마무리하려고 해요",
                reason="first",
            ),
            reaction_json(
                should_react=True,
                reaction="수진 씨, 디카프 테스트 반응은 어땠나요?",
                reason="retry",
            ),
        ]
    )
    service = LlmGateway(client)

    decision = service.decide_reaction(
        build_reaction_input(
            dialogue_history=[
                ("안녕하세요 오늘 연습 문제를 마무리하려고 해요", "none"),
            ]
        )
    )

    assert decision.reaction == "수진 씨, 디카프 테스트 반응은 어땠나요?"
    assert client.calls == 3


def test_decide_reaction_uses_first_output_when_not_repetitive() -> None:
    client = StubGenerationClient(
        responses=[
            intent_json(should_react=True, reason="react"),
            reaction_json(
                should_react=True,
                reaction="수진 씨, 이번 주 테스트한 블렌드는 어땠어요?",
                reason="ok",
            ),
        ]
    )
    service = LlmGateway(client)

    decision = service.decide_reaction(
        build_reaction_input(
            dialogue_history=[
                ("안녕하세요", "none"),
            ]
        )
    )

    assert decision.reaction == "수진 씨, 이번 주 테스트한 블렌드는 어땠어요?"
    assert client.calls == 2


def test_decide_reaction_semantic_retry_when_embedding_similarity_is_high() -> None:
    client = StubGenerationClient(
        responses=[
            intent_json(should_react=True, reason="react"),
            reaction_json(
                should_react=True,
                reaction="같은 말 반복",
                reason="first",
            ),
            reaction_json(
                should_react=True,
                reaction="다른 반응으로 바꿔볼게요",
                reason="retry",
            ),
        ]
    )
    embedding = StubEmbeddingEncoder(
        vectors={
            "같은 말 반복": [1.0, 0.0],
            "다른 반응으로 바꿔볼게요": [0.0, 1.0],
            "같은 말": [1.0, 0.0],
        }
    )
    service = LlmGateway(client, embedding_encoder=cast(EmbeddingEncoder, embedding))

    decision = service.decide_reaction(
        build_reaction_input(dialogue_history=[("partner", "같은 말")])
    )

    assert client.calls == 3
    assert decision.reaction == "다른 반응으로 바꿔볼게요"
    assert decision.trace.semantic_retry_count == 1


def test_decide_reaction_parses_thought_critique_and_utterance() -> None:
    client = StubGenerationClient(
        responses=[
            intent_json(
                should_react=True,
                reason="short",
                thought="상대 근황 확인과 카페 맥락 연결",
                critique="반복 인사를 피하고 구체 질문으로 시작",
            ),
            reaction_json(
                should_react=True,
                reaction="수진 씨, 테스트한 디카프 반응은 어땠어요?",
                reason="utterance_stage",
                use_utterance_field=True,
            ),
        ]
    )
    service = LlmGateway(client)

    decision = service.decide_reaction(build_reaction_input(dialogue_history=[]))

    assert decision.should_react is True
    assert decision.reaction == "수진 씨, 테스트한 디카프 반응은 어땠어요?"
    assert decision.thought == "상대 근황 확인과 카페 맥락 연결"
    assert decision.critique == "반복 인사를 피하고 구체 질문으로 시작"
    assert decision.trace.parse_success is True


def test_decide_reaction_propagates_end_dialogue_signal() -> None:
    client = StubGenerationClient(
        responses=[
            intent_json(should_react=True, reason="wrap_up", end_dialogue=True),
            reaction_json(
                should_react=True,
                reaction="그럼 난 이만 가볼게.",
                reason="closing",
                end_dialogue=True,
                use_utterance_field=True,
            ),
        ]
    )
    service = LlmGateway(client)

    decision = service.decide_reaction(
        build_reaction_input(dialogue_history=[("반가워", "응")])
    )

    assert decision.should_react is True
    assert decision.end_dialogue is True
    assert decision.reaction == "그럼 난 이만 가볼게."


def test_decide_reaction_records_parse_failure_trace() -> None:
    client = StubGenerationClient(responses=["not-json"])
    service = LlmGateway(client)

    decision = service.decide_reaction(build_reaction_input(dialogue_history=[]))

    assert decision.should_react is False
    assert decision.trace.parse_success is False
    assert decision.trace.fallback_reason == "parse_failure"


def test_decide_reaction_retries_once_for_partner_utterance_when_silent() -> None:
    client = StubGenerationClient(
        responses=[
            intent_json(should_react=True, reason="react"),
            reaction_json(should_react=True, reaction="", reason="first_silent"),
            reaction_json(
                should_react=True,
                reaction="좋아요, 방금 이야기해준 블렌드가 궁금해요.",
                reason="respond_after_nudge",
            ),
        ]
    )
    service = LlmGateway(client)

    decision = service.decide_reaction(
        build_reaction_input(
            dialogue_history=[("수진 씨, 오늘 테스트 어땠어요?", "none")]
        )
    )

    assert client.calls == 3
    assert decision.should_react is True
    assert decision.trace.partner_retry_count == 1


def test_decide_reaction_repairs_truncated_json_once() -> None:
    client = StubGenerationClient(
        responses=[
            intent_json(should_react=True, reason="react"),
            '{"should_react": true, "utterance": "좋아요", "reason": "ok"',
        ]
    )
    service = LlmGateway(client)

    decision = service.decide_reaction(build_reaction_input(dialogue_history=[]))

    assert decision.should_react is True
    assert decision.reaction == "좋아요"
    assert decision.trace.parse_success is True
    assert decision.trace.parse_error == "repaired_once"
