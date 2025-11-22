"""add_webhook_fields_to_teams

Revision ID: 71521c6321dc
Revises: 0c855e0b81e0
Create Date: 2025-11-01 09:23:26.607156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71521c6321dc'
down_revision: Union[str, None] = '0c855e0b81e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add webhook fields to teams table
    op.add_column('teams', sa.Column('webhook_url', sa.String(length=2048), nullable=True))
    op.add_column('teams', sa.Column('webhook_secret', sa.String(length=255), nullable=True))
    op.add_column('teams', sa.Column('webhook_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove webhook fields from teams table
    op.drop_column('teams', 'webhook_enabled')
    op.drop_column('teams', 'webhook_secret')
    op.drop_column('teams', 'webhook_url')
