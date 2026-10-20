import datetime

from agents.agent import AgentIdentity, AgentProfile
from agents.memory.memory_object import MemoryObject


def format_date_text(value: datetime.datetime, *, include_year: bool = True) -> str:
    format_string = "%A %B %d %Y" if include_year else "%A %B %d"
    return value.strftime(format_string).replace(" 0", " ")


def format_time_text(value: datetime.datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def format_datetime_text(value: datetime.datetime, *, include_year: bool = True) -> str:
    return (
        f"{format_date_text(value, include_year=include_year)} "
        f"at {format_time_text(value)}"
    )


def format_time_span_text(
    start_time: datetime.datetime, end_time: datetime.datetime
) -> str:
    if start_time.date() == end_time.date():
        return (
            f"From {format_date_text(start_time)} at {format_time_text(start_time)} "
            f"to {format_time_text(end_time)}"
        )
    return (
        f"From {format_datetime_text(start_time)} to {format_datetime_text(end_time)}"
    )


def format_plan_line(
    *,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    location: str,
    action_content: str,
) -> str:
    return f"- {format_time_span_text(start_time, end_time)} | {location} | {action_content}"


def build_agent_context_lines(
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


def build_memory_statements_text(
    *,
    agent_name: str,
    memories: list[MemoryObject],
) -> str:
    memory_lines = [f"Statements about {agent_name}"]
    for index, memory in enumerate(memories, start=1):
        memory_lines.append(f"{index}. {memory.content}")
    return "\n".join(memory_lines)


def build_summary_description(
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


def build_agent_status(profile: AgentProfile) -> str:
    if profile.extended.current_plan_context:
        return profile.extended.current_plan_context[0]
    return "Idle"


def summarize_retrieved_memories(retrieved_memories: list[MemoryObject]) -> str:
    if not retrieved_memories:
        return "- no relevant memory found"

    lines: list[str] = []
    for index, memory in enumerate(retrieved_memories[:5], start=1):
        lines.append(f"- ({index}) [importance={memory.importance}] {memory.content}")
    return "\n".join(lines)


def build_reflection_anchor(
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
