"""
Orange County, CA — OC Assessor parcel data via ArcGIS open data.

Endpoint: Orange County ArcGIS public FeatureServer.
Discovery: query by SITUS_ZIP → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class OrangeCountyCAScraper(CACountyArcGISScraper):
    adapter_name = "orange_ca"

    # OC GIS open data parcel layer
    _GIS_URL = (
        "https://services.arcgis.com/UXmFoWC7yDHcDN5Q/arcgis/rest/services"
        "/OC_Parcel_Data/FeatureServer/0/query"
    )
    _STATE = "CA"
    _ZIP_FIELD = "SITUS_ZIP"

    # OC field names match the SD default map; minor overrides only
    _FIELD_MAP = {
        "apn":       "APN",
        "address":   "SITUS_ADDR",
        "city":      "SITUS_CITY",
        "zip":       "SITUS_ZIP",
        "use_desc":  "USE_DESC",
        "bldg_sqft": "BLDG_SQFT",
        "land_sqft": "LAND_SQFT",
        "year_built": "YEAR_BUILT",
        "net_av":    "NET_AV",
        "land_av":   "LAND_AV",
        "impr_av":   "IMPR_AV",
        "owner":     "OWNER_NAME",
    }

    # Orange County zip codes (Anaheim, Irvine, Santa Ana, Huntington Beach…)
    _ZIPS = [
        "92601", "92602", "92603", "92604", "92606",
        "92612", "92614", "92617", "92618", "92620",
        "92630", "92637", "92647", "92648", "92649",
        "92651", "92652", "92653", "92655", "92656",
        "92657", "92660", "92661", "92662", "92663",
        "92672", "92673", "92675", "92676", "92677",
        "92679", "92683", "92686", "92688", "92691",
        "92692", "92694", "92697", "92698", "92701",
        "92703", "92704", "92705", "92706", "92707",
        "92708", "92780", "92782", "92801", "92802",
        "92804", "92805", "92806", "92807", "92808",
        "92821", "92823", "92831", "92832", "92833",
        "92835", "92840", "92841", "92843", "92844",
        "92845", "92861", "92865", "92866", "92867",
        "92868", "92869", "92870", "92886", "92887",
    ]
