"""add recurring_expenses table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'recurring_expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('frequency', sa.String(16), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('last_generated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('name_encrypted', sa.String(512), nullable=False),
        sa.Column('category_encrypted', sa.String(512), nullable=False),
        sa.Column('planned_amount_encrypted', sa.String(512), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recurring_expenses_id', 'recurring_expenses', ['id'], unique=False)
    op.create_index('ix_recurring_expenses_user_id', 'recurring_expenses', ['user_id'], unique=False)
    op.create_index('ix_recurring_expenses_deleted_at', 'recurring_expenses', ['deleted_at'], unique=False)


def downgrade():
    op.drop_index('ix_recurring_expenses_deleted_at', table_name='recurring_expenses')
    op.drop_index('ix_recurring_expenses_user_id', table_name='recurring_expenses')
    op.drop_index('ix_recurring_expenses_id', table_name='recurring_expenses')
    op.drop_table('recurring_expenses')
