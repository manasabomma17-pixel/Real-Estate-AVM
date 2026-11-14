"""
Everything the app shows about an area, worked out from our data files:
the area summary, comparable flats, nearby areas and the nearest named places.

The Streamlit app used to do this itself. It now lives here so that any
frontend (the React app, or anything else that speaks HTTP) gets the same
answers from the API. Only pandas and numpy are used, so it can be tested
without the model or a running server.
"""

import pandas as pd

from backend.config import PROJECT_ROOT
from backend.services.exact_location import distances_km, nearest_places
from backend.services.suggestions import MIN_LISTINGS, clean_name

DATA_DIR = PROJECT_ROOT / "data" / "processed"

GROUPS = ["school", "hospital", "transit"]


def _read_optional(path):
    """some files are made by optional scripts: without them, that part is skipped"""
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        return None


# ----- the data, read once when the server starts -----

listings = pd.read_csv(DATA_DIR / "bangalore_final_dataset.csv")

# the 881 areas the model was trained on (the dataset has a few more that
# the model cannot price, so the lookup is the list of areas we offer)
lookup = pd.read_csv(DATA_DIR / "location_lookup.csv").set_index("location")

# the 5 nearest named schools, hospitals and transit stops for every area
amenity_places = _read_optional(DATA_DIR / "amenity_places.csv")
if amenity_places is not None:
    amenity_places = amenity_places[amenity_places["group"].isin(GROUPS)]

# every named place in the city, for distances from an exact spot
city_places = _read_optional(DATA_DIR / "bangalore_places.csv")

# how much each area's prices have risen since our 2017-19 data
market_table = _read_optional(DATA_DIR / "price_adjustment.csv")


def _market_factors():
    if market_table is None:
        return {}, 1.0
    city = market_table.loc[market_table["location"] == "_city_", "factor"]
    areas = market_table[market_table["location"] != "_city_"].set_index("location")["factor"].to_dict()
    return areas, (float(city.iloc[0]) if len(city) else 1.0)


AREA_FACTORS, CITY_FACTOR = _market_factors()

# rupees per sqft for every listing, at 2017-19 prices (1 Lakh = 1,00,000 rupees)
listings["rate"] = listings["price"] / listings["total_sqft_clean"] * 100000
LISTING_COUNTS = listings["location"].value_counts()
AREA_RATES = listings.groupby("location")["rate"].median()


def market_factor(area):
    """(factor, basis): multiply 2017-19 prices by the factor for today's level.
    basis is 'area' when the area has its own published rate, else 'city'"""
    if area in AREA_FACTORS:
        return float(AREA_FACTORS[area]), "area"
    if CITY_FACTOR != 1.0:
        return CITY_FACTOR, "city"
    return 1.0, "none"


def known(area):
    return area in lookup.index


def round_to(value, step):
    return int(round(float(value) / step) * step)


# ----- the list of areas for the dropdown -----

def area_list():
    """every area the model can price, with its position and how many records we have"""
    rows = []
    for name, row in lookup.sort_index().iterrows():
        rows.append({
            "name": name,
            "lat": round(float(row["lat"]), 6),
            "lon": round(float(row["lon"]), 6),
            "records": int(LISTING_COUNTS.get(name, 0)),
        })
    return rows


# ----- a short summary of the area, shown next to the form -----

def area_summary(area, bedrooms):
    """real numbers about the area from our data, brought up to today's prices"""
    rows = listings[listings["location"] == area]
    factor, basis = market_factor(area)
    centre = lookup.loc[area]

    summary = {
        "area": area,
        "records": int(len(rows)),
        "market_factor": round(factor, 3),
        "market_basis": basis,
        "distances_km": {
            "school": _number_or_none(centre["dist_to_school_km"]),
            "hospital": _number_or_none(centre["dist_to_hospital_km"]),
            "transit": _number_or_none(centre["dist_to_transit_km"]),
        },
        "typical_rate_today": None,
        "typical_bhk_price_today": None,
        "bhk_records": 0,
        "ready_percent": None,
        "common_type": None,
        "price_range_2017_19": None,
    }
    if len(rows) == 0:
        return summary

    # median, because a few luxury listings would pull an average up
    summary["typical_rate_today"] = round_to(rows["rate"].median() * factor, 100)

    same_bhk = rows[rows["bhk"] == bedrooms]
    summary["bhk_records"] = int(len(same_bhk))
    if len(same_bhk) > 0:
        summary["typical_bhk_price_today"] = round(float(same_bhk["price"].median() * factor), 1)

    ready = (rows["availability"].astype(str).str.strip() == "Ready To Move").mean() * 100
    summary["ready_percent"] = int(round(ready))
    common = rows["area_type"].mode()
    summary["common_type"] = " ".join(str(common.iloc[0]).split()) if len(common) else None
    summary["price_range_2017_19"] = [round(float(rows["price"].min()), 1), round(float(rows["price"].max()), 1)]
    return summary


