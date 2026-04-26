import uuid
from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel

from app.models.appeal import AppealStatus


class AppealCreate(BaseModel):
    lead_score_id: uuid.UUID
    deadline_date: date | None = None
    assigned_agent: str | None = None


class AppealUpdate(BaseModel):
    status: AppealStatus | None = None
    assigned_agent: str | None = None
    filing_date: date | None = None
    actual_savings: Decimal | None = None
    outcome: str | None = None


class AppealRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    lead_score_id: uuid.UUID
    status: AppealStatus
    filing_date: date | None
    deadline_date: date | None
    assigned_agent: str | None
    actual_savings: Decimal | None
    outcome: str | None
    created_at: datetime
    updated_at: datetime
