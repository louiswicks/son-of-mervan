"""make bank_connection_id nullable for disconnect support

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-04-08 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "v2w3x4y5z6a7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade():
    # Allow bank_connection_id to be NULL so confirmed transactions are
    # preserved when a bank connection is deleted (Phase 15.4 disconnect).
    with op.batch_alter_table("bank_transactions") as batch_op:
        batch_op.alter_column(
            "bank_connection_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade():
    # Restore NOT NULL constraint (requires no NULL rows in the column).
    with op.batch_alter_table("bank_transactions") as batch_op:
        batch_op.alter_column(
            "bank_connection_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
