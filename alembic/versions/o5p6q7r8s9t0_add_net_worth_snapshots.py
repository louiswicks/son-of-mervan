"""add net worth snapshots table

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-04-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "net_worth_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_assets", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_liabilities", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("assets_json_encrypted", sa.String(length=4096), nullable=True),
        sa.Column("liabilities_json_encrypted", sa.String(length=4096), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_net_worth_snapshots_id", "net_worth_snapshots", ["id"])
    op.create_index("ix_net_worth_snapshots_user_id", "net_worth_snapshots", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_net_worth_snapshots_user_id", table_name="net_worth_snapshots")
    op.drop_index("ix_net_worth_snapshots_id", table_name="net_worth_snapshots")
    op.drop_table("net_worth_snapshots")
