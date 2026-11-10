"""성찰 프롬프트 (SPEC §6). 기억이 한국어이므로 질문·통찰도 한국어로 받는다."""

from llm.template_loader import render_template

from ..memory.memory_object import MemoryObject

SALIENT_QUESTIONS_JSON_SHAPE = (
    '{"questions": ["<한국어 질문 1>", "<한국어 질문 2>", "<한국어 질문 3>"]}'
)

INSIGHTS_JSON_SHAPE = (
    '{"insights": ['
    '{"insight": "<한국어 통찰>", "citation_statement_numbers": [1, 5, 3]}, '
    '{"insight": "<한국어 통찰>", "citation_statement_numbers": [2, 4]}'
    "]}"
)


def build_memory_statements_text(
    *,
    agent_name: str,
    memories: list[MemoryObject],
) -> str:
    memory_lines = [f"## {agent_name}에 관한 진술", ""]
    for index, memory in enumerate(memories, start=1):
        memory_lines.append(f"{index}. {memory.content}")
    return "\n".join(memory_lines)


def build_salient_questions_prompt(
    *,
    agent_name: str,
    memories: list[MemoryObject],
) -> str:
    memory_text = build_memory_statements_text(agent_name=agent_name, memories=memories)
    instruction = render_template(
        "salient_questions_instruction.md",
        json_shape=SALIENT_QUESTIONS_JSON_SHAPE,
    )
    return f"{memory_text}\n\n{instruction.strip()}"


def build_insights_with_citation_prompt(
    *,
    agent_name: str,
    memories: list[MemoryObject],
) -> str:
    memory_text = build_memory_statements_text(agent_name=agent_name, memories=memories)
    instruction = render_template(
        "insights_instruction.md",
        json_shape=INSIGHTS_JSON_SHAPE,
    )
    return f"{memory_text}\n\n{instruction.strip()}"
