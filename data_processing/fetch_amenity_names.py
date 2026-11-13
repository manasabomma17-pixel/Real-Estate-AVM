"""
Finds the names of the 5 nearest schools, hospitals/clinics and transit stops
(bus, Metro, railway) for every area the app can price, so the app can list
"Schools nearby: Delhi Public School, 450 m ..." instead of only a distance.

It asks the free OpenStreetMap Overpass API about each area once and saves
the answers to data/processed/amenity_places.csv, one row per place. The model is not changed:
it still uses the distances it was trained on. This file is only for display.

Two ways to run it, from the project folder (needs internet):

    python data_processing/fetch_amenity_names.py --bulk
        Recommended. Downloads every school, hospital and transit stop in
        Bangalore in ONE request (a few minutes), keeps a copy in data/raw/,
        then works out the 5 nearest for all areas on this computer. Much
        kinder to the free servers than 881 separate requests.

    python data_processing/fetch_amenity_names.py               # one request per area
    python data_processing/fetch_amenity_names.py --area "Whitefield"
        Slower. Safe to stop and restart: areas already saved are skipped.
"""

import argparse
import math
import os
import time

import pandas as pd
import requests

LOOKUP_PATH = "data/processed/location_lookup.csv"
OUTPUT_PATH = "data/processed/amenity_places.csv"
PLACES_PER_GROUP = 5

SEARCH_RADIUS_M = 3000  # the same 3 km radius used for the model's distances

# bulk mode: one box around Bangalore. areas geocoded outside it (a few names
# matched places elsewhere in India) are fetched one by one instead
CITY_BOX = {"south": 12.60, "west": 77.25, "north": 13.40, "east": 77.95}
BULK_CACHE_PATH = "data/raw/bangalore_osm_places.json"

# every school, hospital and transit stop in the city with its position, as a
# small table the app can search from any exact point a user gives it
PLACES_TABLE_PATH = "data/processed/bangalore_places.csv"

# free public Overpass servers. if one is busy or down, the next is tried
SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]
HEADERS = {"User-Agent": "real-estate-avm-project (student OJT project)"}

# one row per place. rank 1 is the nearest in its group. an area where nothing
# at all was found gets a single row with group "none", so it counts as done
COLUMNS = ["location", "group", "rank", "name", "km", "type", "lat", "lon"]


def distance_km(lat1, lon1, lat2, lon2):
    """haversine distance between two points on the earth, in km"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def build_query(lat, lon):
    """nwr = nodes, ways and relations. schools and hospitals are often drawn
    as building outlines (ways), not single points, so all three are needed.
    'out center' gives each outline a centre point to measure distance to"""
    around = "(around:%d,%f,%f)" % (SEARCH_RADIUS_M, lat, lon)
    return (
        "[out:json][timeout:60];("
        'nwr["amenity"="school"]' + around + ";"
        'nwr["amenity"~"^(hospital|clinic)$"]' + around + ";"
        'node["highway"="bus_stop"]' + around + ";"
        'nwr["railway"~"^(station|halt)$"]' + around + ";"
        'nwr["station"="subway"]' + around + ";"
        ");out center tags;"
    )


def category_of(tags):
    """which of our three groups an OpenStreetMap place belongs to"""
    if tags.get("amenity") == "school":
        return "school"
    if tags.get("amenity") in ("hospital", "clinic"):
        return "hospital"
    if tags.get("station") == "subway" or tags.get("railway") in ("station", "halt") \
            or tags.get("highway") == "bus_stop":
        return "transit"
    return None


def transit_type(tags):
    if tags.get("station") == "subway":
        return "Metro station"
    if tags.get("railway") in ("station", "halt"):
        return "Railway station"
    return "Bus stop"


def place_name(tags):
    return tags.get("name:en") or tags.get("name")


def pick_nearest(elements, lat, lon, per_group=PLACES_PER_GROUP):
    """for each group, the nearest places that have a name, closest first.
    the same name twice (bus stops on both sides of a road, or a building
    mapped twice) is kept once, at its nearest distance. unnamed places are
    left out, unless a group has no named place at all.

    returns {"school": [...], "hospital": [...], "transit": [...]}, each a
    list of {"name", "km", "type"}"""
    named = {"school": {}, "hospital": {}, "transit": {}}
    unnamed = {}

    for element in elements:
        tags = element.get("tags", {})
        group = category_of(tags)
        if group is None:
            continue

        # nodes have lat/lon, ways and relations have a centre point
        point = element if "lat" in element else element.get("center")
        if not point:
            continue

        km = round(distance_km(lat, lon, point["lat"], point["lon"]), 3)
        kind = transit_type(tags) if group == "transit" else group.title()
        name = place_name(tags)

        if name:
            key = name.strip().lower()
            if key not in named[group] or km < named[group][key]["km"]:
                named[group][key] = {"name": name.strip(), "km": km, "type": kind,
                                     "lat": point["lat"], "lon": point["lon"]}
        elif group not in unnamed or km < unnamed[group]["km"]:
            label = "Unnamed " + (kind.lower() if group == "transit" else group)
            unnamed[group] = {"name": label, "km": km, "type": kind,
                              "lat": point["lat"], "lon": point["lon"]}

    result = {}
    for group in named:
        places = sorted(named[group].values(), key=lambda p: p["km"])[:per_group]
        if not places and group in unnamed:
            places = [unnamed[group]]
        result[group] = places
    return result


def to_rows(location, places):
    """turns pick_nearest's answer into rows for the CSV"""
    rows = []
    for group, group_places in places.items():
        for rank, place in enumerate(group_places, start=1):
            rows.append({"location": location, "group": group, "rank": rank,
                         "name": place["name"], "km": place["km"], "type": place["type"],
                         "lat": place.get("lat"), "lon": place.get("lon")})
    if not rows:
        rows.append({"location": location, "group": "none", "rank": 0, "name": "", "km": None, "type": "",
                     "lat": None, "lon": None})
    return rows


