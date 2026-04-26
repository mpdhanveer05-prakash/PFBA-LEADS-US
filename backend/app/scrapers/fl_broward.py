"""
Broward County, FL — Broward County Property Appraiser (BCPA).

Uses the standard Florida PApublicServiceProxy REST API.
Discovery: search by major Fort Lauderdale / Broward streets → collect folio
           numbers → fetch full detail per folio.
"""
from __future__ import annotations

from app.scrapers._fl_pa_base import FLPropertyAppraiserScraper


class BrowardCountyScraper(FLPropertyAppraiserScraper):
    adapter_name = "broward_fl"

    _API = "https://webservices.bcpa.net/bcpaClientApp/api/PApublicServiceProxy/PaServicesProxy.ashx"
    _CITY = "FORT LAUDERDALE"

    _STREETS = [
        "BROWARD BLVD", "COMMERCIAL BLVD", "SUNRISE BLVD", "OAKLAND PARK BLVD",
        "SAMPLE RD", "ATLANTIC BLVD", "HALLANDALE BEACH BLVD", "HOLLYWOOD BLVD",
        "PEMBROKE RD", "GRIFFIN RD", "STIRLING RD", "SHERIDAN ST",
        "US 1", "US 441", "STATE RD 7", "FEDERAL HWY",
        "NW 2 AVE", "NW 9 AVE", "NW 27 AVE", "SW 27 AVE",
        "NE 4 AVE", "SE 17 ST", "DAVIE BLVD", "UNIVERSITY DR",
        "PINE ISLAND RD", "HIATUS RD", "FLAMINGO RD", "DYKES RD",
        "WILES RD", "COCONUT CREEK PKWY",
    ]
