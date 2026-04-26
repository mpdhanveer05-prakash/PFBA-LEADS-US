import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.database import SessionLocal, get_db
from app.models.county import County
from app.models.sync_job import SyncJob, SyncStatus, SyncType
from app.schemas.auth import TokenData
from app.schemas.sync import CountyScheduleUpdate, SyncJobRead, SyncTriggerRequest
from app.services.county_repository import CountyRepository

router = APIRouter()
logger = logging.getLogger(__name__)


# ── background runner ────────────────────────────────────────────────────────


def _run_full_sync(job_id: str, county_id: str, count: int) -> None:
    from app.scrapers.registry import ScraperRegistry
    from app.models.assessment import Assessment
    from app.models.lead_score import LeadScore
    from app.models.property import Property
    from app.ml.scoring_service import ScoringService
    from sqlalchemy import select

    db = SessionLocal()
    try:
        job = db.get(SyncJob, uuid.UUID(job_id))
        if not job:
            return

        job.status = SyncStatus.RUNNING
        db.commit()

        county = CountyRepository(db).get(uuid.UUID(county_id))
        if not county:
            job.status = SyncStatus.FAILED
            job.error_message = "County not found"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # ── scrape real county data ───────────────────────────────────────────
        scraper_cls = ScraperRegistry.get(county.scraper_adapter)
        is_real_scraper = (
            scraper_cls is not None
            and scraper_cls.__module__ != "app.scrapers.generic_stub"
        )

        records_scraped = 0
        if is_real_scraper:
            logger.info("Scraping %s via %s", county.name, county.scraper_adapter)
            try:
                scraper = scraper_cls(county=county, db=db)
                result = scraper.run(limit=count)
                records_scraped = result.get("records_fetched", 0)
                logger.info(
                    "Scrape done for %s: fetched=%d changed=%d errors=%d",
                    county.name,
                    records_scraped,
                    result.get("records_changed", 0),
                    result.get("errors", 0),
                )
            except Exception:
                logger.exception("Scraper failed for %s", county.name)
                job.error_message = f"Scraper error for {county.scraper_adapter}"

        # ── seed fallback when real scraper returns nothing (e.g. no internet) ─
        if records_scraped == 0:
            from app.scrapers.seed_data import seed_county as _seed_county, COUNTY_CONFIGS
            if county.scraper_adapter in COUNTY_CONFIGS:
                logger.info("Falling back to seed data for %s (count=%d)", county.name, count)
                try:
                    _seed_county(db, county, count)
                    records_scraped = count
                    # Mark that this job used generated data so the UI can show a warning
                    job.error_message = (
                        (job.error_message + " | " if job.error_message else "") + "[seed] real scraper unavailable"
                    )
                    logger.info("Seed fallback done for %s", county.name)
                except Exception:
                    logger.exception("Seed fallback failed for %s", county.name)
            else:
                logger.info("No seed config for %s — skipping", county.name)

        # Commit scraped count immediately so the frontend poll can read it
        job.records_seeded = records_scraped
        db.commit()

        # ── score new assessments ─────────────────────────────────────────────
        svc = ScoringService(db)
        q = select(Assessment.id).where(
            ~Assessment.id.in_(select(LeadScore.assessment_id))
        ).join(Property, Assessment.property_id == Property.id).where(
            Property.county_id == uuid.UUID(county_id)
        )
        assessment_ids = list(db.execute(q).scalars().all())
        scored = 0
        BATCH = 50
        for i, aid in enumerate(assessment_ids):
            try:
                svc.score_assessment(aid)
                scored += 1
            except Exception:
                logger.exception("Failed to score assessment %s", aid)
            if (i + 1) % BATCH == 0:
                svc.commit()
        svc.commit()
        job.records_scored = scored

        # ── update county sync timestamps ─────────────────────────────────────
        county.last_scraped_at = datetime.now(timezone.utc)
        interval = county.sync_interval_hours or 24
        county.next_sync_at = datetime.now(timezone.utc) + timedelta(hours=interval)

        job.status = SyncStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Sync complete for %s: scraped=%d scored=%d",
            county.name, job.records_seeded, scored,
        )

    except Exception as exc:
        logger.exception("Sync failed for county %s", county_id)
        try:
            job = db.get(SyncJob, uuid.UUID(job_id))
            if job:
                job.status = SyncStatus.FAILED
                job.error_message = str(exc)[:1000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/sync/trigger", status_code=202)
def trigger_sync(
    body: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    if not body.county_ids:
        raise HTTPException(status_code=400, detail="No counties selected")

    # Clamp count — no hard ceiling for full sync, but keep it sane
    count = max(1, min(body.count, 10_000))
    triggered_by = body.triggered_by or current_user.sub or "system"

    jobs_created = []
    for cid in body.county_ids:
        county = db.get(County, cid)
        if not county:
            continue
        job = SyncJob(
            county_id=cid,
            sync_type=SyncType.MANUAL,
            status=SyncStatus.PENDING,
            triggered_by=triggered_by,
            lead_count=count,
        )
        db.add(job)
        db.flush()
        background_tasks.add_task(_run_full_sync, str(job.id), str(cid), count)
        jobs_created.append({"job_id": str(job.id), "county_name": county.name, "county_id": str(cid)})

    db.commit()
    return {"status": "queued", "jobs": jobs_created}


@router.get("/sync/jobs", response_model=list[SyncJobRead])
def list_sync_jobs(
    county_id: uuid.UUID | None = None,
    status: SyncStatus | None = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    from app.models.county import County as CountyModel
    q = (
        select(
            SyncJob.id,
            SyncJob.county_id,
            CountyModel.name.label("county_name"),
            SyncJob.sync_type,
            SyncJob.status,
            SyncJob.triggered_by,
            SyncJob.lead_count,
            SyncJob.records_seeded,
            SyncJob.records_scored,
            SyncJob.error_message,
            SyncJob.started_at,
            SyncJob.completed_at,
        )
        .join(CountyModel, SyncJob.county_id == CountyModel.id)
        .order_by(desc(SyncJob.started_at))
        .limit(limit)
    )
    if county_id:
        q = q.where(SyncJob.county_id == county_id)
    if status:
        q = q.where(SyncJob.status == status)

    rows = db.execute(q).all()
    return [SyncJobRead.model_validate(dict(r._mapping)) for r in rows]


@router.get("/sync/jobs/{job_id}", response_model=SyncJobRead)
def get_sync_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    from app.models.county import County as CountyModel
    row = db.execute(
        select(
            SyncJob.id,
            SyncJob.county_id,
            CountyModel.name.label("county_name"),
            SyncJob.sync_type,
            SyncJob.status,
            SyncJob.triggered_by,
            SyncJob.lead_count,
            SyncJob.records_seeded,
            SyncJob.records_scored,
            SyncJob.error_message,
            SyncJob.started_at,
            SyncJob.completed_at,
        )
        .join(CountyModel, SyncJob.county_id == CountyModel.id)
        .where(SyncJob.id == job_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return SyncJobRead.model_validate(dict(row._mapping))


@router.put("/counties/{county_id}/schedule")
def update_county_schedule(
    county_id: uuid.UUID,
    body: CountyScheduleUpdate,
    db: Session = Depends(get_db),
    _: TokenData = Depends(require_role("admin", "manager")),
):
    county = db.get(County, county_id)
    if not county:
        raise HTTPException(status_code=404, detail="County not found")

    county.sync_interval_hours = max(1, body.sync_interval_hours)
    county.auto_sync_enabled = body.auto_sync_enabled
    if body.auto_sync_enabled and county.last_scraped_at:
        county.next_sync_at = county.last_scraped_at + timedelta(hours=county.sync_interval_hours)
    elif not body.auto_sync_enabled:
        county.next_sync_at = None

    db.commit()
    db.refresh(county)
    return {"status": "updated", "county_id": str(county_id), "sync_interval_hours": county.sync_interval_hours, "auto_sync_enabled": county.auto_sync_enabled, "next_sync_at": county.next_sync_at}
