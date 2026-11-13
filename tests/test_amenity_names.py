"""Checks how the nearest named schools, hospitals and transit stops are picked
from an OpenStreetMap answer (no internet needed: the answer is made up here)."""

from data_processing.fetch_amenity_names import build_query, pick_nearest, to_rows

LAT, LON = 12.9716, 77.5946


def node(lat_offset, tags):
    return {"type": "node", "lat": LAT + lat_offset, "lon": LON, "tags": tags}


ELEMENTS = [
    node(0.0001, {"amenity": "school"}),                                   # unnamed, very close
    {"type": "way", "center": {"lat": LAT + 0.0024, "lon": LON},
     "tags": {"amenity": "school", "name": "Green Valley School"}},        # drawn as an outline
    node(0.0010, {"amenity": "school", "name": "Sunrise School"}),
    node(0.0300, {"amenity": "hospital", "name": "Far Hospital"}),
    node(0.0014, {"amenity": "clinic", "name": "Near Clinic"}),
    node(0.0004, {"railway": "station", "station": "subway", "name": "MG Road"}),
    node(0.0002, {"highway": "bus_stop", "name": "Church Street"}),
    node(0.0003, {"highway": "bus_stop", "name": "Church Street"}),        # same stop, other side of the road
    node(0.0000, {"shop": "bakery", "name": "Bakery"}),                    # not one of our groups
]


def test_named_places_sorted_nearest_first():
    places = pick_nearest(ELEMENTS, LAT, LON)
    assert [p["name"] for p in places["school"]] == ["Sunrise School", "Green Valley School"]
    assert [p["name"] for p in places["hospital"]] == ["Near Clinic", "Far Hospital"]


def test_unnamed_places_left_out_when_named_ones_exist():
    names = [p["name"] for p in pick_nearest(ELEMENTS, LAT, LON)["school"]]
    assert not any(name.startswith("Unnamed") for name in names)


def test_duplicate_names_kept_once():
    transit = pick_nearest(ELEMENTS, LAT, LON)["transit"]
    assert [p["name"] for p in transit] == ["Church Street", "MG Road"]
    assert transit[1]["type"] == "Metro station"
    assert transit[0]["type"] == "Bus stop"


def test_at_most_five_per_group():
    many = [node(0.0001 * i, {"amenity": "school", "name": "School " + str(i)}) for i in range(1, 9)]
    schools = pick_nearest(many, LAT, LON)["school"]
    assert len(schools) == 5
    assert schools[0]["name"] == "School 1"


def test_ways_use_their_centre_point():
    green = [p for p in pick_nearest(ELEMENTS, LAT, LON)["school"] if p["name"] == "Green Valley School"][0]
    assert 0.2 < green["km"] < 0.3  # 0.0024 degrees of latitude is about 0.27 km


def test_unnamed_only_group_gets_one_label():
    places = pick_nearest([node(0.0001, {"highway": "bus_stop"})], LAT, LON)
    assert [p["name"] for p in places["transit"]] == ["Unnamed bus stop"]


def test_rows_for_csv():
    rows = to_rows("Test Area", pick_nearest(ELEMENTS, LAT, LON))
    assert rows[0]["rank"] == 1
    assert {row["group"] for row in rows} == {"school", "hospital", "transit"}
    assert to_rows("Empty", pick_nearest([], LAT, LON))[0]["group"] == "none"


def test_query_uses_three_km_radius():
    assert "around:3000" in build_query(LAT, LON)


def test_places_near_keeps_only_within_three_km():
    from data_processing.fetch_amenity_names import places_near
    near_school = node(0.01, {"amenity": "school", "name": "Close"})     # about 1.1 km
    far_school = node(0.05, {"amenity": "school", "name": "Far"})        # about 5.6 km
    kept = places_near([near_school, far_school], LAT, LON)
    assert [e["tags"]["name"] for e in kept] == ["Close"]


def test_city_box_contains_bangalore():
    from data_processing.fetch_amenity_names import CITY_BOX, inside
    assert inside(CITY_BOX, 12.9957, 77.7579)        # Whitefield
    assert not inside(CITY_BOX, 15.3508, 75.1420)    # an area geocoded far away


def test_rows_keep_each_place_position_for_the_map():
    rows = to_rows("Test Area", pick_nearest(ELEMENTS, LAT, LON))
    green = [r for r in rows if r["name"] == "Green Valley School"][0]
    assert abs(green["lat"] - (LAT + 0.0024)) < 1e-9   # a way's centre point
    assert green["lon"] == LON
