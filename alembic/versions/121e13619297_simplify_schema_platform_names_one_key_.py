"""simplify_schema_platform_names_one_key_per_team

Revision ID: 121e13619297
Revises: 6f4dbeea5805
Create Date: 2025-11-09 03:16:13.579947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '121e13619297'
down_revision: Union[str, None] = '6f4dbeea5805'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Simplify schema for cleaner architecture:
    1. Add platform_name to teams (e.g., "Internal-BI", "External-Telegram")
    2. Remove description from teams (not needed)
    3. Remove webhook fields from teams (webhooks removed)
    4. Add unique constraint to api_keys.team_id (one key per team)
    """

    # Add platform_name column (nullable first for existing data)
    op.add_column('teams', sa.Column('platform_name', sa.String(255), nullable=True))

    # Migrate existing teams: set platform_name from name with "Internal-" prefix
    # This handles existing teams gracefully
    op.execute("""
        UPDATE teams
        SET platform_name = CONCAT('Internal-', name)
        WHERE platform_name IS NULL
    """)

    # Now make platform_name NOT NULL and UNIQUE
    op.alter_column('teams', 'platform_name', nullable=False)
    op.create_unique_constraint('uq_teams_platform_name', 'teams', ['platform_name'])

    # Remove description column
    op.drop_column('teams', 'description')

    # Remove webhook columns
    op.drop_column('teams', 'webhook_url')
    op.drop_column('teams', 'webhook_secret')
    op.drop_column('teams', 'webhook_enabled')

    # Add unique constraint to api_keys.team_id (one key per team)
    # First, handle case where teams might have multiple keys
    op.execute("""
        DELETE FROM api_keys
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM api_keys
            GROUP BY team_id
        )
    """)
    op.create_unique_constraint('uq_api_keys_team_id', 'api_keys', ['team_id'])


def downgrade() -> None:
    """Rollback schema changes"""

    # Remove unique constraint from api_keys
    op.drop_constraint('uq_api_keys_team_id', 'api_keys', type_='unique')

    # Re-add webhook columns
    op.add_column('teams', sa.Column('webhook_enabled', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('teams', sa.Column('webhook_secret', sa.String(255), nullable=True))
    op.add_column('teams', sa.Column('webhook_url', sa.String(500), nullable=True))

    # Re-add description column
    op.add_column('teams', sa.Column('description', sa.Text(), nullable=True))

    # Remove platform_name
    op.drop_constraint('uq_teams_platform_name', 'teams', type_='unique')
    op.drop_column('teams', 'platform_name')
