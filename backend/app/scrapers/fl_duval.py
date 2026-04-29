"""
Duval County, FL — Duval County Property Appraiser (Jacksonville).

Uses the standard Florida PApublicServiceProxy REST API.
Discovery: search by major Jacksonville street names → collect strap numbers.

Reference: https://www.duvalassessor.com/
"""
from __future__ import annotations

from app.scrapers._fl_pa_base import FLPropertyAppraiserScraper


class DuvalCountyScraper(FLPropertyAppraiserScraper):
    adapter_name = "duval_fl"

    _API = "https://www.duvalassessor.com/PApublicServiceProxy/PaServicesProxy.ashx"
    _CITY = "JACKSONVILLE"

    _STREETS = [
        "BEACH BLVD", "ATLANTIC BLVD", "UNIVERSITY BLVD", "ARLINGTON RD",
        "SOUTHSIDE BLVD", "ST AUGUSTINE RD", "OLD ST AUGUSTINE RD",
        "SAN JOSE BLVD", "PHILIPS HWY", "US 1", "US 17",
        "BLANDING BLVD", "ARGYLE FOREST BLVD", "103RD ST", "NORMANDY BLVD",
        "RAMONA BLVD", "COMMONWEALTH AVE", "EDGEWOOD AVE",
        "PEARL ST", "RIVERSIDE AVE", "POST ST", "PARK ST",
        "CASSAT AVE", "LANE AVE", "MAIN ST", "UNION ST",
        "MONCRIEF RD", "NORWOOD AVE", "LEM TURNER RD",
        "NEW KINGS RD", "DUNN AVE", "PECAN PARK RD",
    ]
