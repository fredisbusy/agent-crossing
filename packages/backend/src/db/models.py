import datetime
import enum
import uuid

from pgvector.sqlalchemy import Vector
from settings import EMBEDDING_DIMENSION
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class VectorMemory(Base):
    """에이전트가 생성한 기억을 벡터와 함께 저장하는 테이블 모델."""

    __tablename__ = "vector_memories"

    """각 메모리 레코드를 고유하게 식별하는 기본 키."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    """메모리의 원문 텍스트(검색 및 표시 기준 설명)."""
    description: Mapped[str] = mapped_column(String, nullable=False)

    """메모리 중요도 점수(회상 우선순위 계산에 사용)."""
    importance: Mapped[int] = mapped_column(Integer, nullable=False)

    """메모리 임베딩 벡터(pgvector, 차원은 EMBEDDING_DIMENSION)."""
    embedding: Mapped[Vector] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=False
    )

    """메모리가 생성된 시각(서버 기준 현재 시각으로 자동 기록)."""
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


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
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    saved_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class SessionCharacterRecord(Base):
    __tablename__ = "session_characters"
    __table_args__ = (UniqueConstraint("session_id", "agent_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
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
    __table_args__ = (UniqueConstraint("character_id", "runtime_local_id"),)

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
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    game_created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    last_accessed_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    inserted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class SessionMemoryCitationRecord(Base):
    __tablename__ = "session_memory_citations"

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
    __table_args__ = (UniqueConstraint("character_id", "level", "ordinal"),)

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
    __table_args__ = (UniqueConstraint("session_id", "sequence"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
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
    thought: Mapped[str] = mapped_column(Text, nullable=False)
    model_thought: Mapped[str] = mapped_column(Text, nullable=False)
    self_critique: Mapped[str] = mapped_column(Text, nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_summary: Mapped[str] = mapped_column(Text, nullable=False)
    decision_process: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    governance_trace: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
