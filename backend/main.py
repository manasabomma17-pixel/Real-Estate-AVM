"""
The FastAPI backend. It loads the trained model once at startup and answers
requests from the React app (or anything else that speaks HTTP).

Run from the project folder:  uvicorn backend.main:app --reload
Interactive docs:             http://127.0.0.1:8000/docs
"""

import os

import joblib
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.config import PROJECT_ROOT, load_config
from backend.schemas import (
    AdviceRequest,
    ListingText,
    PlaceQuery,
    PredictionRequest,
    PredictionResponse,
    PriceFactor,
)
from backend.services import area_data
from backend.services.building_age import age_adjustment, age_suggestions, find_building_age
from backend.services.exact_location import geocode, parse_coordinates
from backend.services.listing_parser import is_link, parse_listing
from backend.services.suggestions import area_rates, build_suggestions, cheaper_nearby_areas

app = FastAPI(
    title="Real Estate AVM - Bangalore",
    description="Estimates property prices in Bangalore and explains each estimate.",
    version="2.0",
)

# the React app runs on a different address (port 5173 locally, its own
# domain when deployed), so the browser needs permission to call this API.
# ALLOWED_ORIGINS can list the app's address; by default anyone may call it,
# which is fine because the API only reads public data
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

config = load_config()
app_settings = config["app"]

MODEL_VERSION = "xgboost_tuned_v1"

# the column order the model was trained with. it must match exactly
FEATURES = config["features"]["property"] + config["features"]["location"]

model = joblib.load(PROJECT_ROOT / "backend" / "models" / "trained_model.pkl")

location_lookup = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "location_lookup.csv")
location_lookup = location_lookup.set_index("location")

# SHAP values tell us how much each feature pushed this one property's price
# up or down. XGBoost can work out exact SHAP values for its own trees
# (pred_contribs=True), the same TreeSHAP method the shap library uses, so the
# server does not need the heavy shap package. this keeps it small enough for
# free hosting. backend/models/explain_model.py still uses shap for the charts
booster = model.get_booster()


def shap_contributions(features):
    """returns (one SHAP value per feature, the base value) for a single row.
    XGBoost puts the base value (the average prediction) in the last column"""
    contributions = booster.predict(xgb.DMatrix(features), pred_contribs=True)
    return contributions[0, :-1], float(contributions[0, -1])


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

MARKET_SOURCE = app_settings.get("market_adjustment_source", "")


def load_market_factors():
    """today's-market factors per area, made by data_processing/build_price_adjustment.py.
    returns ({area: factor}, city factor). without the file nothing is adjusted"""
    path = PROJECT_ROOT / "data" / "processed" / "price_adjustment.csv"
    try:
        table = pd.read_csv(path)
    except FileNotFoundError:
        return {}, 1.0
    city = table.loc[table["location"] == "_city_", "factor"]
    city_factor = float(city.iloc[0]) if len(city) else 1.0
    areas = table[table["location"] != "_city_"].set_index("location")["factor"].to_dict()
    return areas, city_factor


AREA_FACTORS, CITY_FACTOR = load_market_factors()


def market_factor(location):
    """how much prices in this area have risen since our data: (factor, basis)"""
    if location in AREA_FACTORS:
        return float(AREA_FACTORS[location]), "area"
    if CITY_FACTOR != 1.0:
        return CITY_FACTOR, "city"
    return 1.0, "none"


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


def _base_price():
    """the base value is the same for every property, so it is worked out once
    at startup from any valid row"""
    area = location_lookup.iloc[0]
    sample = pd.DataFrame([{
        "bhk": 2, "bath": 2, "total_sqft_clean": 1200,
        "lat": area["lat"], "lon": area["lon"],
        "dist_to_school_km": area["dist_to_school_km"],
        "dist_to_hospital_km": area["dist_to_hospital_km"],
        "dist_to_transit_km": area["dist_to_transit_km"],
        "location_price": area["location_price"],
    }])[FEATURES]
    return round(shap_contributions(sample)[1], 2)


BASE_PRICE = _base_price()


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
        warnings.append("Very small flat. We have few flats under "
                        + str(app_settings["training_sqft_min"]) + " sqft.")
    if request.size_sqft > app_settings["training_sqft_max"]:
        warnings.append("Very big flat. We have few flats over "
                        + str(app_settings["training_sqft_max"]) + " sqft.")
    if request.bedrooms > app_settings["training_bhk_max"]:
        warnings.append("We have very few flats with this many bedrooms.")
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
        "data_period": "about 2017-2019",
        "city_market_factor": CITY_FACTOR,
        "areas_with_own_factor": len(AREA_FACTORS),
        "market_source": MARKET_SOURCE,
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
    shap_values, _ = shap_contributions(features)
    factors = build_factors(features, shap_values, request.location)

    # the range uses the model's measured average error on unseen test data
    margin = predicted_price * ERROR_PERCENT / 100
    price_low = round(max(1.0, predicted_price - margin), 2)
    price_high = round(predicted_price + margin, 2)

    # 1 Lakh = 1,00,000 rupees
    price_per_sqft = round(predicted_price * 100000 / request.size_sqft, 0)

    # bring the estimate up to today's market. asking prices people paste from
    # property sites are today's prices, so the verdict compares with this
    factor, basis = market_factor(request.location)
    today_price = round(predicted_price * factor, 2)
    today_low = round(price_low * factor, 2)
    today_high = round(price_high * factor, 2)
    today_price_per_sqft = round(today_price * 100000 / request.size_sqft, 0)

    verdict = None
    difference_percent = None
    if request.asking_price is not None:
        verdict, difference_percent = price_verdict(request.asking_price, today_price)

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
        today_price=today_price,
        today_low=today_low,
        today_high=today_high,
        today_price_per_sqft=today_price_per_sqft,
        market_factor=round(factor, 3),
        market_basis=basis,
        market_source=MARKET_SOURCE if basis != "none" else None,
    )


