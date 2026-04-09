"""add category_rules table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-09 17:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'category_rules',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('pattern', sa.String(256), nullable=False),
        sa.Column('category_encrypted', sa.String(512), nullable=False),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table('category_rules')
