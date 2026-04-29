import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.lead_score import PriorityTier


class ComparableSaleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    comp_apn: str
    sale_price: Decimal
    sale_date: datetime
    sqft: int | None
    price_per_sqft: Decimal | None
    distance_miles: float | None
    similarity_score: float | None


class AssessmentHistoryItem(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    tax_year: int
    assessed_land: Decimal | None
    assessed_improvement: Decimal | None
    assessed_total: Decimal
    tax_amount: Decimal | None
    fetched_at: datetime


class LeadListItem(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    property_id: uuid.UUID
    assessment_id: uuid.UUID
    apn: str | None = None
    address: str
    city: str
    state: str
    county_name: str
    property_type: str
    assessed_total: Decimal
    market_value_est: Decimal | None
    gap_pct: float | None
    appeal_probability: float | None
    estimated_savings: Decimal | None
    priority_tier: PriorityTier
    deadline_date: datetime | None = None
    scored_at: datetime
    is_verified: bool = False
    verified_by: str | None = None
    verified_at: datetime | None = None


class LeadDetail(LeadListItem):
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    # Property details
    apn: str | None = None
    zip: str | None = None
    building_sqft: int | None = None
    lot_size_sqft: int | None = None
    year_built: int | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None

    # Owner contact
    owner_name: str | None = None
    owner_email: str | None = None
    owner_phone: str | None = None
    mailing_address: str | None = None

    # Scoring details
    assessment_gap: Decimal | None
    shap_explanation: dict | None
    model_version: str | None

    # Related records
    comparable_sales: list[ComparableSaleRead] = []
    assessment_history: list[AssessmentHistoryItem] = []


class LeadAssign(BaseModel):
    assigned_agent: str


class LeadVerify(BaseModel):
    verified_by: str


class PaginatedLeads(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LeadListItem]
