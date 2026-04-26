"""add lat lng to properties

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-24

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("latitude", sa.Float, nullable=True))
    op.add_column("properties", sa.Column("longitude", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "latitude")
    op.drop_column("properties", "longitude")
