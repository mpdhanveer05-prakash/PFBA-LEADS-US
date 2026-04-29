"""
Philadelphia County, PA — Office of Property Assessment via Philadelphia Open Data.

Dataset: w7rb-qrn8 (OPA Properties Public)
Fields: parcel_number, location, zip_code, market_value, taxable_land, taxable_building,
        year_built, total_livable_area, owner_1, number_of_bedrooms,
        number_of_bathrooms, category_code_description

API: https://data.phila.gov/resource/w7rb-qrn8.json
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

_API = "https://data.phila.gov/resource/w7rb-qrn8.json"


class PhillyCountyScraper(BaseCountyScraper):
    adapter_name = "pa_philly"

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        rows = self._fetch_rows(limit)
        logger.info("Philly OPA: fetched %d rows", len(rows))

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
                logger.exception("Philly: error processing parcel %s", row.get("parcel_number"))
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
                        "$select": "parcel_number,location,zip_code,market_value,taxable_land,taxable_building,year_built,total_livable_area,owner_1,owner_2,number_of_bedrooms,number_of_bathrooms,category_code_description,mailing_address_1,mailing_address_2,mailing_care_of,mailing_city_state,mailing_zip",
                        "$where": "market_value > 300000",
                        "$order": "market_value DESC",
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
                logger.exception("Philly: page fetch failed at offset %d", offset)
                break
        return results[:limit]

    def _parse_row(self, row: dict) -> dict | None:
        apn = str(row.get("parcel_number") or "").strip()
        if not apn:
            return None

        address = str(row.get("location") or "").strip().title()
        if not address:
            return None

        zip_code = str(row.get("zip_code") or "").strip()[:10]
        assessed_total = to_decimal(row.get("market_value"))
        if not assessed_total or assessed_total <= Decimal("0"):
            return None

        use_desc = str(row.get("category_code_description") or "").upper()
        if any(k in use_desc for k in ("SINGLE", "CONDO", "RESID", "DWELLING", "ROW", "TWIN")):
            prop_type = "RESIDENTIAL"
        elif any(k in use_desc for k in ("COMMERCIAL", "OFFICE", "INDUSTRIAL", "STORE")):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        # Owner name — combine owner_1 + owner_2 if both present
        o1 = str(row.get("owner_1") or "").strip().title()
        o2 = str(row.get("owner_2") or "").strip().title()
        owner_name = f"{o1} & {o2}" if o1 and o2 else (o1 or o2 or None)

        # Mailing address — where tax bills are sent (useful for outreach)
        mail_line1 = str(row.get("mailing_address_1") or "").strip()
        mail_line2 = str(row.get("mailing_address_2") or "").strip()
        mail_care  = str(row.get("mailing_care_of") or "").strip()
        mail_city  = str(row.get("mailing_city_state") or "").strip()
        mail_zip   = str(row.get("mailing_zip") or "").strip()
        mailing_parts = [p for p in [mail_care, mail_line1, mail_line2, mail_city, mail_zip] if p]
        mailing_address = ", ".join(mailing_parts) if mailing_parts else None

        return {
            "apn": apn,
            "address": address,
            "city": "Philadelphia",
            "state": "PA",
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": to_int(row.get("total_livable_area")),
            "bedrooms": to_int(row.get("number_of_bedrooms")),
            "bathrooms": to_int(row.get("number_of_bathrooms")),
            "year_built": to_int(row.get("year_built")),
            "owner_name": owner_name,
            "owner_email": None,
            "owner_phone": None,
            "mailing_address": mailing_address,
            "assessed_total": assessed_total,
            "assessed_land": to_decimal(row.get("taxable_land")),
            "assessed_improvement": to_decimal(row.get("taxable_building")),
            "tax_year": 2024,
            "latitude": None,
            "longitude": None,
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
                state="PA",
                zip=raw_data.get("zip", ""),
                property_type=raw_data.get("property_type", "RESIDENTIAL"),
                building_sqft=raw_data.get("building_sqft"),
                year_built=raw_data.get("year_built"),
                bedrooms=raw_data.get("bedrooms"),
                bathrooms=raw_data.get("bathrooms"),
                owner_name=raw_data.get("owner_name"),
                owner_email=raw_data.get("owner_email"),
                owner_phone=raw_data.get("owner_phone"),
                mailing_address=raw_data.get("mailing_address"),
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
