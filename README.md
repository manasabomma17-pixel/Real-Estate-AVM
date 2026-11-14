# 🏠 Real Estate AVM: Bangalore

> **Found a flat online? Check if the price is fair.**

An **Automated Valuation Model (AVM)** for Bangalore flats, built as a simple **fair-price checker**. Paste a property ad or type the details, and it gives a fair price at **today's** market level, says whether the seller's price is too high, fair or low, and explains why. Behind it is a controlled machine learning experiment on one question: *does knowing where a home is actually help predict its price?*

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![XGBoost](https://img.shields.io/badge/Model-XGBoost-EB5E28)
![SHAP](https://img.shields.io/badge/Explainability-SHAP-8E44AD)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/Website-React%2019-61DAFB?logo=react&logoColor=black)
![Tests](https://img.shields.io/badge/tests-73%20passing-2EA44F)

---

## Contents

1. [Key findings](#-key-findings)
2. [The website](#-the-website)
3. [How it works](#-how-it-works)
4. [Quick start](#-quick-start)
5. [Deployment](#-deployment)
6. [API](#-api)
7. [The data](#-the-data)
8. [Results in detail](#-results-in-detail)
9. [Project structure](#-project-structure)
10. [Testing](#-testing)
11. [Limitations and future work](#-limitations-and-future-work)
12. [Team](#-team)

---

## 🔑 Key findings

**Research question:** does adding location and amenity data (schools, hospitals, transit) meaningfully improve price prediction over property attributes alone, and by how much?

**Answer: yes, location matters a lot, but at the neighbourhood level.**

| | Property only | + Location | Change |
|---|:---:|:---:|:---:|
| XGBoost RMSE (Lakhs) | 58.95 | **48.28** | **18% lower** |
| XGBoost R² | 0.600 | **0.732** | +0.13 |

- 📉 **Without location, every model loses** to a simple *area rate × size* rule of thumb (baseline RMSE 54.82).
- 📍 **With location, error drops by 18%**, and the tree models clearly beat the baseline.
- 🏘️ **It is the area that matters, not the nearest amenity.** SHAP shows size has the largest effect, then the area's price level. Property features make up **69.5%** of the price effect and location **30.5%**.
- 🎯 **Final tuned model:** 23.7% average error, R² 0.752, and **56.7% of estimates within 20%** of the real price on 2,255 unseen listings.

---

## 🖥️ The website

Every word on the site is short and simple, so anyone can use it. Details are one tap away instead of paragraphs.

| Page | What you get |
|---|---|
| **Check price** | Paste an ad (or type the details), then get a big clear answer: *Price is too high / fair / low*. A **Cheap / Fair / Costly** bar shows the fair range and the seller's price. Tips say what to offer. **Why this price?** opens a SHAP waterfall. Optional building age and a Lakhs/Crore switch |
| **Compare** | Price per sqft of similar flats, with our price and the seller's price marked |
| **Places nearby** | The 5 closest schools, hospitals and bus/metro/train stops on a map, from the area centre or from a society name or Google Maps link |
| **Other areas** | The 10 closest areas and how much cheaper or costlier they are |
| **Before you buy** | A checklist: visit, RERA number, papers, seller, written agreement, lawyer |
| **Loan EMI** | Monthly EMI, the bank's down-payment rule, and the best loan length for your salary |

**Example:** a 1,200 sqft, 2 BHK flat in Whitefield listed at **₹1.75 Cr** → our price today **₹1.57 Cr**, fair range ₹1.41–1.72 Cr → **"Price is too high"** (seller asks 12% more). With a 20-year-old building: about ₹1.48 Cr.

**Smart checks**
- **Today's prices:** the data is from 2017–19, so each estimate is multiplied by how much that area's prices have risen (published 2026 rates, Home Bazaar, Oct 2026; Whitefield ×2.49, city ×1.84). Small areas are pulled toward the city figure.
- **Typo check:** a seller's price under 30% or over 3× our price is not judged; the site asks *"Did you mean ₹3 Cr?"*
- **Building age:** the data has no age, so the standard valuer rule (60-year life, 10% salvage, applied only to the rebuild cost at ₹2,500/sqft) is shown separately as a rough guide.

> We do not list flats for sale. Old records appear only as comparisons, clearly labelled.

---

## ⚙️ How it works

```
OFFLINE (run once, results committed)
Kaggle listings (13,320)
   │  clean sizes and sqft, geocode area names (Nominatim)
   │  nearest school / hospital / transit (OpenStreetMap Overpass)
   │  5 nearest named places per area, 2026 price factors
   ▼
Models: baseline → linear → Random Forest / XGBoost → tuned XGBoost → SHAP

ONLINE
React website (Vite)  ── fetch, JSON ──►  FastAPI backend
                                            ├─ XGBoost model + exact SHAP values
                                            └─ services: tips, area data, ad reader,
                                               exact location, building age
```

**Features used by the model**

| Group | Features |
|---|---|
| Property | bedrooms (`bhk`), bathrooms (`bath`), size (`total_sqft_clean`) |
| Location | `lat`, `lon`, distance to the nearest school, hospital and transit stop, and `location_price` (the area's median price per sqft, from training rows only to avoid leakage) |

**Built with:** Python · pandas · NumPy · geopy · OpenStreetMap · scikit-learn · XGBoost · SHAP · FastAPI · Pydantic · React · Vite · Leaflet · pytest

---

## 🚀 Quick start

**1. Set up (once)**
```bash
git clone https://github.com/manasabomma17-pixel/Real-Estate-AVM.git
cd Real-Estate-AVM
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

**2. Start everything**
```bash
bash start_app.sh
```
This starts the API on http://127.0.0.1:8000 (docs at `/docs`) and the website on **http://localhost:5173**. Ctrl+C stops both.

Or in two terminals: `uvicorn backend.main:app --reload` and `cd frontend && npm run dev`.

**3. Check everything** (optional)
```bash
bash run_checks.sh
```

> The processed data and the trained model are committed, so the app works straight away. The older Streamlit version is kept in `streamlit_app/` (`bash start_streamlit.sh`).

---

## ☁️ Deployment

| Part | Host | Settings |
|---|---|---|
| Backend | **Render** (free) | Blueprint from `render.yaml`: installs `backend/requirements.txt`, starts `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Website | **Vercel** (free) | Root directory `frontend`, build `npm run build`, output `dist`. Environment variable `VITE_API_URL` = the Render address |

Optional: set `ALLOWED_ORIGINS` on Render to the Vercel address. Both redeploy on every push. Render's free server sleeps when idle, so the first request can take up to a minute; the website says so.

---

## 🔌 API

| Method | Endpoint | Returns |
|---|---|---|
| `GET` | `/health` | Status, model version, number of areas |
| `GET` | `/locations` | The 881 areas the model can price |
| `GET` | `/model-info` | Features, measured error, data period, city factor |
| `POST` | `/predict` | Price (2017–19 and today), range, verdict, SHAP factors, warnings |
| `GET` | `/areas` | Every area with its position and number of records |
| `GET` | `/areas/{area}/summary` | Usual rate today, usual price for the BHK, % ready to move |
| `GET` | `/areas/{area}/places` | 5 nearest schools, hospitals, transit stops (optionally from `lat`, `lon`) |
| `GET` | `/areas/{area}/comparison` | Today's price per sqft of similar flats |
| `GET` | `/areas/{area}/nearby` | 10 closest areas with today's rate |
| `POST` | `/parse-listing` | Details read from a pasted ad, including building age |
| `POST` | `/locate` | Coordinates of a society, landmark, Maps link or "lat, lon" |
| `POST` | `/advice` | Short tips and the building-age guide |

<details>
<summary><b>Example request and response</b></summary>

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"location": "Whitefield", "size_sqft": 1200, "bedrooms": 2, "bathrooms": 2, "asking_price": 175}'
```

```json
{
  "predicted_price": 62.81,
  "today_price": 156.65,
  "today_low": 119.51,
  "today_high": 193.78,
  "market_factor": 2.494,
  "market_basis": "area",
  "verdict": "Looks overpriced",
  "difference_percent": 11.7,
  "base_price": 102.58,
  "factors": [
    {"name": "Size, 1200 sqft", "effect": -26.35},
    {"name": "Bathrooms, 2", "effect": -7.37},
    {"name": "Area price level in Whitefield", "effect": -4.18}
  ],
  "warnings": []
}
```

`factors` are SHAP values: starting from `base_price` (the average property), each pushes the estimate up or down, and together they add up to `predicted_price` (2017–19 level). `today_price` = `predicted_price` × `market_factor`. The verdict compares the seller's price with `today_price`. The response is shortened.
</details>

**Input checks:** sizes must be positive and at least 200 sqft per bedroom, with 1 to 20 bedrooms. Invalid input returns `422`, and an unknown area returns `404`.

---

## 📊 The data

[**Bengaluru House Price Data**](https://www.kaggle.com/datasets/amitabhajoy/bengaluru-house-price-data) on Kaggle (licence: Apache 2.0). Prices are in **Lakhs** (1 Lakh = ₹1,00,000; 1 Crore = 100 Lakhs).

| Step | Rows |
|---|---:|
| Raw listings | 13,320 |
| Valid size and sqft, at least 200 sqft per bedroom | 12,917 |
| Area successfully geocoded (901 areas) | 11,672 |
| Extreme 1% of price per sqft and size removed | **11,272** |
| Train / test split (80/20) | 9,017 / 2,255 |

Extra files for the website: `amenity_places.csv` (5 nearest named places per area), `bangalore_places.csv` (8,448 named places), `price_adjustment.csv` (2026 factors for 64 areas + city), all from OpenStreetMap and Home Bazaar's published rates.

<details>
<summary><b>Rebuild the data from scratch</b></summary>

1. Download the raw CSV into `data/raw/bangalore/`
2. Run, in order:
```bash
python data_processing/load_bangalore.py              # clean + geocode (~25 min)
python data_processing/compute_amenity_distances.py   # OpenStreetMap queries (~1 hour)
python data_processing/build_final_dataset.py         # merge
python data_processing/fetch_amenity_names.py --bulk  # named places
python -m data_processing.build_price_adjustment      # 2026 price factors
```
</details>

---

## 📈 Results in detail

All models use the **same 9,017 training rows** and are scored on the **same 2,255 unseen test rows**. Lower RMSE, MAE and MAPE are better, and higher R² is better.

| Model | Features | RMSE | MAE | MAPE | R² | vs baseline |
|---|---|---:|---:|---:|---:|---:|
| Baseline | Area rate × size | 54.82 | 27.72 | 25.6% | 0.654 | — |
| Random Forest | Property only | 59.17 | 29.73 | 28.4% | 0.597 | −7.9% |
| XGBoost | Property only | 58.95 | 30.06 | 28.7% | 0.600 | −7.5% |
| Random Forest | + position & amenities | 48.07 | 23.77 | 22.7% | 0.734 | +12.3% |
| XGBoost | + position & amenities | 47.52 | 24.14 | 23.3% | 0.740 | +13.3% |
| Random Forest | + area price level (all 9) | 49.41 | 23.61 | 22.0% | 0.719 | +9.9% |
| XGBoost | + area price level (all 9) | 48.28 | 23.88 | 22.7% | 0.732 | +11.9% |
| **Tuned XGBoost** (served) | all 9 | **46.41** | **23.96** | **23.7%** | **0.752** | **+15.3%** |

Linear, Ridge and Lasso regression were also tested (`reports/baseline_and_linear_results.csv`). All did worse than the baseline, which confirms the relationship is non-linear.

**What drives the price (SHAP)**

<p align="center">
  <img src="reports/shap_feature_importance.png" width="48%" alt="SHAP feature importance">
  <img src="reports/shap_summary.png" width="48%" alt="SHAP summary plot">
</p>

| Feature | Average effect (Lakhs) |
|---|---:|
| Size | 39.55 |
| Area price level | 18.28 |
| Bathrooms | 11.01 |
| Bedrooms | 3.71 |
| Latitude / Longitude | 1.64 / 1.48 |
| Distance to hospital / school / transit | 1.06 / 0.79 / 0.54 |

---

## 📁 Project structure

```
Real-Estate-AVM/
├── configs/config.yaml               shared settings: seed, split, features, app rules
├── data/
│   ├── raw/bangalore/                Kaggle CSV (not committed)
│   ├── external/                     published 2026 area rates
│   └── processed/                    cleaned data, places, price factors (committed)
├── data_processing/                  cleaning, geocoding, amenities, names, factors
├── backend/
│   ├── main.py                       FastAPI app (12 endpoints)
│   ├── schemas.py                    request / response validation
│   ├── config.py                     loads config.yaml
│   ├── services/                     area_data, suggestions, listing_parser,
│   │                                 exact_location, building_age
│   └── models/                       training, tuning, SHAP + trained_model.pkl
├── frontend/                         React website (Vite)
│   └── src/                          App.jsx, api.js, format.js, styles.css,
│                                     components/ (15 components)
├── streamlit_app/                    older Streamlit version (backup)
├── reports/                          results, charts, viva study guide, video script
├── tests/                            73 pytest tests
├── start_app.sh                      starts the API + website
├── render.yaml                       backend deployment (Render)
└── requirements.txt
```

<details>
<summary><b>Re-run the models</b></summary>

```bash
python -m backend.models.train_baseline_and_linear
python -m backend.models.train_random_forest_xgboost
python -m backend.models.tune_xgboost
python -m backend.models.measure_error
python -m backend.models.explain_model
```
</details>

---

## 🧪 Testing

```bash
python -m pytest -q
```

There are **73 tests**, covering:
- **Data preparation:** row counts, no missing values, a repeatable split, and no data leakage in the area price level.
- **API:** valid predictions and ranges, SHAP factors adding up to the estimate, today's price using the market factor, the verdict comparing with today's price, 404 and 422 handling, ad reading, tips, and the building-age guide not changing the model's price.
- **Services:** area summaries, comparisons, nearby areas, nearest places, tip rules, ad parsing, coordinates and distances, and the depreciation rule (20 years = 30%).

---

## ⚠️ Limitations and future work

| Limitation | Next step |
|---|---|
| Listing (asking) prices, not sale prices; 2026 rates are asking rates too | Use property registration data |
| Location is at area level, not address level | Geocode full addresses where available |
| One growth factor per area, no time series | Use dated transactions or a price index |
| Building age is a rule of thumb, not learned | Train on data that includes age, floor and condition |
| 167 of 901 areas are missing amenity data (median-filled) | Re-query with retries, count amenities nearby |
| About 24% average error | Add floor, area type and metro distance as features |

---

## 👥 Team

| | Role | Owned |
|---|---|---|
| **Sherlyn** | Data & Frontend | Cleaning, geocoding, amenity distances and names, 2026 price factors, location name analysis, React website |
| **Manasa** | Modeling & Backend | Baseline and linear models, Random Forest / XGBoost, tuning, SHAP, FastAPI API and services |

*OJT Project, 2026. Data: Bengaluru House Price Data (Kaggle, Apache 2.0). Amenities, geocoding and map tiles: © OpenStreetMap contributors. 2026 rates: Home Bazaar.*
