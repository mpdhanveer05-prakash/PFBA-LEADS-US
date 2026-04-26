import uuid
import enum
from datetime import datetime, date

from sqlalchemy import NUMERIC, String, Date, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.database import Base


class AppealStatus(str, enum.Enum):
    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    FILED = "FILED"
    WON = "WON"
    LOST = "LOST"
    WITHDRAWN = "WITHDRAWN"


class Appeal(Base):
    __tablename__ = "appeals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_score_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lead_scores.id"), nullable=False
    )
    status: Mapped[AppealStatus] = mapped_column(
        Enum(AppealStatus), nullable=False, default=AppealStatus.NEW
    )
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assigned_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    actual_savings: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    lead_score: Mapped["LeadScore"] = relationship("LeadScore", back_populates="appeals")