def _number_or_none(value):
    return None if pd.isna(value) else round(float(value), 3)


# ----- comparable flats for the Price Comparison page -----

def comparison(area, bedrooms):
    """price per sqft of comparable flats at today's level. starts with the
    same area and BHK, and widens when there are too few records"""
    factor, basis = market_factor(area)
    group = listings[(listings["location"] == area) & (listings["bhk"] == bedrooms)]
    scope = "area_bhk"
    if len(group) < MIN_LISTINGS:
        group = listings[listings["location"] == area]
        scope = "area"
    if len(group) < MIN_LISTINGS:
        group = listings[listings["bhk"] == bedrooms]
        scope = "city_bhk"
        factor, basis = CITY_FACTOR, "city"

    rates = (group["rate"] * factor).round(-1)
    result = {
        "area": area,
        "bedrooms": bedrooms,
        "scope": scope,
        "market_factor": round(factor, 3),
        "market_basis": basis,
        "count": int(len(rates)),
        "rates": sorted(int(r) for r in rates),
        "typical": None,
        "middle_half": None,
    }
    if len(rates) > 0:
        result["typical"] = round_to(rates.median(), 100)
        result["middle_half"] = [round_to(rates.quantile(0.25), 100), round_to(rates.quantile(0.75), 100)]
    return result


# ----- nearby areas, to compare prices -----

def nearby_areas(area, limit=10):
    """the closest areas with enough records to trust, with today's typical rate"""
    centre = lookup.loc[area]
    others = lookup[[known_enough(name) and clean_name(name) != clean_name(area) for name in lookup.index]]
    km = distances_km(float(centre["lat"]), float(centre["lon"]), others["lat"].values, others["lon"].values)
    closest = others.assign(km=km).sort_values("km").head(limit)

    own_rate = _today_rate(area)
    rows = []
    for name, row in closest.iterrows():
        rate = _today_rate(name)
        difference = None
        if rate is not None and own_rate:
            difference = round((rate - own_rate) / own_rate * 100)
        rows.append({
            "name": name,
            "km": round(float(row["km"]), 2),
            "lat": round(float(row["lat"]), 6),
            "lon": round(float(row["lon"]), 6),
            "records": int(LISTING_COUNTS.get(name, 0)),
            "rate_today": rate,
            "difference_percent": difference,
        })
    return {"area": area, "rate_today": own_rate, "areas": rows}


def known_enough(name):
    return LISTING_COUNTS.get(name, 0) >= MIN_LISTINGS


def _today_rate(area):
    if area not in AREA_RATES.index:
        return None
    return round_to(AREA_RATES[area] * market_factor(area)[0], 100)


# ----- the nearest named places -----

def places_near_area(area):
    """the up-to-5 nearest places in each group, measured from the area's centre"""
    places = {group: [] for group in GROUPS}
    if amenity_places is not None:
        rows = amenity_places[amenity_places["location"] == area].sort_values(["group", "rank"])
        for _, row in rows.iterrows():
            places[row["group"]].append(_place(row))
    centre = lookup.loc[area]
    return {
        "exact": False,
        "centre": {"lat": float(centre["lat"]), "lon": float(centre["lon"]), "label": "Centre of " + area},
        "places": places,
    }


def places_near_point(lat, lon, label="The exact location you gave"):
    """the up-to-5 nearest places in each group within 3 km of an exact spot"""
    places = {group: [] for group in GROUPS}
    if city_places is not None:
        found = nearest_places(city_places, lat, lon)
        places = {group: [_place(p) for p in found.get(group, [])] for group in GROUPS}
    return {"exact": True, "centre": {"lat": lat, "lon": lon, "label": label}, "places": places}


def _place(row):
    kind = row.get("type")
    return {
        "name": str(row["name"]),
        "km": round(float(row["km"]), 3),
        "type": kind if isinstance(kind, str) else None,
        "lat": _number_or_none(row.get("lat")),
        "lon": _number_or_none(row.get("lon")),
    }


def km_from_centre(area, lat, lon):
    centre = lookup.loc[area]
    return float(distances_km(lat, lon, [float(centre["lat"])], [float(centre["lon"])])[0])
