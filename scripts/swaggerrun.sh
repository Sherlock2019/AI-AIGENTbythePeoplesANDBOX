#!/usr/bin/env bash
set -euo pipefail

# Absolute paths so sudo/home issues don't bite us
ROOT="/home/dzoan/credit-appraisal-agent-poc"
VENV="$ROOT/services/api/.venv"
PORT="${PORT:-8090}"

cd "$ROOT"

# Ensure venv exists and has deps
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r "$ROOT/services/api/requirements.txt"
fi

export PYTHONPATH="$ROOT"
export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-phi3}"

# Stop any previous instance of *this* app (ignore errors)
pkill -f "uvicorn services.api.main:app" || true

# Start foreground (logs in your terminal). Remove --reload for production.
exec "$VENV/bin/python" -m uvicorn services.api.main:app \
  --host 0.0.0.0 --port "$PORT" --reload
