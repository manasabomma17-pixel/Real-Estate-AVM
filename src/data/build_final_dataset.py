"""
Merges the cleaned Bangalore sales data with the per-location amenity
distances, producing one final feature-complete table.
"""

from pathlib import Path

import pandas as pd

SALES_PATH = Path("data/processed/bangalore_sales_clean.csv")
AMENITIES_PATH = Path("data/processed/bangalore_amenity_distances.csv")
OUTPUT_PATH = Path("data/processed/bangalore_final_dataset.csv")


if __name__ == "__main__":
    sales = pd.read_csv(SALES_PATH)
    amenities = pd.read_csv(AMENITIES_PATH)[
        ["location", "dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]
    ]

    print(f"Sales rows: {len(sales)}")
    print(f"Amenity records: {len(amenities)}")

    final = sales.merge(amenities, on="location", how="left")

    for col in ["dist_to_school_km", "dist_to_hospital_km", "dist_to_transit_km"]:
        missing = final[col].isna().sum()
        print(f"{col}: missing for {missing}/{len(final)} rows ({missing/len(final):.1%})")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved final dataset: {len(final)} rows, {len(final.columns)} columns to {OUTPUT_PATH}")
    print(f"Columns: {list(final.columns)}")
