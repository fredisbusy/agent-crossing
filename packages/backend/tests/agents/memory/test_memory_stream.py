import datetime

import numpy as np
import pytest
from agents.memory.memory_object import NodeType
from agents.memory.memory_stream import MemoryStream
from settings import EMBEDDING_DIMENSION


@pytest.fixture
def stream():
    return MemoryStream()


@pytest.fixture
def now():
    return datetime.datetime(2026, 2, 12, 12, 0, 0)


def unit_vector(index: int) -> np.ndarray:
    vector = np.zeros(EMBEDDING_DIMENSION, dtype=float)
    vector[index] = 1.0
    return vector


@pytest.fixture
def embedding():
    rng = np.random.default_rng(42)
    return rng.random(EMBEDDING_DIMENSION)


@pytest.fixture
def observation_kwargs(now, embedding):
    return {
        "node_type": NodeType.OBSERVATION,
        "citations": None,
        "content": "지호가 도서관에서 책을 빌렸다.",
        "now": now,
        "importance": 7,
        "embedding": embedding,
    }


@pytest.fixture
def stream_with_memory(stream, observation_kwargs):
    stream.add_memory(**observation_kwargs)
    return stream


def _add_memory(
    stream: MemoryStream,
    *,
    now: datetime.datetime,
    content: str,
    importance: int,
    embedding: np.ndarray,
):
    stream.add_memory(
        node_type=NodeType.OBSERVATION,
        citations=None,
        content=content,
        now=now,
        importance=importance,
        embedding=embedding,
    )


def test_add_memory(stream, observation_kwargs, now, embedding):
    stream.add_memory(**observation_kwargs)

    assert len(stream.memories) == 1

    memory = stream.memories[0]
    assert memory.id == 0
    assert memory.content == observation_kwargs["content"]
    assert memory.importance == observation_kwargs["importance"]
    assert memory.created_at == now
    assert np.array_equal(memory.embedding, embedding)

    stream.add_memory(
        node_type=NodeType.OBSERVATION,
        citations=None,
        content="두 번째 기억",
        now=now,
        importance=3,
        embedding=np.zeros(EMBEDDING_DIMENSION),
    )
    assert len(stream.memories) == 2
    assert stream.memories[1].id == 1


def test_retrieve_top_k_is_consistent_for_repeated_same_query(stream, now):
    query = unit_vector(0)

    _add_memory(
        stream,
        now=now - datetime.timedelta(hours=1),
        content="query와 매우 유사한 기억",
        importance=5,
        embedding=unit_vector(0),
    )
    _add_memory(
        stream,
        now=now - datetime.timedelta(hours=2),
        content="query와 어느 정도 유사한 기억",
        importance=5,
        embedding=unit_vector(0) * 0.8 + unit_vector(1) * 0.2,
    )
    _add_memory(
        stream,
        now=now - datetime.timedelta(hours=3),
        content="query와 덜 유사한 기억",
        importance=5,
        embedding=unit_vector(1) * 0.8 + unit_vector(0) * 0.2,
    )
    _add_memory(
        stream,
        now=now - datetime.timedelta(hours=4),
        content="query와 반대 방향 기억",
        importance=5,
        embedding=unit_vector(0) * -1.0,
    )

    first = stream.retrieve(query_embedding=query, current_time=now, top_k=3)
    second = stream.retrieve(query_embedding=query, current_time=now, top_k=3)

    first_ids = [m.id for m in first]
    second_ids = [m.id for m in second]

    assert first_ids == second_ids


def test_high_importance_memory_surfaces_when_relevance_and_recency_are_controlled(
    stream, now
):
    query = unit_vector(0)
    shared_embedding = unit_vector(0)

    _add_memory(
        stream,
        now=now,
        content="낮은 중요도",
        importance=2,
        embedding=shared_embedding,
    )
    _add_memory(
        stream,
        now=now,
        content="중간 중요도",
        importance=6,
        embedding=shared_embedding,
    )
    _add_memory(
        stream,
        now=now,
        content="높은 중요도",
        importance=10,
        embedding=shared_embedding,
    )

    top = stream.retrieve(query_embedding=query, current_time=now, top_k=1)

    assert len(top) == 1
    assert top[0].content == "높은 중요도"
    assert top[0].importance == 10


def test_retrieval_score_uses_default_equal_weights_with_normalized_components(
    stream, now
):
    query = unit_vector(0)

    _add_memory(
        stream,
        now=now,
        content="높은 relevance + 높은 importance",
        importance=10,
        embedding=unit_vector(0),
    )
    _add_memory(
        stream,
        now=now,
        content="낮은 relevance + 낮은 importance",
        importance=1,
        embedding=unit_vector(1),
    )

    scores = stream._calculate_retrieval_scores(
        memories=stream.memories,
        query_embedding=query,
        current_time=now,
    )
    score_by_content = {memory.content: score for memory, score in scores}

    # recency는 둘 다 동일하므로 정규화 결과 0.5로 동일, 차이는 relevance/importance에서만 발생
    assert score_by_content["높은 relevance + 높은 importance"] == pytest.approx(2.5)
    assert score_by_content["낮은 relevance + 낮은 importance"] == pytest.approx(0.5)

    # alpha=beta=gamma=1.0 기본 가중치 기준 score 범위 sanity check
    assert all(0.0 <= score <= 3.0 for score in score_by_content.values())


def test_add_memory_rejects_wrong_embedding_dimension(stream, now):
    with pytest.raises(ValueError):
        _add_memory(
            stream,
            now=now,
            content="잘못된 차원",
            importance=5,
            embedding=np.zeros(3),
        )


def test_retrieve_with_query_dimension_mismatch_keeps_system_usable(stream, now):
    _add_memory(
        stream,
        now=now,
        content="낮은 중요도",
        importance=2,
        embedding=np.zeros(EMBEDDING_DIMENSION),
    )
    _add_memory(
        stream,
        now=now,
        content="높은 중요도",
        importance=10,
        embedding=np.zeros(EMBEDDING_DIMENSION),
    )

    top = stream.retrieve(
        query_embedding=np.array([1.0, 0.0, 0.0]), current_time=now, top_k=1
    )

    assert len(top) == 1
    assert top[0].content == "높은 중요도"
