"""drop vector_memories (dead code)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-25

`vector_memories` was a session/character-independent prototype table with no
FK relations and no reader anywhere in the codebase — a leftover from before
session persistence existed (docs/architecture-analysis/02_design.md §4.6).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = 1024


def upgrade() -> None:
    op.drop_table("vector_memories")


def downgrade() -> None:
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
