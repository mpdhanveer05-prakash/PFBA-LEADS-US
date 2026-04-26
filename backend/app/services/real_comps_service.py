"""
RealCompsService — fetch comparable sales from public Socrata open-data APIs
and store them in the comparable_sales table.

Supported county adapters (scraper_adapter slug):
    nyc_ny      → NYC Department of Finance rolling sales
    philly_pa   → Philadelphia OPA property sales
    sf_ca       → San Francisco Assessor-Recorder
    cook_il     → Cook County Assessor sales

Each fetcher queries the relevant Socrata endpoint, matches records to
existing properties in the county, scores similarity, and persists comps
where distance <= 0.75 miles and similarity > 0.3.
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.comparable_sale import ComparableSale
from app.models.county import County
from app.models.property import Property

logger = logging.getLogger(__name__)

_MAX_DISTANCE_MILES = 0.75
_MIN_SIMILARITY = 0.3
_SOCRATA_LIMIT = 5000
_REQUEST_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Haversine helper
# ---------------------------------------------------------------------------


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in miles between two lat/lng points."""
    R = 3958.8  # Earth radius in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Similarity scorer
# ---------------------------------------------------------------------------


def _similarity_score(
    subject_sqft: int | None,
    comp_sqft: int | None,
    subject_year: int | None,
    comp_year: int | None,
) -> float:
    """
    Weighted similarity: sqft ratio (0.6) + year_built proximity (0.4).
    Returns a value in [0, 1].
    """
    sqft_score = 0.5  # neutral default
    if subject_sqft and comp_sqft and subject_sqft > 0:
        ratio = min(subject_sqft, comp_sqft) / max(subject_sqft, comp_sqft)
        sqft_score = ratio  # 1.0 when identical, approaches 0 as they diverge

    year_score = 0.5  # neutral default
    if subject_year and comp_year:
        diff = abs(subject_year - comp_year)
        year_score = max(0.0, 1.0 - diff / 30.0)  # 30 yr span → 0

    return round(sqft_score * 0.6 + year_score * 0.4, 4)


# ---------------------------------------------------------------------------
# Shared persistence helper
# ---------------------------------------------------------------------------


def _upsert_comp(
    db: Session,
    *,
    property_id: uuid.UUID,
    comp_apn: str,
    comp_address: str | None,
    sale_price: Decimal,
    sale_date: date,
    sqft: int | None,
    comp_lat: float | None,
    comp_lng: float | None,
    subject: Property,
    source: str = "live",
) -> ComparableSale | None:
    """
    Compute distance + similarity, then insert a ComparableSale if the
    record clears the quality threshold.  Returns the saved object or None.
    """
    # Distance
    if (
        subject.latitude
        and subject.longitude
        and comp_lat is not None
        and comp_lng is not None
    ):
        dist = haversine(subject.latitude, subject.longitude, comp_lat, comp_lng)
    else:
        dist = 0.5  # no coords — treat as borderline

    if dist > _MAX_DISTANCE_MILES:
        return None

    sim = _similarity_score(subject.building_sqft, sqft, subject.year_built, None)
    if sim < _MIN_SIMILARITY:
        return None

    price_per_sqft: Decimal | None = None
    if sqft and sqft > 0:
        price_per_sqft = Decimal(str(round(float(sale_price) / sqft, 2)))

    comp = ComparableSale(
        property_id=property_id,
        comp_apn=comp_apn,
        sale_price=sale_price,
        sale_date=sale_date,
        sqft=sqft,
        price_per_sqft=price_per_sqft,
        distance_miles=round(dist, 4),
        similarity_score=sim,
    )
    # Attach extra columns added by migration 0006 (present at runtime)
    comp.__dict__.update(
        {
            "source": source,
            "comp_address": comp_address,
            "comp_lat": comp_lat,
            "comp_lng": comp_lng,
        }
    )
    db.add(comp)
    return comp


def _safe_date(raw: Any) -> date | None:
    """Parse an ISO-8601 date string or return None."""
    if not raw:
        return None
    try:
        if isinstance(raw, date):
            return raw
        return datetime.fromisoformat(str(raw)[:10]).date()
    except (ValueError, TypeError):
        return None


def _safe_decimal(raw: Any, min_val: float = 0.0) -> Decimal | None:
    """Convert raw value to Decimal; return None on failure or if below min_val."""
    try:
        val = float(raw)
        if val < min_val:
            return None
        return Decimal(str(round(val, 2)))
    except (TypeError, ValueError):
        return None


