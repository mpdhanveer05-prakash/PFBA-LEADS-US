import logging
import uuid

from app.workers import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def score_new_assessments(self, county_id: str | None = None) -> dict:
    from app.ml.scoring_service import ScoringService
    from sqlalchemy import select
    from app.models.assessment import Assessment
    from app.models.lead_score import LeadScore

    db = SessionLocal()
    try:
        svc = ScoringService(db)

        unscored_q = (
            select(Assessment.id)
            .where(
                ~Assessment.id.in_(select(LeadScore.assessment_id))
            )
        )
        if county_id:
            from app.models.property import Property
            unscored_q = unscored_q.join(Property, Assessment.property_id == Property.id).where(
                Property.county_id == uuid.UUID(county_id)
            )

        assessment_ids = list(db.execute(unscored_q).scalars().all())
        scored = 0
        for aid in assessment_ids:
            try:
                svc.score_assessment(aid)
                scored += 1
            except Exception:
                logger.exception("Failed to score assessment %s", aid)

        logger.info("Scored %d/%d assessments", scored, len(assessment_ids))
        return {"status": "ok", "scored": scored, "total": len(assessment_ids)}

    except Exception as exc:
        logger.exception("score_new_assessments failed")
        raise self.retry(exc=exc)
    finally:
        db.close()
