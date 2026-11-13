"""Checks reading exact positions and finding the places nearest to them."""

import pandas as pd

from frontend.exact_location import distances_km, nearest_places, parse_coordinates


def test_google_maps_link_with_at_sign():
    link = "https://www.google.com/maps/@12.9352,77.6974,17z"
    assert parse_coordinates(link) == (12.9352, 77.6974)


def test_google_maps_query_link():
    assert parse_coordinates("https://maps.google.com/?q=12.9716,77.5946") == (12.9716, 77.5946)


def test_google_maps_place_link():
    link = "https://www.google.com/maps/place/Some+Society/data=!4m6!3m5!1s0x0:0x0!8m2!3d12.9611!4d77.6387"
    assert parse_coordinates(link) == (12.9611, 77.6387)


def test_plain_coordinates():
    assert parse_coordinates("12.9716, 77.5946") == (12.9716, 77.5946)


def test_points_outside_bangalore_are_rejected():
    assert parse_coordinates("19.0760, 72.8777") is None   # Mumbai
    assert parse_coordinates("Prestige Lakeside Habitat") is None   # a name, not coordinates


def test_distance_is_right():
    # 0.01 degrees of latitude is about 1.11 km
    assert abs(distances_km(12.97, 77.59, [12.98], [77.59])[0] - 1.112) < 0.01


PLACES = pd.DataFrame([
    {"group": "school", "name": "Near School", "type": "School", "lat": 12.9720, "lon": 77.5946},
    {"group": "school", "name": "Far School", "type": "School", "lat": 12.9900, "lon": 77.5946},
    {"group": "school", "name": "Too Far School", "type": "School", "lat": 13.0500, "lon": 77.5946},
    {"group": "transit", "name": "Stop A", "type": "Bus stop", "lat": 12.9717, "lon": 77.5946},
    {"group": "transit", "name": "stop a", "type": "Bus stop", "lat": 12.9718, "lon": 77.5946},
    {"group": "hospital", "name": "Clinic", "type": "Hospital", "lat": 12.9730, "lon": 77.5950},
])


def test_nearest_places_sorted_within_radius():
    result = nearest_places(PLACES, 12.9716, 77.5946)
    assert [p["name"] for p in result["school"]] == ["Near School", "Far School"]


def test_same_name_kept_once():
    result = nearest_places(PLACES, 12.9716, 77.5946)
    assert len(result["transit"]) == 1


def test_real_city_table_gives_five_near_whitefield():
    places = pd.read_csv("data/processed/bangalore_places.csv")
    result = nearest_places(places, 12.9957, 77.7579)
    assert len(result["school"]) == 5
    assert result["school"][0]["km"] <= result["school"][-1]["km"]
