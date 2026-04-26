"""CLI entrypoint: python -m app.scrapers.run --county travis_tx"""
import argparse
import logging

from app.database import SessionLocal
from app.scrapers.registry import ScraperRegistry
from app.services.county_repository import CountyRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--county", required=True, help="County adapter slug, e.g. travis_tx")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        repo = CountyRepository(db)
        counties = [c for c in repo.list() if c.scraper_adapter == args.county]
        if not counties:
            logger.error("No county found with adapter '%s'", args.county)
            return

        county = counties[0]
        scraper_cls = ScraperRegistry.get(args.county)
        if not scraper_cls:
            logger.error("No scraper registered for adapter '%s'", args.county)
            return

        scraper = scraper_cls(county=county, db=db)
        result = scraper.run()
        repo.update_last_scraped(county.id)
        logger.info("Done: %s", result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
