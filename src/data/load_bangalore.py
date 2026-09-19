"""
Cleans the Bengaluru House Price dataset and geocodes each unique location
to latitude/longitude using OpenStreetMap's Nominatim (free, but rate-limited
to 1 request/second - this script respects that automatically).

Setup:
    pip install pandas geopy

Usage:
    python -m src.data.load_bangalore
"""

import time
import re
from pathlib import Path

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

RAW_PATH = Path("data/raw/bangalore/Bengaluru_House_Data.csv")
GEOCODE_CACHE_PATH = Path("data/processed/bangalore_location_coords.csv")
OUTPUT_PATH = Path("data/processed/bangalore_sales_clean.csv")

USER_AGENT = "real-estate-avm-ojt-project"


def clean_bhk(size_value) -> float:
    if pd.isna(size_value):
        return None
    match = re.search(r"(\d+)", str(size_value))
    return float(match.group(1)) if match else None


def clean_sqft(sqft_value) -> float:
    sqft_value = str(sqft_value).strip()

    if "-" in sqft_value:
        parts = sqft_value.split("-")
        try:
            low, high = float(parts[0].strip()), float(parts[1].strip())
            return (low + high) / 2
        except ValueError:
            return None

    try:
        return float(sqft_value)
    except ValueError:
        pass

    conversions = {
        "Sq. Meter": 10.7639,
        "Sq. Yards": 9.0,
        "Acres": 43560.0,
        "Cents": 435.6,
        "Guntha": 1089.0,
        "Grounds": 2400.0,
        "Perch": 272.25,
    }
    for unit, factor in conversions.items():
        if unit in sqft_value:
            number = re.search(r"[\d.]+", sqft_value)
            if number:
                return float(number.group()) * factor

    return None


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["bhk"] = df["size"].apply(clean_bhk)
    df["total_sqft_clean"] = df["total_sqft"].apply(clean_sqft)

    before = len(df)
    df = df.dropna(subset=["bhk", "total_sqft_clean", "price", "location"])
    print(f"Dropped {before - len(df)} rows with missing bhk/sqft/price/location")

    before = len(df)
    df = df[df["total_sqft_clean"] / df["bhk"] >= 200]
    print(f"Dropped {before - len(df)} rows with implausible sqft-per-bedroom")

    df["location"] = df["location"].str.strip()

    return df


def _save_geocode_cache(results: list) -> None:
    coords_df = pd.DataFrame(
        [{"location": loc, "lat": lat, "lon": lon} for loc, (lat, lon) in results]
    )
    GEOCODE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    coords_df.to_csv(GEOCODE_CACHE_PATH, index=False)


def geocode_locations(locations: list[str]) -> pd.DataFrame:
    already_done = {}
    if GEOCODE_CACHE_PATH.exists():
        cached = pd.read_csv(GEOCODE_CACHE_PATH)
        already_done = {row["location"]: (row["lat"], row["lon"]) for _, row in cached.iterrows()}
        print(f"Resuming: {len(already_done)} locations already geocoded")

    geolocator = Nominatim(user_agent=USER_AGENT, timeout=10)
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1,
        max_retries=2,
        error_wait_seconds=5.0,
        swallow_exceptions=True,
    )

    results = list(already_done.items())
    remaining = [loc for loc in locations if loc not in already_done]
    print(f"{len(remaining)} locations left to geocode")

    for i, loc in enumerate(remaining, 1):
        query = f"{loc}, Bangalore, Karnataka, India"
        print(f"[{i}/{len(remaining)}] Geocoding: {loc}")
        location = geocode(query)
        if location:
            results.append((loc, (location.latitude, location.longitude)))
        else:
            print(f"  -> not found, skipping")
            results.append((loc, (None, None)))

        if i % 50 == 0:
            _save_geocode_cache(results)
            print(f"  [progress saved: {len(results)} total]")

    _save_geocode_cache(results)
    print(f"Saved geocode cache to {GEOCODE_CACHE_PATH}")
    return pd.read_csv(GEOCODE_CACHE_PATH)


if __name__ == "__main__":
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"{RAW_PATH} not found. Download the dataset from Kaggle and place "
            f"the CSV there first."
        )

    print("Loading raw data...")
    raw = pd.read_csv(RAW_PATH)
    print(f"Loaded {len(raw)} rows")

    cleaned = clean_dataframe(raw)
    print(f"{len(cleaned)} rows remain after cleaning")

    unique_locations = sorted(cleaned["location"].unique())
    print(f"Geocoding {len(unique_locations)} unique locations (this takes a few minutes)...")
    coords = geocode_locations(unique_locations)

    final = cleaned.merge(coords, on="location", how="left")

    before = len(final)
    final = final.dropna(subset=["lat", "lon"])
    print(f"Dropped {before - len(final)} rows where location couldn't be geocoded")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved {len(final)} clean, geocoded rows to {OUTPUT_PATH}")
