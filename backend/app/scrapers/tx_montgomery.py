"""
Montgomery County, TX — Montgomery Central Appraisal District (MCAD).

Uses the PropAccess iSite API at propaccess.mcad-tx.org/clientdb.
Discovery: Conroe, The Woodlands, Spring, Humble (partial) zip codes.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class MontgomeryCountyScraper(PropAccessScraper):
    adapter_name = "montgomery_tx"

    _API = "https://propaccess.mcad-tx.org/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "77301", "77302", "77303", "77304", "77306",
        "77316", "77318", "77327", "77339", "77354",
        "77356", "77357", "77362", "77380", "77381",
        "77382", "77384", "77385", "77386", "77388",
        "77389", "77393",
    ]
