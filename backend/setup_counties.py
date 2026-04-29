"""
Insert all supported counties into the database.
Safe to re-run — skips counties that already exist (matched by scraper_adapter).

Usage:
    docker compose exec backend python setup_counties.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "postgresql://pathfinder:pathfinder@db:5432/pathfinder")

from sqlalchemy import select
from app.database import SessionLocal
from app.models.county import County

COUNTIES = [
    # ── Texas ────────────────────────────────────────────────────────────
    {"name": "Travis County",       "state": "TX", "scraper_adapter": "travis_tx",     "portal_url": "https://www.traviscad.org/",             "approval_rate_hist": 0.38},
    {"name": "Harris County",       "state": "TX", "scraper_adapter": "harris_tx",     "portal_url": "https://public.hcad.org/records/",       "approval_rate_hist": 0.42},
    {"name": "Dallas County",       "state": "TX", "scraper_adapter": "dallas_tx",     "portal_url": "https://www.dallascad.org/",             "approval_rate_hist": 0.40},
    {"name": "Tarrant County",      "state": "TX", "scraper_adapter": "tarrant_tx",    "portal_url": "https://www.tad.org/",                   "approval_rate_hist": 0.37},
    {"name": "Bexar County",        "state": "TX", "scraper_adapter": "bexar_tx",      "portal_url": "https://bexar.org/",                     "approval_rate_hist": 0.35},
    {"name": "Collin County",       "state": "TX", "scraper_adapter": "collin_tx",     "portal_url": "https://www.collincad.org/",             "approval_rate_hist": 0.36},
    {"name": "Denton County",       "state": "TX", "scraper_adapter": "denton_tx",     "portal_url": "https://www.dentoncad.com/",             "approval_rate_hist": 0.36},
    {"name": "Williamson County",   "state": "TX", "scraper_adapter": "williamson_tx", "portal_url": "https://www.wcad.org/",                  "approval_rate_hist": 0.35},
    {"name": "Montgomery County",   "state": "TX", "scraper_adapter": "montgomery_tx", "portal_url": "https://www.mcad-tx.org/",               "approval_rate_hist": 0.34},
    {"name": "Bastrop County",      "state": "TX", "scraper_adapter": "bastrop_tx",    "portal_url": "https://www.bastropcad.org/",            "approval_rate_hist": 0.33},
    {"name": "Hays County",         "state": "TX", "scraper_adapter": "hays_tx",       "portal_url": "https://www.hayscad.com/",               "approval_rate_hist": 0.34},
    # ── Florida ──────────────────────────────────────────────────────────
    {"name": "Miami-Dade County",   "state": "FL", "scraper_adapter": "miami_dade_fl", "portal_url": "https://www.miamidadeproperty.com/",     "approval_rate_hist": 0.45},
    {"name": "Broward County",      "state": "FL", "scraper_adapter": "broward_fl",    "portal_url": "https://www.bcpa.net/",                  "approval_rate_hist": 0.43},
    {"name": "Palm Beach County",   "state": "FL", "scraper_adapter": "palm_beach_fl", "portal_url": "https://pbcpao.gov/",                   "approval_rate_hist": 0.44},
    {"name": "Hillsborough County", "state": "FL", "scraper_adapter": "hillsborough_fl","portal_url": "https://www.hcpafl.org/",               "approval_rate_hist": 0.41},
    {"name": "Orange County",       "state": "FL", "scraper_adapter": "orange_fl",     "portal_url": "https://ocpafl.org/",                   "approval_rate_hist": 0.40},
    {"name": "Pinellas County",     "state": "FL", "scraper_adapter": "pinellas_fl",   "portal_url": "https://www.pcpao.gov/",                 "approval_rate_hist": 0.39},
    {"name": "Duval County",        "state": "FL", "scraper_adapter": "duval_fl",      "portal_url": "https://www.duvalassessor.com/",         "approval_rate_hist": 0.38},
    # ── California ───────────────────────────────────────────────────────
    {"name": "Los Angeles County",  "state": "CA", "scraper_adapter": "los_angeles_ca","portal_url": "https://portal.assessor.lacounty.gov/", "approval_rate_hist": 0.48},
    {"name": "San Diego County",    "state": "CA", "scraper_adapter": "san_diego_ca",  "portal_url": "https://www.sdarcc.gov/",               "approval_rate_hist": 0.44},
    {"name": "Orange County",       "state": "CA", "scraper_adapter": "orange_ca",     "portal_url": "https://ocassessor.gov/",               "approval_rate_hist": 0.43},
    {"name": "Riverside County",    "state": "CA", "scraper_adapter": "riverside_ca",  "portal_url": "https://assessor.riversideca.gov/",     "approval_rate_hist": 0.42},
    {"name": "Santa Clara County",  "state": "CA", "scraper_adapter": "santa_clara_ca","portal_url": "https://www.sccassessor.org/",          "approval_rate_hist": 0.46},
    {"name": "San Francisco",       "state": "CA", "scraper_adapter": "ca_sf",         "portal_url": "https://data.sfgov.org/",               "approval_rate_hist": 0.50},
    # ── Other states ─────────────────────────────────────────────────────
    {"name": "Cook County",         "state": "IL", "scraper_adapter": "cook_il",       "portal_url": "https://www.cookcountyassessor.com/",   "approval_rate_hist": 0.52},
    {"name": "King County",         "state": "WA", "scraper_adapter": "king_wa",       "portal_url": "https://kingcounty.gov/assessor/",      "approval_rate_hist": 0.41},
    {"name": "Maricopa County",     "state": "AZ", "scraper_adapter": "maricopa_az",   "portal_url": "https://mcassessor.maricopa.gov/",      "approval_rate_hist": 0.39},
    {"name": "Clark County",        "state": "NV", "scraper_adapter": "clark_nv",      "portal_url": "https://www.clarkcountynv.gov/",        "approval_rate_hist": 0.36},
    {"name": "Fulton County",       "state": "GA", "scraper_adapter": "fulton_ga",     "portal_url": "https://www.fultoncountyga.gov/",       "approval_rate_hist": 0.38},
    {"name": "Mecklenburg County",  "state": "NC", "scraper_adapter": "mecklenburg_nc","portal_url": "https://www.mecklenburgcountync.gov/",  "approval_rate_hist": 0.37},
    {"name": "Wake County",         "state": "NC", "scraper_adapter": "wake_nc",       "portal_url": "https://www.wake.gov/",                 "approval_rate_hist": 0.36},
    {"name": "New York City",       "state": "NY", "scraper_adapter": "ny_nyc",        "portal_url": "https://www.nyc.gov/finance/",          "approval_rate_hist": 0.55},
    {"name": "Philadelphia County", "state": "PA", "scraper_adapter": "pa_philly",     "portal_url": "https://data.phila.gov/",               "approval_rate_hist": 0.48},
]


def main() -> None:
    db = SessionLocal()
    try:
        existing = {
            row.scraper_adapter
            for row in db.execute(select(County.scraper_adapter)).scalars().all()
        }
        added = 0
        for c in COUNTIES:
            if c["scraper_adapter"] in existing:
                print(f"  skip  {c['scraper_adapter']} (already exists)")
                continue
            county = County(
                name=c["name"],
                state=c["state"],
                portal_url=c["portal_url"],
                scraper_adapter=c["scraper_adapter"],
                approval_rate_hist=c.get("approval_rate_hist"),
                appeal_deadline_days=30,
            )
            db.add(county)
            added += 1
            print(f"  add   {c['scraper_adapter']} — {c['name']}, {c['state']}")
        db.commit()
        print(f"\nDone: {added} counties added, {len(existing)} already existed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
