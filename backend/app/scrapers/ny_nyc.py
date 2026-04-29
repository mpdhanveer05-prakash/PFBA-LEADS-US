"""
New York City, NY — NYC MapPLUTO via NYC Open Data Socrata.

Dataset: 64uk-42ks (NYC MapPLUTO) — parcel-level land use, ownership,
assessed values, and coordinates for all ~850k NYC tax lots.

API: https://data.cityofnewyork.us/resource/64uk-42ks.json
No authentication required.
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, to_decimal, to_int
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)

_API = "https://data.cityofnewyork.us/resource/64uk-42ks.json"

# Borough code → city name
_BOROUGH_CITY = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}


class NYCCountyScraper(BaseCountyScraper):
    adapter_name = "ny_nyc"

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        rows = self._fetch_rows(limit)
        logger.info("NYC PLUTO: fetched %d rows", len(rows))

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
                logger.exception("NYC: error processing BBL %s", row.get("bbl"))
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
                        "$select": "bbl,address,zipcode,assesstot,assessland,yearbuilt,bldgarea,ownername,latitude,longitude,bldgclass,borocode,lotarea,numfloors,unitsres",
                        "$where": "assesstot>'1000000' AND latitude IS NOT NULL",
                        "$order": "assesstot DESC",
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
                logger.exception("NYC: page fetch failed at offset %d", offset)
                break
        return results[:limit]

    def _parse_row(self, row: dict) -> dict | None:
        bbl = str(row.get("bbl") or "").strip()
        if not bbl:
            return None

        address = str(row.get("address") or "").strip().title()
        if not address:
            return None

        zip_code = str(row.get("zipcode") or "").strip()[:10]
        borocode = str(row.get("borocode") or "1")
        city = _BOROUGH_CITY.get(borocode, "New York")

        assessed_total = to_decimal(row.get("assesstot"))
        if not assessed_total or assessed_total <= Decimal("0"):
            return None

        bldg_class = str(row.get("bldgclass") or "").upper()
        if bldg_class.startswith(("A", "B", "C", "D")):
            prop_type = "RESIDENTIAL"
        elif bldg_class.startswith(("O", "K", "L", "S", "E")):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        lat: float | None = None
        lng: float | None = None
        try:
            raw_lat = row.get("latitude")
            raw_lng = row.get("longitude")
            if raw_lat:
                lat = float(raw_lat) or None
                lng = float(raw_lng) if raw_lng else None
        except (TypeError, ValueError):
            pass

        owner_name = str(row.get("ownername") or "").strip().title() or None

        return {
            "apn": bbl,
            "address": address,
            "city": city,
            "state": "NY",
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": to_int(row.get("bldgarea")),
            "lot_size_sqft": to_int(row.get("lotarea")),
            "year_built": to_int(row.get("yearbuilt")),
            "owner_name": owner_name,
            "owner_email": None,
            "owner_phone": None,
            "assessed_total": assessed_total,
            "assessed_land": to_decimal(row.get("assessland")),
            "assessed_improvement": None,
            "tax_year": 2024,
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
                state="NY",
                zip=raw_data.get("zip", ""),
                property_type=raw_data.get("property_type", "RESIDENTIAL"),
                building_sqft=raw_data.get("building_sqft"),
                lot_size_sqft=raw_data.get("lot_size_sqft"),
                year_built=raw_data.get("year_built"),
                owner_name=raw_data.get("owner_name"),
                owner_email=raw_data.get("owner_email"),
                owner_phone=raw_data.get("owner_phone"),
                latitude=raw_data.get("latitude"),
                longitude=raw_data.get("longitude"),
            ),
        )
        hash_data = {k: str(v) for k, v in raw_data.items() if v is not None and k not in ("latitude", "longitude")}
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
