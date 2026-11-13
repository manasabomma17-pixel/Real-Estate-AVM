"""
Builds the factors that bring our 2017-19 prices up to today's market.

Our model learned how size, rooms and area affect price from listings of
around 2017-19. Prices have risen a lot since, so each estimate is multiplied
by a market-growth factor ("time adjustment", a standard method for valuation
models whose data is older than today).

For each area we compare today's published average asking rate with the
median asking rate in our data:

    raw factor = today's rate / our data's rate for that area

Published averages are noisy for single areas, so each raw factor is pulled
toward the city-wide median factor, more strongly when the area has few
listings in our data (shrinkage):

    weight = listings / (listings + SHRINK_STRENGTH)
    factor = weight x raw factor + (1 - weight) x city factor

then kept between MIN_FACTOR and MAX_FACTOR. Areas without a published rate
use the city factor.

Input:  data/external/current_rates_2026.csv  (locality, rate_rs_per_sqft)
Output: data/processed/price_adjustment.csv

Source of the current rates: Home Bazaar, "Property Rates in Bangalore",
updated 22 October 2026 (average asking rates per locality).

Run from the project folder:  python -m data_processing.build_price_adjustment
To update next quarter: replace the rates file with newer figures and re-run.
"""

import re

import pandas as pd

from data_processing.prepare_model_data import prepare_train_test

RATES_PATH = "data/external/current_rates_2026.csv"
OUTPUT_PATH = "data/processed/price_adjustment.csv"

SHRINK_STRENGTH = 20   # an area needs about 20 listings to be trusted half-way
MIN_LISTINGS = 5       # areas with fewer listings are too noisy to compare
MIN_FACTOR = 1.0
MAX_FACTOR = 3.0

# published locality names that are spelled differently in our dataset
ALIASES = {"Kasavanahalli": "Kasavanhalli", "Hennur": "Hennur Road", "Bannerghatta": "Bannerghatta Road"}


def simplify(name):
    """'R.T. Nagar' and 'RT Nagar' compare as the same name"""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def main():
    data, train_data, test_data, location_price, overall_price = prepare_train_test()
    our_rates = (data["price_per_sqft"] * 100000).groupby(data["location"]).median()
    listings = data["location"].value_counts()

    by_simple_name = {}
    for location in our_rates.index:
        by_simple_name.setdefault(simplify(location), []).append(location)

    current = pd.read_csv(RATES_PATH)
    rows = []
    for _, published in current.iterrows():
        name = ALIASES.get(published["locality"], published["locality"])
        matches = by_simple_name.get(simplify(name), [])
        if not matches:
            print("  no match in our data for", published["locality"])
            continue
        location = max(matches, key=lambda m: listings.get(m, 0))
        if listings[location] < MIN_LISTINGS:
            continue
        rows.append({
            "location": location,
            "published_name": published["locality"],
            "listings": int(listings[location]),
            "our_rate": round(float(our_rates[location])),
            "current_rate": int(published["rate_rs_per_sqft"]),
        })

    table = pd.DataFrame(rows)
    table["raw_factor"] = (table["current_rate"] / table["our_rate"]).round(3)
    city_factor = round(float(table["raw_factor"].median()), 3)

    weight = table["listings"] / (table["listings"] + SHRINK_STRENGTH)
    factor = weight * table["raw_factor"] + (1 - weight) * city_factor
    table["factor"] = factor.clip(MIN_FACTOR, MAX_FACTOR).round(3)

    # one extra row holds the city-wide factor used for every other area
    city_row = pd.DataFrame([{"location": "_city_", "published_name": "median of all areas",
                              "listings": int(table["listings"].sum()), "our_rate": None,
                              "current_rate": None, "raw_factor": city_factor, "factor": city_factor}])
    pd.concat([table, city_row], ignore_index=True).to_csv(OUTPUT_PATH, index=False)

    print("City-wide factor (median):", city_factor)
    print("Areas with their own factor:", len(table), "covering", table["listings"].sum(), "listings")
    print(table.sort_values("listings", ascending=False).head(10).to_string(index=False))
    print("Saved", OUTPUT_PATH)


if __name__ == "__main__":
    main()
