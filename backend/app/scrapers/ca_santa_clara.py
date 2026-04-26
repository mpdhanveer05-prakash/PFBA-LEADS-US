"""
Santa Clara County, CA — Assessor parcel data via SCC GIS ArcGIS service.

Endpoint: Santa Clara County GIS open FeatureServer.
Discovery: query by SITUS_ZIP → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class SantaClaraCountyScraper(CACountyArcGISScraper):
    adapter_name = "santa_clara_ca"

    # Santa Clara County GIS assessor parcel layer
    _GIS_URL = (
        "https://gis.sccgov.org/arcgis/rest/services/Assessor"
        "/AssessorParcelData/MapServer/0/query"
    )
    _STATE = "CA"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":       "APN",
        "address":   "SITUS_ADDR",
        "city":      "SITUS_CITY",
        "zip":       "SITUS_ZIP",
        "use_desc":  "USE_CODE_DESC",
        "bldg_sqft": "BLDG_AREA",
        "land_sqft": "LAND_AREA",
        "year_built": "YR_BILT",
        "net_av":    "NET_AV",
        "land_av":   "LAND_AV",
        "impr_av":   "IMPR_AV",
        "owner":     "OWNER_NAME",
    }

    # San Jose, Sunnyvale, Santa Clara, Cupertino, Mountain View, Palo Alto…
    _ZIPS = [
        "95002", "95008", "95010", "95013", "95014",
        "95020", "95023", "95030", "95032", "95033",
        "95035", "95037", "95038", "95046", "95050",
        "95051", "95054", "95070", "95101", "95103",
        "95106", "95108", "95110", "95111", "95112",
        "95113", "95116", "95117", "95118", "95119",
        "95120", "95121", "95122", "95123", "95124",
        "95125", "95126", "95127", "95128", "95129",
        "95130", "95131", "95132", "95133", "95134",
        "95135", "95136", "95138", "95139", "95140",
        "95141", "95148", "94022", "94024", "94025",
        "94026", "94027", "94028", "94040", "94041",
        "94043", "94301", "94303", "94304", "94305",
        "94306", "94085", "94086", "94087", "94088",
        "94089",
    ]
