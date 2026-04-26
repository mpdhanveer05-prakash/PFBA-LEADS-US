import uuid
from datetime import datetime, date

from sqlalchemy import NUMERIC, String, Integer, Float, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from decimal import Decimal

from app.database import Base


class ComparableSale(Base):
    __tablename__ = "comparable_sales"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"), nullable=False)
    comp_apn: Mapped[str] = mapped_column(String(100), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(NUMERIC(12, 2), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_per_sqft: Mapped[Decimal | None] = mapped_column(NUMERIC(12, 2), nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    property: Mapped["Property"] = relationship("Property", back_populates="comparable_sales")
