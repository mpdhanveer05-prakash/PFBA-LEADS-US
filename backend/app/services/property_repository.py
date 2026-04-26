import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property import Property
from app.schemas.property import PropertyCreate


class PropertyRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, property_id: uuid.UUID) -> Property | None:
        return self._db.get(Property, property_id)

    def get_by_apn(self, county_id: uuid.UUID, apn: str) -> Property | None:
        return (
            self._db.execute(
                select(Property).where(
                    Property.county_id == county_id,
                    Property.apn == apn,
                )
            )
            .scalars()
            .first()
        )

    def list_by_county(self, county_id: uuid.UUID) -> list[Property]:
        return list(
            self._db.execute(
                select(Property).where(Property.county_id == county_id)
            )
            .scalars()
            .all()
        )

    def create(self, schema: PropertyCreate) -> Property:
        prop = Property(**schema.model_dump())
        self._db.add(prop)
        self._db.commit()
        self._db.refresh(prop)
        return prop

    def upsert(self, county_id: uuid.UUID, schema: PropertyCreate) -> Property:
        existing = self.get_by_apn(county_id, schema.apn)
        if existing:
            for field, value in schema.model_dump(exclude={"county_id"}).items():
                setattr(existing, field, value)
            self._db.commit()
            self._db.refresh(existing)
            return existing
        return self.create(schema)
