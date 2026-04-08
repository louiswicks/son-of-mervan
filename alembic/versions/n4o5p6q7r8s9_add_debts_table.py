"""add debts table

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-04-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "n4o5p6q7r8s9"
down_revision = "m3n4o5p6q7r8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "debts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("interest_rate", sa.Float(), nullable=False),
        sa.Column("minimum_payment", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("name_encrypted", sa.String(length=512), nullable=False),
        sa.Column("balance_encrypted", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debts_id", "debts", ["id"])
    op.create_index("ix_debts_user_id", "debts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_debts_user_id", table_name="debts")
    op.drop_index("ix_debts_id", table_name="debts")
    op.drop_table("debts")
