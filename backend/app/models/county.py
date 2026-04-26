import uuid
from datetime import datetime

from sqlalchemy import NUMERIC, String, Integer, Float, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class County(Base):
    __tablename__ = "counties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    portal_url: Mapped[str] = mapped_column(String(500), nullable=False)
    scraper_adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    appeal_deadline_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    approval_rate_hist: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24, server_default="24")
    auto_sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    properties: Mapped[list["Property"]] = relationship("Property", back_populates="county")
