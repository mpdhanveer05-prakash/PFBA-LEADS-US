"""
Maricopa County, AZ — Assessor parcel data via Maricopa County ArcGIS service.

Endpoint: Maricopa County GIS open data FeatureServer.
Discovery: query by ZIP field → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class MaricopaCountyScraper(CACountyArcGISScraper):
    adapter_name = "maricopa_az"

    # Maricopa County GIS parcels open data layer
    _GIS_URL = (
        "https://services.arcgis.com/ELGBwCEYgbFCeQkl/arcgis/rest/services"
        "/Maricopa_County_Parcels/FeatureServer/0/query"
    )
    _STATE = "AZ"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":        "APN",
        "address":    "SITUS_ADDR",
        "city":       "SITUS_CITY",
        "zip":        "SITUS_ZIP",
        "use_desc":   "USE_CODE_DESC",
        "bldg_sqft":  "BLDG_SQFT",
        "land_sqft":  "LAND_SQFT",
        "year_built":  "YEAR_BUILT",
        "net_av":     "FULL_CASH_VALUE",
        "land_av":    "LAND_VALUE",
        "impr_av":    "IMPR_VALUE",
        "owner":      "OWNER_NAME",
    }

    # Phoenix, Scottsdale, Tempe, Mesa, Chandler, Gilbert, Glendale, Peoria…
    _ZIPS = [
        "85001", "85002", "85003", "85004", "85006",
        "85007", "85008", "85009", "85013", "85014",
        "85015", "85016", "85017", "85018", "85019",
        "85020", "85021", "85022", "85023", "85024",
        "85027", "85028", "85029", "85031", "85032",
        "85033", "85034", "85035", "85037", "85040",
        "85041", "85042", "85043", "85044", "85045",
        "85048", "85050", "85051", "85053", "85054",
        "85085", "85086", "85201", "85202", "85203",
        "85204", "85205", "85206", "85207", "85208",
        "85209", "85210", "85212", "85213", "85215",
        "85224", "85225", "85226", "85233", "85234",
        "85248", "85249", "85250", "85251", "85253",
        "85254", "85255", "85257", "85258", "85259",
        "85260", "85262", "85266", "85268", "85281",
        "85282", "85283", "85284", "85296", "85297",
        "85301", "85302", "85303", "85304", "85306",
        "85308", "85310", "85338", "85339", "85340",
        "85345", "85351", "85353", "85354", "85355",
        "85381", "85382", "85383", "85392", "85395",
    ]
