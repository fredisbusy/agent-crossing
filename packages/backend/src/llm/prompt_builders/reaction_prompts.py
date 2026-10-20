import datetime

from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject
from agents.reaction import DialogueArc

from ..template_loader import render_template
from .formatting import (
    build_agent_status,
    build_reflection_anchor,
    build_summary_description,
    summarize_retrieved_memories,
)
from .shapes import REACTION_INTENT_JSON_SHAPE, REACTION_UTTERANCE_JSON_SHAPE


def build_reaction_prompt(
    *,
    agent_identity: AgentIdentity,
    current_time: datetime.datetime,
    observation_content: str,
    dialogue_history: list[tuple[str, str]],
    profile: AgentProfile,
    retrieved_memories: list[MemoryObject],
) -> str:
    summary_description = build_summary_description(agent_identity, profile)
    agent_status = build_agent_status(profile)
    memory_summary = summarize_retrieved_memories(retrieved_memories)

    sections: list[str] = _build_reaction_base_sections(
        agent_identity=agent_identity,
        current_time=current_time,
        summary_description=summary_description,
        agent_status=agent_status,
        observation_content=observation_content,
    )

    if dialogue_history:
        partner_talk, my_talk = dialogue_history[-1]
        sections.append("Recent dialogue context:")
        sections.append(f"- partner: {partner_talk or 'none'}")
        sections.append(f"- self: {my_talk or 'none'}")

    sections.extend(
        [
            f"Summary of relevant context from [{agent_identity.name}]'s memory:",
            memory_summary,
            _reaction_intent_question(agent_identity.name),
        ]
    )

    return "\n".join(sections)


def build_reaction_intent_prompt(
    *,
    agent_identity: AgentIdentity,
    current_time: datetime.datetime,
    observation_content: str,
    dialogue_history: list[tuple[str, str]],
    profile: AgentProfile,
    retrieved_memories: list[MemoryObject],
    dialogue_arc: DialogueArc | None = None,
) -> str:
    summary_description = build_summary_description(agent_identity, profile)
    agent_status = build_agent_status(profile)
    reflection_anchor = build_reflection_anchor(profile, retrieved_memories)
    memory_summary = summarize_retrieved_memories(retrieved_memories)

    sections: list[str] = _build_reaction_base_sections(
        agent_identity=agent_identity,
        current_time=current_time,
        summary_description=summary_description,
        agent_status=agent_status,
        observation_content=observation_content,
        identity_anchor=reflection_anchor,
    )

    if dialogue_history:
        sections.append("Recent dialogue context:")
        for index, (partner_talk, my_talk) in enumerate(dialogue_history, start=1):
            sections.append(f"- turn {index} partner: {partner_talk or 'none'}")
            sections.append(f"- turn {index} self: {my_talk or 'none'}")

    if dialogue_arc is not None:
        sections.extend(_build_dialogue_arc_section(dialogue_arc=dialogue_arc))

    sections.extend(
        [
            (f"Summary of relevant context from [{agent_identity.name}]'s memory:"),
            memory_summary,
            _reaction_intent_question(agent_identity.name),
            _reaction_intent_shape_line(),
        ]
    )

    return "\n".join(sections)


def build_reaction_utterance_prompt(
    *,
    agent_identity: AgentIdentity,
    current_time: datetime.datetime,
    observation_content: str,
    dialogue_history: list[tuple[str, str]],
    profile: AgentProfile,
    retrieved_memories: list[MemoryObject],
    intent_reason: str,
    intent_thought: str,
    intent_critique: str,
    dialogue_arc: DialogueArc | None = None,
) -> str:
    summary_description = build_summary_description(agent_identity, profile)
    agent_status = build_agent_status(profile)
    reflection_anchor = build_reflection_anchor(profile, retrieved_memories)
    memory_summary = summarize_retrieved_memories(retrieved_memories)

    sections: list[str] = _build_reaction_base_sections(
        agent_identity=agent_identity,
        current_time=current_time,
        summary_description=summary_description,
        agent_status=agent_status,
        observation_content=observation_content,
        identity_anchor=reflection_anchor,
    )

    if dialogue_history:
        sections.append("Recent dialogue context:")
        for index, (partner_talk, my_talk) in enumerate(dialogue_history, start=1):
            sections.append(f"- turn {index} partner: {partner_talk or 'none'}")
            sections.append(f"- turn {index} self: {my_talk or 'none'}")

    if dialogue_arc is not None:
        sections.extend(_build_dialogue_arc_section(dialogue_arc=dialogue_arc))

    sections.extend(
        [
            (f"Summary of relevant context from [{agent_identity.name}]'s memory:"),
            memory_summary,
            (
                "Stage 1 decision: should_react=true | "
                f"reason={intent_reason or 'n/a'} | "
                f"thought={intent_thought or 'n/a'} | "
                f"critique={intent_critique or 'n/a'}"
            ),
            render_template("reaction_guidelines.md").strip(),
            "Few-shot calibration examples:",
            _few_shot_reaction_examples(),
            _reaction_utterance_question(agent_identity.name),
            _reaction_utterance_shape_line(),
        ]
    )

    return "\n".join(sections)


