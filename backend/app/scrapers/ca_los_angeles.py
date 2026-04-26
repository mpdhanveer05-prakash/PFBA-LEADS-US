"""
Los Angeles County, CA — LA County Assessor parcel data via ArcGIS open data.

Endpoint: LA County GeoHub public FeatureServer (no API key required).
Discovery: query by zip code → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class LosAngelesCountyScraper(CACountyArcGISScraper):
    adapter_name = "los_angeles_ca"

    # LA County Assessor parcels — ArcGIS Online public layer (AGOL org: i2dkYWmb4wHvYPda)
    _GIS_URL = (
        "https://services3.arcgis.com/i2dkYWmb4wHvYPda/arcgis/rest/services"
        "/Assessor_Parcels_Data_2024/FeatureServer/0/query"
    )
    _STATE = "CA"
    _ZIP_FIELD = "SitusZip"

    # LA County field names differ from the SD defaults
    _FIELD_MAP = {
        "apn":       "APN",
        "address":   "SitusAddress",
        "city":      "SitusCity",
        "zip":       "SitusZip",
        "use_desc":  "UseCode",
        "bldg_sqft": "SQFTmain",
        "land_sqft": "SQFTlot",
        "year_built": "YearBuilt",
        "net_av":    "TotalNetValue",
        "land_av":   "LandValue",
        "impr_av":   "ImprovementValue",
        "owner":     "OwnerName",
    }

    # Central / high-value LA zip codes
    _ZIPS = [
        "90001", "90002", "90003", "90004", "90005",
        "90007", "90010", "90012", "90013", "90014",
        "90015", "90017", "90019", "90020", "90024",
        "90025", "90026", "90027", "90028", "90029",
        "90031", "90033", "90034", "90035", "90036",
        "90038", "90039", "90041", "90042", "90043",
        "90044", "90045", "90046", "90047", "90048",
        "90049", "90056", "90057", "90058", "90059",
        "90062", "90063", "90064", "90065", "90066",
        "90067", "90068", "90069", "90071", "90073",
        "90077", "90210", "90211", "90212", "90230",
        "90232", "90245", "90247", "90248", "90249",
        "90254", "90260", "90262", "90265", "90272",
        "90275", "90277", "90278", "90290", "90291",
        "90292", "90293", "90302", "90304", "90305",
        "91001", "91006", "91007", "91010", "91011",
        "91016", "91020", "91024", "91030", "91040",
        "91042", "91101", "91103", "91104", "91105",
        "91106", "91107", "91108", "91202", "91205",
        "91206", "91207", "91208", "91214",
    ]
