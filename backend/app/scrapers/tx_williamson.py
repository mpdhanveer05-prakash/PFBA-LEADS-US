"""
Williamson County, TX — Williamson Central Appraisal District (WCAD).

Uses the PropAccess iSite API at propaccess.wcad.org/clientdb.
Discovery: Round Rock, Cedar Park, Georgetown, Pflugerville zip codes.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class WilliamsonCountyScraper(PropAccessScraper):
    adapter_name = "williamson_tx"

    _API = "https://propaccess.wcad.org/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "78613", "78626", "78628", "78633", "78634",
        "78641", "78642", "78645", "78660", "78664",
        "78665", "78681", "78717", "78726", "78729",
        "78750", "78759", "76537", "76574", "76527",
    ]
