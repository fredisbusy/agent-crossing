"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-25

Single source of truth for the PostgreSQL + pgvector schema, replacing the
retired Prisma-owned migration (`packages/database/prisma/migrations/
20260825090000_session_persistence/migration.sql`). Table/column/constraint
shapes are unchanged from that migration; this only changes which tool owns
them.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = 1024

game_session_status = postgresql.ENUM(
    "ACTIVE", "SAVED", "ERROR", name="GameSessionStatus", create_type=False
)
plan_level = postgresql.ENUM(
    "DAY", "HOURLY", "MINUTE", name="PlanLevel", create_type=False
)
memory_node_type = postgresql.ENUM(
    "OBSERVATION", "REFLECTION", "PLAN", name="MemoryNodeType", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    bind = op.get_bind()
    game_session_status.create(bind, checkfirst=True)
    plan_level.create(bind, checkfirst=True)
    memory_node_type.create(bind, checkfirst=True)

    op.create_table(
        "vector_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "game_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "status", game_session_status, nullable=False, server_default="SAVED"
        ),
        sa.Column("map_id", sa.String(80), nullable=False),
        sa.Column("world_time", sa.DateTime(), nullable=False),
        sa.Column("turn", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column(
            "parse_failures", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("silent_turns", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_dialogue_end_at", sa.DateTime(), nullable=True),
        sa.Column(
            "scheduler_was_running",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("planning_error", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("save_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 80",
            name="game_sessions_name_check",
        ),
        sa.CheckConstraint(
            "schema_version > 0 AND save_version > 0",
            name="game_sessions_version_check",
        ),
    )
    op.create_index(
        "game_sessions_status_saved_at_idx",
        "game_sessions",
        ["status", sa.text("saved_at DESC")],
    )
    op.create_index(
        "game_sessions_single_active_idx",
        "game_sessions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "session_characters",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("persona_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("tile_x", sa.Integer(), nullable=False),
        sa.Column("tile_y", sa.Integer(), nullable=False),
        sa.Column("goal_x", sa.Integer(), nullable=True),
        sa.Column("goal_y", sa.Integer(), nullable=True),
        sa.Column("destination_path", sa.Text(), nullable=True),
        sa.Column("route", postgresql.JSONB(), nullable=False),
        sa.Column("current_action", sa.Text(), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("current_plan_context", postgresql.JSONB(), nullable=False),
        sa.Column(
            "reflection_accumulated_importance",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_replan_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["game_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "agent_id"),
        sa.CheckConstraint(
            "reflection_accumulated_importance >= 0",
            name="session_characters_reflection_check",
        ),
    )

    op.create_table(
        "session_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("runtime_local_id", sa.Integer(), nullable=False),
        sa.Column("node_type", memory_node_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("game_created_at", sa.DateTime(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=False),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["character_id"], ["session_characters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "runtime_local_id"),
        sa.CheckConstraint(
            "importance BETWEEN 1 AND 10", name="session_memories_importance_check"
        ),
    )
    op.create_index(
        "session_memories_character_created_idx",
        "session_memories",
        ["character_id", sa.text("game_created_at DESC")],
    )
    op.create_index(
        "session_memories_character_accessed_idx",
        "session_memories",
        ["character_id", "last_accessed_at"],
    )

    op.create_table(
        "session_memory_citations",
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cited_memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["session_memories.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["cited_memory_id"], ["session_memories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("memory_id", "cited_memory_id"),
        sa.CheckConstraint(
            "memory_id <> cited_memory_id",
            name="session_memory_citations_no_self_check",
        ),
        sa.CheckConstraint(
            "position >= 0", name="session_memory_citations_position_check"
        ),
    )

    op.create_table(
        "session_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("level", plan_level, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("action_content", sa.Text(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.ForeignKeyConstraint(
            ["character_id"], ["session_characters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["session_plan_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "level", "ordinal"),
        sa.CheckConstraint(
            "end_time > start_time", name="session_plan_items_time_check"
        ),
        sa.CheckConstraint("ordinal >= 0", name="session_plan_items_ordinal_check"),
    )
    op.create_index(
        "session_plan_items_active_idx",
        "session_plan_items",
        ["character_id", "level", "start_time", "end_time"],
    )

    op.create_table(
        "session_dialogue_states",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("dialogue_turn_window", sa.Integer(), nullable=True),
        sa.Column("dialogue_target_turns", sa.Integer(), nullable=False),
        sa.Column("dialogue_turns_taken", sa.Integer(), nullable=False),
        sa.Column("dialogue_goal", sa.Text(), nullable=True),
        sa.Column("history", postgresql.JSONB(), nullable=False),
        sa.Column("history_by_agent", postgresql.JSONB(), nullable=False),
        sa.Column("incoming_queues_by_agent", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["game_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("session_id"),
        sa.CheckConstraint(
            "turn_index >= 0 AND dialogue_target_turns >= 2"
            " AND dialogue_turns_taken >= 0",
            name="session_dialogue_state_counts_check",
        ),
    )

    op.create_table(
        "session_cognitive_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("turn", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("agent_id", sa.String(80), nullable=False),
        sa.Column("agent_name", sa.String(120), nullable=False),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("silent_reason", sa.Text(), nullable=False),
        sa.Column("parse_failure", sa.Boolean(), nullable=False),
        sa.Column("thought", sa.Text(), nullable=False),
        sa.Column("model_thought", sa.Text(), nullable=False),
        sa.Column("self_critique", sa.Text(), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=False),
        sa.Column("action_summary", sa.Text(), nullable=False),
        sa.Column("decision_process", postgresql.JSONB(), nullable=False),
        sa.Column("governance_trace", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["game_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["character_id"], ["session_characters.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence"),
    )
    op.create_index(
        "session_cognitive_logs_session_sequence_idx",
        "session_cognitive_logs",
        ["session_id", sa.text("sequence DESC")],
    )
    op.create_index(
        "session_cognitive_logs_character_sequence_idx",
        "session_cognitive_logs",
        ["character_id", sa.text("sequence DESC")],
    )


def downgrade() -> None:
    op.drop_table("session_cognitive_logs")
    op.drop_table("session_dialogue_states")
    op.drop_table("session_plan_items")
    op.drop_table("session_memory_citations")
    op.drop_table("session_memories")
    op.drop_table("session_characters")
    op.drop_table("game_sessions")
    op.drop_table("vector_memories")

    bind = op.get_bind()
    memory_node_type.drop(bind, checkfirst=True)
    plan_level.drop(bind, checkfirst=True)
    game_session_status.drop(bind, checkfirst=True)
