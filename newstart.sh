#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"

if [[ ! -d "${VENV}" || ! -f "${VENV}/bin/activate" ]]; then
  python3 -m venv "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

pip install --upgrade pip wheel >/dev/null
pip install -r "${ROOT}/services/api/requirements.txt" >/dev/null
pip install -r "${ROOT}/services/ui/requirements.txt" >/dev/null

export PYTHONPATH="${ROOT}"

nohup "${VENV}/bin/uvicorn" services.api.main:app \
  --host 0.0.0.0 --port "${APIPORT}" \
  >/tmp/api_${APIPORT}.log 2>&1 &
API_PID=$!
echo "${API_PID}" > "${ROOT}/.api.pid"

cd "${ROOT}/services/ui"
nohup "${VENV}/bin/streamlit" run "app.py" \
  --server.port "${UIPORT}" \
  --server.address 0.0.0.0 \
  >/tmp/ui_${UIPORT}.log 2>&1 &
UI_PID=$!
echo "${UI_PID}" > "${ROOT}/.ui.pid"
cd "${ROOT}"

echo "API ready  → http://localhost:${APIPORT} (PID ${API_PID})"
echo "UI ready   → http://localhost:${UIPORT} (PID ${UI_PID})"
