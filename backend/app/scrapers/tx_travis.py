"""
Travis County, TX — Travis Central Appraisal District (TCAD).

Uses the PropAccess iSite API at propaccess.traviscad.org.
Reference: https://www.traviscad.org/property-search/

Discovery strategy: search by Austin zip codes → collect prop_ids → fetch detail.
Rate limit: 0.5s between requests to stay under TCAD's threshold.
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, geocode_address, to_decimal, to_int
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)

_API = "https://propaccess.traviscad.org/clientdb"
_CID = 1  # Travis County client ID in PropAccess

# Core Austin zip codes — highest appeal potential
_TRAVIS_ZIPS = [
    "78701", "78702", "78703", "78704", "78705",
    "78721", "78722", "78723", "78724", "78725",
    "78726", "78727", "78728", "78729", "78730",
    "78731", "78732", "78733", "78734", "78735",
    "78736", "78737", "78738", "78739",
    "78741", "78742", "78744", "78745", "78746",
    "78747", "78748", "78749", "78750", "78751",
    "78752", "78753", "78754", "78756", "78757",
    "78758", "78759",
]


class TravisCountyScraper(BaseCountyScraper):
    adapter_name = "travis_tx"

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        prop_ids = self._discover_prop_ids(limit)
        logger.info("Travis CAD: discovered %d property IDs", len(prop_ids))

        for prop_id in prop_ids:
            try:
                raw = self._fetch_property_detail(prop_id)
                if not raw or not raw.get("apn"):
                    continue
                records_fetched += 1

                result = self.process_record(apn=raw["apn"], raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1

                time.sleep(0.5)
            except Exception:
                logger.exception("Travis: error processing prop_id %s", prop_id)
                errors += 1

        return {"records_fetched": records_fetched, "records_changed": records_changed, "errors": errors}

    def _discover_prop_ids(self, limit: int) -> list[str]:
        """
        Search TCAD PropAccess by zip code to build a list of prop_ids.
        PropAccess search endpoint: GET /Property/search?searchtype=a&searchValue=ZIP&cid=1
        """
        prop_ids: list[str] = []
        per_zip = max(5, limit // len(_TRAVIS_ZIPS) + 1)

        for zip_code in _TRAVIS_ZIPS:
            if len(prop_ids) >= limit:
                break
            try:
                resp = self.fetch(
                    f"{_API}/Property/search",
                    params={"searchtype": "a", "searchValue": zip_code, "cid": _CID},
                )
                data = resp.json()
                prop_list = data.get("prop_list") or data.get("result") or []
                for item in prop_list[:per_zip]:
                    pid = (
                        item.get("prop_id")
                        or item.get("prop_id_num")
                        or str(item.get("id", ""))
                    )
                    if pid and str(pid) not in prop_ids:
                        prop_ids.append(str(pid))
                time.sleep(1.0)
            except Exception:
                logger.warning("Travis: zip search failed for %s", zip_code)

        return prop_ids[:limit]

    def _fetch_property_detail(self, prop_id: str) -> dict | None:
        """
        Fetch full property detail from PropAccess.
        GET /Property/details?prop_id=PROP_ID
        """
        try:
            resp = self.fetch(
                f"{_API}/Property/details",
                params={"prop_id": prop_id},
            )
            return self._parse_detail(resp.json())
        except Exception:
            logger.exception("Travis: detail fetch failed for prop_id %s", prop_id)
            return None

    def _parse_detail(self, data: dict) -> dict | None:
        if not data:
            return None

        # Geo ID is the APN in Travis CAD
        geo_id = (
            data.get("geo_id")
            or data.get("prop_id_num")
            or str(data.get("prop_id", ""))
        )
        if not geo_id:
            return None

        # Build situs address from components
        parts = [
            str(data.get("situs_num", "") or ""),
            str(data.get("situs_street_pfx_cd", "") or ""),
            str(data.get("situs_street_name", "") or ""),
            str(data.get("situs_street_type_cd", "") or ""),
            str(data.get("situs_sfx_cd", "") or ""),
        ]
        address = " ".join(p for p in parts if p.strip())
        city = str(data.get("situs_city", "AUSTIN") or "AUSTIN").strip().title()
        zip_code = str(data.get("zip_cd", "") or "").strip()[:10]

        # Normalise property type
        raw_type = str(data.get("prop_type_cd", "R") or "R").upper()
        if raw_type in ("R", "A", "MH"):
            prop_type = "RESIDENTIAL"
        elif raw_type in ("B", "C", "F", "X"):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        living_area = (
            data.get("living_area")
            or data.get("imprv_living_area")
            or data.get("bldg_sqft")
        )
        building_sqft = to_int(living_area)
        year_built = to_int(data.get("yr_impr") or data.get("effective_yr_built"))

        # Valuation — PropAccess stores land and improvement separately
        appraised_val = to_decimal(
            data.get("appraised_val")
            or data.get("tot_appr_val")
            or data.get("market_value")
        )
        land_val = to_decimal(
            data.get("land_hstd_val")
            or data.get("land_non_hstd_val")
            or data.get("land_val")
        )
        imprv_val = to_decimal(
            data.get("imprv_hstd_val")
            or data.get("imprv_non_hstd_val")
            or data.get("imprv_val")
        )

        if not appraised_val or appraised_val <= 0:
            return None

        owner_name = str(
            data.get("owner_name") or data.get("owner_name1") or ""
        ).strip().title()

        # Lat/lng — PropAccess may provide x_coord/y_coord in state plane;
        # fall back to Nominatim if missing
        lat = data.get("lat") or data.get("latitude")
        lng = data.get("lng") or data.get("longitude")
        if not lat and address and city:
            coords = geocode_address(address, city, "TX")
            if coords:
                lat, lng = coords
            time.sleep(1.1)  # Nominatim 1 req/sec policy

        return {
            "apn": geo_id,
            "address": address,
            "city": city,
            "state": "TX",
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": building_sqft,
            "year_built": year_built,
            "owner_name": owner_name or None,
            "assessed_total": appraised_val,
            "assessed_land": land_val,
            "assessed_improvement": imprv_val,
            "tax_year": int(data.get("tax_year") or 2024),
            "latitude": float(lat) if lat else None,
            "longitude": float(lng) if lng else None,
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
                state="TX",
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
