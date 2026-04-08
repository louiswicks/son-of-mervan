"""add session metadata to refresh tokens

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-04-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("refresh_tokens", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("last_used_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("refresh_tokens", "last_used_at")
    op.drop_column("refresh_tokens", "user_agent")
