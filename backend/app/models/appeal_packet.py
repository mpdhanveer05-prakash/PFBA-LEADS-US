from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import NUMERIC, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AppealPacket(Base):
    __tablename__ = "appeal_packets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_score_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lead_scores.id"), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    county_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("counties.id"), nullable=False)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    claimed_value: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    evidence_comps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")

    lead_score: Mapped["LeadScore"] = relationship("LeadScore")
    property: Mapped["Property"] = relationship("Property")
    county: Mapped["County"] = relationship("County")
