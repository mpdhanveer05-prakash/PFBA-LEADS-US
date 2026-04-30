import uuid
from typing import Any

from sqlalchemy import select, func, desc, asc, case, or_
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
        _has_contact = case(
            (
                or_(
                    Property.owner_name.isnot(None),
                    Property.owner_email.isnot(None),
                    Property.owner_phone.isnot(None),
                ),
                True,
            ),
            else_=False,
        ).label("has_contact")

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
                _has_contact,
            )
            .join(Property, LeadScore.property_id == Property.id)
            .join(County, Property.county_id == County.id)
            .join(Assessment, LeadScore.assessment_id == Assessment.id)
        )

        base_q = base_q.where(Property.is_dnc == False)

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

        sub = base_q.subquery()
        total = self._db.execute(
            select(func.count()).select_from(sub)
        ).scalar_one()

        pending_count = self._db.execute(
            select(func.count()).select_from(sub).where(sub.c.is_verified == False)
        ).scalar_one()
        verified_count = total - pending_count

        sort_col = _SORT_COLUMNS.get(sort_by, LeadScore.scored_at)
        order = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
        rows = self._db.execute(
            base_q.order_by(order).offset((page - 1) * page_size).limit(page_size)
        ).all()

        items = [LeadListItem.model_validate(dict(r._mapping)) for r in rows]
        return total, pending_count, verified_count, items

    def get_lead_detail(self, lead_id: uuid.UUID) -> LeadDetail | None:
        row = self._db.execute(
            select(
                LeadScore,
                Property,
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

        lead_score, prop, county_name, assessed_total = row
        address = prop.address
        city = prop.city
        state = prop.state
        zip_code = prop.zip
        property_type = prop.property_type
        apn = prop.apn
        building_sqft = prop.building_sqft
        lot_size_sqft = prop.lot_size_sqft
        year_built = prop.year_built
        bedrooms = prop.bedrooms
        bathrooms = prop.bathrooms
        owner_name = prop.owner_name
        owner_email = prop.owner_email
        owner_phone = prop.owner_phone
        mailing_address = getattr(prop, "mailing_address", None)

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

    def export_leads_bulk(
        self,
        verified_only: bool = False,
        tier_filter: list[PriorityTier] | None = None,
        data_source: str | None = None,
    ):
        """
        Yield one dict per lead for bulk CSV export.
        Streams directly from the DB — no per-row detail fetches needed.
        """
        q = (
            select(
                LeadScore.id,
                LeadScore.priority_tier,
                LeadScore.appeal_probability,
                LeadScore.gap_pct,
                LeadScore.assessment_gap,
                LeadScore.market_value_est,
                LeadScore.estimated_savings,
                LeadScore.model_version,
                LeadScore.scored_at,
                LeadScore.is_verified,
                LeadScore.verified_by,
                LeadScore.verified_at,
                Property.apn,
                Property.address,
                Property.city,
                Property.state,
                Property.zip,
                Property.property_type,
                Property.building_sqft,
                Property.lot_size_sqft,
                Property.year_built,
                Property.bedrooms,
                Property.bathrooms,
                Property.owner_name,
                Property.owner_email,
                Property.owner_phone,
                County.name.label("county_name"),
                Assessment.assessed_total,
                Assessment.assessed_land,
                Assessment.assessed_improvement,
                Assessment.tax_amount,
                Assessment.tax_year,
            )
            .join(Property, LeadScore.property_id == Property.id)
            .join(County, Property.county_id == County.id)
            .join(Assessment, LeadScore.assessment_id == Assessment.id)
            .where(Property.is_dnc == False)
        )
        if verified_only:
            q = q.where(LeadScore.is_verified == True)
        if tier_filter:
            q = q.where(LeadScore.priority_tier.in_(tier_filter))
        if data_source == "generated":
            q = q.where(Property.apn.op("~")(r"^[A-Z]{2}-[0-9]{3}-[0-9]{4}-[0-9]{2}$"))
        elif data_source == "live":
            q = q.where(~Property.apn.op("~")(r"^[A-Z]{2}-[0-9]{3}-[0-9]{4}-[0-9]{2}$"))
        q = q.order_by(desc(LeadScore.appeal_probability))

        for row in self._db.execute(q).mappings():
            yield {
                "lead_id": str(row["id"]),
                "priority_tier": str(row["priority_tier"]),
                "appeal_probability": f"{(row['appeal_probability'] or 0) * 100:.1f}%",
                "gap_pct": f"{(row['gap_pct'] or 0) * 100:.1f}%",
                "assessed_total": str(row["assessed_total"] or ""),
                "assessed_land": str(row["assessed_land"] or ""),
                "assessed_improvement": str(row["assessed_improvement"] or ""),
                "tax_amount": str(row["tax_amount"] or ""),
                "tax_year": str(row["tax_year"] or ""),
                "market_value_est": str(row["market_value_est"] or ""),
                "assessment_gap": str(row["assessment_gap"] or ""),
                "estimated_savings": str(row["estimated_savings"] or ""),
                "model_version": row["model_version"] or "",
                "scored_at": row["scored_at"].isoformat() if row["scored_at"] else "",
                "is_verified": "Yes" if row["is_verified"] else "No",
                "verified_by": row["verified_by"] or "",
                "verified_at": row["verified_at"].isoformat() if row["verified_at"] else "",
                "apn": row["apn"] or "",
                "address": row["address"] or "",
                "city": row["city"] or "",
                "state": row["state"] or "",
                "zip": row["zip"] or "",
                "county": row["county_name"] or "",
                "property_type": row["property_type"] or "",
                "building_sqft": str(row["building_sqft"] or ""),
                "lot_size_sqft": str(row["lot_size_sqft"] or ""),
                "year_built": str(row["year_built"] or ""),
                "bedrooms": str(row["bedrooms"] or ""),
                "bathrooms": str(row["bathrooms"] or ""),
                "owner_name": row["owner_name"] or "",
                "owner_email": row["owner_email"] or "",
                "owner_phone": row["owner_phone"] or "",
            }
