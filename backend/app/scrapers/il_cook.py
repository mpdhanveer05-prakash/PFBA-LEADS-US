"""
Cook County, IL — Cook County Assessor via Socrata open data portal.

Two datasets joined by PIN:
  uzyt-m557 — residential assessments (year, mailed_tot, mailed_land, mailed_bldg)
  c49d-89sn — parcel universe (address, lat/lon)
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, to_decimal
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)

_ASMT_URL = "https://datacatalog.cookcountyil.gov/resource/uzyt-m557.json"
_ADDR_URL  = "https://datacatalog.cookcountyil.gov/resource/c49d-89sn.json"
_ASMT_YEAR = "2026"
_BATCH     = 150  # PINs per Socrata IN() query


class CookCountyScraper(BaseCountyScraper):
    adapter_name = "cook_il"

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        assessments = self._fetch_assessments(limit)
        logger.info("Cook IL: %d assessment rows for year %s", len(assessments), _ASMT_YEAR)
        if not assessments:
            return {"records_fetched": 0, "records_changed": 0, "errors": 0}

        addresses = self._fetch_addresses(list(assessments.keys()))
        logger.info("Cook IL: matched %d/%d addresses", len(addresses), len(assessments))

        for pin, asmt in assessments.items():
            addr = addresses.get(pin)
            if not addr:
                continue
            try:
                raw = self._merge(pin, asmt, addr)
                if not raw:
                    continue
                records_fetched += 1
                result = self.process_record(apn=pin, raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1
            except Exception:
                logger.exception("Cook IL: error processing PIN %s", pin)
                errors += 1

        return {"records_fetched": records_fetched, "records_changed": records_changed, "errors": errors}

    def _fetch_assessments(self, limit: int) -> dict[str, dict]:
        results: dict[str, dict] = {}
        offset = 0
        page_size = min(500, limit)
        while len(results) < limit:
            try:
                resp = self.fetch(
                    _ASMT_URL,
                    params={
                        "$select": "pin,year,mailed_tot,mailed_land,mailed_bldg",
                        "$where": f"year='{_ASMT_YEAR}' AND mailed_tot>'0'",
                        "$limit": page_size,
                        "$offset": offset,
                    },
                )
                page = resp.json()
                if not page:
                    break
                for row in page:
                    pin = str(row.get("pin") or "").strip()
                    if not pin or pin in results:
                        continue
                    tot = to_decimal(row.get("mailed_tot"))
                    if not tot or tot <= Decimal("0"):
                        continue
                    results[pin] = {
                        "assessed_total": tot,
                        "assessed_land": to_decimal(row.get("mailed_land")),
                        "assessed_improvement": to_decimal(row.get("mailed_bldg")),
                        "tax_year": int(row.get("year") or 2026),
                    }
                if len(page) < page_size:
                    break
                offset += page_size
                time.sleep(0.3)
            except Exception:
                logger.exception("Cook IL: assessment fetch failed at offset %d", offset)
                break
        return results

    def _fetch_addresses(self, pins: list[str]) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for i in range(0, len(pins), _BATCH):
            chunk = pins[i: i + _BATCH]
            pin_list = ",".join(f"'{p}'" for p in chunk)
            try:
                resp = self.fetch(
                    _ADDR_URL,
                    params={
                        "$select": "pin,property_address,property_city,property_zip,latitude,longitude",
                        "$where": f"pin IN ({pin_list}) AND indicator_has_address='1'",
                        "$limit": _BATCH,
                    },
                )
                for row in resp.json():
                    p = str(row.get("pin") or "").strip()
                    if p:
                        results[p] = row
                time.sleep(0.3)
            except Exception:
                logger.exception("Cook IL: address batch failed for chunk starting %d", i)
        return results

    def _merge(self, pin: str, asmt: dict, addr: dict) -> dict | None:
        address = str(addr.get("property_address") or "").strip().title()
        if not address:
            return None
        city = str(addr.get("property_city") or "Chicago").strip().title()
        zip_code = str(addr.get("property_zip") or "").split("-")[0].strip()[:10]
        lat: float | None = None
        lng: float | None = None
        try:
            raw_lat = addr.get("latitude")
            raw_lng = addr.get("longitude")
            if raw_lat:
                lat = float(raw_lat) or None
                lng = float(raw_lng) if raw_lng else None
        except (TypeError, ValueError):
            pass
        return {
            "apn": pin,
            "address": address,
            "city": city,
            "state": "IL",
            "zip": zip_code,
            "property_type": "RESIDENTIAL",
            "building_sqft": None,
            "year_built": None,
            "owner_name": None,
            "assessed_total": asmt["assessed_total"],
            "assessed_land": asmt.get("assessed_land"),
            "assessed_improvement": asmt.get("assessed_improvement"),
            "tax_year": asmt.get("tax_year", 2026),
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
                state="IL",
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
        tax_year = int(raw_data.get("tax_year") or 2026)
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
