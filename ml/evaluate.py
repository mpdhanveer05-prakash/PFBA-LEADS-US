"""
Evaluate model performance: AUC-ROC and precision@tier per county.
Usage: python evaluate.py --model-version 1
"""
import argparse
import os

import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, precision_score

from features import build_features


def load_eval_data() -> pd.DataFrame:
    import sqlalchemy as sa

    engine = sa.create_engine(os.environ["DATABASE_URL"])
    query = sa.text("""
        SELECT
            ls.gap_pct,
            p.building_sqft,
            p.year_built,
            p.property_type,
            c.approval_rate_hist AS county_approval_rate,
            c.appeal_deadline_days AS days_to_deadline,
            c.name AS county_name,
            ls.priority_tier,
            COALESCE((
                SELECT COUNT(*) FROM comparable_sales cs WHERE cs.property_id = p.id
            ), 0) AS num_comps,
            COALESCE((
                SELECT STDDEV(CAST(cs.price_per_sqft AS float))
                FROM comparable_sales cs WHERE cs.property_id = p.id
            ), 0) AS comp_price_std_dev,
            CASE WHEN a.status = 'WON' THEN 1 ELSE 0 END AS appeal_success
        FROM lead_scores ls
        JOIN properties p ON ls.property_id = p.id
        JOIN counties c ON p.county_id = c.id
        LEFT JOIN appeals a ON a.lead_score_id = ls.id
        WHERE a.status IN ('WON', 'LOST')
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def evaluate(model_version: int) -> None:
    model = mlflow.xgboost.load_model(f"models:/pathfinder-appeal-scorer/{model_version}")
    df = load_eval_data()

    X = build_features(df)
    y = df["appeal_success"].values
    probs = model.predict_proba(X)[:, 1]

    overall_auc = roc_auc_score(y, probs)
    print(f"\nOverall AUC-ROC: {overall_auc:.4f}")

    print("\nPrecision@Tier per County:")
    for county in df["county_name"].unique():
        mask = df["county_name"] == county
        for tier in ["A", "B", "C", "D"]:
            tier_mask = mask & (df["priority_tier"] == tier)
            if tier_mask.sum() < 5:
                continue
            prec = precision_score(y[tier_mask], (probs[tier_mask] >= 0.5).astype(int), zero_division=0)
            print(f"  {county} | Tier {tier}: precision={prec:.3f} (n={tier_mask.sum()})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-version", type=int, default=1)
    args = parser.parse_args()
    evaluate(args.model_version)
