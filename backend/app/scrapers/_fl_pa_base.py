"""
Shared base for Florida Property Appraiser (PA) county scrapers.

Florida county property appraisers expose a common PApublicServiceProxy REST API.
Each county has its own endpoint URL but identical operation names.

Subclasses set:
    _API      — proxy endpoint URL
    _STREETS  — major street names used for discovery
    _CITY     — primary city name (used as fallback in street search)
"""
from __future__ import annotations

import logging
import random
import time

from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, geocode_address, to_decimal, to_int
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)

_APP = "PropertySearch"


class FLPropertyAppraiserScraper(BaseCountyScraper):
    """Abstract base — subclasses must set _API, _STREETS, _CITY, and adapter_name."""

    _API: str = ""
    _STREETS: list[str] = []
    _CITY: str = ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        folios = self._discover_folios(limit)
        logger.info("%s: discovered %d folio numbers", self.adapter_name, len(folios))

        for folio in folios:
            try:
                raw = self._fetch_property(folio)
                if not raw or not raw.get("apn"):
                    continue
                records_fetched += 1

                result = self.process_record(apn=raw["apn"], raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1

                time.sleep(0.5)
            except Exception:
                logger.exception(
                    "%s: error processing folio %s", self.adapter_name, folio
                )
                errors += 1

        return {
            "records_fetched": records_fetched,
            "records_changed": records_changed,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _discover_folios(self, limit: int) -> list[str]:
        """
        Search by street name to collect folio/strap numbers.
        GET ?Operation=GetPropertySearchByStreetName&stName=STREET&clientAppName=APP
        """
        folios: list[str] = []
        streets = random.sample(self._STREETS, len(self._STREETS))  # shuffle for variety each run
        per_street = max(3, limit // max(len(streets), 1) + 1)

        for street in streets:
            if len(folios) >= limit:
                break
            try:
                resp = self.fetch(
                    self._API,
                    params={
                        "Operation": "GetPropertySearchByStreetName",
                        "clientAppName": _APP,
                        "stName": street,
                        "stNum": "",
                        "suffix": "",
                        "city": self._CITY,
                    },
                )
                data = resp.json()
                items = (
                    data.get("MinimumPropertyInfos", {})
                        .get("MinimumPropertyInfo", [])
                )
                if isinstance(items, dict):
                    items = [items]
                for item in (items or [])[:per_street]:
                    folio = str(
                        item.get("Strap")
                        or item.get("Folio")
                        or item.get("FolioNumber")
                        or ""
                    ).strip()
                    if folio and folio not in folios:
                        folios.append(folio)
                time.sleep(0.5)
            except Exception:
                logger.warning(
                    "%s: street search failed for %s", self.adapter_name, street
                )

        return folios[:limit]

    # ------------------------------------------------------------------
    # Detail fetch
    # ------------------------------------------------------------------

    def _fetch_property(self, folio: str) -> dict | None:
        """
        GET ?Operation=GetPropertySearchByFolio&folioNumber=FOLIO&clientAppName=APP
        """
        try:
            resp = self.fetch(
                self._API,
                params={
                    "Operation": "GetPropertySearchByFolio",
                    "clientAppName": _APP,
                    "folioNumber": folio,
                },
            )
            return self._parse_detail(folio, resp.json())
        except Exception:
            logger.exception(
                "%s: detail fetch failed for folio %s", self.adapter_name, folio
            )
            return None

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_detail(self, folio: str, data: dict) -> dict | None:
        if not data:
            return None

        container = (
            data.get("MinimumPropertyInfos", {}).get("MinimumPropertyInfo", {})
        )
        if isinstance(container, list):
            info = container[0] if container else {}
        else:
            info = container or {}
        if not info:
            return None

        address = str(info.get("SiteAddress", "") or "").strip()
        city = str(info.get("SiteCity", self._CITY) or self._CITY).strip().title()
        zip_code = str(info.get("SiteZip", "") or "").strip()[:10]

        dor = str(info.get("DORDescription", "") or "").upper()
        if any(
            k in dor
            for k in (
                "SINGLE", "CONDO", "DUPLEX", "TRIPLEX", "QUAD",
                "MULTI", "RESIDENTIAL", "VACANT RESID",
            )
        ):
            prop_type = "RESIDENTIAL"
        elif any(
            k in dor
            for k in (
                "COMMERCIAL", "OFFICE", "RETAIL", "INDUSTRIAL",
                "WAREHOUSE", "HOTEL",
            )
        ):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        assessed_total = to_decimal(
            info.get("AssessedValue")
            or info.get("TotalValue")
            or info.get("JustValue")
            or info.get("MarketValue")
        )
        if not assessed_total or assessed_total <= 0:
            return None

        land_val = to_decimal(
            info.get("LandValue")
            or info.get("LandAssessedValue")
            or info.get("LandAV")
        )
        imprv_val = to_decimal(
            info.get("BuildingValue")
            or info.get("ImprovementValue")
            or info.get("ImprAV")
        )

        owner_first = str(info.get("Owner1FirstName", "") or "").strip()
        owner_last = str(info.get("Owner1LastName", "") or "").strip()
        owner_name: str | None = None
        if owner_first or owner_last:
            owner_name = f"{owner_first} {owner_last}".strip().title()
        if not owner_name:
            owner_name = (
                str(info.get("OwnerName1", "") or info.get("OwnerName", "") or "")
                .strip()
                .title()
            ) or None

        lat = info.get("Latitude") or info.get("lat")
        lng = info.get("Longitude") or info.get("lng")
        if not lat and address and city:
            coords = geocode_address(address, city, "FL")
            if coords:
                lat, lng = coords
            time.sleep(1.1)

        return {
            "apn": folio,
            "address": address,
            "city": city,
            "state": "FL",
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": to_int(
                info.get("LivingSquareFeet")
                or info.get("SqFt")
                or info.get("BuildingSqFt")
            ),
            "year_built": to_int(
                info.get("YearBuilt") or info.get("ActualYearBuilt")
            ),
            "owner_name": owner_name,
            "assessed_total": assessed_total,
            "assessed_land": land_val,
            "assessed_improvement": imprv_val,
            "tax_year": int(info.get("TaxYear") or info.get("Year") or 2024),
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
                state="FL",
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
