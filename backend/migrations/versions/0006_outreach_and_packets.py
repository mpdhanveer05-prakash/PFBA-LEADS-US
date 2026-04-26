"""add outreach_campaigns, appeal_packets tables and extend comparable_sales

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outreach_campaigns",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("lead_score_id", sa.UUID(), sa.ForeignKey("lead_scores.id"), nullable=False),
        sa.Column("property_id", sa.UUID(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("channel", sa.String(10), nullable=False, server_default="EMAIL"),
        sa.Column("recipient_email", sa.String(255), nullable=True),
        sa.Column("recipient_phone", sa.String(30), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "appeal_packets",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("lead_score_id", sa.UUID(), sa.ForeignKey("lead_scores.id"), nullable=False),
        sa.Column("property_id", sa.UUID(), sa.ForeignKey("properties.id"), nullable=False),
        sa.Column("county_id", sa.UUID(), sa.ForeignKey("counties.id"), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("claimed_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("evidence_comps", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
    )

    op.add_column("comparable_sales", sa.Column("source", sa.String(20), nullable=True))
    op.add_column("comparable_sales", sa.Column("comp_address", sa.String(300), nullable=True))
    op.add_column("comparable_sales", sa.Column("comp_lat", sa.Float(), nullable=True))
    op.add_column("comparable_sales", sa.Column("comp_lng", sa.Float(), nullable=True))
    op.add_column(
        "properties",
        sa.Column("outreach_status", sa.String(20), nullable=True, server_default="NONE"),
    )


def downgrade() -> None:
    op.drop_table("outreach_campaigns")
    op.drop_table("appeal_packets")
    op.drop_column("comparable_sales", "source")
    op.drop_column("comparable_sales", "comp_address")
    op.drop_column("comparable_sales", "comp_lat")
    op.drop_column("comparable_sales", "comp_lng")
    op.drop_column("properties", "outreach_status")
