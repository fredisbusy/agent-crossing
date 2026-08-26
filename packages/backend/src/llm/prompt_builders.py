import datetime
from collections.abc import Sequence
from typing import Literal

from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject
from agents.planning.models import DayPlanItem, HourlyPlanItem
from agents.reaction import DialogueArc

from .template_loader import render_template
from .structured_outputs import (
    DAY_ACTION_MAX_CHARS,
    DAY_LOCATION_MAX_CHARS,
    DAY_PLAN_MAX_DURATION_MINUTES,
    ENCOUNTER_REASON_MAX_CHARS,
    HOURLY_ACTION_MAX_CHARS,
    IMPORTANCE_REASON_MAX_CHARS,
    INSIGHT_MAX_CHARS,
    INTERVIEW_REASON_MAX_CHARS,
    MINUTE_ACTION_MAX_CHARS,
    PLAN_DISRUPTION_REASON_MAX_CHARS,
    QUESTION_MAX_CHARS,
    REACTION_CRITIQUE_MAX_CHARS,
    REACTION_REASON_MAX_CHARS,
    REACTION_THOUGHT_MAX_CHARS,
    REACTION_UTTERANCE_MAX_CHARS,
)

REACTION_INTENT_JSON_SHAPE = (
    '{"should_react": <boolean>, "thought": "<string>", '
    '"critique": "<string>", "reason": "<short string>", '
    '"end_dialogue": <boolean>}'
)

REACTION_UTTERANCE_JSON_SHAPE = (
    '{"utterance": "<string>", "thought": "<string>", '
    '"critique": "<string>", "reason": "<short string>", '
    '"end_dialogue": <boolean>}'
)

PLAN_DISRUPTION_JSON_SHAPE = (
    '{"should_react": <boolean>, "reason": "<short string>"}'
)

ENCOUNTER_JSON_SHAPE = (
    '{"should_converse": <boolean>, "relationship_summary": "<short string>", '
    '"context_summary": "<short string>", "reason": "<short string>"}'
)

SALIENT_QUESTIONS_JSON_SHAPE = (
    '{"questions": ["<question 1>", "<question 2>", "<question 3>"]}'
)

INSIGHTS_JSON_SHAPE = (
    '{"insights": ['
    '{"insight": "<text>", "citation_statement_numbers": [1, 5, 3]}, '
    '{"insight": "<text>", "citation_statement_numbers": [2, 4]}'
    "]}"
)

INTERVIEW_JSON_SHAPE = (
    '{"answer_yes": <boolean>, "citation_statement_numbers": [1, 3], '
    '"reason": "<short string>"}'
)

IMPORTANCE_JSON_SHAPE = '{"importance": <int 1-10>, "reason": "<short>"}'

DAY_PLAN_JSON_SHAPE = (
    '{"items": ['
    '{"start_time": "<ISO-8601 datetime>", "end_time": "<ISO-8601 datetime later than start_time>", '
    '"location": "<location>", "action_content": "<action text>"}'
    "]}"
)

HOURLY_PLAN_JSON_SHAPE = (
    '{"items": ['
    '{"start_time": "<ISO-8601 datetime>", "end_time": "<ISO-8601 datetime later than start_time>", '
    '"action_content": "<action text>"}'
    "]}"
)

MINUTE_PLAN_JSON_SHAPE = (
    '{"items": ['
    '{"duration_minutes": <5, 10, or 15>, "action_content": "<action text>"}'
    "]}"
)


def _format_date_text(value: datetime.datetime, *, include_year: bool = True) -> str:
    format_string = "%A %B %d %Y" if include_year else "%A %B %d"
    return value.strftime(format_string).replace(" 0", " ")


