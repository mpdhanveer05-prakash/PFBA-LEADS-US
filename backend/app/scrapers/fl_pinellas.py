"""
Pinellas County, FL — Pinellas County Property Appraiser (PCPAO).

Uses the standard Florida PApublicServiceProxy REST API.
Discovery: search by major St. Petersburg / Clearwater streets.
"""
from __future__ import annotations

from app.scrapers._fl_pa_base import FLPropertyAppraiserScraper


class PinellasCountyScraper(FLPropertyAppraiserScraper):
    adapter_name = "pinellas_fl"

    _API = "https://www.pcpao.gov/PApublicServiceProxy/PaServicesProxy.ashx"
    _CITY = "ST PETERSBURG"

    _STREETS = [
        "34TH ST", "CENTRAL AVE", "GULF TO BAY BLVD", "MAIN ST",
        "US 19", "US 19 ALT", "DREW ST", "COURT ST",
        "49TH ST", "66TH ST", "4TH ST", "16TH ST",
        "1ST AVE N", "1ST AVE S", "5TH AVE N", "5TH AVE S",
        "22ND AVE N", "22ND AVE S", "54TH AVE N", "54TH AVE S",
        "TYRONE BLVD", "PARK BLVD", "ULMERTON RD", "BELLEAIR RD",
        "CLEARWATER LARGO RD", "EAST BAY DR", "HIGHLAND AVE", "KEENE RD",
        "SUNSET POINT RD", "NURSERY RD",
    ]
