"""성찰 프롬프트는 한국어로 묻고 한국어 출력을 요구한다 (SPEC §6)."""

import datetime
import re

import numpy as np

from agents.memory.memory_object import MemoryObject, NodeType
from agents.memory.reflection_prompts import (
    build_insights_with_citation_prompt,
    build_salient_questions_prompt,
)

NOW = datetime.datetime(2023, 2, 13, 13, 0)
ENGLISH_SENTENCE = re.compile(r"[A-Za-z]+(?: [A-Za-z]+){3,}")


def memories() -> list[MemoryObject]:
    return [
        MemoryObject(
            id=index,
            node_type=NodeType.OBSERVATION,
            citations=None,
            content=text,
            created_at=NOW,
            last_accessed_at=NOW,
            importance=5,
            embedding=np.zeros(2),
        )
        for index, text in enumerate(
            ("Mei Lin이 홉스 카페 홀에서 점심을 먹는다", "오늘은 밸런타인데이 전날이다"), 1
        )
    ]


def test_question_prompt_is_korean_and_numbers_the_statements() -> None:
    prompt = build_salient_questions_prompt(
        agent_name="Isabella Rodriguez", memories=memories()
    )
    assert prompt.startswith("## Isabella Rodriguez에 관한 진술")
    assert "1. Mei Lin이 홉스 카페 홀에서 점심을 먹는다" in prompt
    assert "2. 오늘은 밸런타인데이 전날이다" in prompt
    assert "한국어" in prompt and '"questions"' in prompt
    assert not ENGLISH_SENTENCE.search(prompt.replace("Isabella Rodriguez", ""))


def test_insight_prompt_is_korean_and_keeps_the_citation_contract() -> None:
    prompt = build_insights_with_citation_prompt(
        agent_name="Klaus Mueller", memories=memories()
    )
    assert "한국어" in prompt and "통찰 5개" in prompt
    assert '"insights"' in prompt and '"citation_statement_numbers"' in prompt
    assert not ENGLISH_SENTENCE.search(prompt.replace("Klaus Mueller", ""))
