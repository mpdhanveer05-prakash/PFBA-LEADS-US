import uuid
import enum
from datetime import datetime

from sqlalchemy import NUMERIC, String, Float, Boolean, DateTime, ForeignKey, Enum, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.database import Base


class PriorityTier(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id"), nullable=False
    )
    market_value_est: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    assessment_gap: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    appeal_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_savings: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    priority_tier: Mapped[PriorityTier] = mapped_column(
        Enum(PriorityTier), nullable=False, default=PriorityTier.D
    )
    shap_explanation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    verified_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    property: Mapped["Property"] = relationship("Property", back_populates="lead_scores")
    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="lead_scores")
    appeals: Mapped[list["Appeal"]] = relationship("Appeal", back_populates="lead_score")
