"""Checks the shared data preparation used by every model script."""

import pandas as pd

from data_processing.prepare_model_data import (
    ALL_FEATURES,
    add_location_price_feature,
    load_clean_data,
    prepare_train_test,
    trim_outliers,
)


def test_no_missing_values_in_model_features():
    data, train_data, test_data, _, _ = prepare_train_test()
    assert train_data[ALL_FEATURES].isna().sum().sum() == 0
    assert test_data[ALL_FEATURES].isna().sum().sum() == 0


def test_row_counts_match_the_report():
    data, train_data, test_data, _, _ = prepare_train_test()
    assert len(load_clean_data()) == 11672
    assert len(data) == 11272
    assert len(train_data) + len(test_data) == len(data)
    # sklearn rounds the 20% test share up: 11,272 x 0.2 = 2,254.4 -> 2,255
    assert len(test_data) == 2255
    assert len(train_data) == 9017


def test_trim_removes_extremes():
    data = load_clean_data()
    trimmed = trim_outliers(data)
    assert len(trimmed) < len(data)
    assert trimmed["total_sqft_clean"].max() <= data["total_sqft_clean"].quantile(0.99)


def test_location_price_uses_training_rows_only():
    # a test-only area must get the overall training median, not its own price,
    # otherwise the model would be peeking at the answers (data leakage)
    train = pd.DataFrame({"location": ["A", "A", "B"], "price_per_sqft": [1.0, 3.0, 10.0]})
    test = pd.DataFrame({"location": ["A", "C"], "price_per_sqft": [100.0, 100.0]})

    train_out, test_out, location_price, overall_price = add_location_price_feature(train, test)

    assert location_price["A"] == 2.0
    assert overall_price == 3.0
    assert test_out["location_price"].tolist() == [2.0, 3.0]


def test_split_is_repeatable():
    _, train_1, test_1, _, _ = prepare_train_test()
    _, train_2, test_2, _, _ = prepare_train_test()
    assert list(test_1.index) == list(test_2.index)
