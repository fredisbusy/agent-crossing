import datetime
import json

import numpy as np
from agents.evaluation.interview_evaluator import (
    INTERVIEW_QUESTIONS,
    InterviewCategory,
    InterviewEvaluator,
)
from agents.memory.memory_object import MemoryObject, NodeType


class AlternatingGenerationClient:
    """Answer/score calls alternate; returns a fixed pair of responses."""

    def __init__(self, *, answer_response: str, score_response: str) -> None:
        self.answer_response = answer_response
        self.score_response = score_response
        self.calls: int = 0

    def generate(self, *, prompt: str, **_: object) -> str:
        _ = prompt
        self.calls += 1
        return self.answer_response if self.calls % 2 == 1 else self.score_response


class StubMemoryService:
    def __init__(self, memories: list[MemoryObject]) -> None:
        self.memories = memories

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
        created_at=datetime.datetime(2026, 8, 27, 9, 0),
        last_accessed_at=datetime.datetime(2026, 8, 27, 9, 0),
        importance=5,
        embedding=np.zeros(3),
    )


def test_question_bank_has_five_categories_of_five_questions() -> None:
    assert set(INTERVIEW_QUESTIONS) == set(InterviewCategory)
    for questions in INTERVIEW_QUESTIONS.values():
        assert len(questions) == 5
    total = sum(len(questions) for questions in INTERVIEW_QUESTIONS.values())
    assert total == 25


def test_run_produces_one_result_per_question_with_scores() -> None:
    memories = [_memory(101, "오늘 아침 시장에서 산책했다.")]
    client = AlternatingGenerationClient(
        answer_response=json.dumps(
            {"answer": "오늘 아침에 시장 산책을 했어요.", "citation_statement_numbers": [1]}
        ),
        score_response=json.dumps({"score": 4, "reasoning": "구체적이고 근거가 있다."}),
    )
    evaluator = InterviewEvaluator(generation_client=client)

    report = evaluator.run(
        agent_name="Jiho",
        memory_service=StubMemoryService(memories),
        current_time=datetime.datetime(2026, 8, 27, 10, 0),
    )

    assert len(report.results) == 25
    assert report.total_score == 25 * 4
    assert report.max_possible_score == 25 * 5
    assert set(report.category_scores) == {c.value for c in InterviewCategory}
    assert all(score == 4.0 for score in report.category_scores.values())
    assert report.failed_question_count == 0
    for result in report.results:
        assert result.answer == "오늘 아침에 시장 산책을 했어요."
        assert result.citation_memory_ids == [101]
        assert result.score == 4


def test_run_records_parse_failures_as_low_score_not_a_crash() -> None:
    client = AlternatingGenerationClient(
        answer_response="not json",
        score_response="also not json",
    )
    evaluator = InterviewEvaluator(generation_client=client)

    report = evaluator.run(
        agent_name="Jiho",
        memory_service=StubMemoryService([]),
        current_time=datetime.datetime(2026, 8, 27, 10, 0),
    )

    assert len(report.results) == 25
    assert report.failed_question_count == 25
    assert all(result.score == 1 for result in report.results)


def test_report_to_json_includes_summary_fields() -> None:
    memories = [_memory(101, "최근에 좋은 일이 있었다.")]
    client = AlternatingGenerationClient(
        answer_response=json.dumps(
            {"answer": "요즘 잘 지내고 있어요.", "citation_statement_numbers": []}
        ),
        score_response=json.dumps({"score": 3, "reasoning": "무난하다."}),
    )
    evaluator = InterviewEvaluator(generation_client=client)

    report = evaluator.run(
        agent_name="Sujin",
        memory_service=StubMemoryService(memories),
        current_time=datetime.datetime(2026, 8, 27, 10, 0),
    )

    payload = report.to_json()

    assert '"agent_name": "Sujin"' in payload
    assert '"total_score": 75' in payload
    assert '"max_possible_score": 125' in payload
    assert '"failed_question_count": 0' in payload
