"""에이전트 요약 설명 (논문 부록 A, SPEC §5 Persona).

핵심 성격 / 요즘 하루 일과·직업 / 자기 삶에 대한 느낌을 기억에서 검색해 LLM이 짧은
문단으로 묶는다. 하루에 한 번 만들어 캐시해 두고 모든 프롬프트 앞에 싣는다.
"""

import datetime
import json
from typing import cast

from llm.clients.types import LlmGenerateOptions
from llm.template_loader import render_template

from .contracts import GenerateClient, LlmPersona, MemoryStore

SUMMARY_TOP_K = 5
"""질의마다 가져오는 기억 수."""
SUMMARY_OPTIONS = LlmGenerateOptions(temperature=0.0, top_p=1.0, num_predict=256)


def identity_text(persona: LlmPersona) -> str:
    """정체성 문장을 한 줄로. 요약을 만들지 못했을 때의 대체 요약이다."""
    return " ".join(persona.identity)


def summary_queries(name: str) -> tuple[str, str, str]:
    return (
        f"{name}의 핵심 성격",
        f"{name}의 요즘 하루 일과와 하는 일",
        f"{name}가 요즘 자기 삶을 어떻게 느끼는지",
    )


def build_summary(
    persona: LlmPersona,
    memory: MemoryStore,
    client: GenerateClient,
    now: datetime.datetime,
) -> str:
    """요약 문단. LLM이 실패하거나 비어 있으면 정체성 문장을 돌려 준다."""
    traits, routine, feelings = (
        _bullets(memory, query, now) for query in summary_queries(persona.display_name)
    )
    prompt = render_template(
        "town_summary.md",
        name=persona.display_name,
        age=str(persona.age),
        identity=identity_text(persona),
        traits=traits,
        routine=routine,
        feelings=feelings,
    )
    try:
        raw = client.generate(prompt=prompt, options=SUMMARY_OPTIONS, format_json=True)
    except (RuntimeError, TimeoutError, ValueError):
        return identity_text(persona)
    return _parse(raw) or identity_text(persona)


def _bullets(memory: MemoryStore, query: str, now: datetime.datetime) -> str:
    found = memory.retrieve(query, now, SUMMARY_TOP_K)
    return "\n".join(f"- {m.content}" for m in found) or "- (없음)"


def _parse(raw: str) -> str:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return ""
    try:
        data = cast(object, json.loads(raw[start : end + 1]))
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    value = cast(dict[str, object], data).get("summary")
    return value.strip() if isinstance(value, str) else ""
