"""
Computes distance from each unique Bangalore location to the nearest
school, hospital, and transit stop/station, using OpenStreetMap's
Overpass API (free, no key required).
"""

import math
import time
from pathlib import Path

import pandas as pd
import requests

LOCATION_COORDS_PATH = Path("data/processed/bangalore_location_coords.csv")
AMENITY_CACHE_PATH = Path("data/processed/bangalore_amenity_distances.csv")

OVERPASS_URL = "https://overpass.openstreetmap.fr/api/interpreter"
SEARCH_RADIUS_M = 3000
MAX_RADIUS_M = 10000
DELAY_BETWEEN_REQUESTS_S = 3.0

REQUEST_HEADERS = {
    "User-Agent": "real-estate-avm-ojt-project",
    "Content-Type": "application/x-www-form-urlencoded",
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_query(lat: float, lon: float, radius_m: int) -> str:
    return f"""
    [out:json][timeout:40];
    (
      node["amenity"="school"](around:{radius_m},{lat},{lon});
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      node["amenity"="clinic"](around:{radius_m},{lat},{lon});
      node["highway"="bus_stop"](around:{radius_m},{lat},{lon});
      node["railway"="station"](around:{radius_m},{lat},{lon});
      node["railway"="halt"](around:{radius_m},{lat},{lon});
      node["railway"="subway_entrance"](around:{radius_m},{lat},{lon});
    );
    out body;
    """


def nearest_distance(lat: float, lon: float, elements: list, tag_key: str, tag_values: set) -> float | None:
    best = None
    for el in elements:
        tags = el.get("tags", {})
        if tags.get(tag_key) in tag_values:
            d = haversine_km(lat, lon, el["lat"], el["lon"])
            if best is None or d < best:
                best = d
    return best


def query_amenities_for_location(lat: float, lon: float) -> dict:
    radius = SEARCH_RADIUS_M
    elements = []

    while radius <= MAX_RADIUS_M:
        query = build_query(lat, lon, radius)
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, headers=REQUEST_HEADERS, timeout=50)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
        except requests.exceptions.RequestException as e:
            print(f"    Overpass request failed: {e}")
            elements = []
            print(f"    Backing off 10s before retrying...")
            time.sleep(10)

        if elements:
            break
        radius *= 2

    return {
        "dist_to_school_km": nearest_distance(lat, lon, elements, "amenity", {"school"}),
        "dist_to_hospital_km": nearest_distance(lat, lon, elements, "amenity", {"hospital", "clinic"}),
        "dist_to_transit_km": min(
            filter(
                None,
                [
                    nearest_distance(lat, lon, elements, "highway", {"bus_stop"}),
                    nearest_distance(lat, lon, elements, "railway", {"station", "halt", "subway_entrance"}),
                ],
            ),
            default=None,
        ),
    }


def _save_cache(results: list) -> None:
    df = pd.DataFrame(results)
    AMENITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(AMENITY_CACHE_PATH, index=False)


if __name__ == "__main__":
    if not LOCATION_COORDS_PATH.exists():
        raise FileNotFoundError(
            f"{LOCATION_COORDS_PATH} not found. Run load_bangalore.py first."
        )

    locations = pd.read_csv(LOCATION_COORDS_PATH).dropna(subset=["lat", "lon"])
    print(f"{len(locations)} geocoded locations to process")

    already_done = {}
    if AMENITY_CACHE_PATH.exists():
        cached = pd.read_csv(AMENITY_CACHE_PATH)
        already_done = {row["location"]: row.to_dict() for _, row in cached.iterrows()}
        print(f"Resuming: {len(already_done)} locations already done")

    results = list(already_done.values())
    remaining = locations[~locations["location"].isin(already_done.keys())]
    print(f"{len(remaining)} locations left to query")

    for i, (_, row) in enumerate(remaining.iterrows(), 1):
        loc, lat, lon = row["location"], row["lat"], row["lon"]
        print(f"[{i}/{len(remaining)}] Querying amenities near: {loc}")

        distances = query_amenities_for_location(lat, lon)
        results.append({"location": loc, "lat": lat, "lon": lon, **distances})

        if i % 25 == 0:
            _save_cache(results)
            print(f"  [progress saved: {len(results)} total]")

        time.sleep(DELAY_BETWEEN_REQUESTS_S)

    _save_cache(results)
    print(f"\nSaved {len(results)} locations' amenity distances to {AMENITY_CACHE_PATH}")

    df = pd.DataFrame(results)
    for col in ["dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]:
        found = df[col].notna().sum()
        print(f"{col}: found for {found}/{len(df)} locations")
