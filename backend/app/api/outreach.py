"""
Outreach campaign API router.

Endpoints:
  POST   /outreach/generate/{lead_score_id}          — generate draft campaign
  GET    /outreach/campaigns                          — list campaigns (filterable)
  POST   /outreach/campaigns/{campaign_id}/send       — send email
  PATCH  /outreach/campaigns/{campaign_id}/status     — update status
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.outreach_campaign import OutreachCampaign
from app.services.outreach_service import OutreachService

router = APIRouter(prefix="/outreach", tags=["outreach"])

_svc = OutreachService()


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class CampaignOut(BaseModel):
    id: uuid.UUID
    lead_score_id: uuid.UUID
    property_id: uuid.UUID
    status: str
    channel: str
    recipient_email: Optional[str]
    recipient_phone: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    sent_at: Optional[str]
    opened_at: Optional[str]
    responded_at: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, obj: OutreachCampaign) -> "CampaignOut":
        return cls(
            id=obj.id,
            lead_score_id=obj.lead_score_id,
            property_id=obj.property_id,
            status=obj.status,
            channel=obj.channel,
            recipient_email=obj.recipient_email,
            recipient_phone=obj.recipient_phone,
            subject=obj.subject,
            body=obj.body,
            sent_at=obj.sent_at.isoformat() if obj.sent_at else None,
            opened_at=obj.opened_at.isoformat() if obj.opened_at else None,
            responded_at=obj.responded_at.isoformat() if obj.responded_at else None,
            created_at=obj.created_at.isoformat(),
        )


class StatusUpdate(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/generate/{lead_score_id}",
    response_model=CampaignOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a draft outreach campaign for a lead",
)
def generate_campaign(
    lead_score_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> CampaignOut:
    """
    Build a professional pitch email (status=DRAFT) for the given lead score
    and persist it. The email is NOT sent automatically — use the /send endpoint.
    """
    try:
        campaign = _svc.generate_campaign(lead_score_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return CampaignOut.from_orm_obj(campaign)


@router.get(
    "/campaigns",
    response_model=list[CampaignOut],
    summary="List outreach campaigns",
)
def list_campaigns(
    lead_score_id: Optional[uuid.UUID] = Query(None, description="Filter by lead score ID"),
    campaign_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[CampaignOut]:
    """Return campaigns ordered by creation date (newest first)."""
    campaigns = _svc.list_campaigns(db, lead_score_id=lead_score_id, status=campaign_status)
    return [CampaignOut.from_orm_obj(c) for c in campaigns]


@router.post(
    "/campaigns/{campaign_id}/send",
    response_model=CampaignOut,
    summary="Send a campaign email via SMTP",
)
def send_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> CampaignOut:
    """
    Send the campaign email. Requires SMTP_HOST, SMTP_PORT, SMTP_USER, and
    SMTP_PASS environment variables to be configured on the server.

    Returns 404 if the campaign does not exist.
    Returns 422 if SMTP is not configured or the recipient email is missing.
    """
    try:
        campaign = _svc.send_campaign(campaign_id, db)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SMTP delivery failed: {exc}",
        )
    return CampaignOut.from_orm_obj(campaign)


@router.patch(
    "/campaigns/{campaign_id}/status",
    response_model=CampaignOut,
    summary="Update campaign status",
)
def update_status(
    campaign_id: uuid.UUID,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> CampaignOut:
    """
    Update the status of a campaign (e.g. RESPONDED, OPTED_OUT, OPENED).
    Timestamps (opened_at, responded_at) are set automatically when applicable.
    """
    valid_statuses = {"DRAFT", "SENT", "OPENED", "RESPONDED", "OPTED_OUT"}
    if body.status.upper() not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status '{body.status}'. Must be one of: {', '.join(sorted(valid_statuses))}",
        )
    try:
        campaign = _svc.update_status(campaign_id, body.status, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return CampaignOut.from_orm_obj(campaign)
