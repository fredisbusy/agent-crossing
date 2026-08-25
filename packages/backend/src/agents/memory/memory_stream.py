import datetime
import threading
from typing import List, Optional

import numpy as np
from settings import EMBEDDING_DIMENSION
from utils.math import cosine_similarity, validate_embedding_dimension

from .memory_object import MemoryObject, NodeType


class MemoryStream:
    """
    MemoryStream은 관찰과 생각을 시간 순서대로 저장하는 구조입니다. 각 기억은 MemoryObject로 표현되며, 중요도와 임베딩을 포함합니다.
    """

    def __init__(self):
        self.memories: list[MemoryObject] = []
        self._lock: threading.RLock = threading.RLock()

    def snapshot(self) -> tuple[MemoryObject, ...]:
        """Return a stable shallow copy for read-only diagnostics."""
        with self._lock:
            return tuple(self.memories)

    def restore(self, memories: list[MemoryObject]) -> None:
        """Replace the stream from a validated session snapshot."""
        with self._lock:
            expected_ids = list(range(len(memories)))
            actual_ids = [memory.id for memory in memories]
            if actual_ids != expected_ids:
                raise ValueError("memory ids must be contiguous and zero-based")
            self.memories = list(memories)

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
        with self._lock:
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
            self.memories.append(new_memory)

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
        - 반환된 memory의 last_accessed_at은 current_time으로 갱신
        """

        with self._lock:
            scores = self._calculate_retrieval_scores(
                self.memories, query_embedding, current_time
            )
            sorted_scores = sorted(
                scores, key=lambda x: (x[1], x[0].created_at), reverse=True
            )
            top_memories = sorted_scores[:top_k]
            for memory, _ in top_memories:
                memory.last_accessed_at = current_time
            return [memory for memory, _ in top_memories]

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

        alpha = beta = gamma = 1.0  # 기본 weight는 1.0

        raw_recencies = [
            self._calculate_recency_score(m, current_time) for m in memories
        ]
        raw_importances = [float(m.importance) for m in memories]
        raw_relevancies = [
            self._calculate_relevance_score(m, query_embedding) for m in memories
        ]

        min_rec, max_rec = min(raw_recencies), max(raw_recencies)
        min_imp, max_imp = min(raw_importances), max(raw_importances)
        min_rel, max_rel = min(raw_relevancies), max(raw_relevancies)

        results: list[tuple[MemoryObject, float]] = []
        for i, memory in enumerate(memories):
            norm_rec = self._normalize(raw_recencies[i], min_rec, max_rec)
            norm_imp = self._normalize(raw_importances[i], min_imp, max_imp)
            norm_rel = self._normalize(raw_relevancies[i], min_rel, max_rel)

            score = alpha * norm_rec + beta * norm_imp + gamma * norm_rel
            results.append((memory, score))

        return results

    def _calculate_recency_score(
        self, memory: MemoryObject, current_time: datetime.datetime
    ) -> float:
        """
        Recency score를 계산한다.
        - 반환 범위: `[0.0, 1.0]`

        공식:
        - `hours_since_last_access = (current_time - memory.last_accessed_at).total_seconds() / 3600`
        - `recency = 0.995 ** hours_since_last_access`
        """
        hour_since_last_access = (
            current_time - memory.last_accessed_at
        ).total_seconds() / (60 * 60)
        recency = 0.995**hour_since_last_access
        return recency

    def _calculate_relevance_score(
        self, memory: MemoryObject, query_embedding: np.ndarray
    ) -> float:
        """
        Relevance score를 계산한다.
        - 반환 범위: `[-1.0, 1.0]`

        공식:
        - `cosine_similarity(a, b) = (a · b) / (||a|| * ||b||)`
        - `relevance = cosine_similarity(query_embedding, memory.embedding)`
        """
        try:
            validate_embedding_dimension(
                query_embedding, expected_dimension=EMBEDDING_DIMENSION
            )
        except ValueError:
            return 0.0

        try:
            return cosine_similarity(query_embedding, memory.embedding)
        except ValueError:
            return 0.0

    def _normalize(self, score: float, min_val: float, max_val: float) -> float:
        """
        Min-Max 정규화를 수행한다.
        - 반환 범위: `[0.0, 1.0]`
        min_val == max_val인 경우, 모든 score가 동일하므로 0.5로 반환한다.

        공식: - `norm_x = (x - min_x) / (max_x - min_x)`
        """
        if max_val == min_val:
            return 0.5
        return (score - min_val) / (max_val - min_val)