def _format_time_text(value: datetime.datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _format_datetime_text(
    value: datetime.datetime, *, include_year: bool = True
) -> str:
    return (
        f"{_format_date_text(value, include_year=include_year)} "
        f"at {_format_time_text(value)}"
    )


def _format_time_span_text(
    start_time: datetime.datetime, end_time: datetime.datetime
) -> str:
    if start_time.date() == end_time.date():
        return (
            f"From {_format_date_text(start_time)} at {_format_time_text(start_time)} "
            f"to {_format_time_text(end_time)}"
        )
    return (
        f"From {_format_datetime_text(start_time)} to {_format_datetime_text(end_time)}"
    )


def _format_plan_line(
    *,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    location: str,
    action_content: str,
) -> str:
    return f"- {_format_time_span_text(start_time, end_time)} | {location} | {action_content}"


def build_salient_questions_prompt(
    *,
    agent_name: str,
    memories: list[MemoryObject],
) -> str:
    memory_text = _build_memory_statements_text(
        agent_name=agent_name, memories=memories
    )
    instruction = render_template(
        "salient_questions_instruction.md",
        json_shape=SALIENT_QUESTIONS_JSON_SHAPE,
        question_max_chars=str(QUESTION_MAX_CHARS),
    )
    return f"{memory_text}\n\n{instruction.strip()}"


def build_insights_with_citation_prompt(
    *,
    agent_name: str,
    memories: list[MemoryObject],
) -> str:
    memory_text = _build_memory_statements_text(
        agent_name=agent_name, memories=memories
    )
    instruction = render_template(
        "insights_instruction.md",
        json_shape=INSIGHTS_JSON_SHAPE,
        insight_max_chars=str(INSIGHT_MAX_CHARS),
    )
    return f"{memory_text}\n\n{instruction.strip()}"


def build_interview_prompt(
    *,
    agent_name: str,
    question: str,
    memories: list[MemoryObject],
) -> str:
    memory_text = _build_memory_statements_text(
        agent_name=agent_name, memories=memories
    )
    instruction = render_template(
        "interview_instruction.md",
        json_shape=INTERVIEW_JSON_SHAPE,
        question=question,
        reason_max_chars=str(INTERVIEW_REASON_MAX_CHARS),
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
        reason_max_chars=str(IMPORTANCE_REASON_MAX_CHARS),
    )


def build_day_plan_prompt(
    *,
    agent_name: str,
    age: int,
    innate_traits: list[str],
    persona_background: str,
    yesterday_date: datetime.datetime,
    yesterday_summary: str,
    today_date: datetime.datetime,
    planning_window_end: datetime.datetime | None = None,
    min_items: int = 5,
    max_items: int = 8,
) -> str:
    """Build a persona-grounded prompt for daily structured plan generation."""
    traits_text = ", ".join(trait.strip() for trait in innate_traits if trait.strip())
    final_planning_window_end = planning_window_end or datetime.datetime.combine(
        today_date.date() + datetime.timedelta(days=1), datetime.time.min
    )
    item_count_requirement = (
        f"exactly {min_items}"
        if min_items == max_items
        else f"{min_items} to {max_items}"
    )
    return render_template(
        "day_plan_broad_strokes_instruction.md",
        agent_name=agent_name,
        age=str(age),
        innate_traits=traits_text or "N/A",
        persona_background=persona_background.strip(),
        yesterday_date_text=_format_date_text(yesterday_date),
        yesterday_summary=yesterday_summary.strip(),
        today_date_text=_format_date_text(today_date),
        planning_window_start=today_date.isoformat(timespec="minutes"),
        planning_window_end=final_planning_window_end.isoformat(timespec="minutes"),
        item_count_requirement=item_count_requirement,
        json_shape=DAY_PLAN_JSON_SHAPE,
        action_max_chars=str(DAY_ACTION_MAX_CHARS),
        location_max_chars=str(DAY_LOCATION_MAX_CHARS),
        day_plan_max_duration_minutes=str(DAY_PLAN_MAX_DURATION_MINUTES),
    )


def build_hourly_plan_prompt(
    *,
    agent_name: str,
    current_time: datetime.datetime,
    day_plan_item: DayPlanItem,
) -> str:
    planning_window_start = max(current_time, day_plan_item.start_time)
    planning_window_end = day_plan_item.end_time
    day_plan_lines = _format_plan_line(
        start_time=day_plan_item.start_time,
        end_time=day_plan_item.end_time,
        location=day_plan_item.location,
        action_content=day_plan_item.action_content,
    )

    return render_template(
        "hourly_plan_instruction.md",
        agent_name=agent_name,
        current_time=_format_datetime_text(current_time),
        planning_date=current_time.date().isoformat(),
        planning_window_start=planning_window_start.isoformat(timespec="minutes"),
        planning_window_end=planning_window_end.isoformat(timespec="minutes"),
        day_plan_lines=day_plan_lines,
        json_shape=HOURLY_PLAN_JSON_SHAPE,
        action_max_chars=str(HOURLY_ACTION_MAX_CHARS),
    )


def build_minute_plan_prompt(
    *,
    agent_name: str,
    current_time: datetime.datetime,
    hourly_plan_item: HourlyPlanItem,
) -> str:
    planning_window_start = max(current_time, hourly_plan_item.start_time)
    planning_window_end = hourly_plan_item.end_time
    total_duration_minutes = int(
        (planning_window_end - planning_window_start).total_seconds() // 60
    )
    hourly_plan_lines = _format_plan_line(
        start_time=hourly_plan_item.start_time,
        end_time=hourly_plan_item.end_time,
        location=hourly_plan_item.location,
        action_content=hourly_plan_item.action_content,
    )

    return render_template(
        "minute_plan_instruction.md",
        agent_name=agent_name,
        current_time=_format_datetime_text(current_time),
        planning_date=current_time.date().isoformat(),
        planning_window_start=planning_window_start.isoformat(timespec="minutes"),
        planning_window_end=planning_window_end.isoformat(timespec="minutes"),
        total_duration_minutes=str(total_duration_minutes),
        canonical_location=hourly_plan_item.location,
        hourly_plan_lines=hourly_plan_lines,
        json_shape=MINUTE_PLAN_JSON_SHAPE,
        action_max_chars=str(MINUTE_ACTION_MAX_CHARS),
    )


def build_retrieval_query(
    *,
    agent_identity: AgentIdentity,
    observation_content: str,
    dialogue_history: list[tuple[str, str]],
    profile: AgentProfile,
) -> str:
    lines: list[str] = _build_agent_context_lines(agent_identity, profile)
    lines.append(f"observation={observation_content}")

    if dialogue_history:
        partner_talk, my_talk = dialogue_history[-1]
        lines.append(f"recent_dialogue_partner={partner_talk}")
        lines.append(f"recent_dialogue_self={my_talk}")

    lines.append("task=상황판단에 필요한 기억 검색")
    return "\n".join(lines)


def build_reaction_prompt(
    *,
    agent_identity: AgentIdentity,
    current_time: datetime.datetime,
    observation_content: str,
    dialogue_history: list[tuple[str, str]],
    profile: AgentProfile,
    retrieved_memories: list[MemoryObject],
) -> str:
    summary_description = _build_summary_description(agent_identity, profile)
    agent_status = _build_agent_status(profile)
    memory_summary = _summarize_retrieved_memories(retrieved_memories)

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
    summary_description = _build_summary_description(agent_identity, profile)
    agent_status = _build_agent_status(profile)
    reflection_anchor = _build_reflection_anchor(profile, retrieved_memories)
    memory_summary = _summarize_retrieved_memories(retrieved_memories)

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
            (
                "Keep thought and critique within "
                f"{REACTION_THOUGHT_MAX_CHARS} and {REACTION_CRITIQUE_MAX_CHARS} "
                f"characters respectively; keep reason within {REACTION_REASON_MAX_CHARS} "
                "characters. Use one concise sentence per text field."
            ),
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
    recent_self_utterances: list[str] | None = None,
) -> str:
    summary_description = _build_summary_description(agent_identity, profile)
    agent_status = _build_agent_status(profile)
    reflection_anchor = _build_reflection_anchor(profile, retrieved_memories)
    memory_summary = _summarize_retrieved_memories(retrieved_memories)

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

    if recent_self_utterances:
        sections.append(
            "Recent utterances by this agent across earlier encounters (do not reuse or closely paraphrase these):"
        )
        sections.extend(
            f"- {utterance}" for utterance in recent_self_utterances[-8:]
        )

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
            (
                f"Keep utterance within {REACTION_UTTERANCE_MAX_CHARS} characters, "
                f"reason within {REACTION_REASON_MAX_CHARS}, thought within "
                f"{REACTION_THOUGHT_MAX_CHARS}, and critique within "
                f"{REACTION_CRITIQUE_MAX_CHARS}. Use one concise sentence per text field."
            ),
            _reaction_utterance_shape_line(),
        ]
    )

    return "\n".join(sections)


