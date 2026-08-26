import datetime

import numpy as np
from agents.memory.memory_manager import MemoryManager
from agents.memory.memory_manager import ObservationContext
from agents.memory.memory_manager import ReflectionContext
from agents.memory.memory_object import NodeType
from agents.memory.memory_stream import MemoryStream
from llm import ImportanceScoringContext
from llm.embedding_encoder import EmbeddingEncodingContext
from llm.llm_gateway import InsightWithCitation
from settings import EMBEDDING_DIMENSION


class StubScorer:
    def __init__(self, score_value: int):
        self.score_value: int = score_value
        self.last_context: ImportanceScoringContext | None = None

    def score(self, context: ImportanceScoringContext) -> int:
        self.last_context = context
        return self.score_value


class StubEmbeddingEncoder:
    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray:
        _ = context
        return np.zeros(EMBEDDING_DIMENSION)


def test_create_observation_uses_scorer_when_importance_missing() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=9)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=StubEmbeddingEncoder(),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)
    embedding = np.zeros(EMBEDDING_DIMENSION)

    memory = service.create_observation(
        content="카페 계약이 성사됐다.",
        now=now,
        embedding=embedding,
        context=ObservationContext(
            agent_name="Sujin Lee",
            identity_stable_set=["Sujin values reliable service."],
            current_plan="오후에 계약서 서명",
        ),
    )

    assert memory.importance == 9
    assert scorer.last_context is not None
    assert scorer.last_context.observation == "카페 계약이 성사됐다."


def test_create_observation_clamps_explicit_importance() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=5)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=StubEmbeddingEncoder(),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)
    embedding = np.zeros(EMBEDDING_DIMENSION)

    memory = service.create_observation(
        content="반복적인 일상 기록",
        now=now,
        embedding=embedding,
        context=ObservationContext(agent_name="Sujin Lee", identity_stable_set=[]),
        importance=42,
    )

    assert memory.importance == 10


def test_create_observation_uses_scorer_value() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=3)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=StubEmbeddingEncoder(),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)
    embedding = np.zeros(EMBEDDING_DIMENSION)

    memory = service.create_observation(
        content="마을 광장을 산책했다.",
        now=now,
        embedding=embedding,
        context=ObservationContext(agent_name="Jiho Park", identity_stable_set=[]),
    )

    assert memory.importance == 3


def test_create_reflection_stores_filtered_citations_and_scored_importance() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=11)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=StubEmbeddingEncoder(),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)
    embedding = np.zeros(EMBEDDING_DIMENSION)

    _ = service.create_observation(
        content="관찰 A",
        now=now,
        embedding=embedding,
        context=ObservationContext(agent_name="Jiho Park", identity_stable_set=[]),
        importance=5,
    )
    _ = service.create_observation(
        content="관찰 B",
        now=now,
        embedding=embedding,
        context=ObservationContext(agent_name="Jiho Park", identity_stable_set=[]),
        importance=6,
    )

    reflection = service.create_reflection(
        InsightWithCitation(
            context="지호는 수진의 업무 상태를 자주 신경 쓴다.",
            citation_memory_ids=[1, 999, 1, 0],
        ),
        now=now,
        context=ReflectionContext(
            agent_name="Jiho Park",
            identity_stable_set=["Jiho values thoughtful conversation."],
            current_plan="책 정리 연습 문제 마무리",
        ),
    )

    assert reflection.node_type.value == "REFLECTION"
    assert reflection.citations == [1, 0]
    assert reflection.importance == 10
    assert scorer.last_context is not None
    assert (
        scorer.last_context.observation == "지호는 수진의 업무 상태를 자주 신경 쓴다."
    )


def test_create_reflection_clamps_explicit_importance() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=5)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=StubEmbeddingEncoder(),
    )
    now = datetime.datetime(2026, 2, 13, 12, 0, 0)

    reflection = service.create_reflection(
        InsightWithCitation(
            context="반복되는 대화 패턴을 끊어야 한다.",
            citation_memory_ids=[],
        ),
        now=now,
        context=ReflectionContext(agent_name="Sujin Lee", identity_stable_set=[]),
        importance=0,
    )

    assert reflection.importance == 1
    assert reflection.citations == []


def test_get_retrieval_memories_includes_reflection_nodes_with_scores() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=5)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=StubEmbeddingEncoder(),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)

    observed = service.create_observation(
        content="기본 관찰",
        now=now,
        embedding=np.zeros(EMBEDDING_DIMENSION),
        context=ObservationContext(agent_name="Jiho Park", identity_stable_set=[]),
        importance=2,
    )

    reflected = service.create_reflection(
        InsightWithCitation(
            context="관찰된 사건에서 의미를 찾았다.",
            citation_memory_ids=[observed.id],
        ),
        now=now + datetime.timedelta(minutes=1),
        context=ReflectionContext(agent_name="Jiho Park", identity_stable_set=[]),
        importance=9,
    )

    retrieval = service.get_retrieval_memories(
        query="무엇이 중요했는가?",
        current_time=now + datetime.timedelta(minutes=2),
        top_k=2,
    )

    assert reflected in retrieval
    assert any(memory.node_type == NodeType.REFLECTION for memory in retrieval)


