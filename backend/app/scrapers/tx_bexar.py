"""
Bexar County, TX — Bexar County Appraisal District (BCAD).

Uses the PropAccess iSite API at propaccess.bcad.org/clientdb.
Discovery: search by San Antonio zip codes → collect prop_ids → fetch detail.
"""
from __future__ import annotations

from app.scrapers._propaccess_base import PropAccessScraper


class BexarCountyScraper(PropAccessScraper):
    adapter_name = "bexar_tx"

    _API = "https://propaccess.bcad.org/clientdb"
    _STATE = "TX"
    _CID = None

    _ZIPS = [
        "78201", "78202", "78203", "78204", "78205",
        "78206", "78207", "78208", "78209", "78210",
        "78211", "78212", "78213", "78214", "78215",
        "78216", "78217", "78218", "78219", "78220",
        "78221", "78222", "78223", "78224", "78225",
        "78226", "78227", "78228", "78229", "78230",
        "78231", "78232", "78233", "78234", "78235",
        "78236", "78237", "78238", "78239", "78240",
        "78241", "78242", "78243", "78244", "78245",
        "78246", "78247", "78248", "78249", "78250",
        "78251", "78252", "78253", "78254", "78255",
        "78256", "78257", "78258", "78259", "78260",
        "78261", "78263", "78264", "78266",
    ]
