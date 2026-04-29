import uuid
from typing import Any

from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.assessment import Assessment
from app.models.comparable_sale import ComparableSale
from app.models.county import County
from app.models.lead_score import LeadScore, PriorityTier
from app.models.property import Property
from datetime import datetime, timezone

from app.models.assessment import Assessment as AssessmentModel
from app.schemas.lead import AssessmentHistoryItem, LeadDetail, LeadListItem


_SORT_COLUMNS = {
    "scored_at": LeadScore.scored_at,
    "gap_pct": LeadScore.gap_pct,
    "appeal_probability": LeadScore.appeal_probability,
    "estimated_savings": LeadScore.estimated_savings,
}


class LeadService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_leads(
        self,
        page: int,
        page_size: int,
        tier_filter: list[PriorityTier] | None,
        county_id: uuid.UUID | None,
        property_type: str | None,
        sort_by: str,
        sort_dir: str,
        min_gap_pct: float | None = None,
        min_estimated_savings: float | None = None,
        min_appeal_probability: float | None = None,
        data_source: str | None = None,
    ) -> tuple[int, list[dict]]:
        base_q = (
            select(
                LeadScore.id,
                LeadScore.property_id,
                LeadScore.assessment_id,
                Property.address,
                Property.city,
                Property.state,
                Property.property_type,
                Property.apn,
                County.name.label("county_name"),
                Assessment.assessed_total,
                LeadScore.market_value_est,
                LeadScore.gap_pct,
                LeadScore.appeal_probability,
                LeadScore.estimated_savings,
                LeadScore.priority_tier,
                LeadScore.scored_at,
                LeadScore.is_verified,
                LeadScore.verified_by,
                LeadScore.verified_at,
            )
            .join(Property, LeadScore.property_id == Property.id)
            .join(County, Property.county_id == County.id)
            .join(Assessment, LeadScore.assessment_id == Assessment.id)
        )

        if tier_filter:
            base_q = base_q.where(LeadScore.priority_tier.in_(tier_filter))
        if county_id:
            base_q = base_q.where(Property.county_id == county_id)
        if property_type:
            base_q = base_q.where(Property.property_type == property_type)
        if min_gap_pct is not None:
            base_q = base_q.where(LeadScore.gap_pct >= min_gap_pct)
        if min_estimated_savings is not None:
            from decimal import Decimal as D
            base_q = base_q.where(LeadScore.estimated_savings >= D(str(min_estimated_savings)))
        if min_appeal_probability is not None:
            base_q = base_q.where(LeadScore.appeal_probability >= min_appeal_probability)
        if data_source == "generated":
            base_q = base_q.where(Property.apn.op("~")(r"^[A-Z]{2}-[0-9]{3}-[0-9]{4}-[0-9]{2}$"))
        elif data_source == "live":
            base_q = base_q.where(~Property.apn.op("~")(r"^[A-Z]{2}-[0-9]{3}-[0-9]{4}-[0-9]{2}$"))

        total = self._db.execute(
            select(func.count()).select_from(base_q.subquery())
        ).scalar_one()

        sort_col = _SORT_COLUMNS.get(sort_by, LeadScore.scored_at)
        order = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
        rows = self._db.execute(
            base_q.order_by(order).offset((page - 1) * page_size).limit(page_size)
        ).all()

        items = [LeadListItem.model_validate(dict(r._mapping)) for r in rows]
        return total, items

    def get_lead_detail(self, lead_id: uuid.UUID) -> LeadDetail | None:
        row = self._db.execute(
            select(
                LeadScore,
                Property.address,
                Property.city,
                Property.state,
                Property.zip,
                Property.property_type,
                Property.apn,
                Property.building_sqft,
                Property.lot_size_sqft,
                Property.year_built,
                Property.bedrooms,
                Property.bathrooms,
                Property.owner_name,
                Property.owner_email,
                Property.owner_phone,
                Property.mailing_address,
                County.name.label("county_name"),
                Assessment.assessed_total,
            )
            .join(Property, LeadScore.property_id == Property.id)
            .join(County, Property.county_id == County.id)
            .join(Assessment, LeadScore.assessment_id == Assessment.id)
            .where(LeadScore.id == lead_id)
        ).first()

        if not row:
            return None

        (
            lead_score, address, city, state, zip_code, property_type,
            apn, building_sqft, lot_size_sqft, year_built, bedrooms, bathrooms,
            owner_name, owner_email, owner_phone, mailing_address,
            county_name, assessed_total,
        ) = row

        comps = self._db.execute(
            select(ComparableSale)
            .where(ComparableSale.property_id == lead_score.property_id)
            .order_by(ComparableSale.similarity_score.desc())
            .limit(10)
        ).scalars().all()

        history_rows = self._db.execute(
            select(AssessmentModel)
            .where(AssessmentModel.property_id == lead_score.property_id)
            .order_by(AssessmentModel.tax_year.desc())
        ).scalars().all()

        data = {
            "id": lead_score.id,
            "property_id": lead_score.property_id,
            "assessment_id": lead_score.assessment_id,
            "address": address,
            "city": city,
            "state": state,
            "zip": zip_code,
            "county_name": county_name,
            "property_type": property_type,
            "apn": apn,
            "building_sqft": building_sqft,
            "lot_size_sqft": lot_size_sqft,
            "year_built": year_built,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "owner_name": owner_name,
            "owner_email": owner_email,
            "owner_phone": owner_phone,
            "mailing_address": mailing_address,
            "assessed_total": assessed_total,
            "market_value_est": lead_score.market_value_est,
            "gap_pct": lead_score.gap_pct,
            "appeal_probability": lead_score.appeal_probability,
            "estimated_savings": lead_score.estimated_savings,
            "priority_tier": lead_score.priority_tier,
            "scored_at": lead_score.scored_at,
            "deadline_date": None,
            "assessment_gap": lead_score.assessment_gap,
            "shap_explanation": lead_score.shap_explanation,
            "model_version": lead_score.model_version,
            "comparable_sales": comps,
            "assessment_history": [AssessmentHistoryItem.model_validate(a) for a in history_rows],
        }
        return LeadDetail.model_validate(data)

    def assign_lead(self, lead_id: uuid.UUID, agent: str) -> bool:
        from app.models.appeal import Appeal, AppealStatus

        appeal = self._db.execute(
            select(Appeal)
            .join(LeadScore, Appeal.lead_score_id == LeadScore.id)
            .where(LeadScore.id == lead_id)
            .limit(1)
        ).scalars().first()

        if not appeal:
            lead = self._db.get(LeadScore, lead_id)
            if not lead:
                return False
            appeal = Appeal(
                lead_score_id=lead_id,
                status=AppealStatus.ASSIGNED,
                assigned_agent=agent,
            )
            self._db.add(appeal)
        else:
            appeal.assigned_agent = agent
            appeal.status = AppealStatus.ASSIGNED

        self._db.commit()
        return True

    def verify_lead(self, lead_id: uuid.UUID, verified_by: str) -> bool:
        lead = self._db.get(LeadScore, lead_id)
        if not lead:
            return False
        lead.is_verified = True
        lead.verified_by = verified_by
        lead.verified_at = datetime.now(timezone.utc)
        self._db.commit()
        return True

    def unverify_lead(self, lead_id: uuid.UUID) -> bool:
        lead = self._db.get(LeadScore, lead_id)
        if not lead:
            return False
        lead.is_verified = False
        lead.verified_by = None
        lead.verified_at = None
        self._db.commit()
        return True

    def export_lead_csv(self, lead: LeadDetail) -> dict:
        return {
            "id": str(lead.id),
            "address": lead.address,
            "county": lead.county_name,
            "assessed_total": str(lead.assessed_total),
            "market_value_est": str(lead.market_value_est),
            "gap_pct": lead.gap_pct,
            "appeal_probability": lead.appeal_probability,
            "estimated_savings": str(lead.estimated_savings),
            "priority_tier": lead.priority_tier,
        }
