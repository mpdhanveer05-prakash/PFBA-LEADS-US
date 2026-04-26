import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.appeal import AppealCreate, AppealRead, AppealUpdate
from app.schemas.auth import TokenData
from app.services.appeal_service import AppealService

router = APIRouter()


@router.get("/appeals", response_model=list[AppealRead])
def list_appeals(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
):
    return AppealService(db).list_appeals(status_filter=status)


@router.post("/appeals", response_model=AppealRead, status_code=201)
def create_appeal(body: AppealCreate, db: Session = Depends(get_db), _: TokenData = Depends(get_current_user)):
    return AppealService(db).create_appeal(body)


@router.patch("/appeals/{appeal_id}", response_model=AppealRead)
def update_appeal(appeal_id: uuid.UUID, body: AppealUpdate, db: Session = Depends(get_db), _: TokenData = Depends(get_current_user)):
    appeal = AppealService(db).update_appeal(appeal_id, body)
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    return appeal
