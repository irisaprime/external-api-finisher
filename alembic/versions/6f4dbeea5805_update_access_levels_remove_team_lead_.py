"""update_access_levels_remove_team_lead_rename_user_to_team

Revision ID: 6f4dbeea5805
Revises: 71521c6321dc
Create Date: 2025-11-08 12:31:09.969280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f4dbeea5805'
down_revision: Union[str, None] = '71521c6321dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove access_level column - TWO-PATH AUTHENTICATION

    BEFORE: Database stored access levels (user, team_lead, admin)
    AFTER: No access_level column - all database keys are for external teams

    TWO-PATH AUTHENTICATION:
    - Super Admins: Environment variable (SUPER_ADMIN_API_KEYS) - NOT in database
    - Teams: Database API keys (this table) - all equal access (chat service only)

    This migration:
    1. Drops the access_level column from api_keys table
    2. All database keys are now for external teams (clients)
    3. Super admin authentication completely separate (environment-based)
    """
    # Drop access_level column - no longer needed
    op.drop_column('api_keys', 'access_level')


def downgrade() -> None:
    """
    Rollback: Re-add access_level column

    NOTE: This is a lossy downgrade - we cannot recover the original access levels.
    All keys will be set to 'team' (external teams).
    """
    # Re-add access_level column with default 'team'
    op.add_column(
        'api_keys',
        sa.Column('access_level', sa.String(50), nullable=False, server_default='team')
    )
