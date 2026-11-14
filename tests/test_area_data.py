"""Checks the numbers the API sends the React app about each area."""

from backend.services import area_data

AREA = "Whitefield"


def test_area_list_matches_the_model_lookup():
    areas = area_data.area_list()
    names = [a["name"] for a in areas]
    assert names == sorted(names)
    assert len(names) == len(area_data.lookup)
    whitefield = next(a for a in areas if a["name"] == AREA)
    assert whitefield["records"] > 100


def test_summary_is_brought_up_to_today():
    summary = area_data.area_summary(AREA, 2)
    factor = area_data.market_factor(AREA)[0]
    rows = area_data.listings[area_data.listings["location"] == AREA]
    expected = rows["rate"].median() * factor
    assert abs(summary["typical_rate_today"] - expected) <= 50
    assert summary["market_basis"] == "area"
    assert 0 <= summary["ready_percent"] <= 100


def test_comparison_uses_same_area_and_bhk_when_there_are_enough():
    result = area_data.comparison(AREA, 2)
    assert result["scope"] == "area_bhk"
    assert result["count"] == len(result["rates"]) >= 5
    low, high = result["middle_half"]
    assert low <= result["typical"] <= high


def test_comparison_widens_when_records_are_few():
    # nobody lists a 9 BHK in Whitefield, so it compares more widely
    result = area_data.comparison(AREA, 9)
    assert result["scope"] in ("area", "city_bhk")


def test_nearby_areas_skip_spelling_variants_and_thin_areas():
    result = area_data.nearby_areas(AREA)
    names = [a["name"] for a in result["areas"]]
    assert len(names) == 10
    assert all(area_data.clean_name(n) != area_data.clean_name(AREA) for n in names)
    assert all(a["records"] >= area_data.MIN_LISTINGS for a in result["areas"])
    distances = [a["km"] for a in result["areas"]]
    assert distances == sorted(distances)


def test_places_from_an_exact_point_are_within_3_km():
    centre = area_data.lookup.loc[AREA]
    result = area_data.places_near_point(float(centre["lat"]), float(centre["lon"]))
    assert result["exact"] is True
    for group in area_data.GROUPS:
        assert len(result["places"][group]) <= 5
        assert all(p["km"] <= 3 for p in result["places"][group])

