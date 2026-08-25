import datetime
import json

import numpy as np

from agents.evaluation.interview import InterviewGate, InterviewQuestion
from agents.memory.memory_object import MemoryObject, NodeType


class StubGenerationClient:
    def __init__(self, response: str) -> None:
        self.response: str = response
        self.calls: int = 0
        self.last_prompt: str = ""

    def generate(self, *, prompt: str, **_: object) -> str:
        self.calls += 1
        self.last_prompt = prompt
        return self.response


class StubMemoryService:
    def __init__(self, memories: list[MemoryObject]) -> None:
        self.memories: list[MemoryObject] = memories

    def get_retrieval_memories(
        self, query: str, *, current_time: datetime.datetime, top_k: int = 3
    ) -> list[MemoryObject]:
        _ = query, current_time
        return self.memories[:top_k]


def _memory(memory_id: int, content: str) -> MemoryObject:
    return MemoryObject(
        id=memory_id,
        node_type=NodeType.OBSERVATION,
        citations=None,
        content=content,
        created_at=datetime.datetime(2026, 8, 24, 9, 0),
        last_accessed_at=datetime.datetime(2026, 8, 24, 9, 0),
        importance=5,
        embedding=np.zeros(3),
    )


def _question() -> InterviewQuestion:
    return InterviewQuestion(
        agent_name="Jiho",
        question="Sam이 시장 선거에 출마한다는 사실을 아는가?",
        current_time=datetime.datetime(2026, 8, 24, 10, 0),
    )


def test_interview_grounded_yes_is_aware() -> None:
    memories = [_memory(101, "Sam이 시장 선거에 출마한다고 들었다.")]
    client = StubGenerationClient(
        json.dumps(
            {
                "answer_yes": True,
                "citation_statement_numbers": [1],
                "reason": "1번 statement에서 들었다.",
            }
        )
    )
    gate = InterviewGate(generation_client=client)

    answer = gate.ask(
        question=_question(), memory_service=StubMemoryService(memories)
    )

    assert answer.answer_yes is True
    assert answer.aware is True
    assert answer.citation_memory_ids == [101]


def test_interview_ungrounded_yes_is_filtered_as_hallucination() -> None:
    """§7.1: 근거(citation)가 없는 'yes'는 실제 인지로 인정하지 않는다."""
    memories = [_memory(101, "Sam이 시장 선거에 출마한다고 들었다.")]
    client = StubGenerationClient(
        json.dumps(
            {
                "answer_yes": True,
                "citation_statement_numbers": [],
                "reason": "그냥 그럴 것 같다.",
            }
        )
    )
    gate = InterviewGate(generation_client=client)

    answer = gate.ask(
        question=_question(), memory_service=StubMemoryService(memories)
    )

    assert answer.answer_yes is True
    assert answer.aware is False


def test_interview_invalid_citation_number_is_dropped() -> None:
    memories = [_memory(101, "Sam이 시장 선거에 출마한다고 들었다.")]
    client = StubGenerationClient(
        json.dumps(
            {
                "answer_yes": True,
                "citation_statement_numbers": [1, 99],
                "reason": "1번에서 들었다.",
            }
        )
    )
    gate = InterviewGate(generation_client=client)

    answer = gate.ask(
        question=_question(), memory_service=StubMemoryService(memories)
    )

    assert answer.citation_memory_ids == [101]
    assert answer.aware is True


def test_interview_no_answer_needs_no_citation() -> None:
    memories = [_memory(101, "Sam이 시장 선거에 출마한다고 들었다.")]
    client = StubGenerationClient(
        json.dumps(
            {
                "answer_yes": False,
                "citation_statement_numbers": [],
                "reason": "들은 적 없다.",
            }
        )
    )
    gate = InterviewGate(generation_client=client)

    answer = gate.ask(
        question=_question(), memory_service=StubMemoryService(memories)
    )

    assert answer.answer_yes is False
    assert answer.aware is False


def test_interview_skips_llm_call_when_no_memories_retrieved() -> None:
    client = StubGenerationClient("should not be used")
    gate = InterviewGate(generation_client=client)

    answer = gate.ask(question=_question(), memory_service=StubMemoryService([]))

    assert answer.aware is False
    assert client.calls == 0


def test_interview_parse_failure_defaults_to_not_aware() -> None:
    memories = [_memory(101, "Sam이 시장 선거에 출마한다고 들었다.")]
    client = StubGenerationClient("not json")
    gate = InterviewGate(generation_client=client)

    answer = gate.ask(
        question=_question(), memory_service=StubMemoryService(memories)
    )

    assert answer.aware is False
    assert answer.parse_success is False
