"""Checks the suggestions shown after a price estimate."""

import pandas as pd

from frontend.suggestions import area_rates, build_suggestions, cheaper_nearby_areas

data = pd.read_csv("data/processed/bangalore_final_dataset.csv")
location_info = pd.read_csv("data/processed/location_lookup.csv").set_index("location")

# a real response from the API for this flat
RESULT = {"predicted_price": 62.81, "price_low": 47.92, "price_high": 77.7,
          "price_per_sqft": 5234.0, "warnings": []}


def titles(asking_price=None, result=RESULT, **changes):
    request = {"location": "Whitefield", "size_sqft": 1200, "bedrooms": 2, "bathrooms": 2,
               "asking_price": asking_price}
    request.update(changes)
    return [title for kind, title, text in build_suggestions(request, result, data, location_info)]


def test_overpriced_gets_negotiation_advice():
    assert "Negotiate the price down" in titles(asking_price=80)


def test_fair_price_is_called_fair():
    assert "Fairly priced" in titles(asking_price=63)


def test_cheap_price_gets_a_caution():
    assert "Possibly a good deal, but check why" in titles(asking_price=40)


def test_no_asking_price_prompts_for_one():
    assert "Check an asking price" in titles()


def test_small_flat_is_flagged():
    assert "Smaller than usual" in titles(size_sqft=600)


def test_fewer_bathrooms_is_flagged():
    assert "Fewer bathrooms than bedrooms" in titles(bedrooms=3, bathrooms=1, size_sqft=1500)


def test_model_warnings_are_passed_on():
    result = dict(RESULT, warnings=["Size is larger than any property the model was trained on."])
    assert "Estimate less reliable" in titles(result=result)


def test_cheaper_areas_are_close_and_cheaper():
    rates = area_rates(data)
    nearby = cheaper_nearby_areas("Whitefield", location_info, rates)
    assert len(nearby) > 0
    for area, km, rate in nearby:
        assert km <= 5
        assert rate < rates.loc["Whitefield", "rate"]


def test_exact_distances_are_used_when_given():
    request = {"location": "Whitefield", "size_sqft": 1200, "bedrooms": 2, "bathrooms": 2, "asking_price": None}
    far = build_suggestions(request, RESULT, data, location_info,
                            exact_distances={"school": 2.5, "hospital": 0.3, "transit": 0.2})
    travel = [text for kind, title, text in far if title == "Check your daily travel"]
    assert travel and travel[0].startswith("From the flat's exact location")
