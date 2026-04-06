"""add multi-currency support

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-04-06 00:00:00.000000

Adds:
  - users.base_currency (VARCHAR 3, default 'GBP')
  - monthly_expenses.currency (VARCHAR 3, default 'GBP')
  - exchange_rates table for daily rate sync
"""
from alembic import op
import sqlalchemy as sa

revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade():
    # Add base_currency to users
    op.add_column('users', sa.Column('base_currency', sa.String(3), nullable=False, server_default='GBP'))

    # Add currency to monthly_expenses
    op.add_column('monthly_expenses', sa.Column('currency', sa.String(3), nullable=False, server_default='GBP'))

    # Create exchange_rates table
    op.create_table(
        'exchange_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('base', sa.String(3), nullable=False),
        sa.Column('target', sa.String(3), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('base', 'target', 'date', name='uq_exchange_rate_base_target_date'),
    )
    op.create_index('ix_exchange_rates_id', 'exchange_rates', ['id'])
    op.create_index('ix_exchange_rates_base', 'exchange_rates', ['base'])
    op.create_index('ix_exchange_rates_target', 'exchange_rates', ['target'])
    op.create_index('ix_exchange_rates_date', 'exchange_rates', ['date'])


def downgrade():
    op.drop_index('ix_exchange_rates_date', 'exchange_rates')
    op.drop_index('ix_exchange_rates_target', 'exchange_rates')
    op.drop_index('ix_exchange_rates_base', 'exchange_rates')
    op.drop_index('ix_exchange_rates_id', 'exchange_rates')
    op.drop_table('exchange_rates')
    op.drop_column('monthly_expenses', 'currency')
    op.drop_column('users', 'base_currency')
