import datetime
from typing import cast

import numpy as np
from agents.memory.memory_manager import MemoryManager
from agents.memory.memory_object import MemoryObject, NodeType
from agents.memory.memory_stream import MemoryStream
from agents.reflection import Reflection, ReflectionGraphRunner
from agents.reflection.graph import REFLECTION_RETRIEVAL_TOP_K
from llm import ImportanceScoringContext
from llm.embedding_encoder import EmbeddingEncodingContext
from llm.llm_gateway import InsightWithCitation, LlmGateway
from settings import EMBEDDING_DIMENSION

NOW = datetime.datetime(2026, 3, 9, 10, 0, 0)
LATER = NOW + datetime.timedelta(hours=1)
SEEDED = 40


class Encoder:
    def __init__(self) -> None:
        self.many_calls: int = 0

    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray:
        _ = context
        return np.ones(EMBEDDING_DIMENSION)

    def encode_many(self, contexts: list[EmbeddingEncodingContext]) -> list[np.ndarray]:
        self.many_calls += 1
        return [np.ones(EMBEDDING_DIMENSION) for _ in contexts]


class Scorer:
    def __init__(self) -> None:
        self.many_calls: int = 0

    def score(self, context: ImportanceScoringContext) -> int:
        _ = context
        return 5

    def score_many(self, contexts: list[ImportanceScoringContext]) -> list[int]:
        self.many_calls += 1
        return [5 for _ in contexts]


class TrackingManager(MemoryManager):
    """검색 결과 리스트 객체와 질문을 짝지어, 가짜 LLM이 어느 질문의 호출인지 알게 한다."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # pyright: ignore[reportArgumentType]
        self.question_by_list_id: dict[int, str] = {}
        self.top_k_seen: list[int] = []

    def get_retrieval_memories_many(
        self,
        queries: list[str],
        *,
        current_time: datetime.datetime,
        top_k: int = 3,
    ) -> list[list[MemoryObject]]:
        self.top_k_seen.append(top_k)
        results = super().get_retrieval_memories_many(
            queries, current_time=current_time, top_k=top_k
        )
        for query, memories in zip(queries, results, strict=True):
            self.question_by_list_id[id(memories)] = query
        return results


class FakeLlm:
    def __init__(self, questions: list[str]):
        self.questions: list[str] = questions
        self.failing: set[str] = set()
        self.fail_questions: bool = False
        self.manager: TrackingManager | None = None
        self.seen: dict[str, list[str]] = {}

    def generate_salient_high_level_questions(
        self, *, agent_name: str, memories: list[MemoryObject]
    ) -> list[str]:
        _ = agent_name
        _ = memories
        if self.fail_questions:
            raise RuntimeError("boom")
        return self.questions

    def generate_insights_with_citation_key(
        self, *, agent_name: str, memories: list[MemoryObject]
    ) -> list[InsightWithCitation]:
        _ = agent_name
        assert self.manager is not None
        question = self.manager.question_by_list_id[id(memories)]
        self.seen[question] = [m.content for m in memories]
        if question in self.failing:
            raise TimeoutError("slow")
        return [
            InsightWithCitation(context=f"{question}-i{n}", citation_memory_ids=[0])
            for n in range(2)
        ]


def _setup(
    llm: FakeLlm,
) -> tuple[ReflectionGraphRunner, TrackingManager, Encoder, Scorer]:
    encoder = Encoder()
    scorer = Scorer()
    manager = TrackingManager(
        memory_stream=MemoryStream(),
        importance_scorer=scorer,
        embedding_encoder=encoder,
    )
    for index in range(SEEDED):
        manager.memory_stream.add_memory(
            node_type=NodeType.OBSERVATION,
            citations=None,
            content=f"obs {index}",
            now=NOW + datetime.timedelta(seconds=index),
            importance=3,
            embedding=np.ones(EMBEDDING_DIMENSION),
        )
    llm.manager = manager
    runner = ReflectionGraphRunner(
        reflection=Reflection(),
        memory_manager=manager,
        llm_gateway=cast(LlmGateway, cast(object, llm)),
        agent_name="Eddy",
        identity_stable_set=[],
    )
    return runner, manager, encoder, scorer


def _stored(manager: TrackingManager) -> list[str]:
    return [m.content for m in manager.memory_stream.memories[SEEDED:]]


def test_retrieval_precedes_persist_with_top_k_30_and_batched_storage() -> None:
    llm = FakeLlm(["q1", "q2", "q3"])
    runner, manager, encoder, scorer = _setup(llm)

    runner.reflect(now=LATER)

    assert REFLECTION_RETRIEVAL_TOP_K == 30
    assert manager.top_k_seen == [30]
    assert set(llm.seen) == {"q1", "q2", "q3"}
    for contents in llm.seen.values():
        assert len(contents) == 30
        assert not any("-i" in c for c in contents)
    assert _stored(manager) == [f"{q}-i{n}" for q in ("q1", "q2", "q3") for n in range(2)]
    assert encoder.many_calls == 2  # 질문 임베딩 1회 + 통찰 임베딩 1회
    assert scorer.many_calls == 1


def test_one_question_failure_keeps_other_insights() -> None:
    llm = FakeLlm(["q1", "q2", "q3"])
    llm.failing = {"q2"}
    runner, manager, _, _ = _setup(llm)
    runner.record_observation_importance(150)

    runner.reflect(now=LATER)

    assert _stored(manager) == [f"{q}-i{n}" for q in ("q1", "q3") for n in range(2)]
    assert runner.reflection.accumulated_importance == 0


def test_llm_error_does_not_escape_and_counter_resets() -> None:
    llm = FakeLlm(["q1"])
    llm.fail_questions = True
    runner, manager, _, _ = _setup(llm)
    runner.record_observation_importance(150)

    runner.reflect(now=LATER)

    assert runner.should_reflect() is False
    assert _stored(manager) == []


def test_counter_resets_even_for_unexpected_errors() -> None:
    llm = FakeLlm(["q1"])
    runner, _, _, _ = _setup(llm)
    runner.record_observation_importance(150)

    def explode(state: object) -> None:
        _ = state
        raise KeyError("unexpected")

    runner.graph.invoke = explode  # pyright: ignore[reportAttributeAccessIssue]
    try:
        runner.reflect(now=LATER)
    except KeyError:
        pass

    assert runner.reflection.accumulated_importance == 0


def test_no_questions_ends_without_storing() -> None:
    llm = FakeLlm([])
    runner, manager, encoder, _ = _setup(llm)

    runner.reflect(now=LATER)

    assert _stored(manager) == []
    assert encoder.many_calls == 0
