"""
Riverside County, CA — Assessor parcel data via ArcGIS open data.

Endpoint: Riverside County GIS public FeatureServer.
Discovery: query by SITUS_ZIP → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class RiversideCountyScraper(CACountyArcGISScraper):
    adapter_name = "riverside_ca"

    # Riverside County GIS parcel layer
    _GIS_URL = (
        "https://services1.arcgis.com/pMLgiVkue0FcJlpO/arcgis/rest/services"
        "/Riverside_County_Parcels/FeatureServer/0/query"
    )
    _STATE = "CA"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":       "APN",
        "address":   "SITUS_ADDR",
        "city":      "SITUS_CITY",
        "zip":       "SITUS_ZIP",
        "use_desc":  "USE_TYPE",
        "bldg_sqft": "BLDG_SQFT",
        "land_sqft": "LAND_SQFT",
        "year_built": "YEAR_BUILT",
        "net_av":    "NET_AV",
        "land_av":   "LAND_AV",
        "impr_av":   "IMPR_AV",
        "owner":     "OWNER_NAME",
    }

    # Riverside, Corona, Moreno Valley, Temecula, Murrieta, Palm Springs…
    _ZIPS = [
        "92501", "92503", "92504", "92505", "92506",
        "92507", "92508", "92509", "92513", "92518",
        "92530", "92532", "92544", "92545", "92548",
        "92551", "92553", "92555", "92557", "92562",
        "92563", "92570", "92571", "92582", "92583",
        "92584", "92585", "92586", "92587", "92590",
        "92591", "92592", "92595", "92596", "92860",
        "92877", "92879", "92880", "92881", "92882",
        "92883", "92223", "92230", "92234", "92236",
        "92240", "92241", "92260", "92262", "92264",
        "92270", "92274", "92276", "92277", "92278",
    ]
