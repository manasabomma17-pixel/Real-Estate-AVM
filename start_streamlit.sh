#!/bin/bash
# The earlier Streamlit version of the app, kept as a backup.
# Usage, from the project folder, with the backend already running:  bash start_streamlit.sh
cd "$(dirname "$0")"
source venv/bin/activate
streamlit run streamlit_app/app.py --server.port 8501
