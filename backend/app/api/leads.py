import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import csv, io

from app.api.deps import get_current_user
from app.database import get_db
from app.models.lead_score import PriorityTier
from app.schemas.auth import TokenData
from app.schemas.lead import LeadDetail, LeadListItem, LeadAssign, LeadVerify, PaginatedLeads
from app.services.lead_service import LeadService

router = APIRouter()


@router.get("/leads/map")
def get_leads_map(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
    tier: list[PriorityTier] | None = Query(None),
    county_id: uuid.UUID | None = None,
    data_source: str | None = Query(None, pattern="^(live|generated)$"),
):
    from sqlalchemy import select
    from app.models.assessment import Assessment
    from app.models.county import County
    from app.models.lead_score import LeadScore
    from app.models.property import Property

    _SEED_APN = r"^[A-Z]{2}-[0-9]{3}-[0-9]{4}-[0-9]{2}$"

    q = (
        select(
            LeadScore.id,
            Property.address,
            Property.city,
            Property.state,
            Property.latitude,
            Property.longitude,
            LeadScore.priority_tier,
            LeadScore.appeal_probability,
            LeadScore.estimated_savings,
            LeadScore.gap_pct,
            County.name.label("county_name"),
        )
        .join(Property, LeadScore.property_id == Property.id)
        .join(County, Property.county_id == County.id)
        .join(Assessment, LeadScore.assessment_id == Assessment.id)
        .where(Property.latitude.isnot(None), Property.longitude.isnot(None))
    )
    if tier:
        q = q.where(LeadScore.priority_tier.in_(tier))
    if county_id:
        q = q.where(Property.county_id == county_id)
    if data_source == "generated":
        q = q.where(Property.apn.op("~")(_SEED_APN))
    elif data_source == "live":
        q = q.where(~Property.apn.op("~")(_SEED_APN))
    q = q.limit(3000)

    rows = db.execute(q).all()
    return [
        {
            "id": str(r.id),
            "address": r.address,
            "city": r.city,
            "state": r.state,
            "lat": r.latitude,
            "lng": r.longitude,
            "tier": str(r.priority_tier),
            "probability": r.appeal_probability,
            "savings": float(r.estimated_savings or 0),
            "gap_pct": r.gap_pct,
            "county_name": r.county_name,
        }
        for r in rows
    ]


@router.get("/leads", response_model=PaginatedLeads)
def list_leads(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    tier: list[PriorityTier] | None = Query(None),
    county_id: uuid.UUID | None = None,
    property_type: str | None = None,
    min_gap_pct: float | None = None,
    min_estimated_savings: float | None = None,
    min_appeal_probability: float | None = None,
    sort_by: str = Query("scored_at", pattern="^(scored_at|gap_pct|appeal_probability|estimated_savings)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    data_source: str | None = Query(None, pattern="^(live|generated)$"),
):
    svc = LeadService(db)
    total, pending_count, verified_count, items = svc.list_leads(
        page=page, page_size=page_size, tier_filter=tier,
        county_id=county_id, property_type=property_type,
        min_gap_pct=min_gap_pct,
        min_estimated_savings=min_estimated_savings,
        min_appeal_probability=min_appeal_probability,
        sort_by=sort_by, sort_dir=sort_dir,
        data_source=data_source,
    )
    return PaginatedLeads(
        total=total, pending_count=pending_count, verified_count=verified_count,
        page=page, page_size=page_size, items=items,
    )


@router.get("/leads/{lead_id}", response_model=LeadDetail)
def get_lead(lead_id: uuid.UUID, db: Session = Depends(get_db), _: TokenData = Depends(get_current_user)):
    svc = LeadService(db)
    lead = svc.get_lead_detail(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("/leads/{lead_id}/assign")
def assign_lead(
    lead_id: uuid.UUID,
    body: LeadAssign,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    svc = LeadService(db)
    if not svc.assign_lead(lead_id, body.assigned_agent):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "assigned", "assigned_agent": body.assigned_agent}


@router.post("/leads/{lead_id}/verify")
def verify_lead(
    lead_id: uuid.UUID,
    body: LeadVerify,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    svc = LeadService(db)
    if not svc.verify_lead(lead_id, body.verified_by):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "verified", "verified_by": body.verified_by}


@router.post("/leads/{lead_id}/unverify")
def unverify_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    svc = LeadService(db)
    if not svc.unverify_lead(lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "unverified"}


@router.post("/leads/{lead_id}/export")
def export_lead(lead_id: uuid.UUID, db: Session = Depends(get_db), _: TokenData = Depends(get_current_user)):
    svc = LeadService(db)
    lead = svc.get_lead_detail(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    row = svc.export_lead_csv(lead)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row.keys()))
    writer.writeheader()
    writer.writerow(row)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lead_{lead_id}.csv"},
    )
