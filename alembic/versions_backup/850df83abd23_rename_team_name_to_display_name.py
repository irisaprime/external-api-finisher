"""rename_team_name_to_display_name

Renames the 'name' column to 'display_name' in the teams table to better reflect
its purpose as a human-friendly display name (distinct from platform_name which is
the system identifier).

Revision ID: 850df83abd23
Revises: db8a923de76e
Create Date: 2025-11-15 16:43:13.761257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '850df83abd23'
down_revision: Union[str, None] = 'db8a923de76e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename 'name' column to 'display_name' in teams table
    op.alter_column('teams', 'name', new_column_name='display_name')

    # Rename index to match new column name
    op.execute('ALTER INDEX ix_teams_name RENAME TO ix_teams_display_name')


def downgrade() -> None:
    # Revert: rename 'display_name' back to 'name'
    op.alter_column('teams', 'display_name', new_column_name='name')

    # Revert index name
    op.execute('ALTER INDEX ix_teams_display_name RENAME TO ix_teams_name')
