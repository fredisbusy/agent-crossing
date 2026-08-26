"""rename session_cognitive_logs.thought to display_thought for clarity

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "session_cognitive_logs",
        "thought",
        new_column_name="display_thought",
    )


def downgrade() -> None:
    op.alter_column(
        "session_cognitive_logs",
        "display_thought",
        new_column_name="thought",
    )
