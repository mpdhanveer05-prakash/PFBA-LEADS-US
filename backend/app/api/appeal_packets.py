"""
Appeal packet API router.

Endpoints:
  POST   /packets/generate/{lead_score_id}   — generate PDF appeal packet
  GET    /packets                             — list packets (filterable)
  GET    /packets/{packet_id}/download        — stream the PDF bytes
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.appeal_packet import AppealPacket
from app.services.appeal_packet_service import AppealPacketService

router = APIRouter(prefix="/packets", tags=["appeal_packets"])

_svc = AppealPacketService()


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class PacketOut(BaseModel):
    id: uuid.UUID
    lead_score_id: uuid.UUID
    property_id: uuid.UUID
    county_id: uuid.UUID
    s3_key: Optional[str]
    generated_at: str
    claimed_value: Optional[str]
    evidence_comps: Optional[int]
    status: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, obj: AppealPacket) -> "PacketOut":
        return cls(
            id=obj.id,
            lead_score_id=obj.lead_score_id,
            property_id=obj.property_id,
            county_id=obj.county_id,
            s3_key=obj.s3_key,
            generated_at=obj.generated_at.isoformat(),
            claimed_value=str(obj.claimed_value) if obj.claimed_value is not None else None,
            evidence_comps=obj.evidence_comps,
            status=obj.status,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/generate/{lead_score_id}",
    response_model=PacketOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a PDF appeal packet for a lead",
)
def generate_packet(
    lead_score_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> PacketOut:
    """
    Build a professional 4-page PDF appeal packet (cover, analysis, comps,
    certification), upload it to MinIO, and return the packet record.

    Returns 404 if the lead score does not exist.
    Returns 503 if reportlab is not installed on the server.
    """
    try:
        packet = _svc.generate(lead_score_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    return PacketOut.from_orm_obj(packet)


@router.get(
    "",
    response_model=list[PacketOut],
    summary="List appeal packets",
)
def list_packets(
    lead_score_id: Optional[uuid.UUID] = Query(None, description="Filter by lead score ID"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[PacketOut]:
    """Return all appeal packets, ordered by generation date (newest first)."""
    stmt = select(AppealPacket).order_by(AppealPacket.generated_at.desc())
    if lead_score_id is not None:
        stmt = stmt.where(AppealPacket.lead_score_id == lead_score_id)
    packets = list(db.execute(stmt).scalars().all())
    return [PacketOut.from_orm_obj(p) for p in packets]


@router.get(
    "/{packet_id}/download",
    summary="Download the PDF for an appeal packet",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF file stream",
        },
        404: {"description": "Packet not found"},
        502: {"description": "Unable to retrieve PDF from storage"},
    },
)
def download_packet(
    packet_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream the PDF bytes for the given appeal packet directly from MinIO.

    Returns 404 if the packet record does not exist or has no stored PDF.
    Returns 502 if the MinIO download fails.
    """
    try:
        pdf_bytes = _svc.get_pdf_bytes(packet_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    import io  # noqa: PLC0415

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="appeal_packet_{packet_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
