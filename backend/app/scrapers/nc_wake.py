"""
Wake County, NC — Assessor parcel data via Wake County GIS ArcGIS service.

Endpoint: Wake County ArcGIS open data FeatureServer (no API key required).
Discovery: query by SITUS_ZIP → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class WakeCountyScraper(CACountyArcGISScraper):
    adapter_name = "wake_nc"

    # Wake County GIS parcel layer (hosted on ArcGIS Online)
    _GIS_URL = (
        "https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services"
        "/Wake_County_Parcels/FeatureServer/0/query"
    )
    _STATE = "NC"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":        "REID",
        "address":    "ADDR1",
        "city":       "CITY",
        "zip":        "SITUS_ZIP",
        "use_desc":   "LAND_CLASS",
        "bldg_sqft":  "CALC_AREA",
        "land_sqft":  "TOTALSQFT",
        "year_built":  "YEAR_BUILT",
        "net_av":     "TOTAL_VALUE_ASSD",
        "land_av":    "LAND_VALUE",
        "impr_av":    "BLDG_VALUE",
        "owner":      "OWNER",
    }

    # Raleigh, Cary, Apex, Morrisville, Durham (Wake portion), Wake Forest…
    _ZIPS = [
        "27502", "27503", "27511", "27512", "27513",
        "27518", "27519", "27523", "27524", "27526",
        "27529", "27539", "27540", "27545", "27560",
        "27562", "27571", "27587", "27591", "27592",
        "27593", "27596", "27597", "27601", "27603",
        "27604", "27605", "27606", "27607", "27608",
        "27609", "27610", "27612", "27613", "27614",
        "27615", "27616", "27617", "27587", "27597",
        "27628", "27629", "27695",
    ]
