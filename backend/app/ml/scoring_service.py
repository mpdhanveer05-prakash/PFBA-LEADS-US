"""Loads the XGBoost model once at startup and scores assessments."""
from __future__ import annotations

import logging
import statistics
import uuid
from decimal import Decimal
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.comparable_sale import ComparableSale
from app.models.county import County
from app.models.lead_score import LeadScore, PriorityTier
from app.models.property import Property

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model() -> Any:
    """Load XGBoost model from MLflow registry. Cached — loads once per process."""
    try:
        import mlflow.xgboost
        from app.config import settings

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        model = mlflow.xgboost.load_model("models:/pathfinder-appeal-scorer/Production")
        logger.info("XGBoost model loaded from MLflow registry")
        return model
    except Exception:
        logger.warning("MLflow model not available — using rule-based scoring fallback")
        return None


def _assign_tier(probability: float, gap_pct: float) -> PriorityTier:
    if probability >= 0.75 and gap_pct >= 0.15:
        return PriorityTier.A
    if probability >= 0.55 and gap_pct >= 0.10:
        return PriorityTier.B
    if probability >= 0.35 and gap_pct >= 0.05:
        return PriorityTier.C
    return PriorityTier.D


class ScoringService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._model = _load_model()

    def score_assessment(self, assessment_id: uuid.UUID) -> LeadScore:
        assessment = self._db.get(Assessment, assessment_id)
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} not found")

        prop = self._db.get(Property, assessment.property_id)
        county = self._db.get(County, prop.county_id)

        comps = list(
            self._db.execute(
                select(ComparableSale)
                .where(ComparableSale.property_id == prop.id)
                .order_by(ComparableSale.similarity_score.desc())
                .limit(5)
            ).scalars().all()
        )

        market_value = self._estimate_market_value(prop, comps)
        used_comps = market_value is not None
        if market_value is None:
            market_value = self._fallback_market_value(prop, county, assessment)

        assessed = float(assessment.assessed_total)

        if market_value and assessed > 0:
            gap = assessed - market_value
            gap_pct = gap / assessed
        else:
            gap = None
            gap_pct = 0.0

        probability, shap = self._predict(prop, county, assessment, comps, gap_pct)
        tier = _assign_tier(probability, gap_pct)

        tax_rate = 0.022
        estimated_savings = Decimal(str(round(gap * tax_rate, 2))) if gap and gap > 0 else None

        # Delete existing score for same assessment to allow re-scoring
        self._db.execute(
            LeadScore.__table__.delete().where(LeadScore.assessment_id == assessment_id)
        )

        if self._model:
            mv = "xgboost-v1"
        elif used_comps:
            mv = "rule-based-comps-v1"
        else:
            mv = "rule-based-no-comps-v1"

        score = LeadScore(
            property_id=prop.id,
            assessment_id=assessment_id,
            market_value_est=Decimal(str(round(market_value, 2))) if market_value else None,
            assessment_gap=Decimal(str(round(gap, 2))) if gap else None,
            gap_pct=round(gap_pct, 6),
            appeal_probability=round(probability, 6),
            estimated_savings=estimated_savings,
            priority_tier=tier,
            shap_explanation=shap,
            model_version=mv,
        )
        self._db.add(score)
        self._db.flush()
        return score

    def commit(self) -> None:
        self._db.commit()

    def _estimate_market_value(self, prop: Property, comps: list[ComparableSale]) -> float | None:
        prices = [float(c.price_per_sqft) for c in comps if c.price_per_sqft]
        if not prices or not prop.building_sqft:
            return None
        return statistics.median(prices) * prop.building_sqft

    def _fallback_market_value(self, prop, county, assessment) -> float | None:
        """Estimate market value without comps using assessed-value brackets and age."""
        assessed = float(assessment.assessed_total or 0)
        if assessed <= 0:
            return None

        # Over-assessment tends to be larger for higher-value properties
        if assessed >= 2_000_000:
            base_gap = 0.22
        elif assessed >= 1_000_000:
            base_gap = 0.18
        elif assessed >= 500_000:
            base_gap = 0.15
        else:
            base_gap = 0.12

        # Older buildings drift further from market value
        if prop.year_built:
            age = 2024 - int(prop.year_built)
            if age > 30:
                base_gap += 0.03
            elif age > 15:
                base_gap += 0.01

        # Counties with higher historical approval → systemic over-assessment
        approval_boost = float(county.approval_rate_hist or 0.30) * 0.10
        gap_pct = min(base_gap + approval_boost, 0.40)

        return assessed * (1.0 - gap_pct)

    def _predict(self, prop, county, assessment, comps, gap_pct) -> tuple[float, dict]:
        features = {
            "gap_pct": gap_pct,
            "building_sqft": prop.building_sqft or 0,
            "year_built": prop.year_built or 1980,
            "county_approval_rate": county.approval_rate_hist or 0.3,
            "days_to_deadline": county.appeal_deadline_days,
            "num_comps": len(comps),
            "comp_price_std_dev": self._std_dev([float(c.price_per_sqft or 0) for c in comps]),
        }

        if self._model:
            try:
                import pandas as pd
                import shap as shap_lib

                df = pd.DataFrame([features])
                prob = float(self._model.predict_proba(df)[0][1])
                explainer = shap_lib.TreeExplainer(self._model)
                shap_values = explainer(df)
                shap_dict = dict(zip(df.columns, shap_values.values[0].tolist()))
            except Exception:
                logger.exception("XGBoost prediction failed, falling back to rule-based")
                prob, shap_dict = self._rule_based(gap_pct, features)
        else:
            prob, shap_dict = self._rule_based(gap_pct, features)

        return prob, {"features": features, "shap_values": shap_dict}

    @staticmethod
    def _rule_based(gap_pct: float, features: dict) -> tuple[float, dict]:
        """Rule-based probability estimate when XGBoost model is unavailable."""
        # Gap size is the strongest predictor; county approval rate adds baseline lift
        # Larger buildings have slightly higher success rates (more at stake)
        sqft_boost = 0.05 if features.get("building_sqft", 0) > 2000 else 0.0
        prob = min(max(
            gap_pct * 3.5
            + features["county_approval_rate"] * 0.5
            + sqft_boost,
            0.05,
        ), 0.95)
        return prob, {k: 0.0 for k in features}

    @staticmethod
    def _std_dev(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return variance ** 0.5
