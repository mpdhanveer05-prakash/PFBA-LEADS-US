"""
ComparableSalesService — finds comparable sales for a subject property.

Matching criteria (all must pass):
  - Same property_type
  - building_sqft within ±20%
  - year_built within ±15 years
  - distance ≤ 0.5 miles (Haversine; falls back to same-zip if no lat/lng)

similarity_score = weighted average of attribute deltas (0–1, higher = more similar)
market_value_est  = median(price_per_sqft of top-5 comps) × subject sqft
"""
from __future__ import annotations

import math
import statistics
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.comparable_sale import ComparableSale
from app.models.property import Property

_MAX_DISTANCE_MILES = 0.5
_SQFT_TOLERANCE = 0.20
_YEAR_TOLERANCE = 15
_TOP_N = 5


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in miles between two lat/lng points."""
    R = 3958.8  # Earth radius miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _similarity(subject: Property, comp: ComparableSale, distance_miles: float) -> float:
    """Compute a 0–1 similarity score; higher = closer match."""
    scores: list[float] = []

    # Distance (weight 0.4)
    dist_score = max(0.0, 1.0 - distance_miles / _MAX_DISTANCE_MILES)
    scores.append(dist_score * 0.4)

    # Sqft delta (weight 0.3)
    if subject.building_sqft and comp.sqft:
        delta = abs(subject.building_sqft - comp.sqft) / max(subject.building_sqft, 1)
        sqft_score = max(0.0, 1.0 - delta / _SQFT_TOLERANCE)
        scores.append(sqft_score * 0.3)
    else:
        scores.append(0.15)  # neutral if unknown

    # Year built delta (weight 0.3)
    if subject.year_built and comp.sqft:
        year_diff = 0  # comp doesn't store year_built; treat as neutral
        year_score = 1.0
        scores.append(year_score * 0.3)
    else:
        scores.append(0.15)

    return round(sum(scores), 4)


class ComparableSalesService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def find_and_store_comps(self, property_id: uuid.UUID, candidate_sales: list[dict]) -> list[ComparableSale]:
        """
        Given a list of candidate sale dicts, filter by matching criteria,
        score similarity, store top-N comps, and return them.

        Each candidate dict must have:
          comp_apn, sale_price, sale_date, sqft, price_per_sqft,
          property_type, year_built, latitude, longitude
        """
        subject = self._db.get(Property, property_id)
        if not subject:
            raise ValueError(f"Property {property_id} not found")

        matched: list[tuple[float, dict]] = []

        for sale in candidate_sales:
            # --- Type filter ---
            if sale.get("property_type") and subject.property_type:
                if sale["property_type"] != subject.property_type:
                    continue

            # --- Sqft filter ±20% ---
            if subject.building_sqft and sale.get("sqft"):
                ratio = sale["sqft"] / subject.building_sqft
                if not (1 - _SQFT_TOLERANCE <= ratio <= 1 + _SQFT_TOLERANCE):
                    continue

            # --- Year built filter ±15yr ---
            if subject.year_built and sale.get("year_built"):
                if abs(subject.year_built - sale["year_built"]) > _YEAR_TOLERANCE:
                    continue

            # --- Distance filter ---
            distance = self._calc_distance(subject, sale)
            if distance > _MAX_DISTANCE_MILES:
                continue

            score = _similarity(subject, _make_comp_stub(sale), distance)
            matched.append((score, sale, distance))

        # Sort by similarity descending, keep top-N
        matched.sort(key=lambda x: x[0], reverse=True)
        top = matched[:_TOP_N]

        # Delete existing comps for this property before re-storing
        self._db.execute(
            ComparableSale.__table__.delete().where(
                ComparableSale.property_id == property_id
            )
        )

        comps: list[ComparableSale] = []
        for score, sale, distance in top:
            price_per_sqft = None
            if sale.get("sqft") and sale.get("sale_price"):
                price_per_sqft = Decimal(str(round(float(sale["sale_price"]) / sale["sqft"], 2)))

            comp = ComparableSale(
                property_id=property_id,
                comp_apn=sale["comp_apn"],
                sale_price=Decimal(str(sale["sale_price"])),
                sale_date=sale["sale_date"] if isinstance(sale["sale_date"], date) else date.fromisoformat(sale["sale_date"]),
                sqft=sale.get("sqft"),
                price_per_sqft=price_per_sqft,
                distance_miles=round(distance, 4),
                similarity_score=score,
            )
            self._db.add(comp)
            comps.append(comp)

        self._db.commit()
        for c in comps:
            self._db.refresh(c)
        return comps

    def estimate_market_value(self, property_id: uuid.UUID) -> Decimal | None:
        """Median price_per_sqft of top-5 comps × subject sqft."""
        subject = self._db.get(Property, property_id)
        if not subject or not subject.building_sqft:
            return None

        comps = list(
            self._db.execute(
                select(ComparableSale)
                .where(ComparableSale.property_id == property_id)
                .order_by(ComparableSale.similarity_score.desc())
                .limit(_TOP_N)
            ).scalars().all()
        )

        prices = [float(c.price_per_sqft) for c in comps if c.price_per_sqft]
        if not prices:
            return None

        median_ppsf = statistics.median(prices)
        return Decimal(str(round(median_ppsf * subject.building_sqft, 2)))

    def _calc_distance(self, subject: Property, sale: dict) -> float:
        """Return distance in miles, falling back to 0.0 (same area) if no coords."""
        if subject.latitude and subject.longitude and sale.get("latitude") and sale.get("longitude"):
            return _haversine(subject.latitude, subject.longitude, sale["latitude"], sale["longitude"])
        # Fallback: same zip = 0.1 miles proxy, different zip = 1.0 miles
        if subject.zip and sale.get("zip"):
            return 0.1 if subject.zip == sale["zip"] else 1.0
        return 0.5  # unknown — treat as borderline


def _make_comp_stub(sale: dict) -> ComparableSale:
    """Create a transient ComparableSale for similarity computation."""
    c = ComparableSale.__new__(ComparableSale)
    c.sqft = sale.get("sqft")
    return c