def build_plan_disruption_prompt(
    *,
    agent_identity: AgentIdentity,
    profile: AgentProfile,
    current_time: datetime.datetime,
    agent_status: str,
    observation_content: str,
) -> str:
    """§4.3.1 continue-vs-react prompt: summary description + time + status
    + observation -> should the agent continue its existing plan or react?"""
    summary_description = _build_summary_description(agent_identity, profile)

    sections: list[str] = _build_reaction_base_sections(
        agent_identity=agent_identity,
        current_time=current_time,
        summary_description=summary_description,
        agent_status=agent_status,
        observation_content=observation_content,
    )
    sections.extend(
        [
            (
                f"Given [{agent_identity.name}]'s summary description, current time, "
                "status, and this observation, should the agent continue with its "
                "existing plan, or react? Only react if the observation genuinely "
                "disrupts or conflicts with the current plan; ignore ordinary, "
                "expected background activity."
            ),
            f"Keep reason within {PLAN_DISRUPTION_REASON_MAX_CHARS} characters.",
            (
                "Return strict JSON only with this exact shape and no extra text: "
                f"{PLAN_DISRUPTION_JSON_SHAPE}"
            ),
        ]
    )
    return "\n".join(sections)


def build_encounter_prompt(
    *,
    self_identity: AgentIdentity,
    other_identity: AgentIdentity,
    self_profile: AgentProfile,
    current_time: datetime.datetime,
    retrieved_memories: list[MemoryObject],
) -> str:
    """§3.4/§4.3 encounter prompt: relationship summary + context summary ->
    pass-by vs converse decision."""
    summary_description = _build_summary_description(self_identity, self_profile)
    memory_summary = _summarize_retrieved_memories(retrieved_memories)

    sections: list[str] = [
        "[Agent's Summary Description]",
        summary_description,
        f"It is {current_time.isoformat()}.",
        (
            f"[{self_identity.name}] just encountered [{other_identity.name}] "
            "nearby while following the current plan."
        ),
        f"Summary of relevant memories about [{other_identity.name}]:",
        memory_summary,
        (
            f"First, summarize [{self_identity.name}]'s relationship with "
            f"[{other_identity.name}] (relationship_summary). Then summarize the "
            "immediate context of this encounter (context_summary). Finally decide: "
            "should they pass by without stopping, or converse?"
        ),
        (
            "Treat MBTI only as a behavioral writing cue, never as compatibility "
            "evidence. Do not infer attraction from a type label or ordinary "
            "friendliness. At low familiarity, repeated unwanted approaches, "
            "ignored requests for quiet, and pressure after refusal are valid "
            "reasons for lower internal affinity or passing by; introversion alone "
            "is not. Respect boundaries and use observed behavior and memories."
        ),
        f"Keep every text field within {ENCOUNTER_REASON_MAX_CHARS} characters.",
        (
            "Return strict JSON only with this exact shape and no extra text: "
            f"{ENCOUNTER_JSON_SHAPE}"
        ),
    ]
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


