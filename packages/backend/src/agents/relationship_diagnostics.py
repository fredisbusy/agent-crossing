import datetime
from dataclasses import dataclass
from typing import Literal

from .memory.memory_object import MemoryObject, NodeType


@dataclass(frozen=True)
class RelationshipEvidence:
    source: Literal["persona", "memory"]
    content: str
    memory_id: int | None = None
    node_type: NodeType | None = None
    importance: int | None = None
    created_at: datetime.datetime | None = None


@dataclass(frozen=True)
class RelationshipSnapshot:
    target_agent_id: str
    target_name: str
    summary: str | None
    summary_status: Literal["available", "no_explicit_evidence"]
    evidence_total: int
    has_more_evidence: bool
    evidence: tuple[RelationshipEvidence, ...]


def build_relationship_snapshot(
    *,
    identity_stable_set: list[str],
    memories: list[MemoryObject],
    target_agent_id: str,
    target_name: str,
    evidence_limit: int = 5,
) -> RelationshipSnapshot:
    """Build safe qualitative evidence for a directional relationship view."""
    aliases = {
        target_agent_id.casefold(),
        target_name.casefold(),
        target_name.split()[0].casefold(),
    }

    def mentions_target(content: str) -> bool:
        normalized = content.casefold()
        return any(alias and alias in normalized for alias in aliases)

    blocked_markers = (
        "planning_route",
        "moving_to:",
        "at:",
        "arrived_at:",
        "blocked:",
        "waiting_for_clear_path",
        "시간=",
        "에이전트=",
        "현재 계획=",
        "raw_response",
        "model_thought",
        "self_critique",
        "decision_process",
        "governance_trace",
        "prompt=",
        "system_prompt",
        "api_key",
        "authorization",
    )
    relationship_markers = (
        "대화",
        "이야기",
        "친구",
        "좋아",
        "호감",
        "도움",
        "약속",
        "갈등",
        "사과",
        "신뢰",
        "편안",
        "소중",
        "부담",
        "경계",
        "걱정",
        "함께",
        "마주",
        "느꼈",
    )

    def is_public_relationship_evidence(
        content: str, *, require_relationship_marker: bool
    ) -> bool:
        normalized = content.casefold()
        return (
            mentions_target(content)
            and not any(marker in normalized for marker in blocked_markers)
            and (
                not require_relationship_marker
                or any(marker in normalized for marker in relationship_markers)
            )
        )

    valid_memory_ids = {memory.id for memory in memories}
    persona_matches = [
        statement
        for statement in identity_stable_set
        if is_public_relationship_evidence(statement, require_relationship_marker=True)
    ]
    memory_matches = [
        memory
        for memory in memories
        if memory.node_type is not NodeType.PLAN
        and (
            memory.node_type is not NodeType.REFLECTION
            or (
                bool(memory.citations)
                and all(citation in valid_memory_ids for citation in memory.citations)
            )
        )
        and is_public_relationship_evidence(
            memory.content, require_relationship_marker=True
        )
    ]
    summary = (
        " ".join(persona_matches[:2])
        if persona_matches
        else memory_matches[0].content
        if memory_matches
        else None
    )

    evidence: list[RelationshipEvidence] = [
        RelationshipEvidence(source="persona", content=statement)
        for statement in persona_matches
    ]
    evidence.extend(
        RelationshipEvidence(
            source="memory",
            content=memory.content,
            memory_id=memory.id,
            node_type=memory.node_type,
            importance=memory.importance,
            created_at=memory.created_at,
        )
        for memory in memory_matches
        if memory.content not in persona_matches
    )

    limited_evidence = tuple(evidence[: max(1, evidence_limit)])
    return RelationshipSnapshot(
        target_agent_id=target_agent_id,
        target_name=target_name,
        summary=summary,
        summary_status="available" if summary is not None else "no_explicit_evidence",
        evidence_total=len(evidence),
        has_more_evidence=len(evidence) > len(limited_evidence),
        evidence=limited_evidence,
    )
