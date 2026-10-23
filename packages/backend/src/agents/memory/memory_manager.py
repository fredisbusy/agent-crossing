import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np
from llm import BatchImportanceScorer, ImportanceScorer, ImportanceScoringContext, clamp_importance
from llm.embedding_encoder import BatchEmbeddingEncoder, EmbeddingEncodingContext
from llm.llm_gateway import InsightWithCitation

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


@dataclass(frozen=True)
class PlanContext:
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
            self.memory_stream.memories,
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
        """
        query_embedding = self.embedding_encoder.encode(
            EmbeddingEncodingContext(text=query)
        )

        return self.memory_stream.retrieve(
            query_embedding=query_embedding,
            top_k=top_k,
            current_time=current_time,
        )

    def create_observation(
        self,
        *,
        content: str,
        now: datetime.datetime,
        embedding: np.ndarray,
        context: ObservationContext,
        importance: int | None = None,
    ) -> MemoryObject:
        return self._store_memory(
            node_type=NodeType.OBSERVATION,
            content=content,
            now=now,
            embedding=embedding,
            importance=importance,
            citations=None,
            agent_name=context.agent_name,
            identity_stable_set=context.identity_stable_set,
            current_plan=context.current_plan,
        )

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

    def create_observations_from_texts(
        self,
        *,
        items: list[tuple[str, datetime.datetime]],
        context: ObservationContext,
    ) -> list[MemoryObject]:
        """관찰 여러 개를 임베딩 1회 + 중요도 1회 배치로 저장한다. 순서를 보존한다."""
        if not items:
            return []
        encoding_contexts = [EmbeddingEncodingContext(text=text) for text, _ in items]
        encoder = self.embedding_encoder
        if isinstance(encoder, BatchEmbeddingEncoder):
            embeddings = encoder.encode_many(encoding_contexts)
        else:
            embeddings = [encoder.encode(c) for c in encoding_contexts]

        scoring_contexts = [
            ImportanceScoringContext(
                observation=text,
                agent_name=context.agent_name,
                identity_stable_set=context.identity_stable_set,
                current_plan=context.current_plan,
            )
            for text, _ in items
        ]
        scorer = self.importance_scorer
        if isinstance(scorer, BatchImportanceScorer):
            importances = scorer.score_many(scoring_contexts)
        else:
            importances = [scorer.score(c) for c in scoring_contexts]

        return [
            self.create_observation(
                content=text,
                now=now,
                embedding=embedding,
                context=context,
                importance=importance,
            )
            for (text, now), embedding, importance in zip(
                items, embeddings, importances, strict=True
            )
        ]

    def create_reflection(
        self,
        insight: InsightWithCitation,
        *,
        now: datetime.datetime,
        context: ReflectionContext,
        importance: int | None = None,
    ) -> MemoryObject:
        embedding = self.embedding_encoder.encode(
            EmbeddingEncodingContext(text=insight.context)
        )
        return self._store_reflection(
            insight,
            now=now,
            embedding=embedding,
            context=context,
            importance=importance,
        )

    def create_plan(
        self,
        *,
        content: str,
        now: datetime.datetime,
        context: PlanContext,
        importance: int | None = None,
    ) -> MemoryObject:
        embedding = self.embedding_encoder.encode(
            EmbeddingEncodingContext(text=content)
        )
        return self._store_memory(
            node_type=NodeType.PLAN,
            content=content,
            now=now,
            embedding=embedding,
            importance=importance,
            citations=None,
            agent_name=context.agent_name,
            identity_stable_set=context.identity_stable_set,
            current_plan=context.current_plan,
        )

    def _store_reflection(
        self,
        insight: InsightWithCitation,
        *,
        now: datetime.datetime,
        embedding: np.ndarray,
        context: ReflectionContext,
        importance: int | None,
    ) -> MemoryObject:
        # MemoryStream.add_memory는 id=len(memories)로 매기므로 id는 0..len-1 범위다.
        memory_count = len(self.memory_stream.memories)
        filtered_citations: list[int] = []
        for citation_memory_id in insight.citation_memory_ids:
            if not 0 <= citation_memory_id < memory_count:
                continue
            if citation_memory_id in filtered_citations:
                continue
            filtered_citations.append(citation_memory_id)
        return self._store_memory(
            node_type=NodeType.REFLECTION,
            content=insight.context,
            now=now,
            embedding=embedding,
            importance=importance,
            citations=filtered_citations,
            agent_name=context.agent_name,
            identity_stable_set=context.identity_stable_set,
            current_plan=context.current_plan,
        )

    def _store_memory(
        self,
        *,
        node_type: NodeType,
        content: str,
        now: datetime.datetime,
        embedding: np.ndarray,
        importance: int | None,
        citations: list[int] | None,
        agent_name: str,
        identity_stable_set: list[str],
        current_plan: str | None,
    ) -> MemoryObject:
        """임베딩이 준비된 기억을 중요도(없으면 채점) clamp 후 저장한다."""
        final_importance = importance
        if final_importance is None:
            final_importance = self.importance_scorer.score(
                ImportanceScoringContext(
                    observation=content,
                    agent_name=agent_name,
                    identity_stable_set=identity_stable_set,
                    current_plan=current_plan,
                )
            )
        self.memory_stream.add_memory(
            node_type=node_type,
            citations=citations,
            content=content,
            now=now,
            importance=clamp_importance(final_importance),
            embedding=embedding,
        )
        return self.memory_stream.memories[-1]
