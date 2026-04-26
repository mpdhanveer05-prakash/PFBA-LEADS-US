"""
Train XGBoost appeal-success classifier.
Usage: python train.py --county all --year 2024
"""
import argparse
import logging

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.metrics import roc_auc_score

from features import build_features, FEATURE_COLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_training_data(county: str, year: int) -> pd.DataFrame:
    """Load historical appeal outcomes from PostgreSQL."""
    import os
    import sqlalchemy as sa

    engine = sa.create_engine(os.environ["DATABASE_URL"])
    query = """
        SELECT
            ls.gap_pct,
            p.building_sqft,
            p.year_built,
            p.property_type,
            c.approval_rate_hist AS county_approval_rate,
            c.appeal_deadline_days AS days_to_deadline,
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
        JOIN assessments asmnt ON ls.assessment_id = asmnt.id
        LEFT JOIN appeals a ON a.lead_score_id = ls.id
        WHERE a.status IN ('WON', 'LOST')
        AND asmnt.tax_year = :year
        {county_filter}
    """.format(
        county_filter="AND c.name = :county" if county != "all" else ""
    )

    params = {"year": year}
    if county != "all":
        params["county"] = county

    with engine.connect() as conn:
        df = pd.read_sql(sa.text(query), conn, params=params)

    logger.info("Loaded %d training records", len(df))
    return df


def train(county: str, year: int) -> None:
    df = load_training_data(county, year)
    if len(df) < 50:
        raise ValueError(f"Insufficient training data: {len(df)} records (need ≥50)")

    X = build_features(df, fit_encoder=True)
    y = df["appeal_success"].values

    splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.30, random_state=42)
    train_idx, temp_idx = next(splitter.split(X, y))
    val_splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.50, random_state=42)
    val_idx, test_idx = next(val_splitter.split(X.iloc[temp_idx], y[temp_idx]))
    val_idx = temp_idx[val_idx]
    test_idx = temp_idx[test_idx]

    X_train, y_train = X.iloc[train_idx], y[train_idx]
    X_val, y_val = X.iloc[val_idx], y[val_idx]
    X_test, y_test = X.iloc[test_idx], y[test_idx]

    scale_pos_weight = float(np.sum(y_train == 0)) / max(np.sum(y_train == 1), 1)

    params = {
        "n_estimators": 400,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": scale_pos_weight,
        "eval_metric": "auc",
        "use_label_encoder": False,
        "random_state": 42,
    }

    with mlflow.start_run():
        mlflow.log_params(params)
        mlflow.log_param("county", county)
        mlflow.log_param("year", year)
        mlflow.log_param("train_size", len(X_train))

        model = xgb.XGBClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=50,
        )

        val_auc = roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])
        test_auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
        mlflow.log_metric("val_auc", val_auc)
        mlflow.log_metric("test_auc", test_auc)
        logger.info("Val AUC=%.4f  Test AUC=%.4f", val_auc, test_auc)

        mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            registered_model_name="pathfinder-appeal-scorer",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--county", default="all")
    parser.add_argument("--year", type=int, default=2024)
    args = parser.parse_args()
    train(args.county, args.year)