def ask_overpass(query, timeout=90):
    """tries each server up to 2 times. returns the list of places, or None"""
    for attempt in range(2):
        for server in SERVERS:
            try:
                response = requests.post(server, data={"data": query}, headers=HEADERS, timeout=timeout)
                if response.status_code == 200:
                    return response.json().get("elements", [])
                # 429 = too many requests, 504 = server busy: wait, then try the next one
                time.sleep(5)
            except (requests.exceptions.RequestException, ValueError):
                time.sleep(3)
        time.sleep(15)
    return None


def build_city_query(box):
    """the same five kinds of place as build_query, but for the whole city box"""
    bbox = "(%f,%f,%f,%f)" % (box["south"], box["west"], box["north"], box["east"])
    return (
        "[out:json][timeout:300];("
        'nwr["amenity"="school"]' + bbox + ";"
        'nwr["amenity"~"^(hospital|clinic)$"]' + bbox + ";"
        'node["highway"="bus_stop"]' + bbox + ";"
        'nwr["railway"~"^(station|halt)$"]' + bbox + ";"
        'nwr["station"="subway"]' + bbox + ";"
        ");out center tags;"
    )


def inside(box, lat, lon):
    return box["south"] <= lat <= box["north"] and box["west"] <= lon <= box["east"]


def places_near(all_places, lat, lon):
    """from the city-wide list, the places within a small square around the
    area. pick_nearest then measures exact distances and keeps those within 3 km.
    0.03 degrees is about 3.3 km, so nothing within 3 km is missed"""
    near = []
    for element in all_places:
        point = element if "lat" in element else element.get("center")
        if point and abs(point["lat"] - lat) <= 0.03 and abs(point["lon"] - lon) <= 0.03:
            if distance_km(lat, lon, point["lat"], point["lon"]) <= SEARCH_RADIUS_M / 1000:
                near.append(element)
    return near


def save_places_table(all_places):
    """one row per named place: group, name, type, lat, lon"""
    rows = []
    for element in all_places:
        tags = element.get("tags", {})
        group = category_of(tags)
        point = element if "lat" in element else element.get("center")
        name = place_name(tags)
        if group is None or not point or not name:
            continue
        kind = transit_type(tags) if group == "transit" else group.title()
        rows.append({"group": group, "name": name.strip(), "type": kind,
                     "lat": round(point["lat"], 6), "lon": round(point["lon"], 6)})
    table = pd.DataFrame(rows).drop_duplicates()
    table.to_csv(PLACES_TABLE_PATH, index=False)
    print("Saved", len(table), "named places to", PLACES_TABLE_PATH)


