"""add created_at to monthly_expenses

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-04-09 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'z6a7b8c9d0e1'
down_revision = 'y5z6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'monthly_expenses',
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column('monthly_expenses', 'created_at')
