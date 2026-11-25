#!/bin/bash
# Rebuilds the data and retrains the model from start to end (about 5-10 minutes).
# Run after a data change, e.g. the metro distance feature:   bash retrain.sh
# Everything is also saved to reports/retrain_log.txt

cd "$(dirname "$0")"
source venv/bin/activate
set -e

{
echo "=== 1. Distance to the nearest metro station ==="
python -m data_processing.add_metro_distance

echo; echo "=== 2. Final dataset ==="
python data_processing/build_final_dataset.py

echo; echo "=== 3. Baseline and linear models ==="
python -m backend.models.train_baseline_and_linear

echo; echo "=== 4. Random Forest and XGBoost (does location help?) ==="
python -m backend.models.train_random_forest_xgboost

echo; echo "=== 5. Tune XGBoost and save the model ==="
python -m backend.models.tune_xgboost

echo; echo "=== 6. Measured error of the saved model ==="
python -m backend.models.measure_error

echo; echo "=== 7. SHAP explanation ==="
python -m backend.models.explain_model

echo; echo "=== 8. Tests ==="
python -m pytest -q

echo; echo "=== DONE: now commit and push ==="
} 2>&1 | tee reports/retrain_log.txt
