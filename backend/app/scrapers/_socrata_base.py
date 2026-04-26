"""
Shared base for Socrata open-data portal scrapers.

Socrata is used by Cook County (IL) and many other government agencies.
Subclasses set:
    _DOMAIN   — e.g. "datacatalog.cookcountyil.gov"
    _DATASET  — 4x4 dataset ID e.g. "tx2p-k2g9"
    _STATE    — 2-letter state code
    _FIELD_MAP — maps canonical keys → Socrata column names
"""
from __future__ import annotations

import logging
import random
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, geocode_address, to_decimal, to_int
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)


class SocrataParcelScraper(BaseCountyScraper):
    """Abstract base — subclasses must set _DOMAIN, _DATASET, _STATE, _FIELD_MAP."""

    _DOMAIN: str = ""
    _DATASET: str = ""
    _STATE: str = ""
    _CITY: str = ""

    _FIELD_MAP: dict[str, str] = {
        "apn":       "pin",
        "address":   "property_address",
        "city":      "property_city",
        "zip":       "property_zip",
        "use_desc":  "property_class",
        "bldg_sqft": "building_sq_ft",
        "year_built": "age",
        "net_av":    "assessed_value",
        "land_av":   "land_value",
        "impr_av":   "improvement_value",
        "owner":     "taxpayer_name",
    }

    @property
    def _api_base(self) -> str:
        return f"https://{self._DOMAIN}/resource/{self._DATASET}.json"

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        rows = self._fetch_rows(limit)
        logger.info("%s: fetched %d rows from Socrata", self.adapter_name, len(rows))

        for row in rows:
            try:
                raw = self._parse_row(row)
                if not raw or not raw.get("apn") or not raw.get("assessed_total"):
                    continue
                records_fetched += 1
                result = self.process_record(apn=raw["apn"], raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1
                time.sleep(0.1)
            except Exception:
                logger.exception("%s: error processing row", self.adapter_name)
                errors += 1

        return {
            "records_fetched": records_fetched,
            "records_changed": records_changed,
            "errors": errors,
        }

    def _fetch_rows(self, limit: int) -> list[dict]:
        results: list[dict] = []
        page_size = min(500, limit)
        offset = random.randint(0, 5000)  # start at a random offset for variety

        while len(results) < limit:
            try:
                resp = self.fetch(
                    self._api_base,
                    params={
                        "$limit": page_size,
                        "$offset": offset,
                        "$order": ":id",
                    },
                )
                page = resp.json()
                if not page:
                    break
                results.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
                time.sleep(0.5)
            except Exception:
                logger.warning(
                    "%s: Socrata page fetch failed at offset %d", self.adapter_name, offset
                )
                break

        return results[:limit]

    def _parse_row(self, row: dict) -> dict | None:
        fm = self._FIELD_MAP

        apn = str(row.get(fm.get("apn", "pin")) or "").strip().replace("-", "").replace(" ", "")
        if not apn:
            return None

        address = str(row.get(fm.get("address", "property_address")) or "").strip().title()
        city = str(row.get(fm.get("city", "property_city")) or self._CITY).strip().title()
        zip_code = str(row.get(fm.get("zip", "property_zip")) or "").strip()[:10]

        use_desc = str(row.get(fm.get("use_desc", "property_class")) or "").upper()
        if any(k in use_desc for k in ("SINGLE", "CONDO", "RESID", "2-6", "1-6", "CLASS 2")):
            prop_type = "RESIDENTIAL"
        elif any(k in use_desc for k in ("COMMERCIAL", "OFFICE", "INDUSTRIAL", "RETAIL")):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        assessed_total = to_decimal(row.get(fm.get("net_av", "assessed_value")))
        if not assessed_total or assessed_total <= Decimal("0"):
            return None

        land_val = to_decimal(row.get(fm.get("land_av", "land_value")))
        imprv_val = to_decimal(row.get(fm.get("impr_av", "improvement_value")))
        owner_name: str | None = (
            str(row.get(fm.get("owner", "taxpayer_name")) or "").strip().title() or None
        )

        # Socrata rows rarely include lat/lng; geocode if missing
        lat: float | None = None
        lng: float | None = None
        raw_lat = row.get("latitude") or row.get("lat")
        raw_lng = row.get("longitude") or row.get("lng") or row.get("lon")
        if raw_lat:
            try:
                lat = float(raw_lat)
                lng = float(raw_lng)
            except (TypeError, ValueError):
                pass
        if not lat and address and city:
            coords = geocode_address(address, city, self._STATE)
            if coords:
                lat, lng = coords
            time.sleep(1.1)

        bldg_sqft = to_int(row.get(fm.get("bldg_sqft", "building_sq_ft")))
        year_built = to_int(row.get(fm.get("year_built", "age")))

        return {
            "apn": apn,
            "address": address,
            "city": city,
            "state": self._STATE,
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": bldg_sqft,
            "year_built": year_built,
            "owner_name": owner_name,
            "assessed_total": assessed_total,
            "assessed_land": land_val,
            "assessed_improvement": imprv_val,
            "tax_year": int(row.get("tax_year") or row.get("year") or 2024),
            "latitude": lat,
            "longitude": lng,
        }

    def process_record(self, apn: str, raw_data: dict, db: Session) -> dict:
        prop_repo = PropertyRepository(db)
        assess_repo = AssessmentRepository(db)

        prop = prop_repo.upsert(
            self.county.id,
            PropertyCreate(
                county_id=self.county.id,
                apn=apn,
                address=raw_data.get("address", ""),
                city=raw_data.get("city", ""),
                state=self._STATE,
                zip=raw_data.get("zip", ""),
                property_type=raw_data.get("property_type", "RESIDENTIAL"),
                building_sqft=raw_data.get("building_sqft"),
                year_built=raw_data.get("year_built"),
                owner_name=raw_data.get("owner_name"),
                latitude=raw_data.get("latitude"),
                longitude=raw_data.get("longitude"),
            ),
        )

        hash_data = {
            k: str(v)
            for k, v in raw_data.items()
            if v is not None and k not in ("latitude", "longitude")
        }
        data_hash = self.hash_record(hash_data)
        tax_year = int(raw_data.get("tax_year") or 2024)
        changed = assess_repo.has_changed(prop.id, tax_year, data_hash)

        if changed:
            assess_repo.create(
                property_id=prop.id,
                tax_year=tax_year,
                assessed_total=raw_data["assessed_total"],
                assessed_land=raw_data.get("assessed_land"),
                assessed_improvement=raw_data.get("assessed_improvement"),
                data_hash=data_hash,
            )

        return {"changed": changed}
