#!/usr/bin/env bash
set -euo pipefail

API_PORT="${API_PORT:-${APIPORT:-8090}}"
UI_PORT="${UI_PORT:-${UIPORT:-8502}}"
export API_PORT UI_PORT
export API_URL="${API_URL:-http://localhost:${API_PORT}}"
export PYTHONPATH="/app"
export STREAMLIT_TELEMETRY_DISABLED=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

cleanup() {
  echo "Stopping services..."
  if [[ -n "${API_PID:-}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" 2>/dev/null || true
  fi
  if [[ -n "${UI_PID:-}" ]] && kill -0 "${UI_PID}" 2>/dev/null; then
    kill "${UI_PID}" 2>/dev/null || true
  fi
  wait "${API_PID:-}" "${UI_PID:-}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting API on ${API_PORT}..."
uvicorn services.api.main:app \
  --host 0.0.0.0 \
  --port "${API_PORT}" \
  --forwarded-allow-ips='*' &
API_PID=$!

echo "Starting Streamlit UI on ${UI_PORT}..."
streamlit run services/ui/app.py \
  --server.port "${UI_PORT}" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --browser.gatherUsageStats false &
UI_PID=$!

wait -n "${API_PID}" "${UI_PID}"
