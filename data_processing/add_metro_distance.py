"""
Adds the distance from each area to its nearest Namma Metro station.

Metro access is one of the biggest things Bangalore buyers ask about, and our
first amenity step only had "transit" (bus stop, railway or metro, whichever
was nearest), so a bus stop next door hid a metro station 5 km away.

Uses the metro stations already downloaded from OpenStreetMap by
fetch_amenity_names.py --bulk (data/processed/bangalore_places.csv, 97 stations),
so no new download is needed. Saves data/processed/metro_distances.csv with one
row per area: location, dist_to_metro_km, nearest_metro.

Note: the stations are today's network, while the listings are from 2017-19,
when the metro was smaller. So this feature says "how well connected is this
area now", which is what a buyer today cares about.

Run from the project folder:  python -m data_processing.add_metro_distance
"""

import numpy as np
import pandas as pd

from backend.config import PROJECT_ROOT

PLACES_PATH = PROJECT_ROOT / "data" / "processed" / "bangalore_places.csv"
COORDS_PATH = PROJECT_ROOT / "data" / "processed" / "bangalore_location_coords.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "metro_distances.csv"
EARTH_RADIUS_KM = 6371


def metro_stations(path=PLACES_PATH):
    places = pd.read_csv(path)
    stations = places[places["type"] == "Metro station"].drop_duplicates(subset="name")
    return stations[["name", "lat", "lon"]].reset_index(drop=True)


def nearest_station(lat, lon, stations):
    """(distance in km, station name) using the haversine formula, all stations at once"""
    lat1, lon1 = np.radians(lat), np.radians(lon)
    lat2, lon2 = np.radians(stations["lat"].to_numpy()), np.radians(stations["lon"].to_numpy())
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    km = 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))
    best = int(np.argmin(km))
    return float(km[best]), stations.loc[best, "name"]


def build(coords_path=COORDS_PATH, places_path=PLACES_PATH):
    stations = metro_stations(places_path)
    areas = pd.read_csv(coords_path).dropna(subset=["lat", "lon"])
    rows = []
    for _, area in areas.iterrows():
        km, name = nearest_station(area["lat"], area["lon"], stations)
        rows.append({"location": area["location"], "dist_to_metro_km": round(km, 4), "nearest_metro": name})
    return pd.DataFrame(rows), len(stations)


def main():
    table, count = build()
    table.to_csv(OUTPUT_PATH, index=False)
    print("Metro stations:", count)
    print("Areas:", len(table))
    print("Median distance to metro: %.1f km" % table["dist_to_metro_km"].median())
    print("Areas within 1 km of a metro:", int((table["dist_to_metro_km"] <= 1).sum()))
    print("Saved", OUTPUT_PATH)


if __name__ == "__main__":
    main()
