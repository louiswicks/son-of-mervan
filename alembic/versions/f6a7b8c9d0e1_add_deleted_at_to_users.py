"""add deleted_at to users

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('deleted_at', sa.DateTime(), nullable=True, server_default=None),
    )
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'], unique=False)


def downgrade():
    op.drop_index('ix_users_deleted_at', table_name='users')
    op.drop_column('users', 'deleted_at')
