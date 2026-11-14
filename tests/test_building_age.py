"""Checks the building-age rule of thumb and the age advice."""

from backend.services.building_age import age_adjustment, age_suggestions, depreciation_share, find_building_age


def test_valuer_rule_20_years_is_30_percent():
    # registered valuer textbook case: 20 / 60 x (100 - 10) = 30%
    assert round(depreciation_share(20), 3) == 0.30


def test_depreciation_stops_at_the_end_of_life():
    assert depreciation_share(0) == 0
    assert depreciation_share(90) == depreciation_share(60) == 0.9


def test_adjustment_only_touches_the_building_not_the_land():
    result = age_adjustment(1200, 20, 157.0)
    # 1200 sqft x Rs 2,500 = Rs 30 Lakhs to rebuild, 30% of that is 9 Lakhs
    assert result["rebuild_cost_lakhs"] == 30.0
    assert result["deduction_lakhs"] == 9.0
    assert result["adjusted_price"] == 148.0


def test_age_advice_matches_the_age():
    assert age_suggestions(None, False) == []
    assert "RERA" in age_suggestions(None, True)[0][2]
    assert age_suggestions(3, False)[0][0] == "good"
    assert age_suggestions(25, False)[0][0] == "warning"


def test_age_is_read_from_listing_text():
    assert find_building_age("2 BHK, 8 years old, east facing") == (8, False)
    assert find_building_age("Age of property: 12 years") == (12, False)
    assert find_building_age("Under Construction, possession Dec 2027") == (None, True)
    assert find_building_age("2 BHK in Whitefield, 1200 sqft") == (None, False)
