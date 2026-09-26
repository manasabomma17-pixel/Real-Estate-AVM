from fastapi import FastAPI
import pandas as pd
import joblib
from backend.schemas import PredictionRequest, PredictionResponse

app = FastAPI()

# load the trained model and location lookup table once, when the server starts
model = joblib.load("backend/models/trained_model.pkl")
location_lookup = pd.read_csv("data/processed/location_lookup.csv")
location_lookup = location_lookup.set_index("location")

# how far the asking price can be from our estimate and still count as fair
FAIR_RANGE_PERCENT = 10


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    if request.location not in location_lookup.index:
        return PredictionResponse(predicted_price=0.0, model_version="unknown location")

    location_row = location_lookup.loc[request.location]

    features = pd.DataFrame([{
        "bhk": request.bedrooms,
        "bath": request.bathrooms,
        "total_sqft_clean": request.size_sqft,
        "lat": location_row["lat"],
        "lon": location_row["lon"],
        "dist_to_school_km": location_row["dist_to_school_km"],
        "dist_to_hospital_km": location_row["dist_to_hospital_km"],
        "dist_to_transit_km": location_row["dist_to_transit_km"],
        "location_price": location_row["location_price"]
    }])

    predicted_price = round(float(model.predict(features)[0]), 2)

    # if the user gave an asking price, compare it with our estimate
    verdict = None
    difference_percent = None

    if request.asking_price is not None and predicted_price > 0:
        difference_percent = round(
            ((request.asking_price - predicted_price) / predicted_price) * 100, 1
        )

        if difference_percent > FAIR_RANGE_PERCENT:
            verdict = "Looks overpriced"
        elif difference_percent < -FAIR_RANGE_PERCENT:
            verdict = "Looks underpriced"
        else:
            verdict = "Looks fairly priced"

    return PredictionResponse(
        predicted_price=predicted_price,
        model_version="xgboost_tuned_v1",
        verdict=verdict,
        difference_percent=difference_percent
    )
