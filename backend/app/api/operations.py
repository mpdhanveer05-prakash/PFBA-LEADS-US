import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_role, get_current_user
from app.database import SessionLocal, get_db
from app.schemas.auth import TokenData
from app.services.county_repository import CountyRepository
from fastapi import HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)


def _run_scrape(county_id: str) -> None:
    from app.scrapers.registry import ScraperRegistry
    db = SessionLocal()
    try:
        county = CountyRepository(db).get(uuid.UUID(county_id))
        if not county:
            return
        records_scraped = 0
        scraper_cls = ScraperRegistry.get(county.scraper_adapter)
        is_real = scraper_cls and scraper_cls.__module__ != "app.scrapers.generic_stub"
        if is_real:
            try:
                scraper = scraper_cls(county=county, db=db)
                result = scraper.run(limit=200)
                records_scraped = result.get("records_fetched", 0)
            except Exception:
                logger.exception("Scraper failed for %s", county.name)
        if records_scraped == 0:
            from app.scrapers.seed_data import seed_county as _seed, COUNTY_CONFIGS
            if county.scraper_adapter in COUNTY_CONFIGS:
                _seed(db, county, 200)
                records_scraped = 200
        CountyRepository(db).update_last_scraped(county.id)
        logger.info("Scrape complete for %s: %d records", county.name, records_scraped)
    except Exception:
        logger.exception("Scrape failed for county %s", county_id)
    finally:
        db.close()


def _run_scoring(county_id: str | None = None, force: bool = False) -> None:
    from sqlalchemy import select, delete
    from app.models.assessment import Assessment
    from app.models.lead_score import LeadScore
    from app.models.property import Property
    from app.ml.scoring_service import ScoringService

    db = SessionLocal()
    try:
        svc = ScoringService(db)

        if force:
            # Wipe existing lead scores so all assessments are re-evaluated
            if county_id:
                sub = (
                    select(Assessment.id)
                    .join(Property, Assessment.property_id == Property.id)
                    .where(Property.county_id == uuid.UUID(county_id))
                )
                db.execute(
                    delete(LeadScore).where(LeadScore.assessment_id.in_(sub))
                )
            else:
                db.execute(delete(LeadScore))
            db.commit()
            logger.info("Force-rescore: cleared existing lead_scores")

        q = select(Assessment.id).where(
            ~Assessment.id.in_(select(LeadScore.assessment_id))
        )
        if county_id:
            q = q.join(Property, Assessment.property_id == Property.id).where(
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
        logger.info("Scoring complete: %d/%d assessments scored", scored, len(assessment_ids))
    except Exception:
        logger.exception("Scoring run failed")
    finally:
        db.close()


@router.post("/counties/{county_id}/scrape", status_code=202)
def trigger_scrape(
    county_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: TokenData = Depends(require_role("admin", "manager")),
):
    county = CountyRepository(db).get(county_id)
    if not county:
        raise HTTPException(status_code=404, detail="County not found")
    background_tasks.add_task(_run_scrape, str(county_id))
    return {"status": "running", "county": county.name}


@router.get("/scoring/status")
def scoring_status(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    from sqlalchemy import select, func
    from app.models.assessment import Assessment
    from app.models.lead_score import LeadScore

    total = db.execute(select(func.count()).select_from(Assessment)).scalar() or 0
    scored = db.execute(select(func.count()).select_from(LeadScore)).scalar() or 0
    return {"total": total, "scored": scored, "unscored": max(0, total - scored)}


@router.post("/scoring/run", status_code=202)
def trigger_scoring(
    background_tasks: BackgroundTasks,
    county_id: uuid.UUID | None = None,
    force: bool = False,
    _: TokenData = Depends(require_role("admin", "manager")),
):
    background_tasks.add_task(
        _run_scoring,
        str(county_id) if county_id else None,
        force,
    )
    return {"status": "running", "force": force}
