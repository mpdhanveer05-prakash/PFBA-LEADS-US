import logging
import uuid

from app.workers import celery_app
from app.database import SessionLocal
from app.services.county_repository import CountyRepository
from app.scrapers.registry import ScraperRegistry

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_county(self, county_id: str) -> dict:
    db = SessionLocal()
    try:
        repo = CountyRepository(db)
        county = repo.get(uuid.UUID(county_id))
        if not county:
            return {"status": "error", "message": f"County {county_id} not found"}

        scraper_cls = ScraperRegistry.get(county.scraper_adapter)
        if not scraper_cls:
            return {"status": "error", "message": f"No scraper for adapter {county.scraper_adapter}"}

        scraper = scraper_cls(county=county, db=db)
        result = scraper.run(limit=500)

        repo.update_last_scraped(county.id)
        logger.info("Scraped county %s: %s records", county.name, result.get("records_processed", 0))
        return {"status": "ok", **result}

    except Exception as exc:
        logger.exception("Failed to scrape county %s", county_id)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_raw_record(self, county_id: str, apn: str, raw_data: dict) -> dict:
    db = SessionLocal()
    try:
        scraper_cls = ScraperRegistry.get_for_county(uuid.UUID(county_id), db)
        if not scraper_cls:
            return {"status": "error", "message": "Scraper not found"}

        scraper = scraper_cls.__new__(scraper_cls)
        result = scraper.process_record(apn=apn, raw_data=raw_data, db=db)
        return {"status": "ok", **result}

    except Exception as exc:
        logger.exception("Failed to process raw record APN=%s", apn)
        raise self.retry(exc=exc)
    finally:
        db.close()
