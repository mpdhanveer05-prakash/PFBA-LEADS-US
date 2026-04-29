"""DNC (Do Not Call) management endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.dnc_list import DncEntry, DncList
from app.models.property import Property
from app.schemas.auth import TokenData
from app.services.dnc_matching_service import match_entries
from app.services.dnc_parser_service import parse_file

router = APIRouter()

_MAX_UPLOAD_MB = 10


# ── Upload & Analyse ──────────────────────────────────────────────────────────

@router.post("/dnc/upload", status_code=201)
def upload_dnc_list(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_role("admin", "manager")),
):
    raw = file.file.read(_MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(raw) > _MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {_MAX_UPLOAD_MB} MB limit.")

    filename = file.filename or "upload"
    try:
        file_type, records = parse_file(filename, raw)
    except (ValueError, ImportError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not records:
        raise HTTPException(status_code=422, detail="File is empty or contains no valid records.")

    matches = match_entries(db, records)
    match_by_idx = {m.entry_index: m for m in matches}

    dnc_list = DncList(
        uploaded_by=current_user.sub,
        filename=filename,
        file_type=file_type,
        status="analysed",
        total_records=len(records),
        matched_count=len(matches),
    )
    db.add(dnc_list)
    db.flush()

    saved_entries: list[DncEntry] = []
    for idx, rec in enumerate(records):
        m = match_by_idx.get(idx)
        entry = DncEntry(
            dnc_list_id=dnc_list.id,
            raw_name=rec.get("name"),
            raw_email=rec.get("email"),
            raw_phone=rec.get("phone"),
            raw_address=rec.get("address"),
            raw_apn=rec.get("apn"),
            matched_property_id=m.property_id if m else None,
            match_reason=m.match_reason if m else None,
        )
        db.add(entry)
        saved_entries.append(entry)

    db.commit()
    db.refresh(dnc_list)

    preview = []
    for m in matches:
        e = saved_entries[m.entry_index]
        preview.append({
            "entry_id": str(e.id),
            "raw_name": e.raw_name,
            "raw_email": e.raw_email,
            "raw_phone": e.raw_phone,
            "raw_address": e.raw_address,
            "raw_apn": e.raw_apn,
            "matched_apn": m.apn,
            "matched_address": m.address,
            "matched_city": m.city,
            "matched_state": m.state,
            "matched_owner": m.owner_name,
            "match_reason": m.match_reason,
            "property_id": str(m.property_id),
        })

    return {
        "list_id": str(dnc_list.id),
        "filename": filename,
        "file_type": file_type,
        "total_records": len(records),
        "matched_count": len(matches),
        "status": "analysed",
        "matches": preview,
    }


# ── Apply DNC ─────────────────────────────────────────────────────────────────

@router.post("/dnc/lists/{list_id}/apply")
def apply_dnc_list(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: TokenData = Depends(require_role("admin", "manager")),
):
    dnc_list = db.get(DncList, list_id)
    if not dnc_list:
        raise HTTPException(status_code=404, detail="DNC list not found")
    if dnc_list.status == "applied":
        raise HTTPException(status_code=409, detail="Already applied")

    entries = db.execute(
        select(DncEntry)
        .where(DncEntry.dnc_list_id == list_id)
        .where(DncEntry.matched_property_id.isnot(None))
    ).scalars().all()

    now = datetime.now(timezone.utc)
    applied = 0
    for entry in entries:
        prop = db.get(Property, entry.matched_property_id)
        if prop and not prop.is_dnc:
            prop.is_dnc = True
            prop.dnc_at = now
            prop.dnc_list_id = list_id
            applied += 1

    dnc_list.status = "applied"
    db.commit()
    return {"applied": applied, "list_id": str(list_id), "status": "applied"}


# ── List all uploads ──────────────────────────────────────────────────────────

@router.get("/dnc/lists")
def list_dnc_lists(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    rows = db.execute(
        select(DncList).order_by(DncList.uploaded_at.desc())
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "filename": r.filename,
            "file_type": r.file_type,
            "status": r.status,
            "uploaded_by": r.uploaded_by,
            "total_records": r.total_records,
            "matched_count": r.matched_count,
            "uploaded_at": r.uploaded_at.isoformat(),
        }
        for r in rows
    ]


# ── Entries for one upload ────────────────────────────────────────────────────

@router.get("/dnc/lists/{list_id}/entries")
def get_dnc_entries(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    dnc_list = db.get(DncList, list_id)
    if not dnc_list:
        raise HTTPException(status_code=404, detail="DNC list not found")

    rows = db.execute(
        select(DncEntry, Property.address, Property.city, Property.state, Property.is_dnc)
        .outerjoin(Property, DncEntry.matched_property_id == Property.id)
        .where(DncEntry.dnc_list_id == list_id)
        .order_by(DncEntry.created_at)
    ).all()

    return [
        {
            "id": str(r.DncEntry.id),
            "raw_name": r.DncEntry.raw_name,
            "raw_email": r.DncEntry.raw_email,
            "raw_phone": r.DncEntry.raw_phone,
            "raw_address": r.DncEntry.raw_address,
            "raw_apn": r.DncEntry.raw_apn,
            "matched_property_id": str(r.DncEntry.matched_property_id) if r.DncEntry.matched_property_id else None,
            "match_reason": r.DncEntry.match_reason,
            "matched_address": r.address,
            "matched_city": r.city,
            "matched_state": r.state,
            "is_dnc_applied": bool(r.is_dnc) if r.is_dnc is not None else False,
        }
        for r in rows
    ]


# ── Active DNC properties ─────────────────────────────────────────────────────

@router.get("/dnc/properties")
def list_dnc_properties(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    rows = db.execute(
        select(
            Property.id,
            Property.apn,
            Property.address,
            Property.city,
            Property.state,
            Property.owner_name,
            Property.dnc_at,
            Property.dnc_list_id,
            DncList.filename.label("dnc_source"),
        )
        .outerjoin(DncList, Property.dnc_list_id == DncList.id)
        .where(Property.is_dnc == True)
        .order_by(Property.dnc_at.desc())
    ).all()

    return [
        {
            "id": str(r.id),
            "apn": r.apn,
            "address": r.address,
            "city": r.city,
            "state": r.state,
            "owner_name": r.owner_name,
            "dnc_at": r.dnc_at.isoformat() if r.dnc_at else None,
            "dnc_list_id": str(r.dnc_list_id) if r.dnc_list_id else None,
            "dnc_source": r.dnc_source,
        }
        for r in rows
    ]


# ── Remove DNC from one property ──────────────────────────────────────────────

@router.delete("/dnc/properties/{property_id}")
def remove_dnc_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: TokenData = Depends(require_role("admin", "manager")),
):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if not prop.is_dnc:
        raise HTTPException(status_code=409, detail="Property is not marked DNC")
    prop.is_dnc = False
    prop.dnc_at = None
    prop.dnc_list_id = None
    db.commit()
    return {"status": "removed", "property_id": str(property_id)}


# ── Delete entire upload (optionally unapply) ─────────────────────────────────

@router.delete("/dnc/lists/{list_id}")
def delete_dnc_list(
    list_id: uuid.UUID,
    unapply: bool = True,
    db: Session = Depends(get_db),
    _: TokenData = Depends(require_role("admin")),
):
    dnc_list = db.get(DncList, list_id)
    if not dnc_list:
        raise HTTPException(status_code=404, detail="DNC list not found")

    if unapply:
        props = db.execute(
            select(Property).where(Property.dnc_list_id == list_id)
        ).scalars().all()
        for prop in props:
            prop.is_dnc = False
            prop.dnc_at = None
            prop.dnc_list_id = None

    db.delete(dnc_list)
    db.commit()
    return {"status": "deleted", "list_id": str(list_id), "unapplied": unapply}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/dnc/stats")
def dnc_stats(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    total_dnc = db.execute(
        select(func.count(Property.id)).where(Property.is_dnc == True)
    ).scalar_one()
    total_lists = db.execute(select(func.count(DncList.id))).scalar_one()
    applied = db.execute(
        select(func.count(DncList.id)).where(DncList.status == "applied")
    ).scalar_one()
    return {
        "total_dnc_properties": total_dnc,
        "total_lists": total_lists,
        "applied_lists": applied,
    }
