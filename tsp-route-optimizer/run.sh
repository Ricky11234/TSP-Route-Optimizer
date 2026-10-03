#!/usr/bin/env bash
# One-command launcher for the TSP Route Optimizer.
# Usage:  ./run.sh
#
# It installs dependencies (first run only is slow) and starts the server.
# Then open http://127.0.0.1:8000 in your browser.

set -e  # stop on any error

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting server at http://127.0.0.1:8000 (Ctrl+C to stop)..."
cd backend
uvicorn main:app --reload
