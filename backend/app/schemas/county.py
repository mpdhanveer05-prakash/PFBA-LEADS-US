import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl


class CountyBase(BaseModel):
    name: str
    state: str
    portal_url: str
    scraper_adapter: str
    appeal_deadline_days: int = 30
    approval_rate_hist: float | None = None


class CountyCreate(CountyBase):
    pass


class CountyUpdate(BaseModel):
    name: str | None = None
    portal_url: str | None = None
    appeal_deadline_days: int | None = None
    approval_rate_hist: float | None = None


class CountyRead(CountyBase):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    last_scraped_at: datetime | None
    sync_interval_hours: int = 24
    auto_sync_enabled: bool = True
    next_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CountyWithStats(CountyRead):
    lead_count: int = 0
    property_count: int = 0
