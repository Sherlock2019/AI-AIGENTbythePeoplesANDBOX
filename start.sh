#!/usr/bin/env bash 
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"

mkdir -p "$LOGDIR" \
         "${ROOT}/services/api/.runs" \
         "${ROOT}/agents/credit_appraisal/models/production" \
         "${ROOT}/.pids"

# ─────────────────────────────────────────────
# 🧹 PRE-CLEANUP — Kill old processes on used ports
# ─────────────────────────────────────────────
echo "🧹 Checking for existing processes on ports ${APIPORT} and ${UIPORT}..."
sudo fuser -k "${APIPORT}/tcp" 2>/dev/null || true
sudo fuser -k "${UIPORT}/tcp" 2>/dev/null || true
sleep 1
echo "✅ Old processes cleaned up."

# ─────────────────────────────────────────────
# Timestamped logs
# ─────────────────────────────────────────────
TS=$(date +"%Y%m%d-%H%M%S")
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
COMBINED_LOG="${LOGDIR}/live_combined_${TS}.log"

# ─────────────────────────────────────────────
# Virtual environment
# ─────────────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
source "${VENV}/bin/activate"

python -V
pip -V

# ─────────────────────────────────────────────
# Install deps
# ─────────────────────────────────────────────
python -m pip install -U pip wheel
pip install -r "${ROOT}/services/api/requirements.txt"
pip install -r "${ROOT}/services/ui/requirements.txt"

export PYTHONPATH="${ROOT}"

# ─────────────────────────────────────────────
# Color helper
# ─────────────────────────────────────────────
color_echo() {
  local color="$1"; shift
  local msg="$*"
  case "$color" in
    red) echo -e "\033[1;31m$msg\033[0m" ;;
    green) echo -e "\033[1;32m$msg\033[0m" ;;
    yellow) echo -e "\033[1;33m$msg\033[0m" ;;
    blue) echo -e "\033[1;34m$msg\033[0m" ;;
    *) echo "$msg" ;;
  esac
}

# ─────────────────────────────────────────────
# Start API
# ─────────────────────────────────────────────
if [[ -f "${ROOT}/.pids/api.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/api.pid")" 2>/dev/null; then
  color_echo yellow "API already running (PID $(cat "${ROOT}/.pids/api.pid"))."
else
  nohup "${VENV}/bin/uvicorn" services.api.main:app \
    --host 0.0.0.0 --port "${APIPORT}" --reload \
    > "${API_LOG}" 2>&1 &
  echo $! > "${ROOT}/.pids/api.pid"
  color_echo green "✅ API started (PID=$(cat "${ROOT}/.pids/api.pid")) | log: ${API_LOG}"
fi

# ─────────────────────────────────────────────
# Start UI (Streamlit)
# ─────────────────────────────────────────────
if [[ -f "${ROOT}/.pids/ui.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/ui.pid")" 2>/dev/null; then
  color_echo yellow "UI already running (PID $(cat "${ROOT}/.pids/ui.pid"))."
else
  color_echo blue "Starting Streamlit UI..."
  cd "${ROOT}/services/ui"
  nohup "${VENV}/bin/streamlit" run "app.py" \
    --server.port "${UIPORT}" --server.address 0.0.0.0 \
    --server.fileWatcherType none \
    > "${UI_LOG}" 2>&1 &
  echo $! > "${ROOT}/.pids/ui.pid"
  cd "${ROOT}"
  color_echo green "✅ UI started (PID=$(cat "${ROOT}/.pids/ui.pid")) | log: ${UI_LOG}"
fi

# ─────────────────────────────────────────────
# Info
# ─────────────────────────────────────────────
echo "----------------------------------------------------"
color_echo blue "🎯 All services running!"
color_echo blue "📘 Swagger: http://localhost:${APIPORT}/docs"
color_echo blue "🌐 Web UI:  http://localhost:${UIPORT}"
color_echo blue "📂 Logs:    ${LOGDIR}"
echo "----------------------------------------------------"

# ─────────────────────────────────────────────
# Combined Log Monitor
# ─────────────────────────────────────────────
color_echo blue "🧩 Starting live log monitor..."
nohup bash -c "tail -n 0 -F '${API_LOG}' '${UI_LOG}' | tee -a '${COMBINED_LOG}'" >/dev/null 2>&1 &
LOG_MONITOR_PID=$!
echo $LOG_MONITOR_PID > "${ROOT}/.pids/logmonitor.pid"
color_echo green "✅ Live log monitor running (PID=${LOG_MONITOR_PID})"
color_echo blue "📄 Combined live output → ${COMBINED_LOG}"

# Wait until combined log exists
sleep 1
touch "${COMBINED_LOG}"

# ─────────────────────────────────────────────
# Live Error View
# ─────────────────────────────────────────────
color_echo yellow "👁  Real-time ERROR view (press Ctrl+C to exit)..."
tail -n 20 -f "${COMBINED_LOG}" | grep --line-buffered -E --color=always "ERROR|Exception|Traceback|CRITICAL" || true
