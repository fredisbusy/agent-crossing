"""add session_position_history (agent tile-position replay log)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-25

Agent `tile_position` previously only existed as live runtime state and as
the *current* snapshot column on `session_characters` (overwritten on every
save). This adds an append-only history table so a specific game-time
position can be reconstructed later. Rows are written only when an agent's
tile actually changes (see `world.spatial.PositionHistoryBuffer`), not on
every real-time world tick, to keep volume bounded.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_position_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.String(80), nullable=False),
        sa.Column("turn", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("tile_x", sa.Integer(), nullable=False),
        sa.Column("tile_y", sa.Integer(), nullable=False),
        sa.Column("destination_path", sa.Text(), nullable=True),
        sa.Column("current_action", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["game_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["character_id"], ["session_characters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "session_position_history_character_time_idx",
        "session_position_history",
        ["character_id", "occurred_at"],
    )
    op.create_index(
        "session_position_history_session_time_idx",
        "session_position_history",
        ["session_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "session_position_history_session_time_idx",
        table_name="session_position_history",
    )
    op.drop_index(
        "session_position_history_character_time_idx",
        table_name="session_position_history",
    )
    op.drop_table("session_position_history")
