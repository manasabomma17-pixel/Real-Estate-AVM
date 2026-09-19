
# 🏠 Real Estate AVM

**Can knowing a house is near a good school actually predict its price?** That's what this project is testing.

An OJT project building a machine learning model that predicts property prices in Bangalore — and answers a real question: does location and nearby amenities (schools, hospitals, transit) actually move the needle on price prediction, or is it all just square footage and bedroom count?

---

## The Question

Does adding location + amenity data meaningfully improve price prediction accuracy over property attributes alone — and by how much?

## A Quick Note on Scope

We originally planned to also test the model against market surges (2020-2022 price boom, etc.), which needed dated, multi-year transaction data. Turns out no Indian city publishes that in bulk for free - checked Bangalore, Mumbai, and Delhi. So we dropped that piece and doubled down on the core question above, using a single solid Bangalore dataset instead.

## Team

| Who | Owns |
|---|---|
| Sherlyn | Data + Frontend - cleaning, geocoding, amenities, EDA, Streamlit dashboard |
| Manasa | Modeling + Backend - models, tuning, evaluation, SHAP, FastAPI |

## The Data

Bengaluru House Price Data (Kaggle, Apache 2.0): https://www.kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data - 13,320 real property listings across Bangalore.

## Built With

- Data: pandas, geopy, Nominatim (geocoding), OpenStreetMap Overpass API (amenities)
- Modeling: scikit-learn, XGBoost, SHAP
- Serving: FastAPI + Streamlit
- Testing: pytest

## How It's Organized

Real-Estate-AVM/
  configs/
    config.yaml              - one file to control every experiment: dataset, features, model, seed
  data/
    raw/                     - not committed, download it yourself (see below)
    processed/               - committed, the actual clean usable data
      bangalore_location_coords.csv
      bangalore_sales_clean.csv
      bangalore_amenity_distances.csv
      bangalore_final_dataset.csv    - the one you actually train on
  notebooks/                 - exploration and EDA
  reports/                   - writeups, charts, results
  src/
    config.py                - loads config.yaml
    data/
      load_bangalore.py               - clean and geocode
      compute_amenity_distances.py    - distance to nearest school, hospital, transit
      build_final_dataset.py          - merges everything into one table
    api/
      main.py                - FastAPI app
      schemas.py             - request and response shapes
  .gitignore
  README.md
  requirements.txt

## Getting Started

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## Rebuilding the Data (if you don't trust our cache)

1. Grab the raw CSV from the Kaggle link above, drop it in data/raw/bangalore/
2. Run these three, in order:

python -m src.data.load_bangalore
python -m src.data.compute_amenity_distances
python -m src.data.build_final_dataset

Or just use what's already in data/processed/ - it's committed, so you don't have to.

## Running the API

uvicorn src.api.main:app --reload

Then hit http://127.0.0.1:8000/docs - /predict is stubbed for now until a real model is trained.

## Where We're At

- [x] PRD approved
- [x] Repo set up
- [x] Dev environment + config system + FastAPI skeleton
- [x] Data cleaned, geocoded, and joined with amenity distances (11,672 rows, ready to train on)
- [ ] Baseline model
- [ ] Full model comparison + SHAP
- [ ] Dashboard