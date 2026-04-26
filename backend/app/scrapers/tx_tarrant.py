"""
Tarrant County, TX — Tarrant Appraisal District (TAD).

Uses the PropAccess iSite API at propaccess.tad.org/clientdb.
Discovery: search by Fort Worth / DFW zip codes → collect prop_ids → fetch detail.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class TarrantCountyScraper(PropAccessScraper):
    adapter_name = "tarrant_tx"

    _API = "https://propaccess.tad.org/clientdb"
    _STATE = "TX"
    _CID = None  # TAD does not require a cid parameter

    _ZIPS = [
        "76001", "76002", "76006", "76010", "76011",
        "76012", "76013", "76014", "76015", "76016",
        "76017", "76018", "76019", "76020", "76021",
        "76022", "76028", "76034", "76036", "76039",
        "76040", "76102", "76103", "76104", "76105",
        "76106", "76107", "76108", "76109", "76110",
        "76111", "76112", "76114", "76115", "76116",
        "76117", "76118", "76119", "76120", "76123",
        "76126", "76127", "76129", "76131", "76132",
        "76133", "76134", "76135", "76137", "76140",
    ]
