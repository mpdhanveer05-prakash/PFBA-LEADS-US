import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appeal import Appeal, AppealStatus
from app.schemas.appeal import AppealCreate, AppealRead, AppealUpdate


class AppealService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_appeals(self, status_filter: str | None = None) -> list[Appeal]:
        q = select(Appeal)
        if status_filter:
            q = q.where(Appeal.status == status_filter)
        return list(self._db.execute(q.order_by(Appeal.created_at.desc())).scalars().all())

    def create_appeal(self, schema: AppealCreate) -> Appeal:
        appeal = Appeal(**schema.model_dump())
        self._db.add(appeal)
        self._db.commit()
        self._db.refresh(appeal)
        return appeal

    def update_appeal(self, appeal_id: uuid.UUID, schema: AppealUpdate) -> Appeal | None:
        appeal = self._db.get(Appeal, appeal_id)
        if not appeal:
            return None
        for field, value in schema.model_dump(exclude_none=True).items():
            setattr(appeal, field, value)
        self._db.commit()
        self._db.refresh(appeal)
        return appeal
