"""add investments

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-08

Phase 8.3: Investment Portfolio Tracking.
Adds investments + investment_prices tables.
"""
from alembic import op
import sqlalchemy as sa

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("asset_type", sa.String(16), nullable=False, server_default="stock"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("name_encrypted", sa.String(512), nullable=False),
        sa.Column("units_encrypted", sa.String(512), nullable=False),
        sa.Column("purchase_price_encrypted", sa.String(512), nullable=False),
        sa.Column("notes_encrypted", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investments_id", "investments", ["id"])
    op.create_index("ix_investments_user_id", "investments", ["user_id"])
    op.create_index("ix_investments_deleted_at", "investments", ["deleted_at"])

    op.create_table(
        "investment_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "investment_id",
            sa.Integer(),
            sa.ForeignKey("investments.id"),
            nullable=False,
        ),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investment_prices_id", "investment_prices", ["id"])
    op.create_index(
        "ix_investment_prices_investment_id",
        "investment_prices",
        ["investment_id"],
    )
    op.create_index(
        "ix_investment_prices_fetched_at",
        "investment_prices",
        ["fetched_at"],
    )


def downgrade():
    op.drop_index("ix_investment_prices_fetched_at", table_name="investment_prices")
    op.drop_index("ix_investment_prices_investment_id", table_name="investment_prices")
    op.drop_index("ix_investment_prices_id", table_name="investment_prices")
    op.drop_table("investment_prices")

    op.drop_index("ix_investments_deleted_at", table_name="investments")
    op.drop_index("ix_investments_user_id", table_name="investments")
    op.drop_index("ix_investments_id", table_name="investments")
    op.drop_table("investments")
