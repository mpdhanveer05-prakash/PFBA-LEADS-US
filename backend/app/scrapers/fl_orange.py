"""
Orange County, FL — Orange County Property Appraiser (OCPA).

Uses the standard Florida PApublicServiceProxy REST API.
Discovery: search by major Orlando / Kissimmee area streets.
"""
from __future__ import annotations

from app.scrapers._fl_pa_base import FLPropertyAppraiserScraper


class OrangeCountyFLScraper(FLPropertyAppraiserScraper):
    adapter_name = "orange_fl"

    _API = "https://www.ocpafl.org/PApublicServiceProxy/PaServicesProxy.ashx"
    _CITY = "ORLANDO"

    _STREETS = [
        "ORANGE BLOSSOM TRL", "COLONIAL DR", "COLONIAL PKWY", "SAND LAKE RD",
        "INTERNATIONAL DR", "OAK RIDGE RD", "MICHIGAN ST", "SOUTH ST",
        "GORE ST", "MICHIGAN AVE", "ORANGE AVE", "CURRY FORD RD",
        "SEMORAN BLVD", "GOLDENROD RD", "UNIVERSITY BLVD", "ALAFAYA TRL",
        "DEAN RD", "LAKE UNDERHILL RD", "CONWAY RD", "JOHN YOUNG PKWY",
        "KIRKMAN RD", "APOPKA VINELAND RD", "TURKEY LAKE RD", "HIAWASSEE RD",
        "EDGEWATER DR", "FAIRBANKS AVE", "CORRINE DR", "MILLS AVE",
        "BUMBY AVE", "CHICKASAW TRL",
    ]
