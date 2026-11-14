#!/bin/bash
# Starts the FastAPI backend and the React frontend together.
# Usage, from the project folder:  bash start_app.sh
# The first time, install the frontend's packages:  cd frontend && npm install
# Press Ctrl+C once to stop both.

cd "$(dirname "$0")"
source venv/bin/activate

echo "Starting backend on http://127.0.0.1:8000 ..."
uvicorn backend.main:app --port 8000 --reload &
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

if [ ! -d frontend/node_modules ]; then
    echo "Installing the frontend's packages (first time only) ..."
    (cd frontend && npm install)
fi

echo "Starting frontend on http://localhost:5173 ..."
cd frontend && npm run dev