def language_system_prompt(language: Literal["ko", "en"]) -> str:
    if language == "ko":
        return render_template("language_system_ko.md").strip()

    return render_template("language_system_en.md").strip()


def build_overlap_guard_block(
    *,
    recent_sentences: Sequence[str],
    previous_candidate: str,
) -> str:
    recent_dialogue_lines = "\n".join(
        f"- {index}. {sentence}"
        for index, sentence in enumerate(recent_sentences, start=1)
    )
    return render_template(
        "overlap_guard.md",
        previous_candidate=previous_candidate,
        recent_dialogue_lines=recent_dialogue_lines,
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()


def build_semantic_guard_block(
    *,
    semantic_history: Sequence[str],
    previous_candidate: str,
    max_similarity: float,
    trigger: str,
    soft_threshold: float,
    hard_threshold: float,
) -> str:
    level = "hard block" if trigger == "hard" else "soft penalty"
    semantic_history_lines = "\n".join(
        f"- {index}. {sentence}"
        for index, sentence in enumerate(semantic_history, start=1)
    )
    return render_template(
        "semantic_guard.md",
        level=level,
        max_similarity=f"{max_similarity:.3f}",
        soft_threshold=str(soft_threshold),
        hard_threshold=str(hard_threshold),
        previous_candidate=previous_candidate,
        semantic_history_lines=semantic_history_lines,
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()


def build_partner_response_nudge_block(*, latest_partner_utterance: str) -> str:
    return render_template(
        "partner_response_nudge.md",
        latest_partner_utterance=latest_partner_utterance,
        json_shape=REACTION_UTTERANCE_JSON_SHAPE,
    ).strip()


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


def _build_agent_context_lines(
    agent_identity: AgentIdentity,
    profile: AgentProfile,
) -> list[str]:
    lines: list[str] = [
        f"agent={agent_identity.name}",
        f"traits={', '.join(agent_identity.traits)}",
    ]

    if profile.fixed.identity_stable_set:
        lines.append(
            "identity_stable_set=" + " | ".join(profile.fixed.identity_stable_set[:2])
        )

    if profile.extended.current_plan_context:
        lines.append(
            "current_plan_context="
            + " | ".join(profile.extended.current_plan_context[:2])
        )

    return lines


def _build_memory_statements_text(
    *,
    agent_name: str,
    memories: list[MemoryObject],
) -> str:
    memory_lines = [f"Statements about {agent_name}"]
    for index, memory in enumerate(memories, start=1):
        memory_lines.append(f"{index}. {memory.content}")
    return "\n".join(memory_lines)


def _build_summary_description(
    agent_identity: AgentIdentity,
    profile: AgentProfile,
) -> str:
    summary_lines: list[str] = [
        f"Name: {agent_identity.name}",
        f"Age: {agent_identity.age}",
        f"Traits: {', '.join(agent_identity.traits)}",
    ]

    if profile.fixed.identity_stable_set:
        summary_lines.append(
            "Identity stable set: " + " | ".join(profile.fixed.identity_stable_set[:3])
        )

    if profile.extended.lifestyle_and_routine:
        summary_lines.append(
            "Lifestyle and routine: "
            + " | ".join(profile.extended.lifestyle_and_routine[:2])
        )

    if profile.extended.current_plan_context:
        summary_lines.append(
            "Current plan context: "
            + " | ".join(profile.extended.current_plan_context[:2])
        )

    return "\n".join(summary_lines)


def _build_agent_status(profile: AgentProfile) -> str:
    if profile.extended.current_plan_context:
        return profile.extended.current_plan_context[0]
    return "Idle"


def _summarize_retrieved_memories(retrieved_memories: list[MemoryObject]) -> str:
    if not retrieved_memories:
        return "- no relevant memory found"

    lines: list[str] = []
    for index, memory in enumerate(retrieved_memories[:5], start=1):
        lines.append(f"- ({index}) [importance={memory.importance}] {memory.content}")
    return "\n".join(lines)


def _build_reflection_anchor(
    profile: AgentProfile,
    retrieved_memories: list[MemoryObject],
) -> str:
    reflection_items = [
        memory.content
        for memory in retrieved_memories
        if memory.node_type.value == "REFLECTION" and memory.content.strip()
    ]
    if reflection_items:
        return " | ".join(reflection_items[:2])

    if profile.fixed.identity_stable_set:
        return " | ".join(profile.fixed.identity_stable_set[:2])

    return "Keep consistency with your core identity and current plan."


def _few_shot_reaction_examples() -> str:
    return render_template("reaction_few_shot_examples.md").strip()


def template_file_plan() -> list[str]:
    return [
        "salient_questions_instruction.md",
        "insights_instruction.md",
        "importance_scoring.md",
        "day_plan_broad_strokes_instruction.md",
        "hourly_plan_instruction.md",
        "minute_plan_instruction.md",
        "reaction_guidelines.md",
        "reaction_few_shot_examples.md",
        "reaction_decision_question.md",
        "reaction_intent_question.md",
        "reaction_utterance_question.md",
        "language_system_ko.md",
        "language_system_en.md",
        "overlap_guard.md",
        "semantic_guard.md",
        "partner_response_nudge.md",
    ]
