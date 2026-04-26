"""add verification fields to lead_scores

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-25

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lead_scores", sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("lead_scores", sa.Column("verified_by", sa.String(200), nullable=True))
    op.add_column("lead_scores", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("lead_scores", "is_verified")
    op.drop_column("lead_scores", "verified_by")
    op.drop_column("lead_scores", "verified_at")
