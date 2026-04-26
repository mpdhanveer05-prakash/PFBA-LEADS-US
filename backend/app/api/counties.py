from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.schemas.auth import TokenData
from app.schemas.county import CountyCreate, CountyRead, CountyWithStats
from app.services.county_repository import CountyRepository

router = APIRouter()


@router.get("/counties", response_model=list[CountyWithStats])
def list_counties(db: Session = Depends(get_db), _: TokenData = Depends(get_current_user)):
    return CountyRepository(db).list_with_stats()


@router.post("/counties", response_model=CountyRead, status_code=201)
def create_county(
    body: CountyCreate,
    db: Session = Depends(get_db),
    _: TokenData = Depends(require_role("admin")),
):
    return CountyRepository(db).create(body)


@router.get("/counties/{county_id}", response_model=CountyWithStats)
def get_county(county_id: str, db: Session = Depends(get_db), _: TokenData = Depends(get_current_user)):
    county = CountyRepository(db).get_with_stats(county_id)
    if not county:
        raise HTTPException(status_code=404, detail="County not found")
    return county
