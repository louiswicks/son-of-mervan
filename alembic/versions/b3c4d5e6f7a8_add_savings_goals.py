"""add savings goals and contributions tables

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-04-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "savings_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name_encrypted", sa.String(512), nullable=False),
        sa.Column("target_amount_encrypted", sa.String(512), nullable=False),
        sa.Column("target_date", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_savings_goals_id", "savings_goals", ["id"])
    op.create_index("ix_savings_goals_user_id", "savings_goals", ["user_id"])
    op.create_index("ix_savings_goals_deleted_at", "savings_goals", ["deleted_at"])

    op.create_table(
        "savings_contributions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("savings_goals.id"), nullable=False),
        sa.Column("amount_encrypted", sa.String(512), nullable=False),
        sa.Column("note_encrypted", sa.String(512), nullable=True),
        sa.Column("contributed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_savings_contributions_id", "savings_contributions", ["id"])
    op.create_index("ix_savings_contributions_goal_id", "savings_contributions", ["goal_id"])


def downgrade():
    op.drop_index("ix_savings_contributions_goal_id", table_name="savings_contributions")
    op.drop_index("ix_savings_contributions_id", table_name="savings_contributions")
    op.drop_table("savings_contributions")

    op.drop_index("ix_savings_goals_deleted_at", table_name="savings_goals")
    op.drop_index("ix_savings_goals_user_id", table_name="savings_goals")
    op.drop_index("ix_savings_goals_id", table_name="savings_goals")
    op.drop_table("savings_goals")
