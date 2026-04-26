import io
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.county import County
from app.schemas.auth import TokenData
from app.services.ai_service import generate_appeal_letter, parse_nl_search
from app.services.lead_service import LeadService

router = APIRouter()


class NLSearchRequest(BaseModel):
    query: str


class BulkLetterRequest(BaseModel):
    lead_ids: list[uuid.UUID]


@router.post("/ai/generate-letter/{lead_id}")
def generate_letter(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    svc = LeadService(db)
    lead = svc.get_lead_detail(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Pull county metadata for deadline/approval rate context
    from app.models.property import Property as PropModel
    prop = db.get(PropModel, lead.property_id)
    county = db.get(County, prop.county_id) if prop else None

    lead_dict = lead.model_dump()
    lead_dict["comparable_sales"] = [c.model_dump() for c in lead.comparable_sales]
    if county:
        lead_dict["appeal_deadline_days"] = county.appeal_deadline_days
        lead_dict["approval_rate_hist"] = county.approval_rate_hist

    try:
        letter = generate_appeal_letter(lead_dict)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

    return {"letter": letter, "lead_id": str(lead_id)}


@router.post("/ai/nl-search")
def nl_search(
    body: NLSearchRequest,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    county_rows = db.execute(select(County.name, County.id)).all()
    county_names = [r.name for r in county_rows]
    county_map = {r.name: str(r.id) for r in county_rows}

    try:
        result = parse_nl_search(body.query, county_names)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"NL parsing failed: {e}")

    # Resolve county name → id
    if "county_name" in result:
        cname = result.pop("county_name")
        cid = county_map.get(cname)
        if cid:
            result["county_id"] = cid

    return result


@router.post("/ai/bulk-letters")
def bulk_letters(
    body: BulkLetterRequest,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    if not body.lead_ids:
        raise HTTPException(status_code=400, detail="No lead IDs provided")
    if len(body.lead_ids) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 leads per bulk export")

    svc = LeadService(db)
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for lead_id in body.lead_ids:
            lead = svc.get_lead_detail(lead_id)
            if not lead:
                continue

            from app.models.property import Property as PropModel
            prop = db.get(PropModel, lead.property_id)
            county = db.get(County, prop.county_id) if prop else None

            lead_dict = lead.model_dump()
            lead_dict["comparable_sales"] = [c.model_dump() for c in lead.comparable_sales]
            if county:
                lead_dict["appeal_deadline_days"] = county.appeal_deadline_days
                lead_dict["approval_rate_hist"] = county.approval_rate_hist

            try:
                letter = generate_appeal_letter(lead_dict)
            except Exception as e:
                letter = f"[Letter generation failed: {e}]"

            safe_addr = lead.address.replace("/", "-").replace("\\", "-")[:50]
            zf.writestr(f"{safe_addr} - {lead.city}.txt", letter)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=appeal_letters.zip"},
    )
