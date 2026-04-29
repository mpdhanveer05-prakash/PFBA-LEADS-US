"""
Hays County, TX — Hays Central Appraisal District (HCAD).

Uses the PropAccess iSite API at propaccess.hayscad.com/clientdb.
Coverage: San Marcos, Kyle, Buda, Wimberley, Dripping Springs.

Note: Uses _VERIFY_SSL = False (inherited) due to common cert mismatches on CAD portals.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class HaysCountyScraper(PropAccessScraper):
    adapter_name = "hays_tx"

    _API = "https://propaccess.hayscad.com/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "78666", "78676", "78610", "78640", "78737",
        "78620", "78623", "78655", "78669", "78736",
        "78701", "78748",
    ]
