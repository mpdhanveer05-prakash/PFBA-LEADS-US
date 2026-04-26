"""
Generic stub scraper used by all counties that don't have a custom adapter.
Returns empty results — populate via the Sync UI (seed data path).
"""
from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper


class GenericStubScraper(BaseCountyScraper):
    adapter_name = "generic"

    def run(self, limit: int = 500) -> dict:  # noqa: ARG002
        return {"records_fetched": 0, "records_changed": 0}

    def process_record(self, apn: str, raw_data: dict, db: Session) -> dict:  # noqa: ARG002
        return {"changed": False}