def bulk_main(places_only=False):
    import json

    areas = pd.read_csv(LOOKUP_PATH)

    if os.path.exists(BULK_CACHE_PATH):
        print("Using the saved city download:", BULK_CACHE_PATH)
        with open(BULK_CACHE_PATH) as f:
            all_places = json.load(f)
    else:
        print("Downloading every school, hospital and transit stop in Bangalore (one request,")
        print("usually 1-5 minutes; if the servers are busy it tries again)...")
        all_places = ask_overpass(build_city_query(CITY_BOX), timeout=400)
        if all_places is None:
            print("The servers are busy right now. Please try again in a while.")
            return
        os.makedirs(os.path.dirname(BULK_CACHE_PATH), exist_ok=True)
        with open(BULK_CACHE_PATH, "w") as f:
            json.dump(all_places, f)
        print("Downloaded", len(all_places), "places and saved them to", BULK_CACHE_PATH)

    save_places_table(all_places)
    if places_only:
        return

    rows = []
    outside = []
    for number, (_, area) in enumerate(areas.iterrows(), start=1):
        if not inside(CITY_BOX, area["lat"], area["lon"]):
            outside.append(area)
            continue
        places = pick_nearest(places_near(all_places, area["lat"], area["lon"]), area["lat"], area["lon"])
        rows.extend(to_rows(area["location"], places))
        if number % 100 == 0:
            print("  worked out", number, "of", len(areas), "areas")

    # the few areas outside the city box get their own small request
    for area in outside:
        elements = ask_overpass(build_query(area["lat"], area["lon"]))
        if elements is None:
            print("  could not fetch", area["location"], "(outside the city box); skipped")
            continue
        rows.extend(to_rows(area["location"], pick_nearest(elements, area["lat"], area["lon"])))
        time.sleep(1)

    # the bulk run replaces the whole file, so every area comes from the same
    # download. an area it could not fetch keeps its rows from the last run
    result = pd.DataFrame(rows, columns=COLUMNS)
    if os.path.exists(OUTPUT_PATH):
        previous = pd.read_csv(OUTPUT_PATH)
        kept = previous[~previous["location"].isin(result["location"])]
        result = pd.concat([result, kept], ignore_index=True)
    result.to_csv(OUTPUT_PATH, index=False)

    found = result[result["group"] != "none"]
    print("\nSaved", OUTPUT_PATH, "for", result["location"].nunique(), "areas")
    for group in ["school", "hospital", "transit"]:
        counts = found[found["group"] == group].groupby("location").size()
        print(" ", group + ":", (counts >= 5).sum(), "areas have 5,", (counts < 5).sum(), "have fewer")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="only do this many new areas (for a quick test)")
    parser.add_argument("--area", help="only do this one area")
    parser.add_argument("--bulk", action="store_true",
                        help="download the whole city in one request (recommended)")
    parser.add_argument("--places-only", action="store_true",
                        help="only rebuild data/processed/bangalore_places.csv from the saved download")
    args = parser.parse_args()

    if args.bulk or args.places_only:
        bulk_main(places_only=args.places_only)
        return

    areas = pd.read_csv(LOOKUP_PATH)
    if args.area:
        areas = areas[areas["location"] == args.area]
        if len(areas) == 0:
            print("Unknown area:", args.area)
            return

    if os.path.exists(OUTPUT_PATH):
        done = pd.read_csv(OUTPUT_PATH)
    else:
        done = pd.DataFrame(columns=COLUMNS)
    done_names = set(done["location"])

    to_do = areas[~areas["location"].isin(done_names)]
    if args.limit:
        to_do = to_do.head(args.limit)
    print("Areas already saved:", len(done_names), "| to fetch now:", len(to_do))

    failed = 0
    for number, (_, area) in enumerate(to_do.iterrows(), start=1):
        elements = ask_overpass(build_query(area["lat"], area["lon"]))
        if elements is None:
            failed += 1
            print(number, "/", len(to_do), area["location"], "- FAILED, will retry on the next run")
            continue

        places = pick_nearest(elements, area["lat"], area["lon"])

        # save after every area, so stopping the script loses nothing
        pd.DataFrame(to_rows(area["location"], places), columns=COLUMNS).to_csv(
            OUTPUT_PATH, mode="a", header=not os.path.exists(OUTPUT_PATH), index=False)

        counts = ", ".join(group + ": " + str(len(places[group])) for group in places)
        nearest = places["school"][0]["name"] if places["school"] else "no school found"
        print(number, "/", len(to_do), area["location"], "-", counts, "| nearest school:", nearest)

        time.sleep(1)  # be polite to the free servers

    print("\nDone. Failed this run:", failed, "(run again to retry them)")


if __name__ == "__main__":
    main()
