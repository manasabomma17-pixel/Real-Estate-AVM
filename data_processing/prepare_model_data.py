"""
Shared data preparation for every model script.

Before this file existed, each training script copied the same cleaning steps
(fill missing values, trim outliers, add the location price feature). Keeping
them in one place means every model is trained and tested on exactly the same
rows, so their scores can be compared fairly.
"""

import pandas as pd
from sklearn.model_selection import train_test_split

from backend.config import load_config

# the shared settings live in configs/config.yaml
config = load_config()

DATA_PATH = config["dataset"]["path"]
RANDOM_SEED = config["random_seed"]
TEST_SIZE = config["split"]["test_size"]
TARGET = config["dataset"]["target"]  # price is in Lakhs (1 Lakh = 1,00,000 rupees)
LOWER_QUANTILE = config["outlier_trim"]["lower_quantile"]
UPPER_QUANTILE = config["outlier_trim"]["upper_quantile"]

# the three facts about the property itself
PROPERTY_FEATURES = ["bhk", "bath", "total_sqft_clean"]

# where the property is, what is near it, and how pricey the area is
LOCATION_FEATURES = [
    "lat", "lon",
    "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km",
    "location_price",
]

# the exact order the saved model expects its columns in
ALL_FEATURES = PROPERTY_FEATURES + LOCATION_FEATURES

DISTANCE_COLUMNS = ["dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]


def load_clean_data(path=DATA_PATH):
    """loads the final dataset and fills the gaps the models cannot handle"""
    data = pd.read_csv(path)

    # a missing bathroom count is treated as 0, the same as in training
    data["bath"] = data["bath"].fillna(0)

    # some areas had no amenity found within 3 km. the median is used so
    # those rows can still be used for training
    for column in DISTANCE_COLUMNS:
        data[column] = data[column].fillna(data[column].median())

    data["price_per_sqft"] = data[TARGET] / data["total_sqft_clean"]
    return data


def trim_outliers(data):
    """drops the most extreme 1% at each end of price per sqft and of size.
    these are mostly data entry mistakes, like land measured in other units.
    both sets of limits are worked out on the untrimmed data, exactly as when
    the saved model was trained (11,672 rows in, 11,272 rows out)"""
    low_rate = data["price_per_sqft"].quantile(LOWER_QUANTILE)
    high_rate = data["price_per_sqft"].quantile(UPPER_QUANTILE)
    small = data["total_sqft_clean"].quantile(LOWER_QUANTILE)
    large = data["total_sqft_clean"].quantile(UPPER_QUANTILE)

    data = data[(data["price_per_sqft"] >= low_rate) & (data["price_per_sqft"] <= high_rate)]
    data = data[(data["total_sqft_clean"] >= small) & (data["total_sqft_clean"] <= large)]
    return data


def split_data(data):
    """the same 80/20 split everywhere, so the test rows never change"""
    return train_test_split(data, test_size=TEST_SIZE, random_state=RANDOM_SEED)


def add_location_price_feature(train_data, test_data):
    """adds location_price: the median price per sqft of each area.

    it is worked out from the training rows only. if the test rows were used
    too, the model would be peeking at the answers it is tested on (leakage).
    areas with no training rows get the overall median."""
    train_data = train_data.copy()
    test_data = test_data.copy()

    location_price = train_data.groupby("location")["price_per_sqft"].median()
    overall_price = train_data["price_per_sqft"].median()

    train_data["location_price"] = train_data["location"].map(location_price).fillna(overall_price)
    test_data["location_price"] = test_data["location"].map(location_price).fillna(overall_price)

    return train_data, test_data, location_price, overall_price


def build_location_lookup(data, location_price, overall_price):
    """one row per area with everything the API needs to make a prediction,
    so a user only has to pick an area name"""
    columns = ["location", "lat", "lon"] + DISTANCE_COLUMNS
    lookup = data.drop_duplicates(subset="location")[columns].copy()
    lookup["location_price"] = lookup["location"].map(location_price).fillna(overall_price)
    return lookup


def prepare_train_test():
    """runs every step above and returns train and test rows ready to use"""
    data = load_clean_data()
    data = trim_outliers(data)
    train_data, test_data = split_data(data)
    train_data, test_data, location_price, overall_price = add_location_price_feature(train_data, test_data)
    return data, train_data, test_data, location_price, overall_price
