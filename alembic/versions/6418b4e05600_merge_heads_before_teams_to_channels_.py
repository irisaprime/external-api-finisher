"""merge heads before teams to channels refactor

Revision ID: 6418b4e05600
Revises: 850df83abd23, a1b2c3d4e5f6
Create Date: 2025-11-18 07:39:04.115870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6418b4e05600'
down_revision: Union[str, None] = ('850df83abd23', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
