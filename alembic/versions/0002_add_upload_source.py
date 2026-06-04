"""add upload to sourcetype enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE sourcetype ADD VALUE 'upload'")


def downgrade() -> None:
    pass
