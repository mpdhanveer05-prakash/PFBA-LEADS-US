"""
Mecklenburg County, NC — Assessor parcel data via Mecklenburg County GIS (POLARIS).

Endpoint: Mecklenburg County ArcGIS FeatureServer (public, no key required).
Discovery: query by SITUS_ZIP → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class MecklenburgCountyScraper(CACountyArcGISScraper):
    adapter_name = "mecklenburg_nc"

    # Mecklenburg County GIS parcel data layer
    _GIS_URL = (
        "https://gis.mecklenburgcountync.gov/arcgis/rest/services"
        "/Parcels/Parcels/MapServer/0/query"
    )
    _STATE = "NC"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":        "PARCEL_ID",
        "address":    "SITUS_ADDRESS",
        "city":       "SITUS_CITY",
        "zip":        "SITUS_ZIP",
        "use_desc":   "LAND_USE_CODE",
        "bldg_sqft":  "HEATED_AREA",
        "land_sqft":  "PARCEL_AREA",
        "year_built":  "YEAR_BUILT",
        "net_av":     "TOTAL_APPRAISAL",
        "land_av":    "LAND_APPRAISAL",
        "impr_av":    "BUILDING_APPRAISAL",
        "owner":      "OWNER_NAME",
    }

    # Charlotte and Mecklenburg County zip codes
    _ZIPS = [
        "28025", "28026", "28027", "28031", "28032",
        "28034", "28036", "28056", "28078", "28105",
        "28106", "28107", "28110", "28112", "28117",
        "28120", "28126", "28134", "28173", "28202",
        "28203", "28204", "28205", "28206", "28207",
        "28208", "28209", "28210", "28211", "28212",
        "28213", "28214", "28215", "28216", "28217",
        "28218", "28219", "28220", "28221", "28222",
        "28223", "28224", "28226", "28227", "28228",
        "28229", "28230", "28231", "28232", "28233",
        "28234", "28241", "28242", "28243", "28244",
        "28246", "28247", "28253", "28254", "28255",
        "28256", "28258", "28260", "28262", "28263",
        "28265", "28266", "28269", "28270", "28271",
        "28272", "28273", "28274", "28275", "28277",
        "28278", "28280", "28281", "28282", "28284",
        "28285", "28287", "28288", "28289", "28290",
    ]
