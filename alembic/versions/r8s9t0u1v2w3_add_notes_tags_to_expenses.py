"""add note and tags to monthly_expenses

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-04-08 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "r8s9t0u1v2w3"
down_revision = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("monthly_expenses", sa.Column("note_encrypted", sa.String(1024), nullable=True))
    op.add_column("monthly_expenses", sa.Column("tags_encrypted", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("monthly_expenses", "tags_encrypted")
    op.drop_column("monthly_expenses", "note_encrypted")
