"""
Bastrop County, TX — Bastrop Central Appraisal District (BCAD).

Uses the PropAccess iSite API at propaccess.bastropcad.org/clientdb.
Coverage: Bastrop, Elgin, Smithville, Cedar Creek, Lockhart-area properties.

Note: The site has a TLS cert mismatch — _VERIFY_SSL = False (inherited from PropAccessScraper).
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class BastropCountyScraper(PropAccessScraper):
    adapter_name = "bastrop_tx"

    _API = "https://propaccess.bastropcad.org/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "78602", "78612", "78621", "78644", "78659",
        "78662", "78953", "78957", "78617", "78738",
    ]