def build_reaction_decision_prompt(
    *,
    agent_identity: AgentIdentity,
    current_time: datetime.datetime,
    observation_content: str,
    dialogue_history: list[tuple[str, str]],
    profile: AgentProfile,
    retrieved_memories: list[MemoryObject],
) -> str:
    return build_reaction_intent_prompt(
        agent_identity=agent_identity,
        current_time=current_time,
        observation_content=observation_content,
        dialogue_history=dialogue_history,
        profile=profile,
        retrieved_memories=retrieved_memories,
    )


def _build_dialogue_arc_section(*, dialogue_arc: DialogueArc) -> list[str]:
    lines = [
        "[Short Conversation Arc]",
        "Treat this as a short game-style exchange rather than a long open-ended chat.",
        f"Conversation goal: {dialogue_arc.goal}",
        (
            "Arc status: "
            f"turns_taken={dialogue_arc.turns_taken}, "
            f"target_turns={dialogue_arc.target_turns}, "
            f"remaining_turns={dialogue_arc.remaining_turns}, "
            f"phase={dialogue_arc.phase}"
        ),
    ]

    if dialogue_arc.phase == "opening":
        lines.append(
            "Open warmly, move into the main topic quickly, and avoid over-explaining."
        )
    elif dialogue_arc.phase == "middle":
        lines.append(
            "Advance the current topic with one concrete reply or one practical follow-up."
        )
    else:
        lines.append(
            "Start wrapping up naturally. Prefer a brief closing remark or one final useful response."
        )
        lines.append(
            "If this turn should conclude the exchange, set end_dialogue=true."
        )

    if dialogue_arc.should_wrap_up:
        lines.append(
            "Do not introduce a new major topic unless the partner just introduced important new information."
        )
        lines.append(
            "If there is no strong reason to continue, it is acceptable to end the exchange and return to the current plan."
        )
        lines.append(
            "If no reply is needed because the exchange is already complete, return should_react=false and end_dialogue=true."
        )

    return lines


def _build_reaction_base_sections(
    *,
    agent_identity: AgentIdentity,
    current_time: datetime.datetime,
    summary_description: str,
    agent_status: str,
    observation_content: str,
    identity_anchor: str | None = None,
) -> list[str]:
    sections: list[str] = [
        "[Agent's Summary Description]",
        summary_description,
    ]
    if identity_anchor is not None:
        sections.extend(
            [
                "[Identity Anchor - highest priority]",
                identity_anchor,
            ]
        )

    sections.extend(
        [
            f"It is {current_time.isoformat()}.",
            f"[{agent_identity.name}]'s status: {agent_status}.",
            f"Observation: {observation_content}",
        ]
    )
    return sections


def _reaction_intent_question(agent_name: str) -> str:
    rendered = render_template(
        "reaction_intent_question.md",
        agent_name=agent_name,
        json_shape=REACTION_INTENT_JSON_SHAPE,
    ).strip()
    return _first_content_line(rendered)


def _reaction_intent_shape_line() -> str:
    rendered = render_template(
        "reaction_intent_question.md",
        agent_name="agent",
        json_shape=REACTION_INTENT_JSON_SHAPE,
    ).strip()
    for line in rendered.splitlines():
        if line.startswith("Return strict JSON only"):
            return line
    return (
        "Return strict JSON only with this exact shape and no extra text: "
        f"{REACTION_INTENT_JSON_SHAPE}"
    )


def _reaction_utterance_question(agent_name: str) -> str:
    rendered = render_template(
        "reaction_utterance_question.md",
        agent_name=agent_name,
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()
    return _first_content_line(rendered)


def _reaction_utterance_shape_line() -> str:
    rendered = render_template(
        "reaction_utterance_question.md",
        agent_name="agent",
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()
    for line in rendered.splitlines():
        if line.startswith("Return strict JSON only"):
            return line
    return (
        "Return strict JSON only with this exact shape and no extra text: "
        f"{REACTION_UTTERANCE_JSON_SHAPE}"
    )


def _first_content_line(rendered: str) -> str:
    for line in rendered.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("##"):
            continue
        return stripped
    return ""


def _few_shot_reaction_examples() -> str:
    return render_template("reaction_few_shot_examples.md").strip()
