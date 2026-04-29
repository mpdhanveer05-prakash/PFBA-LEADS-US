"""
San Francisco County, CA — SF Assessor Closed Roll via SF Open Data Socrata.

Dataset: wv5m-vpq2 (Assessor Historical Secured Property Tax Rolls)
Fields: parcel_number, property_location, assessed_land_value,
        assessed_improvement_value, year_property_built, the_geom,
        property_class_code_definition, closed_roll_year

API: https://data.sfgov.org/resource/wv5m-vpq2.json
No authentication required.
"""
from __future__ import annotations

import logging
import re
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, to_decimal, to_int
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)

_API = "https://data.sfgov.org/resource/wv5m-vpq2.json"
_YEAR = "2023"

# SF property_location format: "0000 2801 LEAVENWORTH         ST0000"
# Strip leading/trailing 0000 blocks and normalize spaces
_ADDR_RE = re.compile(r"^0+\s*|\s*0+$")


def _clean_address(raw: str) -> str:
    cleaned = _ADDR_RE.sub("", raw.strip())
    return " ".join(cleaned.split())


class SanFranciscoCountyScraper(BaseCountyScraper):
    adapter_name = "ca_sf"

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        rows = self._fetch_rows(limit)
        logger.info("SF Assessor: fetched %d rows for year %s", len(rows), _YEAR)

        for row in rows:
            try:
                raw = self._parse_row(row)
                if not raw:
                    continue
                records_fetched += 1
                result = self.process_record(apn=raw["apn"], raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1
            except Exception:
                logger.exception("SF: error processing parcel %s", row.get("parcel_number"))
                errors += 1

        return {"records_fetched": records_fetched, "records_changed": records_changed, "errors": errors}

    def _fetch_rows(self, limit: int) -> list[dict]:
        results: list[dict] = []
        page_size = min(500, limit)
        offset = 0
        while len(results) < limit:
            try:
                resp = self.fetch(
                    _API,
                    params={
                        "$select": "parcel_number,property_location,assessed_land_value,assessed_improvement_value,year_property_built,the_geom,property_class_code_definition,closed_roll_year",
                        "$where": f"closed_roll_year='{_YEAR}' AND assessed_improvement_value>'500000'",
                        "$order": "assessed_improvement_value DESC",
                        "$limit": page_size,
                        "$offset": offset,
                    },
                )
                page = resp.json()
                if not page:
                    break
                results.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
                time.sleep(0.3)
            except Exception:
                logger.exception("SF: page fetch failed at offset %d", offset)
                break
        return results[:limit]

    def _parse_row(self, row: dict) -> dict | None:
        apn = str(row.get("parcel_number") or "").strip()
        if not apn:
            return None

        raw_addr = str(row.get("property_location") or "").strip()
        address = _clean_address(raw_addr)
        if not address:
            return None

        imprv = to_decimal(row.get("assessed_improvement_value"))
        if not imprv or imprv <= Decimal("0"):
            return None
        land = to_decimal(row.get("assessed_land_value")) or Decimal("0")
        assessed_total = land + imprv

        use_desc = str(row.get("property_class_code_definition") or "").upper()
        if any(k in use_desc for k in ("SINGLE", "CONDO", "RESID", "DUPLEX", "DWELLING")):
            prop_type = "RESIDENTIAL"
        elif any(k in use_desc for k in ("COMMERCIAL", "OFFICE", "RETAIL", "INDUSTRIAL")):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        lat: float | None = None
        lng: float | None = None
        geom = row.get("the_geom")
        if isinstance(geom, dict) and geom.get("type") == "Point":
            coords = geom.get("coordinates", [])
            if len(coords) == 2:
                lng = float(coords[0])
                lat = float(coords[1])

        return {
            "apn": apn,
            "address": address,
            "city": "San Francisco",
            "state": "CA",
            "zip": "",
            "property_type": prop_type,
            "building_sqft": None,
            "year_built": to_int(row.get("year_property_built")),
            "owner_name": None,
            "assessed_total": assessed_total,
            "assessed_land": land if land > 0 else None,
            "assessed_improvement": imprv,
            "tax_year": int(row.get("closed_roll_year") or 2023),
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
                state="CA",
                zip=raw_data.get("zip", ""),
                property_type=raw_data.get("property_type", "RESIDENTIAL"),
                building_sqft=raw_data.get("building_sqft"),
                year_built=raw_data.get("year_built"),
                owner_name=raw_data.get("owner_name"),
                latitude=raw_data.get("latitude"),
                longitude=raw_data.get("longitude"),
            ),
        )
        hash_data = {k: str(v) for k, v in raw_data.items() if v is not None and k not in ("latitude", "longitude")}
        data_hash = self.hash_record(hash_data)
        tax_year = int(raw_data.get("tax_year") or 2023)
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
