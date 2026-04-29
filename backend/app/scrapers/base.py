from __future__ import annotations

import abc
import hashlib
import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.county import County

logger = logging.getLogger(__name__)

_RETRY_STATUS = {429, 503, 502, 504}
_MAX_RETRIES = 2
_BASE_DELAY = 0.5


def to_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None


def to_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def geocode_address(address: str, city: str, state: str) -> tuple[float, float] | None:
    """Geocode via Nominatim (OpenStreetMap). Free, no key, 1 req/sec limit."""
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{address}, {city}, {state}, USA", "format": "json", "limit": 1},
            headers={"User-Agent": "Pathfinder/1.0 (property-tax-appeals)"},
            timeout=10,
        )
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None


def _send_slack_alert(message: str) -> None:
    if not settings.slack_webhook_url:
        return
    try:
        httpx.post(settings.slack_webhook_url, json={"text": message}, timeout=5)
    except Exception:
        logger.warning("Failed to send Slack alert")


_CIRCUIT_BREAK_AFTER = 2  # fail fast after this many consecutive transport errors


class BaseCountyScraper(abc.ABC):
    adapter_name: str = ""
    # Set to False in subclasses whose government sites have cert mismatches
    _VERIFY_SSL: bool = True

    def __init__(self, county: County, db: Session) -> None:
        self.county = county
        self.db = db
        self._transport_errors = 0  # consecutive network failures
        self._client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            verify=self._VERIFY_SSL,
        )

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def fetch(self, url: str, **kwargs: Any) -> httpx.Response:
        # Circuit-breaker: once enough consecutive failures seen, skip network entirely
        if self._transport_errors >= _CIRCUIT_BREAK_AFTER:
            raise httpx.TransportError(f"Circuit open after {self._transport_errors} failures")

        delay = _BASE_DELAY
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self._client.get(url, **kwargs)
                if resp.status_code in _RETRY_STATUS:
                    logger.warning(
                        "HTTP %s from %s (attempt %d/%d), backing off %.1fs",
                        resp.status_code, url, attempt, _MAX_RETRIES, delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                resp.raise_for_status()
                self._transport_errors = 0  # reset on success
                return resp
            except httpx.TransportError as exc:
                self._transport_errors += 1
                if attempt == _MAX_RETRIES:
                    raise
                logger.warning("Transport error on %s (attempt %d): %s", url, attempt, exc)
                time.sleep(delay)
                delay = min(delay * 2, 120)
        raise RuntimeError(f"Failed to fetch {url} after {_MAX_RETRIES} retries")

    def fetch_and_store(self, url: str, county_slug: str, apn: str, extension: str = "html", **kwargs: Any) -> tuple[httpx.Response, str]:
        """Fetch a URL and store the raw content in MinIO. Returns (response, s3_key)."""
        from app.services.storage_service import upload_raw
        resp = self.fetch(url, **kwargs)
        s3_key = upload_raw(county_slug, apn, resp.content, extension)
        return resp, s3_key

    def alert(self, message: str) -> None:
        logger.error(message)
        _send_slack_alert(f":warning: *Pathfinder Scraper* | {self.county.name}: {message}")

    @staticmethod
    def hash_record(data: dict) -> str:
        content = str(sorted(data.items())).encode()
        return hashlib.sha256(content).hexdigest()

    @abc.abstractmethod
    def run(self, limit: int = 500) -> dict:
        """Execute the full scrape for this county. Return summary stats."""

    @abc.abstractmethod
    def process_record(self, apn: str, raw_data: dict, db: Session) -> dict:
        """Process a single raw property record. Must be idempotent."""
