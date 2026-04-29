from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DncList(Base):
    __tablename__ = "dnc_lists"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # csv / excel / pdf
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entries: Mapped[list["DncEntry"]] = relationship(
        "DncEntry", back_populates="dnc_list", cascade="all, delete-orphan"
    )


class DncEntry(Base):
    __tablename__ = "dnc_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dnc_list_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dnc_lists.id", ondelete="CASCADE"), nullable=False
    )
    raw_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    raw_email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    raw_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_apn: Mapped[str | None] = mapped_column(String(100), nullable=True)
    matched_property_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("properties.id", ondelete="SET NULL"), nullable=True
    )
    match_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dnc_list: Mapped["DncList"] = relationship("DncList", back_populates="entries")
    matched_property: Mapped["Property | None"] = relationship("Property", foreign_keys=[matched_property_id])
