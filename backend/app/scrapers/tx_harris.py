"""
Harris County, TX — Harris Central Appraisal District (HCAD).

Uses the HCAD public property search at public.hcad.org.
Discovery: POST search by zip code → parse HTML for account numbers
Detail:    GET details page per account → parse HTML tables
Rate limit: 0.75s between requests.

Reference: https://hcad.org/property-records/
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.scrapers.base import BaseCountyScraper, geocode_address, to_decimal, to_int
from app.services.assessment_repository import AssessmentRepository
from app.services.property_repository import PropertyRepository
from app.schemas.property import PropertyCreate

logger = logging.getLogger(__name__)

_BASE = "https://public.hcad.org"
_SEARCH_URL = f"{_BASE}/records/searchval.asp"
_DETAIL_URL = f"{_BASE}/records/details.asp"

# Major Houston zip codes covering highest appeal-potential areas
_HOUSTON_ZIPS = [
    "77001", "77002", "77003", "77004", "77005", "77006", "77007", "77008",
    "77009", "77010", "77011", "77012", "77013", "77014", "77015", "77016",
    "77017", "77018", "77019", "77020", "77021", "77022", "77023", "77024",
    "77025", "77026", "77027", "77028", "77029", "77030",
    "77031", "77033", "77035", "77036",
    "77040", "77041", "77042", "77043", "77045", "77046",
    "77055", "77056", "77057",
    "77063", "77064", "77065",
    "77071", "77074", "77075",
    "77080", "77081", "77082", "77083", "77084",
    "77090", "77092", "77094", "77095",
    "77096", "77098", "77099",
]


class HarrisCountyScraper(BaseCountyScraper):
    adapter_name = "harris_tx"
    _VERIFY_SSL = False

    def run(self, limit: int = 500) -> dict:
        records_fetched = 0
        records_changed = 0
        errors = 0

        accounts = self._discover_accounts(limit)
        logger.info("HCAD: discovered %d account numbers", len(accounts))

        for account in accounts:
            try:
                raw = self._fetch_property(account)
                if not raw or not raw.get("apn"):
                    continue
                records_fetched += 1

                result = self.process_record(apn=raw["apn"], raw_data=raw, db=self.db)
                if result.get("changed"):
                    records_changed += 1

                time.sleep(0.75)
            except Exception:
                logger.exception("HCAD: error processing account %s", account)
                errors += 1

        return {"records_fetched": records_fetched, "records_changed": records_changed, "errors": errors}

    def _discover_accounts(self, limit: int) -> list[str]:
        """
        POST to HCAD search by zip code, parse HTML result for account numbers.
        """
        accounts: list[str] = []
        per_zip = max(5, limit // len(_HOUSTON_ZIPS) + 1)

        for zip_code in _HOUSTON_ZIPS:
            if len(accounts) >= limit:
                break
            try:
                # HCAD search form POST — searchtype "a" = address/zip search
                resp = self._client.post(
                    _SEARCH_URL,
                    data={
                        "searchtype": "a",
                        "searchval": zip_code,
                        "taxyear": "2024",
                        "action": "Search",
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": f"{_BASE}/records/index.asp",
                        "Origin": _BASE,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                # HCAD search results table — each row has an account link
                found = 0
                for link in soup.select("a[href*='acct='], a[href*='account=']"):
                    href = link.get("href", "")
                    acct = self._extract_param(href, "acct") or self._extract_param(href, "account")
                    if acct and acct not in accounts:
                        accounts.append(acct)
                        found += 1
                        if found >= per_zip:
                            break

                # Also try table rows with account numbers in first column
                if found == 0:
                    for row in soup.select("table.resultstable tr, table tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            first = cells[0].get_text(strip=True)
                            if first and first.isdigit() and len(first) >= 10:
                                if first not in accounts:
                                    accounts.append(first)
                                    found += 1
                                    if found >= per_zip:
                                        break

                time.sleep(0.75)
            except Exception:
                logger.warning("HCAD: zip search failed for %s", zip_code)

        return accounts[:limit]

    def _extract_param(self, url: str, param: str) -> str | None:
        """Extract a query parameter value from a URL string."""
        key = f"{param}="
        if key in url:
            start = url.index(key) + len(key)
            end = url.find("&", start)
            return url[start:] if end == -1 else url[start:end]
        return None

    def _fetch_property(self, account: str) -> dict | None:
        """
        GET /records/details.asp?crypt=&acct=ACCOUNT&taxyear=2024
        Parse the HTML detail page for property attributes.
        """
        try:
            resp = self.fetch(
                _DETAIL_URL,
                params={"crypt": "", "acct": account, "taxyear": "2024"},
            )
            return self._parse_detail(account, resp.text)
        except Exception:
            logger.exception("HCAD: detail fetch failed for account %s", account)
            return None

    def _parse_detail(self, account: str, html: str) -> dict | None:
        soup = BeautifulSoup(html, "lxml")
        rows: dict[str, str] = {}

        # HCAD detail page uses labeled table rows — collect all label→value pairs
        for tr in soup.select("table tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower().strip(":").strip()
                value = cells[1].get_text(strip=True)
                if label and value:
                    rows[label] = value

        if not rows:
            return None

        def pick(*keys: str) -> str | None:
            for k in keys:
                v = rows.get(k)
                if v and v not in ("-", "N/A", ""):
                    return v
            return None

        # Address
        address = pick("site address", "property address", "situs address", "address")
        if not address:
            return None

        city_state = pick("city, state, zip", "city/state/zip", "city") or "HOUSTON, TX"
        city = "HOUSTON"
        zip_code = ""
        if "," in city_state:
            parts = [p.strip() for p in city_state.split(",")]
            city = parts[0].title()
            if len(parts) >= 2:
                # "TX 77001" or "TX, 77001"
                last = parts[-1].strip()
                tokens = last.split()
                for t in tokens:
                    if t.isdigit() and len(t) == 5:
                        zip_code = t
                        break

        # Property type from state code or description
        state_class = (pick("state class", "state cd", "property class", "property type") or "").upper()
        if any(k in state_class for k in ("A1", "A2", "A3", "A4", "RESIDENTIAL", "SINGLE")):
            prop_type = "RESIDENTIAL"
        elif any(k in state_class for k in ("B", "C", "F", "COMMERCIAL", "OFFICE", "INDUSTRIAL")):
            prop_type = "COMMERCIAL"
        else:
            prop_type = "RESIDENTIAL"

        total_val_str = pick(
            "appraised value", "total appraised", "market value", "total value",
            "appraised", "total appr value"
        ) or "0"
        assessed_total = to_decimal(total_val_str.replace(",", "").replace("$", ""))
        if not assessed_total or assessed_total <= 0:
            return None

        land_val = to_decimal(
            (pick("land value", "land appraised", "land") or "0").replace(",", "").replace("$", "")
        )
        imprv_val = to_decimal(
            (pick("improvement value", "impr value", "improvement") or "0").replace(",", "").replace("$", "")
        )

        owner_name = pick("owner name", "owner", "property owner")
        if owner_name:
            owner_name = owner_name.strip().title()

        building_sqft = to_int((pick("building area", "living area", "bldg sqft", "sqft") or "").replace(",", ""))
        year_built = to_int(pick("year built", "yr built", "year"))

        # Geocode — HCAD detail pages rarely include coordinates
        lat: float | None = None
        lng: float | None = None
        if address and city:
            coords = geocode_address(address, city, "TX")
            if coords:
                lat, lng = coords
            time.sleep(1.1)

        return {
            "apn": account,
            "address": address,
            "city": city,
            "state": "TX",
            "zip": zip_code,
            "property_type": prop_type,
            "building_sqft": building_sqft,
            "year_built": year_built,
            "owner_name": owner_name or None,
            "assessed_total": assessed_total,
            "assessed_land": land_val,
            "assessed_improvement": imprv_val,
            "tax_year": 2024,
            "latitude": lat,
            "longitude": lng,
        }

    def process_record(self, apn: str, raw_data: dict, db: Session) -> dict:
        prop_repo = PropertyRepository(db)
        assess_repo = AssessmentRepository(db)

        prop = prop_repo.upsert(
            self.county.id,
            PropertyCreate(
                county_id=self.county.id,
                apn=apn,
                address=raw_data.get("address", ""),
                city=raw_data.get("city", ""),
                state="TX",
                zip=raw_data.get("zip", ""),
                property_type=raw_data.get("property_type", "RESIDENTIAL"),
                building_sqft=raw_data.get("building_sqft"),
                year_built=raw_data.get("year_built"),
                owner_name=raw_data.get("owner_name"),
                latitude=raw_data.get("latitude"),
                longitude=raw_data.get("longitude"),
            ),
        )

        hash_data = {k: str(v) for k, v in raw_data.items() if v is not None and k not in ("latitude", "longitude")}
        data_hash = self.hash_record(hash_data)
        tax_year = int(raw_data.get("tax_year") or 2024)
        changed = assess_repo.has_changed(prop.id, tax_year, data_hash)

        if changed:
            assess_repo.create(
                property_id=prop.id,
                tax_year=tax_year,
                assessed_total=raw_data["assessed_total"],
                assessed_land=raw_data.get("assessed_land"),
                assessed_improvement=raw_data.get("assessed_improvement"),
                data_hash=data_hash,
            )

        return {"changed": changed}