# ----- helper endpoints for the React app -----
# the app sends what the user typed, and these answer with real numbers from
# our data, so the browser never needs the data files itself


def require_area(area):
    if not area_data.known(area):
        raise HTTPException(status_code=404, detail="Unknown location: " + area)


@app.get("/areas")
def list_areas():
    """every area the model can price, with its map position and record count"""
    return {"areas": area_data.area_list(), "city_market_factor": round(CITY_FACTOR, 3)}


@app.get("/areas/{area}/summary")
def area_summary(area: str, bedrooms: int = 2):
    """real numbers about the area (typical rate today, ready-to-move share...)"""
    require_area(area)
    return area_data.area_summary(area, bedrooms)


@app.get("/areas/{area}/places")
def area_places(area: str, lat: float | None = None, lon: float | None = None):
    """the 5 nearest schools, hospitals and transit stops: from the exact spot
    when lat and lon are given, otherwise from the area's centre"""
    require_area(area)
    if lat is not None and lon is not None:
        return area_data.places_near_point(lat, lon)
    return area_data.places_near_area(area)


@app.get("/areas/{area}/comparison")
def area_comparison(area: str, bedrooms: int = 2):
    """price per sqft of comparable flats at today's level, for the chart"""
    require_area(area)
    return area_data.comparison(area, bedrooms)


@app.get("/areas/{area}/nearby")
def nearby_areas(area: str):
    """the 10 closest areas with today's typical rate"""
    require_area(area)
    return area_data.nearby_areas(area)


@app.post("/parse-listing")
def read_listing(body: ListingText):
    """reads area, BHK, size, bathrooms and price out of pasted listing text"""
    found = parse_listing(body.text, area_data.lookup.index.tolist())
    missing = [name for name, value in found.items() if not value]
    age, under_construction = find_building_age(body.text)
    return {"found": found, "missing": missing, "is_link": is_link(body.text),
            "building_age": age, "under_construction": under_construction}


@app.post("/locate")
def locate(body: PlaceQuery):
    """turns a society name, landmark, Google Maps link or coordinates into a
    position, and says how far it is from the centre of the chosen area"""
    require_area(body.area)
    point = parse_coordinates(body.query)
    label = "the coordinates you gave" if point else None
    if not point:
        found = geocode(body.query)
        if found:
            # "Prestige Shantiniketan, Whitefield Road, Hoodi, ..." -> the first 3 parts
            point, label = (found[0], found[1]), ", ".join(found[2].split(", ")[:3])
    if not point:
        raise HTTPException(status_code=404, detail=(
            "Place not found. Try the society name and area, or paste a Google Maps link."))

    away = area_data.km_from_centre(body.area, point[0], point[1])
    return {"lat": point[0], "lon": point[1], "label": label, "km_from_area_centre": round(away, 2),
            "far_from_area": away > 5}


@app.post("/advice")
def advice(request: AdviceRequest):
    """practical suggestions for this flat, worked out from today's estimate,
    the area's records and the nearest places"""
    require_area(request.location)
    extras = {"exact_lat", "exact_lon", "building_age", "under_construction"}
    result = predict(PredictionRequest(**request.model_dump(exclude=extras)))

    # the suggestions compare asking prices (which are today's) with today's estimate
    today = result.model_dump()
    today.update(predicted_price=result.today_price, price_low=result.today_low,
                 price_high=result.today_high, price_per_sqft=result.today_price_per_sqft)

    # the same flat in cheaper areas close by, priced by the model
    nearby_estimates = []
    rates = SUGGESTION_RATES
    for area, km, rate in cheaper_nearby_areas(request.location, area_data.lookup, rates):
        other = predict(PredictionRequest(location=area, size_sqft=request.size_sqft,
                                          bedrooms=request.bedrooms, bathrooms=request.bathrooms))
        if other.today_price < result.today_price:
            nearby_estimates.append((area, km, rate, other.today_price))

    if request.exact_lat is not None and request.exact_lon is not None:
        nearby = area_data.places_near_point(request.exact_lat, request.exact_lon)
    else:
        nearby = area_data.places_near_area(request.location)
    named = {group: (place_text(group, items[0]) if items else None) for group, items in nearby["places"].items()}
    exact_distances = None
    if nearby["exact"]:
        exact_distances = {group: (items[0]["km"] if items else 99) for group, items in nearby["places"].items()}

    items = build_suggestions(
        request.model_dump(), today, area_data.listings, area_data.lookup, nearby_estimates, named,
        exact_distances, rate_factor=area_data.market_factor(request.location)[0])

    # building age: what to check for this age, and a rough price adjustment
    # shown apart from the model's estimate (the model never saw building age)
    items = age_suggestions(request.building_age, request.under_construction) + items
    age = None
    if request.building_age is not None and not request.under_construction:
        age = age_adjustment(request.size_sqft, request.building_age, result.today_price)

    return {"suggestions": [{"kind": kind, "title": title, "text": text} for kind, title, text in items],
            "age": age}


# median rate and record count per area, worked out once at startup
SUGGESTION_RATES = area_rates(area_data.listings)


def place_text(group, place):
    text = place["name"] + " (" + km_text(place["km"]) + ")"
    if group == "transit" and place.get("type"):
        text += " - " + place["type"]
    return text
