import datetime

import numpy as np
from agents.memory.memory_manager import MemoryManager, ReflectionContext
from agents.memory.memory_object import NodeType
from agents.memory.memory_stream import MemoryStream
from llm import ImportanceScoringContext
from llm.embedding_encoder import EmbeddingEncodingContext
from llm.llm_gateway import InsightWithCitation
from settings import EMBEDDING_DIMENSION

NOW = datetime.datetime(2026, 3, 9, 10, 0, 0)


class BatchEncoder:
    def __init__(self) -> None:
        self.encode_calls: int = 0
        self.encode_many_calls: list[list[str]] = []

    def encode(self, context: EmbeddingEncodingContext) -> np.ndarray:
        _ = context
        self.encode_calls += 1
        return np.ones(EMBEDDING_DIMENSION)

    def encode_many(self, contexts: list[EmbeddingEncodingContext]) -> list[np.ndarray]:
        self.encode_many_calls.append([c.text for c in contexts])
        return [np.ones(EMBEDDING_DIMENSION) for _ in contexts]


class BatchScorer:
    def __init__(self) -> None:
        self.score_calls: int = 0
        self.score_many_calls: int = 0

    def score(self, context: ImportanceScoringContext) -> int:
        _ = context
        self.score_calls += 1
        return 5

    def score_many(self, contexts: list[ImportanceScoringContext]) -> list[int]:
        self.score_many_calls += 1
        return [index + 1 for index, _ in enumerate(contexts)]


def _manager() -> tuple[MemoryManager, BatchEncoder, BatchScorer]:
    encoder = BatchEncoder()
    scorer = BatchScorer()
    manager = MemoryManager(
        memory_stream=MemoryStream(),
        importance_scorer=scorer,
        embedding_encoder=encoder,
    )
    return manager, encoder, scorer


def _context() -> ReflectionContext:
    return ReflectionContext(agent_name="Eddy", identity_stable_set=[])


def _seed(manager: MemoryManager, count: int) -> None:
    for index in range(count):
        _ = manager.memory_stream.add_memory(
            node_type=NodeType.OBSERVATION,
            citations=None,
            content=f"obs {index}",
            now=NOW,
            importance=3,
            embedding=np.ones(EMBEDDING_DIMENSION),
        )


def test_create_reflections_uses_one_batch_call_and_keeps_order() -> None:
    manager, encoder, scorer = _manager()
    _seed(manager, 1)

    created = manager.create_reflections(
        [
            InsightWithCitation(context="a", citation_memory_ids=[0, 0, 99, -1]),
            InsightWithCitation(context="b", citation_memory_ids=[0]),
            InsightWithCitation(context="c", citation_memory_ids=[]),
        ],
        now=NOW,
        context=_context(),
    )

    assert encoder.encode_many_calls == [["a", "b", "c"]]
    assert encoder.encode_calls == 0
    assert scorer.score_many_calls == 1
    assert scorer.score_calls == 0
    assert [m.content for m in created] == ["a", "b", "c"]
    assert [m.importance for m in created] == [1, 2, 3]
    assert [m.id for m in created] == [1, 2, 3]
    assert all(m.node_type == NodeType.REFLECTION for m in created)
    assert [m.citations for m in created] == [[0], [0], []]


def test_create_reflections_empty_makes_no_calls() -> None:
    manager, encoder, scorer = _manager()

    assert manager.create_reflections([], now=NOW, context=_context()) == []
    assert encoder.encode_many_calls == []
    assert scorer.score_many_calls == 0


def test_get_retrieval_memories_many_encodes_once_and_respects_top_k() -> None:
    manager, encoder, _ = _manager()
    _seed(manager, 5)

    results = manager.get_retrieval_memories_many(
        ["q1", "q2"], current_time=NOW, top_k=4
    )

    assert encoder.encode_many_calls == [["q1", "q2"]]
    assert [len(r) for r in results] == [4, 4]
    assert manager.get_retrieval_memories_many([], current_time=NOW, top_k=4) == []
