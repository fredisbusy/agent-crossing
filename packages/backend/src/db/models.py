import datetime
import enum
import uuid

from pgvector.sqlalchemy import Vector
from settings import EMBEDDING_DIMENSION
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GameSessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SAVED = "SAVED"
    ERROR = "ERROR"


class PlanLevel(str, enum.Enum):
    DAY = "DAY"
    HOURLY = "HOURLY"
    MINUTE = "MINUTE"


class MemoryNodeType(str, enum.Enum):
    OBSERVATION = "OBSERVATION"
    REFLECTION = "REFLECTION"
    PLAN = "PLAN"


class GameSessionRecord(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 80",
            name="game_sessions_name_check",
        ),
        CheckConstraint(
            "schema_version > 0 AND save_version > 0",
            name="game_sessions_version_check",
        ),
        Index(
            "game_sessions_status_saved_at_idx",
            "status",
            text("saved_at DESC"),
        ),
        Index(
            "game_sessions_single_active_idx",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[GameSessionStatus] = mapped_column(
        Enum(GameSessionStatus, name="GameSessionStatus"), nullable=False
    )
    map_id: Mapped[str] = mapped_column(String(80), nullable=False)
    world_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    turn: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parse_failures: Mapped[int] = mapped_column(Integer, nullable=False)
    silent_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    last_dialogue_end_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    scheduler_was_running: Mapped[bool] = mapped_column(Boolean, nullable=False)
    planning_error: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    save_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    saved_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class SessionCharacterRecord(Base):
    __tablename__ = "session_characters"
    __table_args__ = (
        UniqueConstraint("session_id", "agent_id"),
        CheckConstraint(
            "reflection_accumulated_importance >= 0",
            name="session_characters_reflection_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    persona_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    tile_x: Mapped[int] = mapped_column(Integer, nullable=False)
    tile_y: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_x: Mapped[int | None] = mapped_column(Integer)
    goal_y: Mapped[int | None] = mapped_column(Integer)
    destination_path: Mapped[str | None] = mapped_column(Text)
    route: Mapped[list[dict[str, int]]] = mapped_column(JSONB, nullable=False)
    current_action: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    current_plan_context: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reflection_accumulated_importance: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    last_replan_reason: Mapped[str | None] = mapped_column(Text)


class SessionMemoryRecord(Base):
    __tablename__ = "session_memories"
    __table_args__ = (
        UniqueConstraint("character_id", "runtime_local_id"),
        CheckConstraint(
            "importance BETWEEN 1 AND 10", name="session_memories_importance_check"
        ),
        Index(
            "session_memories_character_created_idx",
            "character_id",
            text("game_created_at DESC"),
        ),
        Index(
            "session_memories_character_accessed_idx",
            "character_id",
            "last_accessed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    runtime_local_id: Mapped[int] = mapped_column(Integer, nullable=False)
    node_type: Mapped[MemoryNodeType] = mapped_column(
        Enum(MemoryNodeType, name="MemoryNodeType"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=False
    )
    game_created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    last_accessed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False
    )
    inserted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class SessionMemoryCitationRecord(Base):
    __tablename__ = "session_memory_citations"
    __table_args__ = (
        CheckConstraint(
            "memory_id <> cited_memory_id",
            name="session_memory_citations_no_self_check",
        ),
        CheckConstraint(
            "position >= 0", name="session_memory_citations_position_check"
        ),
    )

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_memories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cited_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_memories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class SessionPlanItemRecord(Base):
    __tablename__ = "session_plan_items"
    __table_args__ = (
        UniqueConstraint("character_id", "level", "ordinal"),
        CheckConstraint("end_time > start_time", name="session_plan_items_time_check"),
        CheckConstraint("ordinal >= 0", name="session_plan_items_ordinal_check"),
        Index(
            "session_plan_items_active_idx",
            "character_id",
            "level",
            "start_time",
            "end_time",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session_plan_items.id", ondelete="CASCADE")
    )
    level: Mapped[PlanLevel] = mapped_column(
        Enum(PlanLevel, name="PlanLevel"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    action_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SessionDialogueStateRecord(Base):
    __tablename__ = "session_dialogue_states"
    __table_args__ = (
        CheckConstraint(
            "turn_index >= 0 AND dialogue_target_turns >= 2"
            " AND dialogue_turns_taken >= 0",
            name="session_dialogue_state_counts_check",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    dialogue_turn_window: Mapped[int | None] = mapped_column(Integer)
    dialogue_target_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    dialogue_turns_taken: Mapped[int] = mapped_column(Integer, nullable=False)
    dialogue_goal: Mapped[str | None] = mapped_column(Text)
    history: Mapped[list[list[str]]] = mapped_column(JSONB, nullable=False)
    history_by_agent: Mapped[dict[str, list[list[str]]]] = mapped_column(
        JSONB, nullable=False
    )
    incoming_queues_by_agent: Mapped[dict[str, list[str]]] = mapped_column(
        JSONB, nullable=False
    )


class SessionCognitiveLogRecord(Base):
    __tablename__ = "session_cognitive_logs"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence"),
        Index(
            "session_cognitive_logs_session_sequence_idx",
            "session_id",
            text("sequence DESC"),
        ),
        Index(
            "session_cognitive_logs_character_sequence_idx",
            "character_id",
            text("sequence DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="SET NULL"),
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    turn: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(80), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    reply: Mapped[str] = mapped_column(Text, nullable=False)
    silent_reason: Mapped[str] = mapped_column(Text, nullable=False)
    parse_failure: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # Curated display text for the in-world thought bubble (critique,
    # falling back to reason) — NOT the model's raw reasoning. Query
    # `model_thought` for that; see ActionDiagnostics/DashboardEvent.
    display_thought: Mapped[str] = mapped_column(Text, nullable=False)
    model_thought: Mapped[str] = mapped_column(Text, nullable=False)
    self_critique: Mapped[str] = mapped_column(Text, nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    decision_process: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    governance_trace: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class SessionPositionHistoryRecord(Base):
    """One row per *changed* tile position (§ replay/reconstruction).

    Written only when an agent's tile actually moves (or its destination/
    current_action changes), not on every real-time world tick — see
    `world.spatial.PositionHistoryBuffer`. Reconstructing an agent's
    position at an arbitrary game time is: the latest row with
    `occurred_at <= target_time` for that `character_id`.
    """

    __tablename__ = "session_position_history"
    __table_args__ = (
        Index(
            "session_position_history_character_time_idx",
            "character_id",
            "occurred_at",
        ),
        Index(
            "session_position_history_session_time_idx",
            "session_id",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(80), nullable=False)
    turn: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    tile_x: Mapped[int] = mapped_column(Integer, nullable=False)
    tile_y: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_path: Mapped[str | None] = mapped_column(Text)
    current_action: Mapped[str] = mapped_column(Text, nullable=False)


class SessionRelationshipStateRecord(Base):
    __tablename__ = "session_relationship_states"
    __table_args__ = (
        UniqueConstraint("session_id", "subject_character_id", "target_character_id"),
        CheckConstraint(
            "subject_character_id <> target_character_id",
            name="session_relationship_states_no_self_check",
        ),
        CheckConstraint(
            "familiarity BETWEEN 0 AND 100 AND trust BETWEEN -100 AND 100 "
            "AND affinity BETWEEN -100 AND 100 AND tension BETWEEN 0 AND 100 "
            "AND romantic_interest BETWEEN 0 AND 100",
            name="session_relationship_states_metric_range_check",
        ),
        Index(
            "session_relationship_states_subject_idx",
            "session_id",
            "subject_character_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    familiarity: Mapped[int] = mapped_column(Integer, nullable=False)
    trust: Mapped[int] = mapped_column(Integer, nullable=False)
    affinity: Mapped[int] = mapped_column(Integer, nullable=False)
    tension: Mapped[int] = mapped_column(Integer, nullable=False)
    romantic_interest: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    last_interaction_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class SessionRelationshipEventRecord(Base):
    __tablename__ = "session_relationship_events"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "subject_character_id",
            "target_character_id",
            "source_event_id",
            "event_type",
        ),
        Index(
            "session_relationship_events_pair_time_idx",
            "session_id",
            "subject_character_id",
            "target_character_id",
            "occurred_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("session_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    familiarity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    trust_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    affinity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    tension_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    romantic_interest_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    before_metrics: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    after_metrics: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
