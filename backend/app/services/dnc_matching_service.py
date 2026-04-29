"""Match DNC entries against properties in the database."""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.property import Property

logger = logging.getLogger(__name__)

_PHONE_STRIP = re.compile(r"[^\d]")
_SPACE_COLLAPSE = re.compile(r"\s+")
_APN_STRIP = re.compile(r"[\s\-]")


def _norm_phone(p: str | None) -> str:
    return _PHONE_STRIP.sub("", p or "")


def _norm_apn(a: str | None) -> str:
    return _APN_STRIP.sub("", a or "").upper()


def _norm_address(a: str | None) -> str:
    if not a:
        return ""
    a = a.lower().strip()
    a = re.sub(r"[.,#]", " ", a)
    return _SPACE_COLLAPSE.sub(" ", a).strip()


@dataclass
class MatchResult:
    entry_index: int
    property_id: uuid.UUID
    apn: str
    address: str
    city: str
    state: str
    owner_name: str | None
    match_reason: str  # "email" | "phone" | "apn" | "address" | "name"


def match_entries(db: Session, records: list[dict]) -> list[MatchResult]:
    """
    Try to match each DNC record against a property.
    Returns one MatchResult per matched property (deduped by property_id).
    """
    results: list[MatchResult] = []
    seen: set[str] = set()

    for idx, rec in enumerate(records):
        m = _try_match(db, rec)
        if m and str(m.property_id) not in seen:
            m.entry_index = idx
            results.append(m)
            seen.add(str(m.property_id))

    return results


def _row_to_result(row: tuple, idx: int, reason: str) -> MatchResult:
    pid, apn, address, city, state, owner = row
    return MatchResult(idx, pid, apn, address, city, state, owner, reason)


def _try_match(db: Session, rec: dict) -> MatchResult | None:
    _COLS = (
        Property.id, Property.apn, Property.address,
        Property.city, Property.state, Property.owner_name,
    )

    # 1 — Email (exact, case-insensitive)
    email = (rec.get("email") or "").strip().lower()
    if email:
        row = db.execute(
            select(*_COLS).where(func.lower(Property.owner_email) == email)
        ).first()
        if row:
            return _row_to_result(row, 0, "email")

    # 2 — Phone (digits-only normalisation, PostgreSQL regexp_replace)
    phone = _norm_phone(rec.get("phone"))
    if len(phone) >= 7:
        row = db.execute(
            select(*_COLS).where(
                func.regexp_replace(Property.owner_phone, r"[^\d]", "", "g") == phone
            )
        ).first()
        if row:
            return _row_to_result(row, 0, "phone")

    # 3 — APN (strip dashes/spaces, case-insensitive)
    apn = _norm_apn(rec.get("apn"))
    if apn:
        row = db.execute(
            select(*_COLS).where(
                func.upper(
                    func.regexp_replace(Property.apn, r"[\s\-]", "", "g")
                ) == apn
            )
        ).first()
        if row:
            return _row_to_result(row, 0, "apn")

    # 4 — Address (normalised substring match + state filter if available)
    addr = _norm_address(rec.get("address"))
    if len(addr) >= 8:
        q = select(*_COLS).where(
            func.lower(
                func.regexp_replace(Property.address, r"[.,#]", " ", "g")
            ).ilike(f"%{addr[:60]}%")
        )
        row = db.execute(q).first()
        if row:
            return _row_to_result(row, 0, "address")

    # 5 — Owner name (exact title-case match — last resort)
    name = (rec.get("name") or "").strip()
    if len(name) >= 4:
        row = db.execute(
            select(*_COLS).where(
                func.lower(Property.owner_name) == name.lower()
            )
        ).first()
        if row:
            return _row_to_result(row, 0, "name")

    return None
