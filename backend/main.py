"""
The FastAPI backend. It loads the trained model once at startup and answers
price requests from the Streamlit app (or anything else that speaks HTTP).

Run from the project folder:  uvicorn backend.main:app --reload
Interactive docs:             http://127.0.0.1:8000/docs
"""

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI, HTTPException

from backend.config import PROJECT_ROOT, load_config
from backend.schemas import PredictionRequest, PredictionResponse, PriceFactor

app = FastAPI(
    title="Real Estate AVM - Bangalore",
    description="Estimates property prices in Bangalore and explains each estimate.",
    version="1.0",
)

config = load_config()
app_settings = config["app"]

MODEL_VERSION = "xgboost_tuned_v1"

# the column order the model was trained with. it must match exactly
FEATURES = config["features"]["property"] + config["features"]["location"]

model = joblib.load(PROJECT_ROOT / "backend" / "models" / "trained_model.pkl")

location_lookup = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "location_lookup.csv")
location_lookup = location_lookup.set_index("location")

# shap tells us how much each feature pushed this one property's price up or
# down. building the explainer once at startup keeps every request fast.
explainer = shap.TreeExplainer(model)
BASE_PRICE = round(float(np.array(explainer.expected_value).reshape(-1)[0]), 2)

# how far the asking price can be from our estimate and still count as fair
FAIR_RANGE_PERCENT = app_settings["fair_range_percent"]


def load_model_error():
    """the measured test error, saved by backend/models/measure_error.py"""
    path = PROJECT_ROOT / "reports" / "model_error.csv"
    try:
        return pd.read_csv(path).iloc[0].to_dict()
    except (FileNotFoundError, IndexError):
        return {"mape_percent": app_settings["fallback_error_percent"]}


model_error = load_model_error()
ERROR_PERCENT = float(model_error["mape_percent"])


def km_text(value):
    if pd.isna(value):
        return "not known"
    # under 1 km reads better in metres: "13 m" instead of "0.0 km"
    if float(value) < 1:
        return str(int(round(float(value) * 1000))) + " m"
    return str(round(float(value), 1)) + " km"


def build_features(request, location_row):
    """one row with every column the model needs, in the right order"""
    row = {
        "bhk": request.bedrooms,
        "bath": request.bathrooms,
        "total_sqft_clean": request.size_sqft,
        "lat": location_row["lat"],
        "lon": location_row["lon"],
        "dist_to_school_km": location_row["dist_to_school_km"],
        "dist_to_hospital_km": location_row["dist_to_hospital_km"],
        "dist_to_transit_km": location_row["dist_to_transit_km"],
        "location_price": location_row["location_price"],
    }
    return pd.DataFrame([row])[FEATURES]


def build_factors(features, shap_values, location_name):
    """turns the raw shap numbers into readable lines for the app"""
    row = features.iloc[0]
    effects = dict(zip(features.columns, shap_values))

    def effect(*columns):
        return round(sum(float(effects[c]) for c in columns), 2)

    factors = [
        PriceFactor(name="Size, " + str(int(row["total_sqft_clean"])) + " sqft",
                    effect=effect("total_sqft_clean")),
        PriceFactor(name="Area price level in " + location_name,
                    effect=effect("location_price")),
        PriceFactor(name="Bedrooms, " + str(int(row["bhk"])) + " BHK",
                    effect=effect("bhk")),
        PriceFactor(name="Bathrooms, " + str(int(row["bath"])),
                    effect=effect("bath")),
        # lat and lon only mean anything together, so they are shown as one line
        PriceFactor(name="Position on the map",
                    effect=effect("lat", "lon")),
        PriceFactor(name="Nearest school, " + km_text(row["dist_to_school_km"]),
                    effect=effect("dist_to_school_km")),
        PriceFactor(name="Nearest hospital, " + km_text(row["dist_to_hospital_km"]),
                    effect=effect("dist_to_hospital_km")),
        PriceFactor(name="Nearest transit, " + km_text(row["dist_to_transit_km"]),
                    effect=effect("dist_to_transit_km")),
    ]

    # biggest effect first, whether it pushed the price up or down
    factors.sort(key=lambda f: abs(f.effect), reverse=True)
    return factors


def build_warnings(request):
    """tree models cannot extrapolate: outside the training range their
    estimate just stays flat, so the user is told when that happens"""
    warnings = []
    if request.size_sqft < app_settings["training_sqft_min"]:
        warnings.append("Size is smaller than any property the model was trained on ("
                        + str(app_settings["training_sqft_min"]) + " sqft), so the estimate is less reliable.")
    if request.size_sqft > app_settings["training_sqft_max"]:
        warnings.append("Size is larger than any property the model was trained on ("
                        + str(app_settings["training_sqft_max"]) + " sqft), so the estimate is less reliable.")
    if request.bedrooms > app_settings["training_bhk_max"]:
        warnings.append("Very few properties in the data have this many bedrooms.")
    return warnings


def price_verdict(asking_price, predicted_price):
    """compares an asking price with our estimate"""
    difference_percent = round(((asking_price - predicted_price) / predicted_price) * 100, 1)

    if difference_percent > FAIR_RANGE_PERCENT:
        verdict = "Looks overpriced"
    elif difference_percent < -FAIR_RANGE_PERCENT:
        verdict = "Looks underpriced"
    else:
        verdict = "Looks fairly priced"

    return verdict, difference_percent


@app.get("/health")
def health_check():
    return {"status": "ok", "model_version": MODEL_VERSION, "locations": len(location_lookup)}


@app.get("/locations")
def list_locations():
    """every area the model can price, in alphabetical order"""
    return {"locations": sorted(location_lookup.index.tolist())}


@app.get("/model-info")
def model_info():
    """what the model is and how accurate it is, for the app's About tab"""
    return {
        "model_version": MODEL_VERSION,
        "features": FEATURES,
        "base_price": BASE_PRICE,
        "fair_range_percent": FAIR_RANGE_PERCENT,
        "error": {key: float(value) for key, value in model_error.items()},
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    if request.location not in location_lookup.index:
        # 404 tells the caller clearly that the area is unknown, instead of
        # sending back a fake price of 0
        raise HTTPException(status_code=404, detail="Unknown location: " + request.location)

    location_row = location_lookup.loc[request.location]
    features = build_features(request, location_row)

    # the model can, in rare cases, go below zero for tiny properties
    predicted_price = max(1.0, round(float(model.predict(features)[0]), 2))

    # the starting point is the average property in the training data.
    # every factor adds to or subtracts from it, and they add up to the
    # model's prediction
    shap_values = explainer.shap_values(features)[0]
    factors = build_factors(features, shap_values, request.location)

    # the range uses the model's measured average error on unseen test data
    margin = predicted_price * ERROR_PERCENT / 100
    price_low = round(max(1.0, predicted_price - margin), 2)
    price_high = round(predicted_price + margin, 2)

    # 1 Lakh = 1,00,000 rupees
    price_per_sqft = round(predicted_price * 100000 / request.size_sqft, 0)

    verdict = None
    difference_percent = None
    if request.asking_price is not None:
        verdict, difference_percent = price_verdict(request.asking_price, predicted_price)

    return PredictionResponse(
        predicted_price=predicted_price,
        price_low=price_low,
        price_high=price_high,
        error_percent=ERROR_PERCENT,
        price_per_sqft=price_per_sqft,
        model_version=MODEL_VERSION,
        verdict=verdict,
        difference_percent=difference_percent,
        base_price=BASE_PRICE,
        factors=factors,
        warnings=build_warnings(request),
    )
