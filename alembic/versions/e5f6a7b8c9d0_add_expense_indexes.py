"""add indexes on monthly_expenses for pagination performance

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-06 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index on (monthly_data_id, deleted_at) — speeds up the primary
    # query pattern: fetch all non-deleted expenses for a given month record.
    op.create_index(
        'ix_monthly_expenses_data_id_deleted_at',
        'monthly_expenses',
        ['monthly_data_id', 'deleted_at'],
    )

    # Index on deleted_at alone — helps any global soft-delete scans.
    op.create_index(
        'ix_monthly_expenses_deleted_at',
        'monthly_expenses',
        ['deleted_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_monthly_expenses_deleted_at', table_name='monthly_expenses')
    op.drop_index('ix_monthly_expenses_data_id_deleted_at', table_name='monthly_expenses')
