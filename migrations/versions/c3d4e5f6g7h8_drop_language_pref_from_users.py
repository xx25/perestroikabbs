"""Drop language_pref from users table

Language is selected on each login, so storing preference is unnecessary.

Revision ID: c3d4e5f6g7h8
Revises: a1b2c3d4e5f6
Create Date: 2025-12-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('users', 'language_pref')


def downgrade() -> None:
    op.add_column('users', sa.Column('language_pref', sa.String(5), nullable=True, server_default='en'))
