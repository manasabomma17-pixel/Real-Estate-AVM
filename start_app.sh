#!/bin/bash
# Starts the FastAPI backend and the Streamlit frontend together.
# Usage, from the project folder:  bash start_app.sh
# Press Ctrl+C once to stop both.

cd "$(dirname "$0")"
source venv/bin/activate

echo "Starting backend on http://127.0.0.1:8000 ..."
uvicorn backend.main:app --port 8000 &
BACKEND_PID=$!

# stop the backend too when this script is stopped
trap "echo; echo 'Stopping...'; kill $BACKEND_PID 2>/dev/null" EXIT

# wait until the backend answers before opening the app
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/health > /dev/null; then
        echo "Backend is ready."
        break
    fi
    sleep 1
done

echo "Starting frontend on http://localhost:8501 ..."
streamlit run frontend/app.py --server.port 8501
