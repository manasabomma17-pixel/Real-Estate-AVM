"""
Finding a flat's exact position, and the places nearest to it.

Our dataset only knows each listing's area, so by default everything is
measured from the area's centre. When a user knows more (the society name, a
street or landmark, or a Google Maps link), this file turns that into a
latitude and longitude, then finds the nearest schools, hospitals and transit
stops from that exact point using the city-wide table of places.

The price estimate does not use this: the model was trained with every listing
at its area's centre, so it keeps getting the same kind of input it learned on.
"""

import math
import re

import numpy as np
import requests

# Bangalore and its surroundings. points outside are rejected as a likely
# mistake, and geocoder searches are limited to this box
CITY_BOX = {"south": 12.60, "west": 77.25, "north": 13.40, "east": 77.95}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "real-estate-avm-project (student OJT project)"}


def inside_city(lat, lon):
    return CITY_BOX["south"] <= lat <= CITY_BOX["north"] and CITY_BOX["west"] <= lon <= CITY_BOX["east"]


def parse_coordinates(text):
    """reads a position from a Google Maps link or typed coordinates:
    '...google.com/maps/@12.9352,77.6974,17z', '...?q=12.9352,77.6974',
    or just '12.9352, 77.6974'. returns (lat, lon) or None"""
    patterns = [
        r"@(-?\d{1,2}\.\d+),\s*(-?\d{1,3}\.\d+)",                       # .../@lat,lon,zoom
        r"[?&](?:q|query|ll|destination|center)=(-?\d{1,2}\.\d+),\s*(-?\d{1,3}\.\d+)",
        r"!3d(-?\d{1,2}\.\d+)!4d(-?\d{1,3}\.\d+)",                       # place links
        r"^\s*(-?\d{1,2}\.\d+)\s*[, ]\s*(-?\d{1,3}\.\d+)\s*$",           # plain numbers
    ]
    for pattern in patterns:
        match = re.search(pattern, text.strip())
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))
            if inside_city(lat, lon):
                return lat, lon
    return None


def geocode(query):
    """looks up a society, street or landmark in Bangalore with Nominatim
    (OpenStreetMap's free geocoder, the same one used to build our dataset).
    returns (lat, lon, the name it matched) or None"""
    if "bangalore" not in query.lower() and "bengaluru" not in query.lower():
        query = query + ", Bangalore"
    params = {
        "q": query, "format": "json", "limit": 1, "countrycodes": "in", "bounded": 1,
        "viewbox": "%f,%f,%f,%f" % (CITY_BOX["west"], CITY_BOX["north"], CITY_BOX["east"], CITY_BOX["south"]),
    }
    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=15)
        results = response.json() if response.status_code == 200 else []
    except (requests.exceptions.RequestException, ValueError):
        return None
    if not results:
        return None
    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    if not inside_city(lat, lon):
        return None
    return lat, lon, results[0].get("display_name", query)


def distances_km(lat, lon, lats, lons):
    """haversine distance from one point to many, in km, all at once with numpy"""
    lat1, lon1 = math.radians(lat), math.radians(lon)
    lat2, lon2 = np.radians(lats), np.radians(lons)
    a = np.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def nearest_places(places, lat, lon, per_group=5, radius_km=3):
    """the nearest named places in each group from an exact point, closest
    first, each name once. places is the city table (group, name, type, lat, lon).
    returns {"school": [...], "hospital": [...], "transit": [...]} with
    {"name", "km", "type", "lat", "lon"} for each place"""
    table = places.copy()
    table["km"] = distances_km(lat, lon, table["lat"].values, table["lon"].values)
    table = table[table["km"] <= radius_km].sort_values("km")

    result = {}
    for group in ["school", "hospital", "transit"]:
        rows = table[table["group"] == group]
        rows = rows.loc[~rows["name"].str.strip().str.lower().duplicated()].head(per_group)
        result[group] = [
            {"name": r["name"], "km": round(float(r["km"]), 3), "type": r["type"], "lat": r["lat"], "lon": r["lon"]}
            for _, r in rows.iterrows()
        ]
    return result
