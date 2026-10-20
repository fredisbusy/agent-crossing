import datetime
from typing import cast

import numpy as np
from agents.memory.memory_manager import MemoryManager
from agents.memory.memory_object import MemoryObject, NodeType
from agents.reflection import Reflection, ReflectionGraphRunner
from llm.llm_gateway import InsightWithCitation, LlmGateway


class StubMemoryService:
    def __init__(self, recent_memories: list[MemoryObject]):
        self.recent_memories: list[MemoryObject] = recent_memories
        self.retrieval_queries: list[str] = []
        self.created_reflections: list[InsightWithCitation] = []

    def get_recent_memories(self, limit: int) -> list[MemoryObject]:
        return self.recent_memories[:limit]

    def get_retrieval_memories(
        self,
        *,
        query: str,
        current_time: datetime.datetime,
    ) -> list[MemoryObject]:
        _ = current_time
        self.retrieval_queries.append(query)
        return self.recent_memories

    def create_reflection(
        self,
        insight: InsightWithCitation,
        *,
        now: datetime.datetime,
        context: object,
    ) -> InsightWithCitation:
        _ = now
        _ = context
        self.created_reflections.append(insight)
        return insight


class StubLlmService:
    def __init__(
        self,
        *,
        questions: list[str],
        insights_by_question: dict[str, list[InsightWithCitation]],
    ):
        self.questions: list[str] = questions
        self.insights_by_question: dict[str, list[InsightWithCitation]] = (
            insights_by_question
        )
        self.current_question_index: int = 0

    def generate_salient_high_level_questions(
        self,
        *,
        agent_name: str,
        memories: list[MemoryObject],
    ) -> list[str]:
        _ = agent_name
        _ = memories
        return self.questions

    def generate_insights_with_citation_key(
        self,
        *,
        agent_name: str,
        memories: list[MemoryObject],
    ) -> list[InsightWithCitation]:
        _ = agent_name
        _ = memories
        question = self.questions[self.current_question_index]
        self.current_question_index += 1
        return self.insights_by_question[question]


def _memory(*, memory_id: int, content: str) -> MemoryObject:
    now = datetime.datetime(2026, 3, 9, 10, 0, 0)
    return MemoryObject(
        id=memory_id,
        node_type=NodeType.OBSERVATION,
        citations=None,
        content=content,
        created_at=now,
        last_accessed_at=now,
        importance=5,
        embedding=np.zeros(2, dtype=np.float32),
    )


def test_reflection_threshold_triggers_at_150() -> None:
    reflection = Reflection()

    reflection.record_observation_importance(149)
    assert reflection.should_reflect() is False

    reflection.record_observation_importance(1)
    assert reflection.should_reflect() is True


def test_reflection_graph_runner_clears_importance_after_reflect() -> None:
    question = "What pattern matters most from the recent events?"
    insight = InsightWithCitation(
        context="Eddy keeps prioritizing composition practice over errands.",
        citation_memory_ids=[0],
    )
    memory_service = StubMemoryService(
        recent_memories=[_memory(memory_id=0, content="Eddy practiced composition.")]
    )
    llm_service = StubLlmService(
        questions=[question],
        insights_by_question={question: [insight]},
    )
    reflection_graph = ReflectionGraphRunner(
        reflection=Reflection(),
        memory_manager=cast(MemoryManager, cast(object, memory_service)),
        llm_gateway=cast(LlmGateway, cast(object, llm_service)),
        agent_name="Eddy Lin",
        identity_stable_set=["composer"],
    )

    reflection_graph.record_observation_importance(150)
    assert reflection_graph.should_reflect() is True

    reflection_graph.reflect(now=datetime.datetime(2026, 3, 9, 10, 30, 0))

    assert reflection_graph.reflection.accumulated_importance == 0
    assert reflection_graph.should_reflect() is False
    assert memory_service.retrieval_queries == [question]
    assert memory_service.created_reflections == [insight]


def test_reflection_graph_runner_processes_multiple_questions() -> None:
    question_one = "What pattern matters most from the recent events?"
    question_two = "What should Eddy remember for later?"
    first_insight = InsightWithCitation(
        context="Eddy keeps prioritizing composition practice over errands.",
        citation_memory_ids=[0],
    )
    second_insight = InsightWithCitation(
        context="Eddy should protect focused practice time tomorrow too.",
        citation_memory_ids=[0],
    )
    memory_service = StubMemoryService(
        recent_memories=[_memory(memory_id=0, content="Eddy practiced composition.")]
    )
    llm_service = StubLlmService(
        questions=[question_one, question_two],
        insights_by_question={
            question_one: [first_insight],
            question_two: [second_insight],
        },
    )
    reflection_graph = ReflectionGraphRunner(
        reflection=Reflection(),
        memory_manager=cast(MemoryManager, cast(object, memory_service)),
        llm_gateway=cast(LlmGateway, cast(object, llm_service)),
        agent_name="Eddy Lin",
        identity_stable_set=["composer"],
    )

    reflection_graph.reflect(now=datetime.datetime(2026, 3, 9, 10, 30, 0))

    assert memory_service.retrieval_queries == [question_one, question_two]
    assert memory_service.created_reflections == [first_insight, second_insight]
