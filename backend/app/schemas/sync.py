import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.sync_job import SyncStatus, SyncType


class SyncTriggerRequest(BaseModel):
    county_ids: list[uuid.UUID]
    count: int = 50
    triggered_by: str | None = None


class SyncJobRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    county_id: uuid.UUID
    county_name: str
    sync_type: SyncType
    status: SyncStatus
    triggered_by: str | None
    lead_count: int
    records_seeded: int
    records_scored: int
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class CountyScheduleUpdate(BaseModel):
    sync_interval_hours: int = 24
    auto_sync_enabled: bool = True
