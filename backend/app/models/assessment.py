import uuid
from datetime import datetime

from sqlalchemy import NUMERIC, String, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.database import Base


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (Index("ix_assessments_property_tax_year", "property_id", "tax_year"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    tax_year: Mapped[int] = mapped_column(Integer, nullable=False)
    assessed_land: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    assessed_improvement: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    assessed_total: Mapped[Decimal] = mapped_column(NUMERIC(12, 2), nullable=False)
    tax_amount: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    raw_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    property: Mapped["Property"] = relationship("Property", back_populates="assessments")
    lead_scores: Mapped[list["LeadScore"]] = relationship(
        "LeadScore", back_populates="assessment"
    )
