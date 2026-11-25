"""
Keeps today's prices up to date between our yearly locality rates.

Our area factors (data/processed/price_adjustment.csv) bring the 2017-19
model prices up to October 2026, using published locality rates. After that,
every quarter, official house price indices for Bengaluru are published:

- National Housing Bank (NHB) RESIDEX, quarterly, from bank valuation prices
- Reserve Bank of India (RBI) House Price Index, quarterly, from registrations

Each new quarter's change for Bengaluru is added as one row to
data/external/bengaluru_price_index.csv (python -m data_processing.update_price_index),
and every price on the site moves with it:

    today's factor = area factor x (1 + change_1) x (1 + change_2) x ...

The index is city-wide, so all areas move together; differences between areas
still come from the locality rates.
"""

import pandas as pd

from backend.config import PROJECT_ROOT

INDEX_PATH = PROJECT_ROOT / "data" / "external" / "bengaluru_price_index.csv"
BASE_LABEL = "October 2026"   # when the locality rates were published
COLUMNS = ["quarter", "change_percent", "source", "released"]


def load_updates(path=INDEX_PATH):
    """the quarterly changes after the base date, oldest first (empty if none yet)"""
    try:
        table = pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return []
    return table[COLUMNS].to_dict("records")


def multiplier(updates):
    """how much prices moved since the base date, e.g. 1.031 after a +3.1% quarter"""
    value = 1.0
    for row in updates:
        value *= 1 + float(row["change_percent"]) / 100
    return value


def updated_to(updates):
    """the latest quarter the prices include, in words"""
    return updates[-1]["quarter"] if updates else BASE_LABEL


UPDATES = load_updates()
MULTIPLIER = multiplier(UPDATES)
UPDATED_TO = updated_to(UPDATES)
