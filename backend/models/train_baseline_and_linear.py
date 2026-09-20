"""
Trains the neighborhood $/sqft baseline, then Linear/Ridge/Lasso regression
across property-only, property+location, encoded, and interaction conditions.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path("data/processed/bangalore_final_dataset.csv")
RANDOM_SEED = 42
TEST_SIZE = 0.2

PROPERTY_FEATURES = ["bhk", "bath", "balcony", "total_sqft_clean"]
LOCATION_FEATURES = ["lat", "lon", "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]
TARGET = "price"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)

    for col in ["bath", "balcony"]:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    for col in ["dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    return df


def print_diagnostics(df: pd.DataFrame) -> None:
    print("\n--- Price distribution diagnostics ---")
    print(df["price"].describe())
    price_per_sqft = df["price"] / df["total_sqft_clean"]
    print("\nPrice-per-sqft distribution:")
    print(price_per_sqft.describe())
    print("\nTotal sqft distribution (checking for land-unit conversion outliers):")
    print(df["total_sqft_clean"].describe())
    print(f"\n99th percentile price: {df['price'].quantile(0.99):.1f}")
    print(f"Max price: {df['price'].max():.1f}")
    print(f"99th percentile sqft: {df['total_sqft_clean'].quantile(0.99):.1f}")
    print(f"Max sqft: {df['total_sqft_clean'].max():.1f}")


def trim_outliers(df: pd.DataFrame) -> pd.DataFrame:
    price_per_sqft = df["price"] / df["total_sqft_clean"]
    price_low, price_high = price_per_sqft.quantile([0.01, 0.99])
    sqft_low, sqft_high = df["total_sqft_clean"].quantile([0.01, 0.99])

    before = len(df)
    df = df[
        (price_per_sqft >= price_low) & (price_per_sqft <= price_high)
        & (df["total_sqft_clean"] >= sqft_low) & (df["total_sqft_clean"] <= sqft_high)
    ]
    print(f"Trimmed {before - len(df)} extreme outliers (price/sqft ratio and/or raw sqft) ({before} -> {len(df)} rows)")
    return df


def add_location_encoding(train_df: pd.DataFrame, test_df: pd.DataFrame) -> tuple:
    train_df = train_df.copy()
    test_df = test_df.copy()

    train_df["price_per_sqft"] = train_df[TARGET] / train_df["total_sqft_clean"]
    location_median = train_df.groupby("location")["price_per_sqft"].median()
    global_median = train_df["price_per_sqft"].median()

    train_df["location_encoded"] = train_df["location"].map(location_median).fillna(global_median)
    test_df["location_encoded"] = test_df["location"].map(location_median).fillna(global_median)

    train_df["location_price_estimate"] = train_df["location_encoded"] * train_df["total_sqft_clean"]
    test_df["location_price_estimate"] = test_df["location_encoded"] * test_df["total_sqft_clean"]

    return train_df, test_df


def compute_baseline_predictions(train_df: pd.DataFrame, test_df: pd.DataFrame) -> np.ndarray:
    train_df = train_df.copy()
    train_df["price_per_sqft"] = train_df[TARGET] / train_df["total_sqft_clean"]

    location_median = train_df.groupby("location")["price_per_sqft"].median()
    global_median = train_df["price_per_sqft"].median()

    predicted_per_sqft = test_df["location"].map(location_median).fillna(global_median)
    return predicted_per_sqft.values * test_df["total_sqft_clean"].values


def evaluate(y_true, y_pred, label: str) -> dict:
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    mape = mean_absolute_percentage_error(y_true, y_pred) * 100
    r2 = r2_score(y_true, y_pred)
    print(f"  {label:20s}  RMSE={rmse:8.2f}  MAE={mae:8.2f}  MAPE={mape:6.2f}%  R2={r2:.4f}")
    return {"label": label, "rmse": rmse, "mae": mae, "mape": mape, "r2": r2}


def run_condition(name, feature_cols, X_train_full, X_test_full, y_train_log, y_test, baseline_rmse):
    print(f"\n--- Condition: {name} ({len(feature_cols)} features) ---")
    X_train = X_train_full[feature_cols]
    X_test = X_test_full[feature_cols]

    models = {
        "Linear Regression": make_pipeline(StandardScaler(), LinearRegression()),
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0, random_state=RANDOM_SEED)),
        "Lasso": make_pipeline(StandardScaler(), Lasso(alpha=0.01, random_state=RANDOM_SEED)),
    }

    results = []
    for model_name, model in models.items():
        model.fit(X_train, y_train_log)
        preds_log = model.predict(X_test)
        preds_log = np.clip(preds_log, y_train_log.min(), y_train_log.max())
        preds = np.expm1(preds_log)
        result = evaluate(y_test, preds, model_name)
        result["condition"] = name
        result["rmse_improvement_vs_baseline"] = (1 - result["rmse"] / baseline_rmse) * 100
        results.append(result)

    return results


if __name__ == "__main__":
    df = load_data()
    print(f"Loaded {len(df)} rows")

    print_diagnostics(df)
    df = trim_outliers(df)

    train_df, test_df = train_test_split(df, test_size=TEST_SIZE, random_state=RANDOM_SEED)
    print(f"\nTrain: {len(train_df)} rows | Test: {len(test_df)} rows")

    y_train, y_test = train_df[TARGET], test_df[TARGET]
    y_train_log = np.log1p(y_train)

    print("\n--- Baseline: neighborhood median $/sqft ---")
    baseline_preds = compute_baseline_predictions(train_df, test_df)
    baseline_result = evaluate(y_test, baseline_preds, "Baseline")
    baseline_rmse = baseline_result["rmse"]

    all_results = [baseline_result | {"condition": "baseline", "rmse_improvement_vs_baseline": 0.0}]

    all_results += run_condition(
        "property_only", PROPERTY_FEATURES, train_df, test_df, y_train_log, y_test, baseline_rmse
    )
    all_results += run_condition(
        "plus_location", PROPERTY_FEATURES + LOCATION_FEATURES, train_df, test_df, y_train_log, y_test, baseline_rmse
    )

    train_df_enc, test_df_enc = add_location_encoding(train_df, test_df)
    all_results += run_condition(
        "plus_location_encoded",
        PROPERTY_FEATURES + LOCATION_FEATURES + ["location_encoded"],
        train_df_enc, test_df_enc, y_train_log, y_test, baseline_rmse
    )

    all_results += run_condition(
        "plus_location_interaction",
        PROPERTY_FEATURES + LOCATION_FEATURES + ["location_encoded", "location_price_estimate"],
        train_df_enc, test_df_enc, y_train_log, y_test, baseline_rmse
    )

    print("\n=== Summary: RMSE improvement over baseline ===")
    for r in all_results:
        if r["condition"] != "baseline":
            print(f"  [{r['condition']:14s}] {r['label']:20s}  {r['rmse_improvement_vs_baseline']:+6.1f}%  (target: >=60%)")

    results_df = pd.DataFrame(all_results)
    Path("reports").mkdir(exist_ok=True)
    results_df.to_csv("reports/baseline_and_linear_results.csv", index=False)
    print("\nSaved results to reports/baseline_and_linear_results.csv")
