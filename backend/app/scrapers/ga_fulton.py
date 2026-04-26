"""
Fulton County, GA — Assessor parcel data via Fulton County GIS ArcGIS service.

Endpoint: Fulton County open data FeatureServer.
Discovery: query by SITUS_ZIP → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class FultonCountyScraper(CACountyArcGISScraper):
    adapter_name = "fulton_ga"

    # Fulton County GIS parcel viewer layer
    _GIS_URL = (
        "https://gis.fultoncountyga.gov/arcgis/rest/services"
        "/FCGIS_ParcelViewer/ParcelViewer/MapServer/0/query"
    )
    _STATE = "GA"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":        "PARCEL_ID",
        "address":    "SITUS_ADDRESS",
        "city":       "SITUS_CITY",
        "zip":        "SITUS_ZIP",
        "use_desc":   "PROPERTY_CLASS",
        "bldg_sqft":  "TOTAL_SQFT",
        "land_sqft":  "LOT_SIZE_SQFT",
        "year_built":  "YEAR_BUILT",
        "net_av":     "ASSESSED_VALUE",
        "land_av":    "LAND_VALUE",
        "impr_av":    "IMPROVEMENT_VALUE",
        "owner":      "OWNER_NAME",
    }

    # Atlanta and surrounding Fulton County zip codes
    _ZIPS = [
        "30004", "30005", "30009", "30022", "30023",
        "30068", "30075", "30076", "30097", "30101",
        "30106", "30127", "30134", "30144", "30152",
        "30168", "30213", "30214", "30228", "30260",
        "30268", "30269", "30291", "30303", "30305",
        "30306", "30307", "30308", "30309", "30310",
        "30311", "30312", "30313", "30314", "30315",
        "30316", "30317", "30318", "30319", "30324",
        "30326", "30327", "30328", "30329", "30331",
        "30336", "30337", "30338", "30339", "30340",
        "30341", "30342", "30344", "30345", "30346",
        "30349", "30350", "30354", "30360", "30361",
        "30363", "30366",
    ]
