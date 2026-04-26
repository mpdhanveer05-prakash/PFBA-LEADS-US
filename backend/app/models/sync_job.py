import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SyncType(str, enum.Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class SyncStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    county_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("counties.id"), nullable=False)
    sync_type: Mapped[SyncType] = mapped_column(Enum(SyncType), nullable=False, default=SyncType.MANUAL)
    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), nullable=False, default=SyncStatus.PENDING)
    triggered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lead_count: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    records_seeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    records_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    county: Mapped["County"] = relationship("County")