def _safe_int(raw: Any) -> int | None:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# County-specific fetchers
# ---------------------------------------------------------------------------


def _fetch_nyc(county_id: uuid.UUID, db: Session) -> int:
    """
    Fetch NYC rolling sales from the Socrata open-data endpoint.
    Constructs BBL (Borough-Block-Lot) as the APN key.
    Only sales within the last 2 years are considered.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=730)).strftime("%Y-%m-%dT00:00:00")
    url = "https://data.cityofnewyork.us/resource/w2pb-icbu.json"
    params = {
        "$limit": _SOCRATA_LIMIT,
        "$where": f"SALE_DATE >= '{cutoff}'",
        "$select": (
            "BOROUGH,BLOCK,LOT,SALE_PRICE,SALE_DATE,"
            "GROSS_SQUARE_FEET,YEAR_BUILT,ADDRESS,ZIP_CODE"
        ),
    }

    try:
        resp = httpx.get(url, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        records = resp.json()
    except Exception as exc:
        logger.error("NYC Socrata fetch failed: %s", exc)
        return 0

    # Load all properties in this county indexed by APN
    props = {
        p.apn: p
        for p in db.execute(
            select(Property).where(Property.county_id == county_id)
        ).scalars().all()
    }

    count = 0
    for rec in records:
        try:
            borough = _safe_int(rec.get("BOROUGH") or rec.get("borough"))
            block = _safe_int(rec.get("BLOCK") or rec.get("block"))
            lot = _safe_int(rec.get("LOT") or rec.get("lot"))
            if not (borough and block and lot):
                continue
            bbl = str(borough * 1_000_000_000 + block * 10_000 + lot)

            sale_price = _safe_decimal(
                rec.get("SALE_PRICE") or rec.get("sale_price"), min_val=10_000
            )
            sale_date = _safe_date(rec.get("SALE_DATE") or rec.get("sale_date"))
            sqft = _safe_int(rec.get("GROSS_SQUARE_FEET") or rec.get("gross_square_feet"))
            address = rec.get("ADDRESS") or rec.get("address")

            if not sale_price or not sale_date:
                continue

            subject = props.get(bbl)
            if not subject:
                continue

            saved = _upsert_comp(
                db,
                property_id=subject.id,
                comp_apn=bbl,
                comp_address=address,
                sale_price=sale_price,
                sale_date=sale_date,
                sqft=sqft,
                comp_lat=subject.latitude,   # NYC sales lack coords; use subject
                comp_lng=subject.longitude,
                subject=subject,
                source="live",
            )
            if saved:
                count += 1
        except Exception as exc:
            logger.debug("Skipping NYC record: %s", exc)
            continue

    db.commit()
    logger.info("NYC: stored %d comps for county %s", count, county_id)
    return count


def _fetch_philly(county_id: uuid.UUID, db: Session) -> int:
    """
    Fetch Philadelphia OPA property sales from the Socrata endpoint.
    """
    url = "https://data.phila.gov/resource/w7rb-qrn8.json"
    params = {
        "$limit": _SOCRATA_LIMIT,
        "$where": "sale_date IS NOT NULL AND sale_price > '50000'",
        "$select": (
            "parcel_number,location,sale_price,sale_date,"
            "total_livable_area,year_built"
        ),
    }

    try:
        resp = httpx.get(url, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        records = resp.json()
    except Exception as exc:
        logger.error("Philly Socrata fetch failed: %s", exc)
        return 0

    props = {
        p.apn: p
        for p in db.execute(
            select(Property).where(Property.county_id == county_id)
        ).scalars().all()
    }

    count = 0
    for rec in records:
        try:
            apn = rec.get("parcel_number", "").strip().replace("-", "")
            sale_price = _safe_decimal(rec.get("sale_price"), min_val=50_000)
            sale_date = _safe_date(rec.get("sale_date"))
            sqft = _safe_int(rec.get("total_livable_area"))
            address = rec.get("location")

            if not sale_price or not sale_date or not apn:
                continue

            subject = props.get(apn)
            if not subject:
                continue

            saved = _upsert_comp(
                db,
                property_id=subject.id,
                comp_apn=apn,
                comp_address=address,
                sale_price=sale_price,
                sale_date=sale_date,
                sqft=sqft,
                comp_lat=subject.latitude,
                comp_lng=subject.longitude,
                subject=subject,
                source="live",
            )
            if saved:
                count += 1
        except Exception as exc:
            logger.debug("Skipping Philly record: %s", exc)
            continue

    db.commit()
    logger.info("Philly: stored %d comps for county %s", count, county_id)
    return count


def _fetch_sf(county_id: uuid.UUID, db: Session) -> int:
    """
    Fetch San Francisco Assessor-Recorder data from the Socrata endpoint.
    Uses prior_sales_amount as the sale price.
    """
    url = "https://data.sfgov.org/resource/wv5m-vpq2.json"
    params = {
        "$limit": _SOCRATA_LIMIT,
        "$where": "closed_roll_year='2023' AND prior_sales_amount > 100000",
        "$select": (
            "parcel_number,property_location,prior_sales_date,"
            "prior_sales_amount,assessed_land_value,"
            "assessed_improvement_value,year_property_built"
        ),
    }

    try:
        resp = httpx.get(url, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        records = resp.json()
    except Exception as exc:
        logger.error("SF Socrata fetch failed: %s", exc)
        return 0

    props = {
        p.apn: p
        for p in db.execute(
            select(Property).where(Property.county_id == county_id)
        ).scalars().all()
    }

    count = 0
    for rec in records:
        try:
            apn = rec.get("parcel_number", "").strip()
            sale_price = _safe_decimal(rec.get("prior_sales_amount"), min_val=100_000)
            sale_date = _safe_date(rec.get("prior_sales_date"))
            address = rec.get("property_location")

            if not sale_price or not sale_date or not apn:
                continue

            subject = props.get(apn)
            if not subject:
                continue

            saved = _upsert_comp(
                db,
                property_id=subject.id,
                comp_apn=apn,
                comp_address=address,
                sale_price=sale_price,
                sale_date=sale_date,
                sqft=subject.building_sqft,   # SF dataset lacks sqft; use subject
                comp_lat=subject.latitude,
                comp_lng=subject.longitude,
                subject=subject,
                source="live",
            )
            if saved:
                count += 1
        except Exception as exc:
            logger.debug("Skipping SF record: %s", exc)
            continue

    db.commit()
    logger.info("SF: stored %d comps for county %s", count, county_id)
    return count


def _fetch_cook(county_id: uuid.UUID, db: Session) -> int:
    """
    Fetch Cook County (IL) sales from the Socrata endpoint.
    Joins on APN = pin.
    """
    url = "https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json"
    params = {
        "$limit": _SOCRATA_LIMIT,
        "$select": "pin,sale_price,sale_date,class_description",
    }

    try:
        resp = httpx.get(url, params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        records = resp.json()
    except Exception as exc:
        logger.error("Cook County Socrata fetch failed: %s", exc)
        return 0

    props = {
        p.apn: p
        for p in db.execute(
            select(Property).where(Property.county_id == county_id)
        ).scalars().all()
    }

    count = 0
    for rec in records:
        try:
            pin = rec.get("pin", "").strip().replace("-", "").replace(" ", "")
            sale_price = _safe_decimal(rec.get("sale_price"), min_val=10_000)
            sale_date = _safe_date(rec.get("sale_date"))

            if not sale_price or not sale_date or not pin:
                continue

            subject = props.get(pin)
            if not subject:
                continue

            saved = _upsert_comp(
                db,
                property_id=subject.id,
                comp_apn=pin,
                comp_address=None,
                sale_price=sale_price,
                sale_date=sale_date,
                sqft=subject.building_sqft,
                comp_lat=subject.latitude,
                comp_lng=subject.longitude,
                subject=subject,
                source="live",
            )
            if saved:
                count += 1
        except Exception as exc:
            logger.debug("Skipping Cook record: %s", exc)
            continue

    db.commit()
    logger.info("Cook County: stored %d comps for county %s", count, county_id)
    return count


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_FETCHER_MAP = {
    "nyc_ny": _fetch_nyc,
    "philly_pa": _fetch_philly,
    "sf_ca": _fetch_sf,
    "cook_il": _fetch_cook,
}


class RealCompsService:
    """
    Top-level service that dispatches to the correct county fetcher based on
    the county's scraper_adapter slug.
    """

    def run_for_county(
        self,
        county_adapter: str,
        county_id: uuid.UUID,
        db: Session,
    ) -> int:
        """
        Fetch live comparable sales for the given county adapter slug.

        Returns the number of comp records stored.
        Raises ValueError for unknown adapters.
        """
        fetcher = _FETCHER_MAP.get(county_adapter)
        if fetcher is None:
            supported = ", ".join(sorted(_FETCHER_MAP))
            raise ValueError(
                f"No live-comps fetcher for adapter '{county_adapter}'. "
                f"Supported: {supported}"
            )
        return fetcher(county_id, db)
