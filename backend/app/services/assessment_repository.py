import hashlib
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment


class AssessmentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, assessment_id: uuid.UUID) -> Assessment | None:
        return self._db.get(Assessment, assessment_id)

    def get_latest_for_property(self, property_id: uuid.UUID) -> Assessment | None:
        return (
            self._db.execute(
                select(Assessment)
                .where(Assessment.property_id == property_id)
                .order_by(Assessment.tax_year.desc(), Assessment.fetched_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

    def list_by_property(self, property_id: uuid.UUID) -> list[Assessment]:
        return list(
            self._db.execute(
                select(Assessment)
                .where(Assessment.property_id == property_id)
                .order_by(Assessment.tax_year.desc())
            )
            .scalars()
            .all()
        )

    def compute_hash(self, data: dict) -> str:
        content = str(sorted(data.items())).encode()
        return hashlib.sha256(content).hexdigest()

    def has_changed(self, property_id: uuid.UUID, tax_year: int, data_hash: str) -> bool:
        existing = (
            self._db.execute(
                select(Assessment).where(
                    Assessment.property_id == property_id,
                    Assessment.tax_year == tax_year,
                )
            )
            .scalars()
            .first()
        )
        if not existing:
            return True
        return existing.data_hash != data_hash

    def create(
        self,
        property_id: uuid.UUID,
        tax_year: int,
        assessed_total: Decimal,
        assessed_land: Decimal | None = None,
        assessed_improvement: Decimal | None = None,
        tax_amount: Decimal | None = None,
        raw_s3_key: str | None = None,
        data_hash: str | None = None,
    ) -> Assessment:
        assessment = Assessment(
            property_id=property_id,
            tax_year=tax_year,
            assessed_total=assessed_total,
            assessed_land=assessed_land,
            assessed_improvement=assessed_improvement,
            tax_amount=tax_amount,
            raw_s3_key=raw_s3_key,
            data_hash=data_hash,
        )
        self._db.add(assessment)
        self._db.commit()
        self._db.refresh(assessment)
        return assessment
