"""
San Diego County, CA — Assessor/Recorder/County Clerk (ARCC).

Uses the San Diego County ArcGIS feature service for parcel/assessment data.
Endpoint: https://services1.arcgis.com/ol22L6kJ3kn2uHKi/arcgis/rest/services/
          (San Diego County GIS — public, no API key required)

Discovery: query parcel feature service by zip code → collect APNs
Detail:    same query, outFields covers all assessment attributes
Rate limit: 1s between zip queries to respect ArcGIS rate limits.

Note: ArcGIS feature service URL and exact field names may shift with
      county GIS updates. See docs/county-adapters.md for current endpoint.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, geocode_address, to_decimal, to_int
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)

# San Diego County ArcGIS open-data feature service for assessor parcels.
# Org ID: ol22L6kJ3kn2uHKi  (San Diego County)
_GIS_URL = (
    "https://services1.arcgis.com/ol22L6kJ3kn2uHKi/arcgis/rest/services"
    "/SDCo_Parcels/FeatureServer/0/query"
)

# Core San Diego zip codes with highest property appeal potential
_SD_ZIPS = [
    "92101", "92102", "92103", "92104", "92105", "92106", "92107", "92108",
    "92109", "92110", "92111", "92113", "92114", "92115", "92116", "92117",
    "92119", "92120", "92121", "92122", "92123", "92124", "92126", "92127",
    "92128", "92129", "92130", "92131", "92132", "92134", "92135", "92136",
    "92139", "92140", "92145", "92147", "92149", "92150", "92152", "92154",
    "92173", "92182", "92037", "92038", "92039", "92067", "92075", "92091",
]

# ArcGIS field names for San Diego County parcel data
_FIELDS = ",".join([
    "APN", "SITUS_ADDR", "SITUS_CITY", "SITUS_ZIP",
    "PROP_USE_CODE", "PROP_USE_DESC", "BLDG_SQFT", "LAND_SQFT",
    "YEAR_BUILT", "NET_AV", "LAND_AV", "IMPR_AV",
    "OWNER_NAME", "OWNER_NAME2",
    "SHAPE",  # returns centroid geometry for lat/lng
])


class SanDiegoScraper(BaseCountyScraper):
    adapter_name = "san_diego_ca"

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        properties = self._discover_properties(limit)
        logger.info("San Diego: discovered %d properties", len(properties))

        for raw in properties:
            try:
                if not raw or not raw.get("apn"):
                    continue
                records_fetched += 1
                result = self.process_record(apn=raw["apn"], raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1
            except Exception:
                logger.exception("San Diego: error processing APN %s", raw.get("apn", "?"))
                errors += 1

        return {"records_fetched": records_fetched, "records_changed": records_changed, "errors": errors}

    def _discover_properties(self, limit: int) -> list[dict]:
        """Query ArcGIS feature service by zip code to get property data."""
        results: list[dict] = []
        per_zip = max(5, limit // len(_SD_ZIPS) + 1)

        for zip_code in _SD_ZIPS:
            if len(results) >= limit:
                break
            try:
                resp = self.fetch(
                    _GIS_URL,
                    params={
                        "where": f"SITUS_ZIP='{zip_code}'",
                        "outFields": _FIELDS,
                        "returnGeometry": "true",
                        "geometryPrecision": 6,
                        "outSR": "4326",  # WGS84 → lat/lng
                        "resultRecordCount": per_zip,
                        "f": "json",
                    },
                )
                data = resp.json()
                features = data.get("features") or []
                for feat in features:
                    parsed = self._parse_feature(feat)
                    if parsed and parsed.get("apn") and parsed not in results:
                        results.append(parsed)
                time.sleep(1.0)
            except Exception:
                logger.warning("San Diego: ArcGIS query failed for zip %s", zip_code)

        return results[:limit]

    def _parse_feature(self, feat: dict) -> dict | None:
        attrs = feat.get("attributes") or {}
        if not attrs:
            return None

        apn = str(attrs.get("APN") or "").strip()
        if not apn:
            return None

        address = str(attrs.get("SITUS_ADDR") or "").strip()
        city = str(attrs.get("SITUS_CITY") or "SAN DIEGO").strip().title()
        zip_code = str(attrs.get("SITUS_ZIP") or "").strip()[:10]

        use_desc = str(attrs.get("PROP_USE_DESC") or attrs.get("PROP_USE_CODE") or "").upper()
        if any(k in use_desc for k in ("SINGLE", "CONDO", "DUPLEX", "TRIPLEX", "RESIDENTIAL", "0100", "0110", "1100")):
            prop_type = "RESIDENTIAL"
        elif any(k in use_desc for k in ("COMMERCIAL", "OFFICE", "INDUSTRIAL", "RETAIL", "HOTEL")):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        assessed_total = to_decimal(attrs.get("NET_AV") or attrs.get("TOTAL_AV") or attrs.get("AV_TOTAL"))
        if not assessed_total or assessed_total <= 0:
            return None

        land_val = to_decimal(attrs.get("LAND_AV") or attrs.get("AV_LAND"))
        imprv_val = to_decimal(attrs.get("IMPR_AV") or attrs.get("AV_IMPR"))

        owner_parts = [
            str(attrs.get("OWNER_NAME") or "").strip(),
            str(attrs.get("OWNER_NAME2") or "").strip(),
        ]
        owner_name: str | None = " ".join(p for p in owner_parts if p).strip().title() or None

        # ArcGIS centroid geometry in WGS84 (outSR=4326)
        lat: float | None = None
        lng: float | None = None
        geom = feat.get("geometry")
        if geom:
            x = geom.get("x")
            y = geom.get("y")
            if x and y:
                lng = float(x)
                lat = float(y)

        if not lat and address and city:
            coords = geocode_address(address, city, "CA")
            if coords:
                lat, lng = coords
            time.sleep(1.1)

        return {
            "apn": apn,
            "address": address,
            "city": city,
            "state": "CA",
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": to_int(attrs.get("BLDG_SQFT")),
            "lot_size_sqft": to_int(attrs.get("LAND_SQFT")),
            "year_built": to_int(attrs.get("YEAR_BUILT")),
            "owner_name": owner_name,
            "assessed_total": assessed_total,
            "assessed_land": land_val,
            "assessed_improvement": imprv_val,
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
                state="CA",
                zip=raw_data.get("zip", ""),
                property_type=raw_data.get("property_type", "RESIDENTIAL"),
                building_sqft=raw_data.get("building_sqft"),
                lot_size_sqft=raw_data.get("lot_size_sqft"),
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
