"""add banking tables

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-04-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_encrypted", sa.String(512), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("account_id_encrypted", sa.String(512), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_connections_id", "bank_connections", ["id"])
    op.create_index("ix_bank_connections_user_id", "bank_connections", ["user_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("bank_connection_id", sa.Integer(), nullable=False),
        sa.Column("monthly_expense_id", sa.Integer(), nullable=True),
        sa.Column("external_id_encrypted", sa.String(512), nullable=False),
        sa.Column("description_encrypted", sa.String(512), nullable=True),
        sa.Column("amount_encrypted", sa.String(64), nullable=True),
        sa.Column("currency_encrypted", sa.String(64), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("suggested_category", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bank_connection_id"], ["bank_connections.id"]),
        sa.ForeignKeyConstraint(["monthly_expense_id"], ["monthly_expenses.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_transactions_id", "bank_transactions", ["id"])
    op.create_index("ix_bank_transactions_user_id", "bank_transactions", ["user_id"])
    op.create_index("ix_bank_transactions_bank_connection_id", "bank_transactions", ["bank_connection_id"])
    op.create_index("ix_bank_transactions_status", "bank_transactions", ["status"])


def downgrade():
    op.drop_index("ix_bank_transactions_status", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_bank_connection_id", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_user_id", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_id", table_name="bank_transactions")
    op.drop_table("bank_transactions")

    op.drop_index("ix_bank_connections_user_id", table_name="bank_connections")
    op.drop_index("ix_bank_connections_id", table_name="bank_connections")
    op.drop_table("bank_connections")
