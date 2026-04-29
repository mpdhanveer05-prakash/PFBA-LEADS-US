"""add dnc_lists, dnc_entries tables and dnc columns to properties

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dnc_lists",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("uploaded_by", sa.String(200), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "dnc_entries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("dnc_list_id", sa.UUID(), sa.ForeignKey("dnc_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_name", sa.String(300), nullable=True),
        sa.Column("raw_email", sa.String(300), nullable=True),
        sa.Column("raw_phone", sa.String(50), nullable=True),
        sa.Column("raw_address", sa.String(500), nullable=True),
        sa.Column("raw_apn", sa.String(100), nullable=True),
        sa.Column("matched_property_id", sa.UUID(), sa.ForeignKey("properties.id", ondelete="SET NULL"), nullable=True),
        sa.Column("match_reason", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("properties", sa.Column("is_dnc", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("properties", sa.Column("dnc_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("properties", sa.Column("dnc_list_id", sa.UUID(), sa.ForeignKey("dnc_lists.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "dnc_list_id")
    op.drop_column("properties", "dnc_at")
    op.drop_column("properties", "is_dnc")
    op.drop_table("dnc_entries")
    op.drop_table("dnc_lists")
