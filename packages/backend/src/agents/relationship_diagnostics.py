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
    affinity_score: None
    measurement: Literal["not_modeled"]
    summary: str | None
    evidence: tuple[RelationshipEvidence, ...]


def build_relationship_snapshot(
    *,
    identity_stable_set: list[str],
    memories: list[MemoryObject],
    target_agent_id: str,
    target_name: str,
    evidence_limit: int = 5,
) -> RelationshipSnapshot:
    """Build a directional relationship view without inventing sentiment scores."""
    aliases = {
        target_agent_id.casefold(),
        target_name.casefold(),
        target_name.split()[0].casefold(),
    }

    def mentions_target(content: str) -> bool:
        normalized = content.casefold()
        return any(alias and alias in normalized for alias in aliases)

    persona_matches = [
        statement for statement in identity_stable_set if mentions_target(statement)
    ]
    memory_matches = [memory for memory in memories if mentions_target(memory.content)]
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

    return RelationshipSnapshot(
        target_agent_id=target_agent_id,
        target_name=target_name,
        affinity_score=None,
        measurement="not_modeled",
        summary=summary,
        evidence=tuple(evidence[: max(1, evidence_limit)]),
    )
