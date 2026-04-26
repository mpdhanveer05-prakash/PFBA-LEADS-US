"""
Collin County, TX — Collin Central Appraisal District (CCAD).

Uses the PropAccess iSite API at propaccess.collincad.org/clientdb.
Discovery: Plano, McKinney, Frisco, Allen, Richardson zip codes.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class CollinCountyScraper(PropAccessScraper):
    adapter_name = "collin_tx"

    _API = "https://propaccess.collincad.org/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "75002", "75009", "75013", "75023", "75024",
        "75025", "75034", "75035", "75069", "75070",
        "75071", "75074", "75075", "75078", "75080",
        "75082", "75093", "75094", "75098", "75166",
    ]
