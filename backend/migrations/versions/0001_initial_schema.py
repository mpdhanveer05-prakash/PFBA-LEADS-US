"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-24

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.execute("""
        CREATE TABLE IF NOT EXISTS counties (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(100) NOT NULL,
            state VARCHAR(2) NOT NULL,
            portal_url VARCHAR(500) NOT NULL,
            scraper_adapter VARCHAR(100) NOT NULL,
            appeal_deadline_days INTEGER NOT NULL DEFAULT 30,
            approval_rate_hist FLOAT,
            last_scraped_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            county_id UUID NOT NULL REFERENCES counties(id),
            apn VARCHAR(100) NOT NULL,
            address VARCHAR(300) NOT NULL,
            city VARCHAR(100) NOT NULL,
            state VARCHAR(2) NOT NULL,
            zip VARCHAR(10) NOT NULL,
            property_type VARCHAR(50) NOT NULL,
            building_sqft INTEGER,
            lot_size_sqft INTEGER,
            year_built INTEGER,
            bedrooms INTEGER,
            bathrooms FLOAT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_properties_apn ON properties (apn)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            property_id UUID NOT NULL REFERENCES properties(id),
            tax_year INTEGER NOT NULL,
            assessed_land NUMERIC(12,2),
            assessed_improvement NUMERIC(12,2),
            assessed_total NUMERIC(12,2) NOT NULL,
            tax_amount NUMERIC(12,2),
            raw_s3_key VARCHAR(500),
            data_hash VARCHAR(64),
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_assessments_property_tax_year ON assessments (property_id, tax_year)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS comparable_sales (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            property_id UUID NOT NULL REFERENCES properties(id),
            comp_apn VARCHAR(100) NOT NULL,
            sale_price NUMERIC(12,2) NOT NULL,
            sale_date DATE NOT NULL,
            sqft INTEGER,
            price_per_sqft NUMERIC(12,2),
            distance_miles FLOAT,
            similarity_score FLOAT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE prioritytier AS ENUM ('A', 'B', 'C', 'D');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS lead_scores (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            property_id UUID NOT NULL REFERENCES properties(id),
            assessment_id UUID NOT NULL REFERENCES assessments(id),
            market_value_est NUMERIC(12,2),
            assessment_gap NUMERIC(12,2),
            gap_pct FLOAT,
            appeal_probability FLOAT,
            estimated_savings NUMERIC(12,2),
            priority_tier prioritytier NOT NULL DEFAULT 'D',
            shap_explanation JSONB,
            model_version VARCHAR(50),
            scored_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE appealstatus AS ENUM ('NEW', 'ASSIGNED', 'FILED', 'WON', 'LOST', 'WITHDRAWN');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS appeals (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            lead_score_id UUID NOT NULL REFERENCES lead_scores(id),
            status appealstatus NOT NULL DEFAULT 'NEW',
            filing_date DATE,
            deadline_date DATE,
            assigned_agent VARCHAR(200),
            actual_savings NUMERIC(12,2),
            outcome VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS appeals")
    op.execute("DROP TYPE IF EXISTS appealstatus")
    op.execute("DROP TABLE IF EXISTS lead_scores")
    op.execute("DROP TYPE IF EXISTS prioritytier")
    op.execute("DROP TABLE IF EXISTS comparable_sales")
    op.execute("DROP INDEX IF EXISTS ix_assessments_property_tax_year")
    op.execute("DROP TABLE IF EXISTS assessments")
    op.execute("DROP INDEX IF EXISTS ix_properties_apn")
    op.execute("DROP TABLE IF EXISTS properties")
    op.execute("DROP TABLE IF EXISTS counties")
