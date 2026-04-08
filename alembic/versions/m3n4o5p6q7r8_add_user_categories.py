"""add user_categories table

Revision ID: m3n4o5p6q7r8
Revises: 137017825f82
Create Date: 2026-04-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "m3n4o5p6q7r8"
down_revision = "137017825f82"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column(
            "color",
            sa.String(length=7),
            nullable=False,
            server_default="#6b7280",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_user_category_name"),
    )
    op.create_index("ix_user_categories_id", "user_categories", ["id"])
    op.create_index("ix_user_categories_user_id", "user_categories", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_categories_user_id", table_name="user_categories")
    op.drop_index("ix_user_categories_id", table_name="user_categories")
    op.drop_table("user_categories")
