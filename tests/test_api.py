"""Checks the API logic. These call the endpoint functions directly, so no
server has to be running."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.main import (
    BASE_PRICE,
    FAIR_RANGE_PERCENT,
    health_check,
    list_locations,
    model_info,
    predict,
    price_verdict,
)
from backend.schemas import PredictionRequest

KNOWN_AREA = "Whitefield"


def make_request(**changes):
    values = {"location": KNOWN_AREA, "size_sqft": 1200, "bedrooms": 2, "bathrooms": 2}
    values.update(changes)
    return PredictionRequest(**values)


def test_health():
    assert health_check()["status"] == "ok"


def test_locations_are_sorted_and_include_known_area():
    locations = list_locations()["locations"]
    assert locations == sorted(locations)
    assert KNOWN_AREA in locations


def test_prediction_is_positive_with_a_range():
    result = predict(make_request())
    assert result.predicted_price > 0
    assert result.price_low < result.predicted_price < result.price_high


def test_factors_add_up_to_the_prediction():
    # shap guarantees: starting price + every factor = the model's prediction
    result = predict(make_request())
    total = BASE_PRICE + sum(f.effect for f in result.factors)
    assert abs(total - result.predicted_price) < 0.5


def test_bigger_home_costs_more():
    small = predict(make_request(size_sqft=800)).predicted_price
    large = predict(make_request(size_sqft=2500, bedrooms=3, bathrooms=3)).predicted_price
    assert large > small


def test_unknown_location_returns_404():
    with pytest.raises(HTTPException) as error:
        predict(make_request(location="Not A Real Place"))
    assert error.value.status_code == 404


def test_bad_inputs_are_rejected():
    with pytest.raises(ValidationError):
        make_request(size_sqft=-5)
    with pytest.raises(ValidationError):
        make_request(bedrooms=0)
    with pytest.raises(ValidationError):
        make_request(size_sqft=300, bedrooms=4)  # under 200 sqft per bedroom


def test_verdicts():
    assert price_verdict(100, 100)[0] == "Looks fairly priced"
    assert price_verdict(100 + FAIR_RANGE_PERCENT + 1, 100)[0] == "Looks overpriced"
    assert price_verdict(100 - FAIR_RANGE_PERCENT - 1, 100)[0] == "Looks underpriced"


def test_asking_price_gives_verdict():
    result = predict(make_request(asking_price=50))
    assert result.verdict is not None
    assert result.difference_percent is not None


def test_warning_for_size_outside_training_data():
    result = predict(make_request(size_sqft=20000, bedrooms=4, bathrooms=4))
    assert len(result.warnings) > 0


def test_model_info_has_error():
    assert model_info()["error"]["mape_percent"] > 0
