import datetime

import numpy as np
import pytest
from agents.memory.memory_object import MemoryObject, NodeType
from agents.memory.memory_stream import MemoryStream
from settings import EMBEDDING_DIMENSION

BASE = datetime.datetime(2026, 2, 12, 12, 0, 0)


def _add(
    stream: MemoryStream,
    created: datetime.datetime,
    importance: int,
    embedding: np.ndarray,
) -> None:
    stream.add_memory(
        node_type=NodeType.OBSERVATION,
        citations=None,
        content=f"memory-{len(stream.memories)}",
        now=created,
        importance=importance,
        embedding=embedding,
    )


def _reference_ranking(
    memories: list[MemoryObject],
    query: np.ndarray,
    current_time: datetime.datetime,
    top_k: int,
) -> list[int]:
    """SPEC §5 공식을 파이썬 루프로 그대로 옮긴 단순 참조 구현(기억 id 순위 반환)."""

    def norm(values: list[float]) -> list[float]:
        lo, hi = min(values), max(values)
        if lo == hi:
            return [0.5] * len(values)
        return [(v - lo) / (hi - lo) for v in values]

    rec = [
        0.995 ** ((current_time - m.last_accessed_at).total_seconds() / 3600)
        for m in memories
    ]
    imp = [float(m.importance) for m in memories]
    rel: list[float] = []
    for m in memories:
        denominator = float(np.linalg.norm(query) * np.linalg.norm(m.embedding))
        rel.append(
            0.0 if denominator == 0 else float(np.dot(query, m.embedding)) / denominator
        )
    scores = [a + b + c for a, b, c in zip(norm(rec), norm(imp), norm(rel))]
    ranked = sorted(
        zip(memories, scores), key=lambda x: (x[1], x[0].created_at), reverse=True
    )
    return [m.id for m, _ in ranked[:top_k]]


def _random_stream(seed: int, count: int) -> MemoryStream:
    rng = np.random.default_rng(seed)
    stream = MemoryStream()
    for _ in range(count):
        created = BASE - datetime.timedelta(minutes=int(rng.integers(0, 60 * 24 * 30)))
        _add(
            stream,
            created,
            int(rng.integers(1, 11)),
            rng.normal(size=EMBEDDING_DIMENSION),
        )
    return stream


@pytest.mark.parametrize("seed,count", [(1, 300), (2, 700), (3, 65), (4, 129)])
def test_retrieve_matches_reference_including_order(seed, count):
    stream = _random_stream(seed, count)
    rng = np.random.default_rng(seed + 100)
    for step in range(3):
        query = rng.normal(size=EMBEDDING_DIMENSION)
        now = BASE + datetime.timedelta(hours=step * 5)
        expected = _reference_ranking(stream.memories, query, now, top_k=20)
        result = stream.retrieve(query, top_k=20, current_time=now)
        assert [m.id for m in result] == expected
        assert all(m.last_accessed_at == now for m in result)


def test_incremental_add_after_retrieve_stays_consistent():
    stream = _random_stream(7, 100)
    rng = np.random.default_rng(8)
    stream.retrieve(rng.normal(size=EMBEDDING_DIMENSION), current_time=BASE)
    for _ in range(100):  # 용량 증가 경로를 지난다
        _add(
            stream, BASE, int(rng.integers(1, 11)), rng.normal(size=EMBEDDING_DIMENSION)
        )
    query = rng.normal(size=EMBEDDING_DIMENSION)
    now = BASE + datetime.timedelta(hours=1)
    expected = _reference_ranking(stream.memories, query, now, top_k=10)
    assert [
        m.id for m in stream.retrieve(query, top_k=10, current_time=now)
    ] == expected


def test_external_list_modification_rebuilds_cache():
    stream = _random_stream(9, 50)
    query = np.random.default_rng(10).normal(size=EMBEDDING_DIMENSION)
    stream.retrieve(query, current_time=BASE)
    removed = stream.memories.pop(10)
    stream.memories.append(removed)
    stream.memories.pop(0)
    now = BASE + datetime.timedelta(hours=2)
    expected = _reference_ranking(stream.memories, query, now, top_k=5)
    assert [m.id for m in stream.retrieve(query, top_k=5, current_time=now)] == expected


def test_ties_prefer_newer_created_at_then_earlier_insertion():
    stream = MemoryStream()
    embedding = np.ones(EMBEDDING_DIMENSION)
    # recency 동일(last_accessed_at 같음 불가 -> 같은 시각 생성), importance/relevance 동일
    _add(stream, BASE, 5, embedding)
    _add(stream, BASE, 5, embedding)
    _add(stream, BASE, 5, embedding)
    result = stream.retrieve(embedding, top_k=3, current_time=BASE)
    assert [m.id for m in result] == [0, 1, 2]

    older = MemoryStream()
    _add(older, BASE - datetime.timedelta(seconds=1), 5, embedding)
    _add(older, BASE, 5, embedding)
    # 두 기억의 last_accessed_at을 같게 맞춰 score를 완전히 동일하게 만든다
    for memory in older.memories:
        memory.last_accessed_at = BASE
    result = older.retrieve(embedding, top_k=2, current_time=BASE)
    assert [m.id for m in result] == [1, 0]


def test_zero_norm_embeddings_get_zero_relevance():
    stream = MemoryStream()
    _add(stream, BASE, 5, np.zeros(EMBEDDING_DIMENSION))
    _add(stream, BASE, 5, np.ones(EMBEDDING_DIMENSION))
    scores = dict(
        (m.id, s)
        for m, s in stream._calculate_retrieval_scores(
            stream.memories, np.ones(EMBEDDING_DIMENSION), BASE
        )
    )
    assert scores[0] == pytest.approx(0.5 + 0.5 + 0.0)
    assert scores[1] == pytest.approx(0.5 + 0.5 + 1.0)
    zero_query = stream.retrieve(
        np.zeros(EMBEDDING_DIMENSION), top_k=2, current_time=BASE
    )
    assert len(zero_query) == 2


def test_empty_stream_returns_nothing():
    stream = MemoryStream()
    query = np.ones(EMBEDDING_DIMENSION)
    assert stream.retrieve(query, current_time=BASE) == []
    assert stream._calculate_retrieval_scores([], query, BASE) == []
