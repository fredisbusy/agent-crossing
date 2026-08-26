"""§6.1 25-question interview evaluator (5 categories x 5 questions).

Distinct from `agents/evaluation/interview.py`'s grounded yes/no gate (used
for §5-A diffusion/relationship-density measurement): this asks free-text,
in-character questions across self-knowledge/memory/plans/reactions/
reflections, then scores each answer 1-5 for believability. Per TODO.md
§5-B, this project uses absolute per-question scoring rather than the
paper's TrueSkill pairwise ranking (no human-evaluator pool available at
this scale) — the report format below is built to compare repeat runs by
total/category score instead.

Offline evaluation tool, not part of the action loop, so — like
`interview.py` — it does not need the Brain/Governance trace split from
AGENTS.md §9.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from .interview import GenerateClient, MemoryServiceProtocol


class InterviewCategory(StrEnum):
    SELF_KNOWLEDGE = "self_knowledge"
    MEMORY = "memory"
    PLANS = "plans"
    REACTIONS = "reactions"
    REFLECTIONS = "reflections"


INTERVIEW_QUESTIONS: dict[InterviewCategory, list[str]] = {
    InterviewCategory.SELF_KNOWLEDGE: [
        "당신을 소개해 주세요.",
        "이상적인 하루를 묘사해 보세요.",
        "무엇을 가장 중요하게 생각하나요?",
        "여가 시간에 주로 무엇을 하나요?",
        "스스로 어떤 성격이라고 생각하나요?",
    ],
    InterviewCategory.MEMORY: [
        "오늘 있었던 일 중 기억나는 것을 말해 주세요.",
        "최근에 누구와 이야기를 나눴나요? 무슨 얘기를 했나요?",
        "최근에 인상 깊었던 순간이 있다면 무엇인가요?",
        "요즘 마을에서 일어난 일 중 알고 있는 것이 있나요?",
        "최근에 감사했거나 화가 났던 일이 있나요?",
    ],
    InterviewCategory.PLANS: [
        "오늘 남은 시간 동안 무엇을 할 계획인가요?",
        "이번 주에 하고 싶은 일이 있나요?",
        "다음에 누군가를 만난다면 누구를 만나고 싶나요?",
        "곧 예정된 약속이나 일정이 있나요?",
        "요즘 이루고 싶은 목표가 있나요?",
    ],
    InterviewCategory.REACTIONS: [
        "친한 친구가 갑자기 화를 낸다면 어떻게 반응하겠어요?",
        "마을에 새로운 사람이 이사 온다면 어떻게 대하겠어요?",
        "누군가 당신에게 도움을 요청하면 어떻게 하겠어요?",
        "계획한 일정이 갑자기 취소된다면 어떻게 하겠어요?",
        "당신이 아끼는 사람이 힘들어하는 걸 본다면 어떻게 하겠어요?",
    ],
    InterviewCategory.REFLECTIONS: [
        "최근에 스스로에 대해 깨달은 것이 있나요?",
        "요즘 관계에서 배운 점이 있다면 무엇인가요?",
        "지금까지의 삶에서 가장 중요한 가치는 무엇인가요?",
        "요즘 스스로 바꾸고 싶은 점이 있나요?",
        "지금 마을에서의 생활에 만족하나요? 왜 그런가요?",
    ],
}


@dataclass(frozen=True)
class InterviewQuestionResult:
    category: InterviewCategory
    question: str
    answer: str
    citation_memory_ids: list[int]
    score: int
    """1-5, see `interview_score_instruction.md`. 1 when scoring itself
    failed to parse, so a failed case is visible as a low score rather than
    silently missing from the report."""
    score_reasoning: str
    answer_parse_success: bool
    score_parse_success: bool


@dataclass(frozen=True)
class InterviewEvaluationReport:
    agent_name: str
    generated_at: datetime.datetime
    results: list[InterviewQuestionResult] = field(default_factory=list)

    @property
    def total_score(self) -> int:
        return sum(result.score for result in self.results)

    @property
    def max_possible_score(self) -> int:
        return len(self.results) * 5

    @property
    def category_scores(self) -> dict[str, float]:
        totals: dict[str, list[int]] = {}
        for result in self.results:
            totals.setdefault(result.category.value, []).append(result.score)
        return {
            category: sum(scores) / len(scores)
            for category, scores in totals.items()
        }

    @property
    def failed_question_count(self) -> int:
        return sum(
            1
            for result in self.results
            if not result.answer_parse_success or not result.score_parse_success
        )

    def to_json(self) -> str:
        payload = {
            "agent_name": self.agent_name,
            "generated_at": self.generated_at.isoformat(),
            "total_score": self.total_score,
            "max_possible_score": self.max_possible_score,
            "category_scores": self.category_scores,
            "failed_question_count": self.failed_question_count,
            "results": [
                {
                    "category": result.category.value,
                    "question": result.question,
                    "answer": result.answer,
                    "citation_memory_ids": result.citation_memory_ids,
                    "score": result.score,
                    "score_reasoning": result.score_reasoning,
                    "answer_parse_success": result.answer_parse_success,
                    "score_parse_success": result.score_parse_success,
                }
                for result in self.results
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


class InterviewEvaluator:
    """Runs all 25 §6.1 interview questions against one agent and scores
    each answer absolutely (see module docstring for why not TrueSkill)."""

    def __init__(self, *, generation_client: GenerateClient, top_k: int = 5):
        self.generation_client: GenerateClient = generation_client
        self.top_k = top_k

    def run(
        self,
        *,
        agent_name: str,
        memory_service: MemoryServiceProtocol,
        current_time: datetime.datetime,
    ) -> InterviewEvaluationReport:
        results = [
            self._ask_and_score(
                category=category,
                question=question,
                agent_name=agent_name,
                memory_service=memory_service,
                current_time=current_time,
            )
            for category, questions in INTERVIEW_QUESTIONS.items()
            for question in questions
        ]
        return InterviewEvaluationReport(
            agent_name=agent_name, generated_at=current_time, results=results
        )

    def _ask_and_score(
        self,
        *,
        category: InterviewCategory,
        question: str,
        agent_name: str,
        memory_service: MemoryServiceProtocol,
        current_time: datetime.datetime,
    ) -> InterviewQuestionResult:
        from llm import prompt_builders
        from llm.clients.types import LlmGenerateOptions
        from llm.structured_outputs import InterviewAnswerOutput, InterviewScoreOutput

        memories = memory_service.get_retrieval_memories(
            question, current_time=current_time, top_k=self.top_k
        )
        statement_to_memory_id = {
            index + 1: memory.id for index, memory in enumerate(memories)
        }

        answer_prompt = prompt_builders.build_interview_answer_prompt(
            agent_name=agent_name, question=question, memories=memories
        )
        answer_response = self.generation_client.generate(
            prompt=answer_prompt,
            system=prompt_builders.language_system_prompt("ko"),
            options=LlmGenerateOptions(temperature=0.7, top_p=0.9, num_predict=384),
            response_model=InterviewAnswerOutput,
        )
        answer_text, citation_memory_ids, answer_parse_success = _parse_answer(
            answer_response, statement_to_memory_id=statement_to_memory_id
        )

        score_prompt = prompt_builders.build_interview_score_prompt(
            agent_name=agent_name,
            question=question,
            answer=answer_text,
            memories=memories,
        )
        score_response = self.generation_client.generate(
            prompt=score_prompt,
            system=prompt_builders.language_system_prompt("ko"),
            options=LlmGenerateOptions(temperature=0.0, top_p=1.0, num_predict=192),
            response_model=InterviewScoreOutput,
        )
        score, score_reasoning, score_parse_success = _parse_score(score_response)

        return InterviewQuestionResult(
            category=category,
            question=question,
            answer=answer_text,
            citation_memory_ids=citation_memory_ids,
            score=score,
            score_reasoning=score_reasoning,
            answer_parse_success=answer_parse_success,
            score_parse_success=score_parse_success,
        )


def _parse_answer(
    response_text: str, *, statement_to_memory_id: dict[int, int]
) -> tuple[str, list[int], bool]:
    try:
        payload = cast(object, json.loads(response_text))
    except json.JSONDecodeError:
        return "(응답 파싱 실패)", [], False

    if not isinstance(payload, dict):
        return "(응답 형식 오류)", [], False

    raw_answer = payload.get("answer")
    answer_text = raw_answer if isinstance(raw_answer, str) and raw_answer else "(빈 응답)"

    citation_memory_ids: list[int] = []
    raw_numbers = payload.get("citation_statement_numbers")
    if isinstance(raw_numbers, list):
        for raw_number in cast(list[object], raw_numbers):
            if not isinstance(raw_number, int):
                continue
            memory_id = statement_to_memory_id.get(raw_number)
            if memory_id is not None:
                citation_memory_ids.append(memory_id)

    return answer_text, citation_memory_ids, True


def _parse_score(response_text: str) -> tuple[int, str, bool]:
    try:
        payload = cast(object, json.loads(response_text))
    except json.JSONDecodeError:
        return 1, "채점 응답 파싱 실패", False

    if not isinstance(payload, dict):
        return 1, "채점 응답 형식 오류", False

    raw_score = payload.get("score")
    score = raw_score if isinstance(raw_score, int) else 1
    score = max(1, min(5, score))

    raw_reasoning = payload.get("reasoning")
    reasoning = raw_reasoning if isinstance(raw_reasoning, str) and raw_reasoning else "근거 없음"

    return score, reasoning, True
