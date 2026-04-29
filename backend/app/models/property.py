import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (Index("ix_properties_apn", "apn"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    county_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("counties.id"), nullable=False)
    apn: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip: Mapped[str] = mapped_column(String(10), nullable=False)
    property_type: Mapped[str] = mapped_column(String(50), nullable=False)
    building_sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lot_size_sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[float | None] = mapped_column(Float, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mailing_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    county: Mapped["County"] = relationship("County", back_populates="properties")
    assessments: Mapped[list["Assessment"]] = relationship("Assessment", back_populates="property")
    comparable_sales: Mapped[list["ComparableSale"]] = relationship(
        "ComparableSale", back_populates="property"
    )
    lead_scores: Mapped[list["LeadScore"]] = relationship("LeadScore", back_populates="property")
