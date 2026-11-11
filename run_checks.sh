#!/bin/bash
# Runs every model script, the tests, and a quick API check.
# Usage, from the project folder:  bash run_checks.sh
# Everything is also saved to reports/run_log.txt

cd "$(dirname "$0")"
source venv/bin/activate

{
echo "=== python and packages ==="
python --version
python -c "import xgboost, shap, fastapi, streamlit; print('xgboost', xgboost.__version__, '| shap', shap.__version__)"
python -c "import pytest" 2>/dev/null || pip install -q pytest

echo; echo "=== 1. Model comparison (does location help?) ==="
python -m backend.models.train_random_forest_xgboost

echo; echo "=== 2. Measured error of the saved model ==="
python -m backend.models.measure_error

echo; echo "=== 3. SHAP explanation ==="
python -m backend.models.explain_model

echo; echo "=== 4. Tests ==="
python -m pytest -q

echo; echo "=== 5. API check ==="
uvicorn backend.main:app --port 8000 > /tmp/avm_api.log 2>&1 &
API_PID=$!
sleep 8
curl -s http://127.0.0.1:8000/health; echo
curl -s -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" \
  -d '{"location":"Whitefield","size_sqft":1200,"bedrooms":2,"bathrooms":2,"asking_price":80}'; echo
curl -s -o /dev/null -w "unknown location status: %{http_code}\n" -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" -d '{"location":"Nowhere","size_sqft":1200,"bedrooms":2,"bathrooms":2}'
kill $API_PID

echo; echo "=== DONE ==="
} 2>&1 | tee reports/run_log.txt
