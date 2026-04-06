"""add budget_alerts and notifications tables

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "budget_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category_encrypted", sa.String(512), nullable=False),
        sa.Column("threshold_pct", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budget_alerts_id", "budget_alerts", ["id"])
    op.create_index("ix_budget_alerts_user_id", "budget_alerts", ["user_id"])
    op.create_index("ix_budget_alerts_deleted_at", "budget_alerts", ["deleted_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("title_encrypted", sa.String(512), nullable=False),
        sa.Column("message_encrypted", sa.String(512), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("dedup_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_dedup_key", "notifications", ["dedup_key"])


def downgrade():
    op.drop_index("ix_notifications_dedup_key", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_budget_alerts_deleted_at", table_name="budget_alerts")
    op.drop_index("ix_budget_alerts_user_id", table_name="budget_alerts")
    op.drop_index("ix_budget_alerts_id", table_name="budget_alerts")
    op.drop_table("budget_alerts")
