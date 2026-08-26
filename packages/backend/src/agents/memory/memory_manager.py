import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np
from llm import ImportanceScorer, ImportanceScoringContext, clamp_importance
from llm.embedding_encoder import EmbeddingEncodingContext
from llm.guardrails import SEMANTIC_HARD_BLOCK_THRESHOLD
from llm.llm_gateway import InsightWithCitation
from utils.math import cosine_similarity

from .memory_object import MemoryObject, NodeType
from .memory_stream import MemoryStream


class OrderBy(Enum):
    ASC = "ASC"
    DESC = "DESC"


@dataclass(frozen=True)
class ObservationContext:
    agent_name: str
    identity_stable_set: list[str]
    current_plan: str | None = None


@dataclass(frozen=True)
class ReflectionContext:
    agent_name: str
    identity_stable_set: list[str]
    current_plan: str | None = None


class EmbeddingEncoder(Protocol):
    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray: ...


class MemoryManager:
    def __init__(
        self,
        *,
        memory_stream: MemoryStream,
        importance_scorer: ImportanceScorer,
        embedding_encoder: EmbeddingEncoder,
    ):
        self.memory_stream: MemoryStream = memory_stream
        self.importance_scorer: ImportanceScorer = importance_scorer
        self.embedding_encoder: EmbeddingEncoder = embedding_encoder

    def get_recent_memories(
        self,
        *,
        limit: int | None = None,
        order_by: OrderBy = OrderBy.DESC,
    ) -> list[MemoryObject]:
        """
        최근 메모리를 반환한다.
        - limit이 주어지면 상위 limit개까지만 반환한다.
        """
        sorted_memories = sorted(
            self.memory_stream.snapshot(),
            key=lambda x: x.created_at,
            reverse=order_by == OrderBy.DESC,
        )

        if limit is not None:
            sorted_memories = sorted_memories[:limit]
        return sorted_memories

    def get_retrieval_memories(
        self,
        query: str,
        *,
        current_time: datetime.datetime,
        top_k: int = 3,
    ) -> list[MemoryObject]:
        """
        검색 쿼리를 기반으로 관련 메모리를 반환한다.

        retrieval 후보가 비어있으면(SPEC.md §3) 최근 메모리로 fallback한다.
        """
        query_embedding = self.embedding_encoder.encode(
            EmbeddingEncodingContext(text=query)
        )

        retrieved = self.memory_stream.retrieve(
            query_embedding=query_embedding,
            top_k=top_k,
            current_time=current_time,
        )
        if retrieved:
            return retrieved

        fallback_memories = self.get_recent_memories(limit=top_k, order_by=OrderBy.DESC)
        for memory in fallback_memories:
            memory.last_accessed_at = current_time
        return fallback_memories

    def create_observation(
        self,
        *,
        content: str,
        now: datetime.datetime,
        embedding: np.ndarray,
        context: ObservationContext,
        importance: int | None = None,
    ) -> MemoryObject:
        final_importance = importance
        if final_importance is None:
            scoring_context = ImportanceScoringContext(
                observation=content,
                agent_name=context.agent_name,
                identity_stable_set=context.identity_stable_set,
                current_plan=context.current_plan,
            )
            final_importance = self.importance_scorer.score(scoring_context)
        final_importance = clamp_importance(final_importance)

        self.memory_stream.add_memory(
            node_type=NodeType.OBSERVATION,
            citations=None,
            content=content,
            now=now,
            importance=final_importance,
            embedding=embedding,
        )

        return self.memory_stream.memories[-1]

    def create_observation_from_text(
        self,
        *,
        content: str,
        now: datetime.datetime,
        context: ObservationContext,
        importance: int | None = None,
    ) -> MemoryObject:
        embedding = self.embedding_encoder.encode(
            EmbeddingEncodingContext(text=content)
        )
        return self.create_observation(
            content=content,
            now=now,
            embedding=embedding,
            context=context,
            importance=importance,
        )

    def create_reflection(
        self,
        insight: InsightWithCitation,
        *,
        now: datetime.datetime,
        context: ReflectionContext,
        importance: int | None = None,
    ) -> MemoryObject | None:
        """새 성찰을 저장한다.

        같은 리플렉션 배치 내에서 여러 질문이 겹치는 근거 메모리를 참조할 때
        의미상 거의 동일한 insight가 중복 생성되는 경우가 있어(SEMANTIC_HARD_BLOCK_THRESHOLD
        이상 유사), 기존 REFLECTION과 임베딩 코사인 유사도가 임계값을 넘으면 저장을 건너뛰고
        None을 반환한다.
        """
        embedding = self.embedding_encoder.encode(
            EmbeddingEncodingContext(text=insight.context)
        )

        existing_reflection_embeddings = [
            memory.embedding
            for memory in self.memory_stream.memories
            if memory.node_type is NodeType.REFLECTION
        ]
        if existing_reflection_embeddings:
            max_similarity = max(
                cosine_similarity(embedding, reference_embedding)
                for reference_embedding in existing_reflection_embeddings
            )
            if max_similarity >= SEMANTIC_HARD_BLOCK_THRESHOLD:
                return None

        final_importance = importance
        if final_importance is None:
            scoring_context = ImportanceScoringContext(
                observation=insight.context,
                agent_name=context.agent_name,
                identity_stable_set=context.identity_stable_set,
                current_plan=context.current_plan,
            )
            final_importance = self.importance_scorer.score(scoring_context)
        final_importance = clamp_importance(final_importance)

        known_memory_ids = {memory.id for memory in self.memory_stream.memories}
        filtered_citations: list[int] = []
        for citation_memory_id in insight.citation_memory_ids:
            if citation_memory_id not in known_memory_ids:
                continue
            if citation_memory_id in filtered_citations:
                continue
            filtered_citations.append(citation_memory_id)

        self.memory_stream.add_memory(
            node_type=NodeType.REFLECTION,
            citations=filtered_citations,
            content=insight.context,
            now=now,
            importance=final_importance,
            embedding=embedding,
        )

        return self.memory_stream.memories[-1]