def test_reflection_can_reference_prior_reflection_memory() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=8)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=StubEmbeddingEncoder(),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)

    observation = service.create_observation(
        content="새로운 대화 기록",
        now=now,
        embedding=np.zeros(EMBEDDING_DIMENSION),
        context=ObservationContext(agent_name="Sujin Lee", identity_stable_set=[]),
        importance=7,
    )

    first_reflection = service.create_reflection(
        InsightWithCitation(
            context="첫 번째 통찰",
            citation_memory_ids=[observation.id],
        ),
        now=now + datetime.timedelta(minutes=1),
        context=ReflectionContext(
            agent_name="Sujin Lee",
            identity_stable_set=["Sujin values consistency."],
        ),
    )

    second_reflection = service.create_reflection(
        InsightWithCitation(
            context="두 번째 통찰",
            citation_memory_ids=[first_reflection.id, observation.id],
        ),
        now=now + datetime.timedelta(minutes=2),
        context=ReflectionContext(
            agent_name="Sujin Lee",
            identity_stable_set=["Sujin values consistency."],
        ),
    )

    assert first_reflection.citations == [observation.id]
    assert second_reflection.citations == [first_reflection.id, observation.id]


class KeywordEmbeddingEncoder:
    """지정한 키워드가 포함되면 유사한 벡터를, 아니면 직교 벡터를 반환하는 스텁."""

    def __init__(self, *, keyword: str):
        self.keyword: str = keyword

    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray:
        vector = np.zeros(EMBEDDING_DIMENSION)
        if self.keyword in context.text:
            vector[0] = 1.0
            vector[1] = 0.01
        else:
            vector[1] = 1.0
        return vector


def test_create_reflection_skips_semantically_duplicate_insight() -> None:
    stream = MemoryStream()
    scorer = StubScorer(score_value=7)
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=scorer,
        embedding_encoder=KeywordEmbeddingEncoder(keyword="수진"),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)

    first_reflection = service.create_reflection(
        InsightWithCitation(
            context="지호는 수진에 대해 깊은 개인적 호감을 느끼며 정서적 유대감을 가지고 있습니다.",
            citation_memory_ids=[],
        ),
        now=now,
        context=ReflectionContext(agent_name="Jiho Park", identity_stable_set=[]),
    )
    assert first_reflection is not None

    duplicate_reflection = service.create_reflection(
        InsightWithCitation(
            context="지호는 수진을 향한 자신의 감정이 단순한 우정을 넘어선 것임을 인지하고 있습니다.",
            citation_memory_ids=[],
        ),
        now=now,
        context=ReflectionContext(agent_name="Jiho Park", identity_stable_set=[]),
    )
    assert duplicate_reflection is None

    distinct_reflection = service.create_reflection(
        InsightWithCitation(
            context="병용은 계획적인 성향을 가지고 있다.",
            citation_memory_ids=[],
        ),
        now=now,
        context=ReflectionContext(agent_name="Jiho Park", identity_stable_set=[]),
    )
    assert distinct_reflection is not None

    stored_reflections = [
        memory for memory in stream.snapshot() if memory.node_type == NodeType.REFLECTION
    ]
    assert len(stored_reflections) == 2


# class StubReflectionService:
#     def __init__(self):
#         self.recorded_importance: list[int] = []

#     def record_observation_importance(self, importance: int) -> None:
#         self.recorded_importance.append(importance)


# def test_create_observation_records_importance_to_reflection_service() -> None:
#     stream = MemoryStream()
#     reflection_service = StubReflectionService()
#     service = MemoryManager(memory_stream=stream, reflection_service=reflection_service)

#     now = datetime.datetime(2026, 2, 13, 12, 0, 0)
#     embedding = np.zeros(EMBEDDING_DIMENSION)

#     _ = service.create_observation(
#         content="중요한 사건 발생",
#         now=now,
#         embedding=embedding,
#         importance=8,
#     )

#     assert reflection_service.recorded_importance == [8]


def test_get_retrieval_memories_falls_back_to_recent_when_stream_returns_empty() -> None:
    """SPEC.md §3: retrieval 후보가 비어있으면 최근 메모리로 fallback한다."""
    stream = MemoryStream()
    service = MemoryManager(
        memory_stream=stream,
        importance_scorer=StubScorer(score_value=5),
        embedding_encoder=StubEmbeddingEncoder(),
    )

    now = datetime.datetime(2026, 2, 13, 12, 0, 0)
    embedding = np.zeros(EMBEDDING_DIMENSION)
    older = service.create_observation(
        content="오래된 사건",
        now=now,
        embedding=embedding,
        context=ObservationContext(agent_name="Sujin Lee", identity_stable_set=[]),
        importance=4,
    )
    newer = service.create_observation(
        content="최근 사건",
        now=now + datetime.timedelta(minutes=5),
        embedding=embedding,
        context=ObservationContext(agent_name="Sujin Lee", identity_stable_set=[]),
        importance=4,
    )

    # retrieval scorer가 후보를 하나도 못 찾은 상황을 시뮬레이션한다.
    stream.retrieve = lambda **kwargs: []  # type: ignore[method-assign]

    query_time = now + datetime.timedelta(minutes=10)
    fallback = service.get_retrieval_memories(
        "아무 쿼리", current_time=query_time, top_k=2
    )

    assert [memory.id for memory in fallback] == [newer.id, older.id]
    assert all(memory.last_accessed_at == query_time for memory in fallback)
