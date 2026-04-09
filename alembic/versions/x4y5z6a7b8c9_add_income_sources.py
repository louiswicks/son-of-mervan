"""add income_sources table

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-04-09 13:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'x4y5z6a7b8c9'
down_revision = 'w3x4y5z6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'income_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('monthly_data_id', sa.Integer(), sa.ForeignKey('monthly_data.id'), nullable=False),
        sa.Column('name_encrypted', sa.String(512), nullable=False),
        sa.Column('amount_encrypted', sa.String(512), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False, server_default='salary'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_income_sources_id', 'income_sources', ['id'])
    op.create_index('ix_income_sources_user_id', 'income_sources', ['user_id'])
    op.create_index('ix_income_sources_monthly_data_id', 'income_sources', ['monthly_data_id'])


def downgrade():
    op.drop_index('ix_income_sources_monthly_data_id', table_name='income_sources')
    op.drop_index('ix_income_sources_user_id', table_name='income_sources')
    op.drop_index('ix_income_sources_id', table_name='income_sources')
    op.drop_table('income_sources')
