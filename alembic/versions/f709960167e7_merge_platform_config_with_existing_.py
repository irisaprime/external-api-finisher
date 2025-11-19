"""merge platform config with existing migrations

Revision ID: f709960167e7
Revises: 850df83abd23, a1b2c3d4e5f6
Create Date: 2025-11-17 15:25:32.838082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f709960167e7'
down_revision: Union[str, None] = ('850df83abd23', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
