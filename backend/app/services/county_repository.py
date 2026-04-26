from __future__ import annotations

import uuid
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.county import County
from app.models.property import Property
from app.models.lead_score import LeadScore
from app.schemas.county import CountyCreate, CountyWithStats


class CountyRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, county_id: uuid.UUID) -> County | None:
        return self._db.get(County, county_id)

    def get_by_slug(self, name: str, state: str) -> County | None:
        return (
            self._db.execute(
                select(County).where(County.name == name, County.state == state)
            )
            .scalars()
            .first()
        )

    def list(self) -> list[County]:
        return list(self._db.execute(select(County)).scalars().all())

    def list_with_stats(self) -> list[CountyWithStats]:
        rows = self._db.execute(
            select(
                County,
                func.count(Property.id.distinct()).label("property_count"),
                func.count(LeadScore.id.distinct()).label("lead_count"),
            )
            .outerjoin(Property, Property.county_id == County.id)
            .outerjoin(LeadScore, LeadScore.property_id == Property.id)
            .group_by(County.id)
        ).all()

        result = []
        for county, property_count, lead_count in rows:
            data = CountyWithStats.model_validate(county)
            data.property_count = property_count or 0
            data.lead_count = lead_count or 0
            result.append(data)
        return result

    def get_with_stats(self, county_id: uuid.UUID) -> CountyWithStats | None:
        row = self._db.execute(
            select(
                County,
                func.count(Property.id.distinct()).label("property_count"),
                func.count(LeadScore.id.distinct()).label("lead_count"),
            )
            .outerjoin(Property, Property.county_id == County.id)
            .outerjoin(LeadScore, LeadScore.property_id == Property.id)
            .where(County.id == county_id)
            .group_by(County.id)
        ).first()

        if not row:
            return None
        county, property_count, lead_count = row
        data = CountyWithStats.model_validate(county)
        data.property_count = property_count or 0
        data.lead_count = lead_count or 0
        return data

    def create(self, schema: CountyCreate) -> County:
        county = County(**schema.model_dump())
        self._db.add(county)
        self._db.commit()
        self._db.refresh(county)
        return county

    def update_last_scraped(self, county_id: uuid.UUID) -> None:
        from datetime import datetime, timezone

        county = self._db.get(County, county_id)
        if county:
            county.last_scraped_at = datetime.now(timezone.utc)
            self._db.commit()
