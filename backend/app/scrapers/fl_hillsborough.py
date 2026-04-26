"""
Hillsborough County, FL — Hillsborough County Property Appraiser (HCPA).

Uses the standard Florida PApublicServiceProxy REST API.
Discovery: search by major Tampa / Brandon / Plant City streets.
"""
from __future__ import annotations

from app.scrapers._fl_pa_base import FLPropertyAppraiserScraper


class HillsboroughCountyScraper(FLPropertyAppraiserScraper):
    adapter_name = "hillsborough_fl"

    _API = "https://www.hcpafl.org/PApublicServiceProxy/PaServicesProxy.ashx"
    _CITY = "TAMPA"

    _STREETS = [
        "DALE MABRY HWY", "FLORIDA AVE", "KENNEDY BLVD", "HILLSBOROUGH AVE",
        "BUSCH BLVD", "FOWLER AVE", "FLETCHER AVE", "BEARSS AVE",
        "BRUCE B DOWNS BLVD", "UNIVERSITY OF SOUTH FLORIDA",
        "NEBRASKA AVE", "ARMENIA AVE", "MACDILL AVE", "WESTSHORE BLVD",
        "WATERS AVE", "LINEBAUGH AVE", "SLIGH AVE", "COLUMBUS DR",
        "INTERBAY BLVD", "GANDY BLVD", "CROSSTOWN EXPY",
        "BRANDON BLVD", "KINGS AVE", "LITHIA PINECREST RD", "VALRICO RD",
        "BLOOMINGDALE AVE", "SUN CITY CENTER BLVD", "BOYETTE RD",
        "GUNN HWY", "EHRLICH RD",
    ]
