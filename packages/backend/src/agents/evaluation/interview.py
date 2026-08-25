"""§7.1 interview mechanism — ask an agent a yes/no question grounded in
retrieved memory statements, and filter out ungrounded ("hallucinated")
"yes" answers.

Used by §5-A information diffusion / relationship density measurement and
by the §5-B interview evaluator. Distinct from `agents/reaction/graph.py`'s
in-dialogue reaction pipeline and from `agents/planning/react_gate.py`'s
plan-disruption judgment: this is an offline evaluation tool, not part of
the action loop, so it does not need the Brain/Governance trace split from
AGENTS.md §9.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from pydantic import BaseModel

    from agents.memory.memory_object import MemoryObject
    from llm.clients.types import LlmGenerateOptions


@dataclass(frozen=True)
class InterviewAnswer:
    """The grounded yes/no verdict for one interview question.

    `answer_yes` is the model's raw claim; `aware` is the hallucination-
    filtered verdict actually used for diffusion/relationship measurement —
    it is only True when `answer_yes` is True *and* at least one citation
    resolved to a real retrieved memory id (§7.1 grounding requirement).
    """

    answer_yes: bool
    aware: bool
    reason: str
    citation_memory_ids: list[int]
    raw_response: str = ""
    parse_success: bool = True


@dataclass(frozen=True)
class InterviewQuestion:
    agent_name: str
    question: str
    current_time: datetime.datetime
    top_k: int = 5


class MemoryServiceProtocol(Protocol):
    def get_retrieval_memories(
        self,
        query: str,
        *,
        current_time: datetime.datetime,
        top_k: int = 3,
    ) -> list["MemoryObject"]: ...


class GenerateClient(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        options: "LlmGenerateOptions | None" = None,
        format_json: bool = False,
        response_model: "type[BaseModel] | None" = None,
    ) -> str: ...


INTERVIEW_GENERATE_OPTIONS_KWARGS: dict[str, object] = {
    "temperature": 0.0,
    "top_p": 1.0,
    "num_predict": 384,
}


class InterviewGate:
    """Runs one grounded yes/no interview question against an agent's memory."""

    def __init__(self, *, generation_client: GenerateClient):
        self.generation_client: GenerateClient = generation_client

    def ask(
        self,
        *,
        question: InterviewQuestion,
        memory_service: MemoryServiceProtocol,
    ) -> InterviewAnswer:
        from llm import prompt_builders
        from llm.clients.types import LlmGenerateOptions
        from llm.language_policy import korean_text_or_fallback
        from llm.structured_outputs import InterviewOutput

        memories = memory_service.get_retrieval_memories(
            question.question,
            current_time=question.current_time,
            top_k=question.top_k,
        )
        if not memories:
            return InterviewAnswer(
                answer_yes=False,
                aware=False,
                reason="관련 기억이 없어 알지 못한다고 판단함",
                citation_memory_ids=[],
            )

        statement_to_memory_id = {
            index + 1: memory.id for index, memory in enumerate(memories)
        }
        prompt = prompt_builders.build_interview_prompt(
            agent_name=question.agent_name,
            question=question.question,
            memories=memories,
        )
        response = self.generation_client.generate(
            prompt=prompt,
            system=prompt_builders.language_system_prompt("ko"),
            options=LlmGenerateOptions(**INTERVIEW_GENERATE_OPTIONS_KWARGS),
            response_model=InterviewOutput,
        )
        return _parse_interview_answer(
            response, statement_to_memory_id=statement_to_memory_id
        )


def _parse_interview_answer(
    response_text: str, *, statement_to_memory_id: dict[int, int]
) -> InterviewAnswer:
    from llm.language_policy import korean_text_or_fallback

    try:
        payload = cast(object, json.loads(response_text))
    except json.JSONDecodeError:
        return InterviewAnswer(
            answer_yes=False,
            aware=False,
            reason="응답 파싱 실패",
            citation_memory_ids=[],
            raw_response=response_text,
            parse_success=False,
        )

    if not isinstance(payload, dict):
        return InterviewAnswer(
            answer_yes=False,
            aware=False,
            reason="응답 형식 오류",
            citation_memory_ids=[],
            raw_response=response_text,
            parse_success=False,
        )

    answer_yes = bool(payload.get("answer_yes", False))
    raw_reason = payload.get("reason")
    reason = korean_text_or_fallback(
        raw_reason if isinstance(raw_reason, str) else "",
        fallback="근거를 한국어로 요약하지 못함",
    )

    citation_memory_ids: list[int] = []
    raw_numbers = payload.get("citation_statement_numbers")
    if isinstance(raw_numbers, list):
        for raw_number in cast(list[object], raw_numbers):
            if not isinstance(raw_number, int):
                continue
            memory_id = statement_to_memory_id.get(raw_number)
            if memory_id is not None:
                citation_memory_ids.append(memory_id)

    aware = answer_yes and len(citation_memory_ids) > 0
    return InterviewAnswer(
        answer_yes=answer_yes,
        aware=aware,
        reason=reason,
        citation_memory_ids=citation_memory_ids,
        raw_response=response_text,
        parse_success=True,
    )
