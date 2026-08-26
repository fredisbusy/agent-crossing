"""add session-scoped directional relationship projections

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_relationship_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("familiarity", sa.Integer(), nullable=False),
        sa.Column("trust", sa.Integer(), nullable=False),
        sa.Column("affinity", sa.Integer(), nullable=False),
        sa.Column("tension", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("last_interaction_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("subject_character_id <> target_character_id", name="session_relationship_states_no_self_check"),
        sa.CheckConstraint("familiarity BETWEEN 0 AND 100 AND trust BETWEEN -100 AND 100 AND affinity BETWEEN -100 AND 100 AND tension BETWEEN 0 AND 100", name="session_relationship_states_metric_range_check"),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_character_id"], ["session_characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_character_id"], ["session_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "subject_character_id", "target_character_id"),
    )
    op.create_index("session_relationship_states_subject_idx", "session_relationship_states", ["session_id", "subject_character_id"])
    op.create_table(
        "session_relationship_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_event_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("familiarity_delta", sa.Integer(), nullable=False),
        sa.Column("trust_delta", sa.Integer(), nullable=False),
        sa.Column("affinity_delta", sa.Integer(), nullable=False),
        sa.Column("tension_delta", sa.Integer(), nullable=False),
        sa.Column("before_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("after_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_character_id"], ["session_characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_character_id"], ["session_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "subject_character_id", "target_character_id", "source_event_id", "event_type"),
    )
    op.create_index("session_relationship_events_pair_time_idx", "session_relationship_events", ["session_id", "subject_character_id", "target_character_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("session_relationship_events_pair_time_idx", table_name="session_relationship_events")
    op.drop_table("session_relationship_events")
    op.drop_index("session_relationship_states_subject_idx", table_name="session_relationship_states")
    op.drop_table("session_relationship_states")
