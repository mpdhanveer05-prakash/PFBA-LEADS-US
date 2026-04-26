import uuid
from datetime import datetime

from pydantic import BaseModel


class PropertyBase(BaseModel):
    apn: str
    address: str
    city: str
    state: str
    zip: str
    property_type: str
    building_sqft: int | None = None
    lot_size_sqft: int | None = None
    year_built: int | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None


class PropertyCreate(PropertyBase):
    county_id: uuid.UUID
    owner_name: str | None = None
    owner_email: str | None = None
    owner_phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class PropertyRead(PropertyBase):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    county_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
