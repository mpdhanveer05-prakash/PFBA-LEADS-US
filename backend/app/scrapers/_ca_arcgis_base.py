"""
Shared base for California county ArcGIS assessor scrapers.

California counties publish parcel and assessment data through Esri ArcGIS
feature services. Each county has its own service URL and slightly different
field names, which are resolved via the _FIELD_MAP class attribute.

Subclasses set:
    _GIS_URL   — ArcGIS FeatureServer query endpoint
    _ZIPS      — zip codes to iterate over
    _STATE     — defaults to "CA"
    _FIELD_MAP — maps canonical names → county-specific ArcGIS field names
    _ZIP_FIELD — the ArcGIS field used in the WHERE clause (default: SITUS_ZIP)
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

# Default canonical-to-ArcGIS field mapping (San Diego / common convention).
_DEFAULT_FIELD_MAP: dict[str, str] = {
    "apn":       "APN",
    "address":   "SITUS_ADDR",
    "city":      "SITUS_CITY",
    "zip":       "SITUS_ZIP",
    "use_desc":  "PROP_USE_DESC",
    "bldg_sqft": "BLDG_SQFT",
    "land_sqft": "LAND_SQFT",
    "year_built":"YEAR_BUILT",
    "net_av":    "NET_AV",
    "land_av":   "LAND_AV",
    "impr_av":   "IMPR_AV",
    "owner":     "OWNER_NAME",
}


class CACountyArcGISScraper(BaseCountyScraper):
    """Abstract base — subclasses must set _GIS_URL, _ZIPS, and adapter_name."""

    _GIS_URL: str = ""
    _ZIPS: list[str] = []
    _STATE: str = "CA"
    _FIELD_MAP: dict[str, str] = {}          # merged with _DEFAULT_FIELD_MAP at runtime
    _ZIP_FIELD: str = "SITUS_ZIP"            # field used in WHERE clause

    # ------------------------------------------------------------------
    # Resolved field map (lazy, per-class singleton)
    # ------------------------------------------------------------------

    @classmethod
    def _fmap(cls) -> dict[str, str]:
        merged = dict(_DEFAULT_FIELD_MAP)
        merged.update(cls._FIELD_MAP)
        return merged

    @classmethod
    def _outfields(cls) -> str:
        return ",".join(set(cls._fmap().values()))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        properties = self._discover_properties(limit)
        logger.info("%s: discovered %d properties", self.adapter_name, len(properties))

        for raw in properties:
            try:
                if not raw or not raw.get("apn"):
                    continue
                records_fetched += 1
                result = self.process_record(apn=raw["apn"], raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1
            except Exception:
                logger.exception(
                    "%s: error processing APN %s",
                    self.adapter_name,
                    raw.get("apn", "?"),
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

    def _discover_properties(self, limit: int) -> list[dict]:
        results: list[dict] = []
        zips = random.sample(self._ZIPS, len(self._ZIPS))  # shuffle for variety each run
        per_zip = max(5, limit // max(len(zips), 1) + 1)
        zip_field = self.__class__._fmap().get("zip", self._ZIP_FIELD)

        for zip_code in zips:
            if len(results) >= limit:
                break
            try:
                resp = self.fetch(
                    self._GIS_URL,
                    params={
                        "where": f"{zip_field}='{zip_code}'",
                        "outFields": self._outfields(),
                        "returnGeometry": "true",
                        "geometryPrecision": 6,
                        "outSR": "4326",
                        "resultRecordCount": per_zip,
                        "resultOffset": random.randint(0, 50),
                        "f": "json",
                    },
                )
                data = resp.json()
                features = data.get("features") or []
                for feat in features:
                    parsed = self._parse_feature(feat)
                    if parsed and parsed.get("apn"):
                        results.append(parsed)
                time.sleep(1.0)
            except Exception:
                logger.warning(
                    "%s: ArcGIS query failed for zip %s", self.adapter_name, zip_code
                )

        return results[:limit]

    # ------------------------------------------------------------------
    # Feature parsing
    # ------------------------------------------------------------------

    def _parse_feature(self, feat: dict) -> dict | None:
        attrs = feat.get("attributes") or {}
        if not attrs:
            return None

        fm = self.__class__._fmap()

        apn = str(attrs.get(fm["apn"]) or "").strip()
        if not apn:
            return None

        address = str(attrs.get(fm["address"]) or "").strip()
        city = str(attrs.get(fm["city"]) or "").strip().title()
        zip_code = str(attrs.get(fm["zip"]) or "").strip()[:10]

        use_desc = str(attrs.get(fm["use_desc"]) or "").upper()
        if any(
            k in use_desc
            for k in (
                "SINGLE", "CONDO", "DUPLEX", "TRIPLEX",
                "RESIDENTIAL", "0100", "0110", "1100",
            )
        ):
            prop_type = "RESIDENTIAL"
        elif any(
            k in use_desc
            for k in (
                "COMMERCIAL", "OFFICE", "INDUSTRIAL", "RETAIL", "HOTEL",
            )
        ):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        assessed_total = to_decimal(attrs.get(fm["net_av"]))
        if not assessed_total or assessed_total <= 0:
            return None

        land_val = to_decimal(attrs.get(fm["land_av"]))
        imprv_val = to_decimal(attrs.get(fm["impr_av"]))

        owner_name: str | None = (
            str(attrs.get(fm["owner"]) or "").strip().title() or None
        )

        # Geometry from ArcGIS (x=lng, y=lat in WGS84)
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
            coords = geocode_address(address, city, self._STATE)
            if coords:
                lat, lng = coords
            time.sleep(1.1)

        return {
            "apn": apn,
            "address": address,
            "city": city,
            "state": self._STATE,
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": to_int(attrs.get(fm["bldg_sqft"])),
            "lot_size_sqft": to_int(attrs.get(fm["land_sqft"])),
            "year_built": to_int(attrs.get(fm["year_built"])),
            "owner_name": owner_name,
            "assessed_total": assessed_total,
            "assessed_land": land_val,
            "assessed_improvement": imprv_val,
            "tax_year": 2024,
            "latitude": lat,
            "longitude": lng,
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
                lot_size_sqft=raw_data.get("lot_size_sqft"),
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
