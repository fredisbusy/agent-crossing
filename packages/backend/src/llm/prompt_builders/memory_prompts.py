from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject

from ..template_loader import render_template
from .formatting import build_agent_context_lines, build_memory_statements_text
from .shapes import (
    IMPORTANCE_BATCH_JSON_SHAPE,
    IMPORTANCE_JSON_SHAPE,
    INSIGHTS_JSON_SHAPE,
    SALIENT_QUESTIONS_JSON_SHAPE,
)


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


def build_importance_scoring_prompt(
    *,
    agent_name: str,
    identity_stable_set: list[str],
    current_plan: str | None,
    observation: str,
) -> str:
    identity_text = " | ".join(identity_stable_set[:3]) or "N/A"
    current_plan_text = current_plan or "N/A"
    return render_template(
        "importance_scoring.md",
        json_shape=IMPORTANCE_JSON_SHAPE,
        agent_name=agent_name,
        identity_text=identity_text,
        current_plan_text=current_plan_text,
        observation=observation,
    )


def build_importance_batch_scoring_prompt(
    *,
    agent_name: str,
    identity_stable_set: list[str],
    current_plan: str | None,
    observations: list[str],
) -> str:
    identity_text = " | ".join(identity_stable_set[:3]) or "N/A"
    current_plan_text = current_plan or "N/A"
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(observations, 1))
    return render_template(
        "importance_scoring_batch.md",
        json_shape=IMPORTANCE_BATCH_JSON_SHAPE,
        agent_name=agent_name,
        identity_text=identity_text,
        current_plan_text=current_plan_text,
        observations=numbered,
        count=str(len(observations)),
    )


def build_retrieval_query(
    *,
    agent_identity: AgentIdentity,
    observation_content: str,
    dialogue_history: list[tuple[str, str]],
    profile: AgentProfile,
) -> str:
    lines: list[str] = build_agent_context_lines(agent_identity, profile)
    lines.append(f"observation={observation_content}")

    if dialogue_history:
        partner_talk, my_talk = dialogue_history[-1]
        lines.append(f"recent_dialogue_partner={partner_talk}")
        lines.append(f"recent_dialogue_self={my_talk}")

    lines.append("task=상황판단에 필요한 기억 검색")
    return "\n".join(lines)
