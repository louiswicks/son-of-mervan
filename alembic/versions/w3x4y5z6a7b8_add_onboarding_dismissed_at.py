"""add onboarding_dismissed_at to users

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-04-09 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'w3x4y5z6a7b8'
down_revision = 'v2w3x4y5z6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('onboarding_dismissed_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('users', 'onboarding_dismissed_at')
