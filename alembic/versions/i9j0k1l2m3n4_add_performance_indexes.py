"""add performance indexes — monthly_data.user_id + connection pool settings

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-06 21:00:00.000000

Adds an index on monthly_data.user_id to speed up the primary query pattern
(fetch all months for a user). The composite index on
(monthly_expenses.monthly_data_id, deleted_at) was added in e5f6a7b8c9d0.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, Sequence[str], None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index on monthly_data.user_id — every endpoint that reads a user's months
    # filters on this column (e.g. annual overview, insights, trends).
    op.create_index(
        'ix_monthly_data_user_id',
        'monthly_data',
        ['user_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_monthly_data_user_id', table_name='monthly_data')
