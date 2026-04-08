"""add milestone_notifications_sent table

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-04-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "milestone_notifications_sent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("milestone_type", sa.String(length=128), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "milestone_type"),
    )
    op.create_index("ix_milestone_notifications_sent_id", "milestone_notifications_sent", ["id"])
    op.create_index("ix_milestone_notifications_sent_user_id", "milestone_notifications_sent", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_milestone_notifications_sent_user_id", table_name="milestone_notifications_sent")
    op.drop_index("ix_milestone_notifications_sent_id", table_name="milestone_notifications_sent")
    op.drop_table("milestone_notifications_sent")
