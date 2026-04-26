"""
Dallas County, TX — Dallas Central Appraisal District (DCAD).

Uses the PropAccess iSite API at propaccess.dallascad.org/clientdb.
Discovery: City of Dallas and inner-ring suburb zip codes.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class DallasCountyScraper(PropAccessScraper):
    adapter_name = "dallas_tx"

    _API = "https://propaccess.dallascad.org/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "75201", "75202", "75203", "75204", "75205",
        "75206", "75207", "75208", "75209", "75210",
        "75211", "75212", "75214", "75215", "75216",
        "75217", "75218", "75219", "75220", "75223",
        "75224", "75225", "75226", "75228", "75229",
        "75230", "75231", "75232", "75233", "75234",
        "75235", "75236", "75237", "75238", "75240",
        "75241", "75243", "75244", "75246", "75247",
        "75248", "75249", "75251", "75252", "75253",
    ]
