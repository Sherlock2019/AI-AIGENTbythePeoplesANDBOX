#!/usr/bin/env bash
set -euo pipefail

# Project root
ROOT="${ROOT:-$HOME/credit-appraisal-agent-poc}"
API_PORT="${API_PORT:-8090}"
UI_PORT="${UI_PORT:-8502}"

LOG_DIR="$ROOT/.logs"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/api_e2e.log"
UI_LOG="$LOG_DIR/ui_e2e.log"

echo "🌱 Ensuring venv & deps..."
python3 -m venv "$ROOT/services/api/.venv" >/dev/null 2>&1 || true
source "$ROOT/services/api/.venv/bin/activate"
pip install -q --upgrade pip
pip install -q fastapi uvicorn "pydantic<2" requests pandas numpy pytest fpdf shap altair streamlit

echo "🧹 Killing old listeners on :$API_PORT and :$UI_PORT (if any)..."
pids=$(lsof -t -i ":$API_PORT" || true)
if [ -n "$pids" ]; then kill -9 $pids || true; fi
pids=$(lsof -t -i ":$UI_PORT" || true)
if [ -n "$pids" ]; then kill -9 $pids || true; fi

echo "🚀 Starting API on :$API_PORT..."
# run from repo root to respect package imports
cd "$ROOT"
( python -m uvicorn services.api.main:app --host 0.0.0.0 --port "$API_PORT" --reload ) \
  > "$API_LOG" 2>&1 &
API_PID=$!

# simple wait for API
echo -n "⏳ Waiting for API..."
for i in {1..30}; do
  if curl -s "http://localhost:${API_PORT}/openapi.json" | grep -q '"paths"'; then
    echo " ready."
    break
  fi
  echo -n "."
  sleep 1
done

echo "🧪 Running pytest e2e..."
export API_URL="http://localhost:${API_PORT}"
pytest -q tests/test_api_e2e.py || ( echo "❌ Tests failed; tailing API logs:"; tail -n 200 "$API_LOG"; kill $API_PID; exit 1 )

echo "✅ E2E tests passed."
echo "📜 API logs (last 60 lines):"
tail -n 60 "$API_LOG"

echo "🛑 Stopping API..."
kill $API_PID >/dev/null 2>&1 || true
sleep 1
echo "🏁 Done."
