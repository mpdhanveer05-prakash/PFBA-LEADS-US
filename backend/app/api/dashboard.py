from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.auth import TokenData
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    _: TokenData = Depends(get_current_user),
    data_source: str | None = Query(None, pattern="^(live|generated)$"),
) -> dict:
    return DashboardService(db).get_summary_stats(data_source=data_source)
