import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.services.county_repository import CountyRepository

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")


def run_migrations() -> None:
    from alembic.config import Config
    from alembic import command

    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        logger.info("Database migrations applied")
    except Exception:
        logger.exception("Failed to run database migrations")


# Four counties with verified, tested public Socrata APIs — no authentication required.
# Cook IL:    datacatalog.cookcountyil.gov (uzyt-m557 assessments + c49d-89sn addresses)
# NYC:        data.cityofnewyork.us (MapPLUTO — 64uk-42ks)
# SF:         data.sfgov.org (Assessor Closed Roll — wv5m-vpq2)
# Philly:     data.phila.gov (OPA Properties — w7rb-qrn8)
_DEFAULT_COUNTIES = [
    {"name": "Cook",         "state": "IL", "portal_url": "https://www.cookcountyassessor.com",        "scraper_adapter": "cook_il",   "appeal_deadline_days": 30, "approval_rate_hist": 0.32},
    {"name": "New York",     "state": "NY", "portal_url": "https://www.nyc.gov/site/finance/taxes",    "scraper_adapter": "ny_nyc",    "appeal_deadline_days": 90, "approval_rate_hist": 0.28},
    {"name": "San Francisco","state": "CA", "portal_url": "https://sfassessor.org",                    "scraper_adapter": "ca_sf",     "appeal_deadline_days": 60, "approval_rate_hist": 0.30},
    {"name": "Philadelphia", "state": "PA", "portal_url": "https://www.phila.gov/departments/office-of-property-assessment", "scraper_adapter": "pa_philly", "appeal_deadline_days": 30, "approval_rate_hist": 0.34},
]

_DEFAULT_KEYS = {(d["name"], d["state"]) for d in _DEFAULT_COUNTIES}


def sync_default_counties() -> None:
    """Ensure the DB contains exactly the 4 default counties, removing any others."""
    from app.schemas.county import CountyCreate
    from sqlalchemy import text

    db = SessionLocal()
    try:
        repo = CountyRepository(db)

        # Remove counties (and all their data) that are not in the defaults list
        for county in repo.list():
            if (county.name, county.state) not in _DEFAULT_KEYS:
                cid = county.id
                # Delete in FK dependency order (no CASCADE in schema)
                db.execute(text(
                    "DELETE FROM appeals WHERE lead_score_id IN "
                    "(SELECT ls.id FROM lead_scores ls JOIN properties p ON ls.property_id = p.id WHERE p.county_id = :cid)"
                ), {"cid": cid})
                db.execute(text(
                    "DELETE FROM lead_scores WHERE property_id IN "
                    "(SELECT id FROM properties WHERE county_id = :cid)"
                ), {"cid": cid})
                db.execute(text(
                    "DELETE FROM comparable_sales WHERE property_id IN "
                    "(SELECT id FROM properties WHERE county_id = :cid)"
                ), {"cid": cid})
                db.execute(text(
                    "DELETE FROM assessments WHERE property_id IN "
                    "(SELECT id FROM properties WHERE county_id = :cid)"
                ), {"cid": cid})
                db.execute(text("DELETE FROM properties WHERE county_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM sync_jobs WHERE county_id = :cid"), {"cid": cid})
                db.execute(text("DELETE FROM counties WHERE id = :cid"), {"cid": cid})
                logger.info("Removed non-default county: %s %s", county.name, county.state)
        db.commit()

        # Add any missing default counties
        repo2 = CountyRepository(db)
        for data in _DEFAULT_COUNTIES:
            if not repo2.get_by_slug(data["name"], data["state"]):
                repo2.create(CountyCreate(**{**data, "auto_sync_enabled": False}))
                logger.info("Created default county: %s %s", data["name"], data["state"])
        db.commit()
    except Exception:
        logger.exception("Failed to sync default counties")
    finally:
        db.close()


def _run_scheduled_syncs() -> None:
    from datetime import datetime, timezone
    from app.api.sync import _run_full_sync
    from app.models.sync_job import SyncJob, SyncType, SyncStatus

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        counties = CountyRepository(db).list()
        for county in counties:
            if not county.auto_sync_enabled:
                continue
            if county.next_sync_at and county.next_sync_at > now:
                continue
            job = SyncJob(
                county_id=county.id,
                sync_type=SyncType.SCHEDULED,
                status=SyncStatus.PENDING,
                triggered_by="scheduler",
                lead_count=20,
            )
            db.add(job)
            db.flush()
            db.commit()
            _run_full_sync(str(job.id), str(county.id), 20)
            logger.info("Scheduled sync complete for %s", county.name)
    except Exception:
        logger.exception("Scheduled sync run failed")
    finally:
        db.close()


def start_scheduler() -> None:
    # Run all county scrapers every night at 02:00 UTC
    _scheduler.add_job(
        _run_scheduled_syncs,
        CronTrigger(hour=2, minute=0),
        id="nightly_scrape",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started — nightly scrape at 02:00 UTC")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def cleanup_stuck_jobs() -> None:
    """Delete any RUNNING/PENDING jobs on startup — they were killed by a restart."""
    from app.models.sync_job import SyncJob, SyncStatus

    db = SessionLocal()
    try:
        deleted = db.query(SyncJob).filter(
            SyncJob.status.in_([SyncStatus.RUNNING, SyncStatus.PENDING])
        ).delete()
        db.commit()
        if deleted:
            logger.info("Removed %d interrupted sync job(s) from previous run", deleted)
    except Exception:
        logger.exception("Failed to clean up stuck jobs")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app):
    import asyncio
    cleanup_stuck_jobs()
    # Run DB-heavy county sync in a thread so the event loop stays unblocked
    # and the app can accept requests immediately while this runs in the background.
    asyncio.get_event_loop().run_in_executor(None, sync_default_counties)
    start_scheduler()
    yield
    stop_scheduler()
