"""add owner contact fields to properties

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("owner_name", sa.String(200), nullable=True))
    op.add_column("properties", sa.Column("owner_email", sa.String(200), nullable=True))
    op.add_column("properties", sa.Column("owner_phone", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "owner_name")
    op.drop_column("properties", "owner_email")
    op.drop_column("properties", "owner_phone")
