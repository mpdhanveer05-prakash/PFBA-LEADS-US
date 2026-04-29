from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from app.models.appeal import Appeal, AppealStatus
from app.models.county import County
from app.models.lead_score import LeadScore, PriorityTier
from app.models.property import Property


_SEED_APN = r"^[A-Z]{2}-[0-9]{3}-[0-9]{4}-[0-9]{2}$"


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _apn_filter(self, q, data_source: str | None):
        if data_source == "generated":
            return q.where(Property.apn.op("~")(_SEED_APN))
        if data_source == "live":
            return q.where(~Property.apn.op("~")(_SEED_APN))
        return q

    def get_summary_stats(self, data_source: str | None = None) -> dict:
        base_q = (
            select(LeadScore.id)
            .join(Property, LeadScore.property_id == Property.id)
            .where(Property.is_dnc == False)
        )
        base_q = self._apn_filter(base_q, data_source)
        filtered_ids = self._db.execute(base_q).scalars().all()

        if filtered_ids:
            id_filter = LeadScore.id.in_(filtered_ids)
        else:
            id_filter = LeadScore.id.in_([])

        total_leads = self._db.execute(
            select(func.count(LeadScore.id)).where(id_filter)
        ).scalar_one()

        total_savings = self._db.execute(
            select(func.sum(LeadScore.estimated_savings)).where(id_filter)
        ).scalar_one() or Decimal("0")

        avg_probability = self._db.execute(
            select(func.avg(LeadScore.appeal_probability)).where(id_filter)
        ).scalar_one() or 0.0

        urgent_cutoff = datetime.now(timezone.utc) + timedelta(days=30)
        urgent_deadlines = self._db.execute(
            select(func.count(Appeal.id)).where(
                Appeal.deadline_date <= urgent_cutoff.date(),
                Appeal.status.notin_([AppealStatus.WON, AppealStatus.LOST, AppealStatus.WITHDRAWN]),
            )
        ).scalar_one()

        tier_counts = self._db.execute(
            select(LeadScore.priority_tier, func.count(LeadScore.id))
            .where(id_filter)
            .group_by(LeadScore.priority_tier)
        ).all()

        appeal_status_counts = self._db.execute(
            select(Appeal.status, func.count(Appeal.id)).group_by(Appeal.status)
        ).all()

        # ROI metrics
        total_savings_f = float(total_savings)
        agency_fees = round(total_savings_f * 0.10, 2)
        avg_savings = round(total_savings_f / total_leads, 2) if total_leads else 0.0
        tier_a_count = next((c for t, c in tier_counts if str(t) == "A"), 0)

        # County over-assessment comparison (top 10)
        county_q = (
            select(
                County.name.label("county"),
                County.state,
                func.count(LeadScore.id).label("lead_count"),
                func.avg(LeadScore.gap_pct).label("avg_gap_pct"),
                func.sum(LeadScore.estimated_savings).label("total_savings"),
            )
            .join(Property, Property.county_id == County.id)
            .join(LeadScore, LeadScore.property_id == Property.id)
            .where(id_filter)
            .group_by(County.id)
            .order_by(desc(func.avg(LeadScore.gap_pct)))
            .limit(10)
        )
        county_rows = self._db.execute(county_q).all()

        county_comparison = [
            {
                "county": f"{r.county}, {r.state}",
                "lead_count": r.lead_count,
                "avg_gap_pct": round(float(r.avg_gap_pct or 0) * 100, 1),
                "total_savings": float(r.total_savings or 0),
            }
            for r in county_rows
        ]

        return {
            "total_leads": total_leads,
            "total_estimated_savings": total_savings_f,
            "avg_appeal_probability": round(float(avg_probability), 4),
            "urgent_deadlines": urgent_deadlines,
            "tier_distribution": {str(tier): count for tier, count in tier_counts},
            "appeal_status_counts": {str(status): count for status, count in appeal_status_counts},
            # ROI
            "agency_fees_estimate": agency_fees,
            "avg_savings_per_lead": avg_savings,
            "tier_a_count": tier_a_count,
            # County comparison
            "county_comparison": county_comparison,
        }
