import datetime
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from settings import EMBEDDING_DIMENSION
from utils.math import validate_embedding_dimension

from .memory_object import MemoryObject, NodeType


_MICROSECOND = datetime.timedelta(microseconds=1)
_INITIAL_CAPACITY = 64
_ALPHA = _BETA = _GAMMA = 1.0  # SPEC §5.1 기본 weight


def _to_micros(moment: datetime.datetime) -> int:
    """datetime을 epoch 기준 정수 마이크로초로 바꾼다(정밀도 손실 없음)."""
    epoch = datetime.datetime(1970, 1, 1, tzinfo=moment.tzinfo)
    return (moment - epoch) // _MICROSECOND


@dataclass
class _Matrix:
    """기억 임베딩 행렬과 행별 norm, created_at(마이크로초)의 증분 버퍼."""

    embeddings: np.ndarray
    norms: np.ndarray
    created: np.ndarray
    size: int


class MemoryStream:
    """
    MemoryStream은 관찰과 생각을 시간 순서대로 저장하는 구조입니다. 각 기억은 MemoryObject로 표현되며, 중요도와 임베딩을 포함합니다.
    """

    def __init__(self):
        self.memories: list[MemoryObject] = []
        self._cache: _Matrix | None = None
        self._cache_last: MemoryObject | None = None

    def add_memory(
        self,
        node_type: NodeType,
        citations: Optional[List[int]],
        content: str,
        now: datetime.datetime,
        importance: int,
        embedding: np.ndarray,
    ):
        """
        새로운 관찰(Observation)이나 생각(Reflection)을 스트림에 추가한다.
        """
        validate_embedding_dimension(embedding, expected_dimension=EMBEDDING_DIMENSION)
        new_memory = MemoryObject(
            id=len(self.memories),
            node_type=node_type,
            citations=citations,
            content=content,
            created_at=now,
            last_accessed_at=now,
            importance=importance,
            embedding=embedding,
        )
        matrix = self._synced_matrix()
        self.memories.append(new_memory)
        if matrix is not None:
            self._append_row(matrix, new_memory)
            self._cache_last = new_memory

    def retrieve(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
        *,
        current_time: datetime.datetime,
    ) -> list[MemoryObject]:
        """
        query_embedding 기준으로 memory를 점수화해 상위 top_k에 해당하는 메모리를 반환한다.

        - 결과는 score 내림차순, 동점 시 최신 created_at 우선으로 정렬
          (score·created_at까지 같으면 먼저 저장된 기억이 앞)
        - 반환된 memory의 last_accessed_at은 current_time으로 갱신
        """
        if not self.memories:
            return []

        matrix = self._synced_matrix()
        if matrix is None:
            return []
        scores = self._score_array(self.memories, matrix, query_embedding, current_time)
        # lexsort는 마지막 키가 주키: score 내림차순, created_at 내림차순, 저장 순서
        order = np.lexsort((-matrix.created[: matrix.size], -scores))
        top_memories = [self.memories[i] for i in order[:top_k]]

        for memory in top_memories:
            memory.last_accessed_at = current_time

        return top_memories

    def _synced_matrix(self) -> _Matrix | None:
        """self.memories와 일치하는 캐시를 돌려준다. 어긋났으면 재구성한다."""
        memories = self.memories
        cache = self._cache
        if (
            cache is not None
            and cache.size == len(memories)
            and (not memories or memories[-1] is self._cache_last)
        ):
            return cache
        cache = self._build_matrix(memories)
        self._cache = cache
        self._cache_last = memories[-1] if memories else None
        return cache

    def _build_matrix(self, memories: list[MemoryObject]) -> _Matrix | None:
        if not memories:
            return None
        embeddings = np.stack([m.embedding for m in memories]).astype(np.float64)
        capacity = max(_INITIAL_CAPACITY, len(memories))
        buffer = np.zeros((capacity, embeddings.shape[1]), dtype=np.float64)
        buffer[: len(memories)] = embeddings
        norms = np.zeros(capacity, dtype=np.float64)
        norms[: len(memories)] = np.linalg.norm(embeddings, axis=1)
        created = np.zeros(capacity, dtype=np.int64)
        created[: len(memories)] = [_to_micros(m.created_at) for m in memories]
        return _Matrix(buffer, norms, created, len(memories))

    def _append_row(self, matrix: _Matrix, memory: MemoryObject) -> None:
        if matrix.size == matrix.embeddings.shape[0]:
            capacity = matrix.size * 2
            grown = np.zeros((capacity, matrix.embeddings.shape[1]), dtype=np.float64)
            grown[: matrix.size] = matrix.embeddings
            matrix.embeddings = grown
            matrix.norms = np.resize(matrix.norms, capacity)
            matrix.created = np.resize(matrix.created, capacity)
        row = memory.embedding.astype(np.float64)
        matrix.embeddings[matrix.size] = row
        matrix.norms[matrix.size] = np.linalg.norm(row)
        matrix.created[matrix.size] = _to_micros(memory.created_at)
        matrix.size += 1

    def _calculate_retrieval_scores(
        self,
        memories: list[MemoryObject],
        query_embedding: np.ndarray,
        current_time: datetime.datetime,
    ) -> list[tuple[MemoryObject, float]]:
        """
        memories의 retrieval score를 계산한다.

        공식:
        - `retrieval_score = alpha * recency + beta * importance + gamma * relevance`
        - 기본 가중치: `alpha = beta = gamma = 1.0`
        - recency/importance/relevance는 최종 합산 전에 각각 Min-Max로 [0, 1] 정규화
        - 반환 범위(기본 가중치 기준): `[0.0, 3.0]`
        """

        if not memories:
            return []

        if memories is self.memories:
            matrix = self._synced_matrix()
        else:
            matrix = self._build_matrix(memories)
        if matrix is None:
            return []
        scores = self._score_array(memories, matrix, query_embedding, current_time)
        return list(zip(memories, scores.tolist()))

    def _score_array(
        self,
        memories: list[MemoryObject],
        matrix: _Matrix,
        query_embedding: np.ndarray,
        current_time: datetime.datetime,
    ) -> np.ndarray:
        """모든 memory의 합산 retrieval score를 numpy 벡터 연산으로 계산한다."""
        recency = self._recency_scores(memories, current_time)
        importance = np.fromiter(
            (m.importance for m in memories), dtype=np.float64, count=len(memories)
        )
        relevance = self._relevance_array(matrix, query_embedding)
        return (
            _ALPHA * self._normalize_array(recency)
            + _BETA * self._normalize_array(importance)
            + _GAMMA * self._normalize_array(relevance)
        )

    def _recency_scores(
        self, memories: list[MemoryObject], current_time: datetime.datetime
    ) -> np.ndarray:
        """
        Recency score를 계산한다.
        - 반환 범위: `[0.0, 1.0]`

        공식:
        - `hours_since_last_access = (current_time - memory.last_accessed_at).total_seconds() / 3600`
        - `recency = 0.995 ** hours_since_last_access`
        """
        hours = np.fromiter(
            ((current_time - m.last_accessed_at) / _MICROSECOND for m in memories),
            dtype=np.float64,
            count=len(memories),
        ) / (1_000_000 * 60 * 60)
        return np.power(0.995, hours)

    def _relevance_array(
        self, matrix: _Matrix, query_embedding: np.ndarray
    ) -> np.ndarray:
        """
        모든 memory의 relevance score를 한 번의 행렬 연산으로 계산한다.
        - 반환 범위: `[-1.0, 1.0]`

        공식:
        - `cosine_similarity(a, b) = (a · b) / (||a|| * ||b||)`
        - `relevance = cosine_similarity(query_embedding, memory.embedding)`
        - query나 memory의 norm이 0이거나 query 차원이 틀리면 0.0
        """
        size = matrix.size
        try:
            validate_embedding_dimension(
                query_embedding, expected_dimension=EMBEDDING_DIMENSION
            )
        except ValueError:
            return np.zeros(size, dtype=np.float64)

        query = query_embedding.astype(np.float64)
        norms = matrix.norms[:size] * np.linalg.norm(query)
        dots = matrix.embeddings[:size] @ query
        zero = norms == 0
        return np.where(zero, 0.0, dots / np.where(zero, 1.0, norms))

    def _normalize_array(self, values: np.ndarray) -> np.ndarray:
        """
        Min-Max 정규화를 수행한다.
        - 반환 범위: `[0.0, 1.0]`
        max == min인 경우, 모든 score가 동일하므로 0.5로 반환한다.

        공식: - `norm_x = (x - min_x) / (max_x - min_x)`
        """
        min_val, max_val = values.min(), values.max()
        if max_val == min_val:
            return np.full(values.shape, 0.5, dtype=np.float64)
        return (values - min_val) / (max_val - min_val)
