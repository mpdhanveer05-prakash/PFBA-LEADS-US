"""add sync_jobs table and schedule fields to counties

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-25

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE synctype AS ENUM ('MANUAL', 'SCHEDULED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE syncstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sync_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            county_id UUID NOT NULL REFERENCES counties(id),
            sync_type synctype NOT NULL DEFAULT 'MANUAL',
            status syncstatus NOT NULL DEFAULT 'PENDING',
            triggered_by VARCHAR(200),
            lead_count INTEGER NOT NULL DEFAULT 500,
            records_seeded INTEGER NOT NULL DEFAULT 0,
            records_scored INTEGER NOT NULL DEFAULT 0,
            error_message VARCHAR(1000),
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sync_jobs_county_id ON sync_jobs(county_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sync_jobs_status ON sync_jobs(status)")

    op.add_column("counties", sa.Column("sync_interval_hours", sa.Integer, nullable=False, server_default="24"))
    op.add_column("counties", sa.Column("auto_sync_enabled", sa.Boolean, nullable=False, server_default="true"))
    op.add_column("counties", sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("counties", "next_sync_at")
    op.drop_column("counties", "auto_sync_enabled")
    op.drop_column("counties", "sync_interval_hours")
    op.execute("DROP TABLE IF EXISTS sync_jobs")
    op.execute("DROP TYPE IF EXISTS syncstatus")
    op.execute("DROP TYPE IF EXISTS synctype")
