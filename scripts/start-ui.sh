#!/usr/bin/env bash
# Launch FastAPI backend + Streamlit UI (stores must already be running).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"

echo "Starting API on http://${API_HOST}:${API_PORT}"
python3 -m uvicorn src.api.main:app --host "$API_HOST" --port "$API_PORT" &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting Streamlit UI on http://localhost:8501"
streamlit run src/ui/app.py --server.port 8501 --server.address localhost
