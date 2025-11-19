"""refactor teams to channels architecture

Revision ID: 7f532f75e129
Revises: 6418b4e05600
Create Date: 2025-11-18 07:39:12.584794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f532f75e129'
down_revision: Union[str, None] = '6418b4e05600'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Refactor teams → channels architecture:
    - Rename table: teams → channels
    - Rename columns: platform_name → channel_id, display_name → title, platform_type → access_type
    - Rename foreign keys: team_id → channel_id in api_keys, usage_logs, messages
    """
    # Step 1: Rename foreign key columns in dependent tables
    op.alter_column('api_keys', 'team_id', new_column_name='channel_id')
    op.alter_column('usage_logs', 'team_id', new_column_name='channel_id')
    op.alter_column('messages', 'team_id', new_column_name='channel_id')

    # Step 2: Rename main table columns
    op.alter_column('teams', 'platform_name', new_column_name='channel_id')
    op.alter_column('teams', 'display_name', new_column_name='title')
    op.alter_column('teams', 'platform_type', new_column_name='access_type')

    # Step 3: Rename indexes
    op.execute('ALTER INDEX ix_teams_platform_name RENAME TO ix_channels_channel_id')
    op.execute('ALTER INDEX ix_teams_platform_type RENAME TO ix_channels_access_type')

    # Step 4: Rename table (do this last)
    op.rename_table('teams', 'channels')

    # Step 5: Rename constraints (if any named with 'team')
    # PostgreSQL auto-renames constraints with the table, so this is optional


def downgrade() -> None:
    """Rollback channels → teams architecture"""
    # Reverse order of upgrade
    op.rename_table('channels', 'teams')

    op.execute('ALTER INDEX ix_channels_channel_id RENAME TO ix_teams_platform_name')
    op.execute('ALTER INDEX ix_channels_access_type RENAME TO ix_teams_platform_type')

    op.alter_column('teams', 'access_type', new_column_name='platform_type')
    op.alter_column('teams', 'title', new_column_name='display_name')
    op.alter_column('teams', 'channel_id', new_column_name='platform_name')

    op.alter_column('messages', 'channel_id', new_column_name='team_id')
    op.alter_column('usage_logs', 'channel_id', new_column_name='team_id')
    op.alter_column('api_keys', 'channel_id', new_column_name='team_id')
