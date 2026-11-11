# 🏠 Real Estate AVM: Bangalore

**Can knowing where a house is actually predict its price, or is it all square footage?**

An OJT project that builds an Automated Valuation Model (AVM) for Bangalore property prices and answers one question with a controlled experiment: **does adding location and amenity data (schools, hospitals, transit) meaningfully improve price prediction over property attributes alone, and by how much?**

## The answer

**Yes, location matters a lot, but at the neighbourhood level.**

| Model | Features | RMSE | MAE | MAPE | R² | vs baseline |
|---|---|---|---|---|---|---|
| Baseline | Area rate × size | 54.82 | 27.72 | 25.6% | 0.654 | - |
| Random Forest | Property only | 59.17 | 29.73 | 28.4% | 0.597 | -7.9% |
| XGBoost | Property only | 58.95 | 30.06 | 28.7% | 0.600 | -7.5% |
| Random Forest | + position & amenities | 48.07 | 23.77 | 22.7% | 0.734 | +12.3% |
| XGBoost | + position & amenities | 47.52 | 24.14 | 23.3% | 0.740 | +13.3% |
| Random Forest | + area price level (all 9) | 49.41 | 23.61 | 22.0% | 0.719 | +9.9% |
| XGBoost | + area price level (all 9) | 48.28 | 23.88 | 22.7% | 0.732 | +11.9% |

- Without location, even XGBoost and Random Forest lose to a simple *area rate × size* baseline.
- Adding location cuts XGBoost's RMSE from 58.95 to 48.28 Lakhs (18% lower).
- SHAP: size is the biggest driver, then the area's price level. Property features account for 69.5% of the price effect and location for 30.5%. Distance to the nearest school, hospital or transit stop adds little on its own.
- The final tuned XGBoost is off by 23.7% on average (MAE 23.96 Lakhs) on unseen test listings.
- After tuning, the served XGBoost reaches RMSE 46.41 Lakhs and R² 0.752. 56.7% of estimates fall within 20% of the real price.

## Team

| Who | Owns |
|---|---|
| Sherlyn | Data + Frontend: cleaning, geocoding, amenities, location name analysis, Streamlit dashboard |
| Manasa | Modeling + Backend: baseline/linear models, Random Forest/XGBoost, tuning, SHAP, FastAPI |

## Scope note

We originally planned to also test the model against market surges (the 2020-2022 price boom), which needs dated, multi-year transaction data. No Indian city publishes that in bulk for free (we checked Bangalore, Mumbai and Delhi), so we dropped it and focused on the core question with one solid Bangalore dataset.

## The data

[Bengaluru House Price Data](https://www.kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data) (Kaggle, Apache 2.0): 13,320 real listings. Prices are in Lakhs (1 Lakh = Rs 1,00,000).

| Step | Rows |
|---|---|
| Raw listings | 13,320 |
| Valid size and sqft, ≥ 200 sqft per bedroom | 12,917 |
| Area geocoded (901 areas) | 11,672 |
| Extreme 1% of price/sqft and size trimmed | 11,272 (9,017 train / 2,255 test) |

## Features

- **Property:** bedrooms (`bhk`), bathrooms (`bath`), size (`total_sqft_clean`)
- **Location:** `lat`, `lon` (Nominatim geocoding), distance to the nearest school / hospital / transit stop (OpenStreetMap Overpass API, haversine), and `location_price`, the area's median price per sqft computed from training rows only (no leakage)

## Built with

pandas · NumPy · geopy/Nominatim · OpenStreetMap Overpass · scikit-learn · XGBoost · SHAP · FastAPI · Pydantic · Streamlit · pydeck · pytest

## Project layout

```
configs/config.yaml          shared settings (seed, split, features, app settings)
data/raw/bangalore/          Kaggle CSV (not committed, download it yourself)
data/processed/              cleaned data, committed so nobody has to re-geocode
data_processing/
  load_bangalore.py              clean + geocode
  compute_amenity_distances.py   nearest school/hospital/transit
  build_final_dataset.py         merge into one training table
  clean_location_names.py        duplicate and typo analysis of area names
  prepare_model_data.py          shared prep used by every model script
backend/
  main.py                    FastAPI app
  schemas.py                 request/response validation
  config.py                  loads config.yaml
  models/
    train_baseline_and_linear.py   baseline + Linear/Ridge/Lasso
    train_random_forest_xgboost.py the main experiment (with vs without location)
    tune_xgboost.py                tunes XGBoost, saves model + location lookup
    measure_error.py               measured test error used by the app
    explain_model.py               SHAP importance + charts
    trained_model.pkl              the served model
frontend/app.py              Streamlit app
reports/                     results CSVs and charts
tests/                       pytest tests
run_checks.sh                runs every script, the tests and an API check
```

## Getting started

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run it

```
# terminal 1: the API (docs at http://127.0.0.1:8000/docs)
uvicorn backend.main:app --reload

# terminal 2: the app (opens http://localhost:8501)
streamlit run frontend/app.py
```

Check everything at once: `bash run_checks.sh` (the output is saved to `reports/run_log.txt`).

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | status, model version, number of areas |
| GET | `/locations` | the 881 areas the model can price |
| GET | `/model-info` | features and measured error |
| POST | `/predict` | estimate, likely range, price per sqft, fair-price verdict, SHAP "why this price" factors, warnings |

Example request:

```json
{"location": "Whitefield", "size_sqft": 1200, "bedrooms": 2, "bathrooms": 2, "asking_price": 80}
```

## App features

- **Predict Price:** estimate with a measured error range, comparison with similar listings, asking-price check, a "Why this price?" SHAP breakdown, a downloadable summary, and a home loan EMI calculator
- **Similar Properties:** listing cards with details, a map, and optional per-listing estimates
- **Nearby Neighborhoods:** the closest 10 areas with price per sqft compared
- **How It Works:** SHAP importance, the property-vs-location split, and the experiment results table

## Rebuilding from scratch

1. Download the raw CSV into `data/raw/bangalore/`
2. Data: `python data_processing/load_bangalore.py`, then `compute_amenity_distances.py`, then `build_final_dataset.py`
3. Models: `python -m backend.models.train_baseline_and_linear`, `train_random_forest_xgboost`, `tune_xgboost`, `measure_error`, `explain_model`

## Known limitations

Listing (asking) prices, not sale prices; location at area level, not address level; no dates; 167 of 901 areas are missing amenity data (median-filled); near-duplicate area names not yet merged; about 24% average error. See the study guide for details and future work.

## Where we're at

- [x] PRD approved, repo, dev environment, config system
- [x] Data cleaned, geocoded, joined with amenity distances
- [x] Baseline and linear models
- [x] Random Forest / XGBoost comparison with and without location
- [x] XGBoost tuning, error measurement, SHAP
- [x] FastAPI backend with validation, explanations and tests
- [x] Streamlit dashboard
