"""add rolled_over_from to monthly_data

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-04-09 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'y5z6a7b8c9d0'
down_revision = 'x4y5z6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'monthly_data',
        sa.Column('rolled_over_from', sa.String(7), nullable=True),
    )


def downgrade():
    op.drop_column('monthly_data', 'rolled_over_from')
