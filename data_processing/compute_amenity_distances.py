import pandas as pd
import requests
import time
import math

locations = pd.read_csv("data/processed/bangalore_location_coords.csv")
locations = locations.dropna(subset=["lat", "lon"])
print("Locations to check:", len(locations))

url = "https://overpass.openstreetmap.fr/api/interpreter"
headers = {"User-Agent": "real-estate-avm-project"}


def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


results = []

for i, row in locations.iterrows():
    lat = row["lat"]
    lon = row["lon"]
    loc = row["location"]
    print(i, "-", loc)

    query = """
    [out:json][timeout:40];
    (
      node["amenity"="school"](around:3000,%f,%f);
      node["amenity"="hospital"](around:3000,%f,%f);
      node["amenity"="clinic"](around:3000,%f,%f);
      node["highway"="bus_stop"](around:3000,%f,%f);
      node["railway"="station"](around:3000,%f,%f);
    );
    out body;
    """ % (lat, lon, lat, lon, lat, lon, lat, lon, lat, lon)

    try:
        response = requests.post(url, data={"data": query}, headers=headers, timeout=50)
        elements = response.json()["elements"]
    except:
        elements = []

    school_dist = None
    hospital_dist = None
    transit_dist = None

    for el in elements:
        tags = el.get("tags", {})
        d = distance_km(lat, lon, el["lat"], el["lon"])

        if tags.get("amenity") == "school":
            if school_dist is None or d < school_dist:
                school_dist = d

        if tags.get("amenity") in ["hospital", "clinic"]:
            if hospital_dist is None or d < hospital_dist:
                hospital_dist = d

        if tags.get("highway") == "bus_stop" or tags.get("railway") == "station":
            if transit_dist is None or d < transit_dist:
                transit_dist = d

    results.append({
        "location": loc,
        "lat": lat,
        "lon": lon,
        "dist_to_school_km": school_dist,
        "dist_to_hospital_km": hospital_dist,
        "dist_to_transit_km": transit_dist
    })

    time.sleep(3)  # be nice to the free server

output = pd.DataFrame(results)
output.to_csv("data/processed/bangalore_amenity_distances.csv", index=False)
print("Saved!")
