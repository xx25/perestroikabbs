"""Drop terminal preferences from users table

Terminal settings are configured on each connection, so storing
preferences per-user is unnecessary.

Revision ID: a1b2c3d4e5f6
Revises: db80637b4ce6
Create Date: 2025-12-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'db80637b4ce6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('users', 'terminal_cols')
    op.drop_column('users', 'terminal_rows')


def downgrade() -> None:
    op.add_column('users', sa.Column('terminal_cols', sa.Integer(), nullable=True, server_default='80'))
    op.add_column('users', sa.Column('terminal_rows', sa.Integer(), nullable=True, server_default='24'))
