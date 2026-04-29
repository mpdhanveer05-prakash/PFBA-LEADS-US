"""
Shared base for all Texas PropAccess county scrapers.

PropAccess iSite is a white-label CAD portal used by multiple Texas counties.
Each county has its own subdomain but the same API structure.

Subclasses set:
    _API   — base URL e.g. https://propaccess.tad.org/clientdb
    _ZIPS  — list of zip codes to search
    _STATE — defaults to "TX"
    _CID   — optional integer client-ID appended to every request
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


class PropAccessScraper(BaseCountyScraper):
    """Abstract base — subclasses must set _API and _ZIPS (and adapter_name)."""

    _API: str = ""
    _ZIPS: list[str] = []
    _STATE: str = "TX"
    _CID: int | None = None
    # Many Texas CAD PropAccess portals use self-signed or mismatched certs
    _VERIFY_SSL: bool = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        prop_ids = self._discover_prop_ids(limit)
        logger.info("%s: discovered %d property IDs", self.adapter_name, len(prop_ids))

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
                logger.exception("%s: error processing prop_id %s", self.adapter_name, prop_id)
                errors += 1

        return {
            "records_fetched": records_fetched,
            "records_changed": records_changed,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _discover_prop_ids(self, limit: int) -> list[str]:
        """
        Search PropAccess by zip code to collect prop_ids.
        GET {_API}/Property/search?searchtype=a&searchValue=ZIP[&cid=_CID]
        """
        prop_ids: list[str] = []
        zips = random.sample(self._ZIPS, len(self._ZIPS))  # shuffle for variety each run
        per_zip = max(5, limit // max(len(zips), 1) + 1)

        for zip_code in zips:
            if len(prop_ids) >= limit:
                break
            try:
                params: dict = {"searchtype": "a", "searchValue": zip_code}
                if self._CID is not None:
                    params["cid"] = self._CID

                resp = self.fetch(
                    f"{self._API}/Property/search",
                    params=params,
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
                logger.warning("%s: zip search failed for %s", self.adapter_name, zip_code)

        return prop_ids[:limit]

    # ------------------------------------------------------------------
    # Detail fetch
    # ------------------------------------------------------------------

    def _fetch_property_detail(self, prop_id: str) -> dict | None:
        """
        GET {_API}/Property/details?prop_id=PROP_ID[&cid=_CID]
        """
        try:
            params: dict = {"prop_id": prop_id}
            if self._CID is not None:
                params["cid"] = self._CID

            resp = self.fetch(
                f"{self._API}/Property/details",
                params=params,
            )
            return self._parse_detail(resp.json())
        except Exception:
            logger.exception(
                "%s: detail fetch failed for prop_id %s", self.adapter_name, prop_id
            )
            return None

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_detail(self, data: dict) -> dict | None:
        if not data:
            return None

        geo_id = (
            data.get("geo_id")
            or data.get("prop_id_num")
            or str(data.get("prop_id", ""))
        )
        if not geo_id:
            return None

        parts = [
            str(data.get("situs_num", "") or ""),
            str(data.get("situs_street_pfx_cd", "") or ""),
            str(data.get("situs_street_name", "") or ""),
            str(data.get("situs_street_type_cd", "") or ""),
            str(data.get("situs_sfx_cd", "") or ""),
        ]
        address = " ".join(p for p in parts if p.strip())
        city = str(data.get("situs_city", "") or "").strip().title()
        zip_code = str(data.get("zip_cd", "") or "").strip()[:10]

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

        if not appraised_val or appraised_val <= Decimal("0"):
            return None

        owner_name = (
            str(data.get("owner_name") or data.get("owner_name1") or "")
            .strip()
            .title()
        )

        lat = data.get("lat") or data.get("latitude")
        lng = data.get("lng") or data.get("longitude")
        if not lat and address and city:
            coords = geocode_address(address, city, self._STATE)
            if coords:
                lat, lng = coords
            time.sleep(1.1)

        return {
            "apn": geo_id,
            "address": address,
            "city": city,
            "state": self._STATE,
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

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

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
