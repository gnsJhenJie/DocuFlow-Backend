"""update document table

Revision ID: 24913bde95d7
Revises: 46489c800beb
Create Date: 2025-05-29 09:39:27.066606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24913bde95d7'
down_revision: Union[str, None] = '46489c800beb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
