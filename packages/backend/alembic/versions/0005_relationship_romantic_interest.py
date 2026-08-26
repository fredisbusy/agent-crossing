"""separate romantic interest from interpersonal affinity

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "session_relationship_states",
        sa.Column("romantic_interest", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "session_relationship_events",
        sa.Column(
            "romantic_interest_delta", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.drop_constraint(
        "session_relationship_states_metric_range_check",
        "session_relationship_states",
        type_="check",
    )
    op.create_check_constraint(
        "session_relationship_states_metric_range_check",
        "session_relationship_states",
        "familiarity BETWEEN 0 AND 100 AND trust BETWEEN -100 AND 100 "
        "AND affinity BETWEEN -100 AND 100 AND tension BETWEEN 0 AND 100 "
        "AND romantic_interest BETWEEN 0 AND 100",
    )
    op.alter_column(
        "session_relationship_states", "romantic_interest", server_default=None
    )
    op.alter_column(
        "session_relationship_events", "romantic_interest_delta", server_default=None
    )


def downgrade() -> None:
    op.drop_constraint(
        "session_relationship_states_metric_range_check",
        "session_relationship_states",
        type_="check",
    )
    op.create_check_constraint(
        "session_relationship_states_metric_range_check",
        "session_relationship_states",
        "familiarity BETWEEN 0 AND 100 AND trust BETWEEN -100 AND 100 "
        "AND affinity BETWEEN -100 AND 100 AND tension BETWEEN 0 AND 100",
    )
    op.drop_column("session_relationship_events", "romantic_interest_delta")
    op.drop_column("session_relationship_states", "romantic_interest")
