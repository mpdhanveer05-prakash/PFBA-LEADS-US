"""Feature engineering for the appeal-success XGBoost classifier."""
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder


PROPERTY_TYPE_ENCODER = LabelEncoder()

FEATURE_COLS = [
    "gap_pct",
    "building_sqft",
    "year_built",
    "property_type_enc",
    "county_approval_rate",
    "days_to_deadline",
    "num_comps",
    "comp_price_std_dev",
]


def build_features(df: pd.DataFrame, fit_encoder: bool = False) -> pd.DataFrame:
    """
    Transform raw assessment + scoring data into the model feature matrix.

    Expected input columns:
        gap_pct, building_sqft, year_built, property_type,
        county_approval_rate, days_to_deadline, num_comps, comp_price_std_dev
    """
    out = df.copy()

    out["gap_pct"] = out["gap_pct"].clip(-1.0, 5.0).fillna(0.0)
    out["building_sqft"] = out["building_sqft"].fillna(out["building_sqft"].median()).clip(0, 20_000)
    out["year_built"] = out["year_built"].fillna(1980).clip(1800, 2024)
    out["county_approval_rate"] = out["county_approval_rate"].fillna(0.3).clip(0.0, 1.0)
    out["days_to_deadline"] = out["days_to_deadline"].fillna(30).clip(0, 365)
    out["num_comps"] = out["num_comps"].fillna(0).clip(0, 50)
    out["comp_price_std_dev"] = out["comp_price_std_dev"].fillna(0.0)

    if fit_encoder:
        PROPERTY_TYPE_ENCODER.fit(out["property_type"].fillna("RESIDENTIAL"))
    out["property_type_enc"] = PROPERTY_TYPE_ENCODER.transform(
        out["property_type"].fillna("RESIDENTIAL")
    )

    return out[FEATURE_COLS]
