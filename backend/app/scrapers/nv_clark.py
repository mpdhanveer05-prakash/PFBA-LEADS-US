"""
Clark County, NV — Assessor parcel data via Clark County GIS ArcGIS service.

Endpoint: Clark County open data FeatureServer.
Discovery: query by SITUS_ZIP → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class ClarkCountyScraper(CACountyArcGISScraper):
    adapter_name = "clark_nv"

    # Clark County GIS parcel layer
    _GIS_URL = (
        "https://gisgate.clarkcountynv.gov/gisgate/rest/services"
        "/Public/Parcels/MapServer/0/query"
    )
    _STATE = "NV"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":        "APN",
        "address":    "SITUS_ADDR",
        "city":       "SITUS_CITY",
        "zip":        "SITUS_ZIP",
        "use_desc":   "PROPERTY_USE_CODE",
        "bldg_sqft":  "BLDG_SQFT",
        "land_sqft":  "LAND_SQFT",
        "year_built":  "YEAR_BUILT",
        "net_av":     "ASSESSED_VALUE",
        "land_av":    "LAND_VALUE",
        "impr_av":    "IMPR_VALUE",
        "owner":      "OWNER_NAME",
    }

    # Las Vegas, Henderson, North Las Vegas, Summerlin, Spring Valley…
    _ZIPS = [
        "89002", "89004", "89005", "89011", "89012",
        "89014", "89015", "89031", "89032", "89044",
        "89048", "89052", "89053", "89074", "89077",
        "89081", "89084", "89085", "89086", "89101",
        "89102", "89103", "89104", "89106", "89107",
        "89108", "89109", "89110", "89113", "89115",
        "89117", "89118", "89119", "89120", "89121",
        "89122", "89123", "89124", "89128", "89129",
        "89130", "89131", "89134", "89135", "89138",
        "89139", "89141", "89142", "89143", "89144",
        "89145", "89146", "89147", "89148", "89149",
        "89156", "89166", "89169", "89178", "89179",
        "89183", "89191",
    ]
