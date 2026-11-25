"""
Exports the real sale prices users reported on the website, ready to add to the
training data once there are enough of them.

Run from the project folder (set DATABASE_URL to the Neon connection string to
read the online reports; without it the laptop's SQLite file is used):

    python -m backend.models.export_sale_reports

Saves data/processed/user_sale_reports.csv with the same columns the model uses
(location, total_sqft_clean, bhk, bath, price) plus kind and our estimate then.

How to retrain with them later:
1. Check the rows (remove obvious mistakes).
2. Convert the 2026 prices back to the 2017-19 level by dividing by the area's
   market factor, or better, retrain on new data only once there are a few
   thousand reports.
3. Re-run tune_xgboost.py and measure_error.py, and keep the new model only if
   its measured error is lower than 23.7%.
"""

import pandas as pd

from backend.config import PROJECT_ROOT
from backend.services.auth import UserStore

OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "user_sale_reports.csv"


def main():
    rows = UserStore().reports()
    table = pd.DataFrame(rows, columns=["location", "size_sqft", "bedrooms", "bathrooms", "price_lakhs", "kind",
                                        "our_estimate", "created_at"])
    table = table.rename(columns={"size_sqft": "total_sqft_clean", "bedrooms": "bhk", "bathrooms": "bath",
                                  "price_lakhs": "price"})
    table["reported_on"] = pd.to_datetime(table["created_at"], unit="s").dt.date
    table.drop(columns="created_at").to_csv(OUTPUT_PATH, index=False)
    print("Saved", len(table), "reports to", OUTPUT_PATH)
    if len(table):
        gap = ((table["price"] - table["our_estimate"]) / table["our_estimate"] * 100).abs().mean()
        print("Average gap between real prices and our estimate: %.1f%%" % gap)


if __name__ == "__main__":
    main()
