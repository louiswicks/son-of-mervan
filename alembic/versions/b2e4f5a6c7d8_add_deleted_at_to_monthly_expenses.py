"""add deleted_at to monthly_expenses

Revision ID: b2e4f5a6c7d8
Revises: a047a3ff3bf1
Create Date: 2026-04-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e4f5a6c7d8'
down_revision: Union[str, Sequence[str], None] = 'a047a3ff3bf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add soft-delete column to monthly_expenses."""
    op.add_column(
        'monthly_expenses',
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Remove soft-delete column from monthly_expenses."""
    op.drop_column('monthly_expenses', 'deleted_at')
