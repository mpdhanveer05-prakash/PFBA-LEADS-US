"""
Denton County, TX — Denton Central Appraisal District (DCAD).

Uses the PropAccess iSite API at propaccess.dentoncad.com/clientdb.
Discovery: Denton, Lewisville, Flower Mound, Carrollton, Frisco (partial) zips.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class DentonCountyScraper(PropAccessScraper):
    adapter_name = "denton_tx"

    _API = "https://propaccess.dentoncad.com/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "75010", "75019", "75022", "75028", "75056",
        "75065", "75067", "75077", "75078", "75287",
        "76201", "76205", "76207", "76208", "76209",
        "76210", "76226", "76227", "76234", "76247",
        "76249", "76258", "76259", "76262", "76266",
    ]
