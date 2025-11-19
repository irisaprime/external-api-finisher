"""add platform config columns

Revision ID: a1b2c3d4e5f6
Revises: 71521c6321dc
Create Date: 2025-01-17 12:00:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '71521c6321dc'
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    # Add platform_type column
    op.add_column('teams',
        sa.Column('platform_type', sa.String(50), nullable=False, server_default='private')
    )

    # Add configuration override columns (NULL = use defaults)
    op.add_column('teams',
        sa.Column('rate_limit', sa.Integer, nullable=True,
                 comment='Override default rate limit (requests/min)')
    )
    op.add_column('teams',
        sa.Column('max_history', sa.Integer, nullable=True,
                 comment='Override default max conversation history')
    )
    op.add_column('teams',
        sa.Column('default_model', sa.String(255), nullable=True,
                 comment='Override default AI model')
    )
    op.add_column('teams',
        sa.Column('available_models', postgresql.JSON, nullable=True,
                 comment='Override available models list')
    )
    op.add_column('teams',
        sa.Column('allow_model_switch', sa.Boolean, nullable=True,
                 comment='Override model switch permission')
    )

    # Set existing Telegram platform as public (if exists)
    op.execute("""
        UPDATE teams
        SET platform_type = 'public'
        WHERE platform_name = 'telegram'
    """)

    # Add index for faster queries
    op.create_index('ix_teams_platform_type', 'teams', ['platform_type'])


def downgrade() -> None:
    op.drop_index('ix_teams_platform_type', table_name='teams')
    op.drop_column('teams', 'allow_model_switch')
    op.drop_column('teams', 'available_models')
    op.drop_column('teams', 'default_model')
    op.drop_column('teams', 'max_history')
    op.drop_column('teams', 'rate_limit')
    op.drop_column('teams', 'platform_type')
