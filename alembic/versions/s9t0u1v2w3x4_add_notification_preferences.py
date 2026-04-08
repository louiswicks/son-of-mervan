"""add notification preference columns to users

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-04-08 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("notif_budget_alerts", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("notif_milestones", sa.Boolean(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("users", "notif_milestones")
    op.drop_column("users", "notif_budget_alerts")
