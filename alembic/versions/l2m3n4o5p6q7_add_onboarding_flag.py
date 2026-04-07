"""add has_completed_onboarding to users

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-04-08 10:00:00.000000

Adds has_completed_onboarding boolean to users table so first-time users
are shown the onboarding wizard and existing users bypass it.
Defaults to False for new users; existing users are set to True via
data migration so they are not unexpectedly redirected to the wizard.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, Sequence[str], None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'has_completed_onboarding',
            sa.Boolean(),
            nullable=False,
            server_default='0',
        ),
    )
    # Mark all existing users as having completed onboarding so they are
    # not sent to the wizard after this migration is applied to production.
    op.execute("UPDATE users SET has_completed_onboarding = 1 WHERE has_completed_onboarding = 0")


def downgrade() -> None:
    op.drop_column('users', 'has_completed_onboarding')
