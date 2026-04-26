"""
King County, WA — Assessor parcel data via King County ArcGIS service.

Endpoint: King County GIS public FeatureServer (no API key required).
Discovery: query by ZIP5 field → returns parcel geometry + assessor attributes.
"""
from __future__ import annotations

from app.scrapers._ca_arcgis_base import CACountyArcGISScraper


class KingCountyScraper(CACountyArcGISScraper):
    adapter_name = "king_wa"

    # King County GIS assessor parcel layer (AGOL hosted)
    _GIS_URL = (
        "https://services.arcgis.com/wlVTGRSYTzAbjjiC/arcgis/rest/services"
        "/Assessor_Parcel_Detail/FeatureServer/0/query"
    )
    _STATE = "WA"
    _ZIP_FIELD = "SITUS_ZIP"

    _FIELD_MAP = {
        "apn":        "PIN",
        "address":    "SITUS_ADDR",
        "city":       "SITUS_CITY",
        "zip":        "SITUS_ZIP",
        "use_desc":   "PRESENT_USE_DESC",
        "bldg_sqft":  "SQ_FT_LOT",
        "land_sqft":  "SQ_FT_LOT",
        "year_built":  "YR_BUILT",
        "net_av":     "APPRAISED_VALUE",
        "land_av":    "LAND_VALUE",
        "impr_av":    "IMPS_VALUE",
        "owner":      "TAXPAYER_NAME",
    }

    # Seattle, Bellevue, Redmond, Kirkland, Renton, Kent, Federal Way…
    _ZIPS = [
        "98001", "98002", "98003", "98004", "98005",
        "98006", "98007", "98008", "98010", "98011",
        "98014", "98019", "98022", "98023", "98024",
        "98025", "98027", "98028", "98029", "98030",
        "98031", "98032", "98033", "98034", "98038",
        "98039", "98040", "98042", "98045", "98047",
        "98050", "98051", "98052", "98053", "98055",
        "98056", "98057", "98058", "98059", "98065",
        "98072", "98074", "98075", "98077", "98092",
        "98101", "98102", "98103", "98104", "98105",
        "98106", "98107", "98108", "98109", "98110",
        "98112", "98115", "98116", "98117", "98118",
        "98119", "98121", "98122", "98125", "98126",
        "98133", "98134", "98136", "98144", "98146",
        "98148", "98155", "98158", "98166", "98168",
        "98177", "98178", "98188", "98198", "98199",
    ]
