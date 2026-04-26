"""
Palm Beach County, FL — Palm Beach County Property Appraiser (PBCPA).

Uses the standard Florida PApublicServiceProxy REST API.
Discovery: search by major West Palm Beach / Boca Raton streets.
"""
from __future__ import annotations

from app.scrapers._fl_pa_base import FLPropertyAppraiserScraper


class PalmBeachCountyScraper(FLPropertyAppraiserScraper):
    adapter_name = "palm_beach_fl"

    _API = "https://www.pbcgov.org/papa/Portals/PaServicesProxy.ashx"
    _CITY = "WEST PALM BEACH"

    _STREETS = [
        "OKEECHOBEE BLVD", "MILITARY TRL", "CONGRESS AVE", "PALM BEACH LAKES BLVD",
        "SOUTHERN BLVD", "FOREST HILL BLVD", "LAKE WORTH RD", "BOYNTON BEACH BLVD",
        "ATLANTIC AVE", "FEDERAL HWY", "US 1", "DIXIE HWY",
        "GLADES RD", "PALMETTO PARK RD", "CAMINO REAL", "YAMATO RD",
        "CLINT MOORE RD", "LINTON BLVD", "WOOLBRIGHT RD", "GATEWAY BLVD",
        "JOG RD", "HAVERHILL RD", "STATE RD 7", "LYONS RD",
        "HYPOLUXO RD", "LANTANA RD", "BELVEDERE RD", "45TH ST",
        "NORTHLAKE BLVD", "PGA BLVD",
    ]
