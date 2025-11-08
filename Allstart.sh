#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────
# PATHS & PORTS
# ───────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"   # Streamlit UI

mkdir -p "${LOGDIR}" \
         "${ROOT}/services/api/.runs" \
         "${ROOT}/agents/credit_appraisal/models/production" \
         "${ROOT}/.pids"

# ───────────────────────────────────────────────
# HELPERS
# ───────────────────────────────────────────────
color_echo() {
  local color="$1"; shift
  local msg="$*"
  case "$color" in
    red)    echo -e "\033[1;31m${msg}\033[0m" ;;
    green)  echo -e "\033[1;32m${msg}\033[0m" ;;
    yellow) echo -e "\033[1;33m${msg}\033[0m" ;;
    blue)   echo -e "\033[1;34m${msg}\033[0m" ;;
    *)      echo "${msg}" ;;
  esac
}

ensure_writable() {
  local d="$1"
  mkdir -p "$d"
  if [[ ! -w "$d" ]]; then
    chmod u+rwx "$d" 2>/dev/null || true
    chown "$(id -u)":"$(id -g)" "$d" 2>/dev/null || true
  fi
  [[ -w "$d" ]] || { color_echo red "❌ '$d' not writable"; exit 1; }
}

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -t -i :"${port}" 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then kill -9 ${pids} 2>/dev/null || true; fi
  sudo -n fuser -k "${port}/tcp" 2>/dev/null || true
}

# ───────────────────────────────────────────────
# PREFLIGHT
# ───────────────────────────────────────────────
ensure_writable "${LOGDIR}"
ensure_writable "${ROOT}/.pids"

color_echo blue "🧹 Freeing ports ${APIPORT}, 8501, ${UIPORT}..."
free_port "${APIPORT}"
free_port 8501
free_port "${UIPORT}"
sleep 1
color_echo green "✅ Ports cleared."

# ───────────────────────────────────────────────
# LOGS
# ───────────────────────────────────────────────
TS="$(date +"%Y%m%d-%H%M%S")"
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
COMBINED_LOG="${LOGDIR}/live_combined_${TS}.log"
ERR_LOG="${LOGDIR}/err.log"
: > "${API_LOG}"; : > "${UI_LOG}"; : > "${COMBINED_LOG}"; : > "${ERR_LOG}"

# ───────────────────────────────────────────────
# PYTHON ENVIRONMENT
# ───────────────────────────────────────────────
if [[ ! -d "${VENV}" ]]; then
  color_echo yellow "🐍 Creating virtual environment..."
  python3 -m venv "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -V
pip -V

color_echo blue "📦 Installing core dependencies..."
python -m pip install -U pip wheel setuptools >/dev/null
pip install -q fastapi uvicorn pydantic[dotenv] datasets huggingface_hub kaggle streamlit requests >/dev/null

# Optional project requirements
if [[ -f "${ROOT}/services/api/requirements.txt" ]]; then
  pip install -r "${ROOT}/services/api/requirements.txt" >/dev/null || true
fi
if [[ -f "${ROOT}/services/ui/requirements.txt" ]]; then
  pip install -r "${ROOT}/services/ui/requirements.txt" >/dev/null || true
fi

export PYTHONPATH="${ROOT}"
pip check || true

# ───────────────────────────────────────────────
# START API (FastAPI / Uvicorn)
# ───────────────────────────────────────────────
if [[ -f "${ROOT}/.pids/api.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/api.pid")" 2>/dev/null; then
  color_echo yellow "API already running (PID $(cat "${ROOT}/.pids/api.pid"))."
else
  color_echo blue "🚀 Starting API on port ${APIPORT}..."
  nohup "${VENV}/bin/uvicorn" services.api.main:app \
      --host 0.0.0.0 --port "${APIPORT}" \
      --reload \
      --access-log \
      --log-level debug \
      > "${API_LOG}" 2>&1 &
  echo $! > "${ROOT}/.pids/api.pid"
  color_echo green "✅ API started (PID=$(cat "${ROOT}/.pids/api.pid")) | log: ${API_LOG}"
fi

# ───────────────────────────────────────────────
# START UI (Streamlit)
# ───────────────────────────────────────────────
if [[ -f "${ROOT}/.pids/ui.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/ui.pid")" 2>/dev/null; then
  color_echo yellow "UI already running (PID $(cat "${ROOT}/.pids/ui.pid"))."
else
  color_echo blue "🚀 Starting Streamlit UI on port ${UIPORT}..."
  cd "${ROOT}/services/ui"
  nohup "${VENV}/bin/streamlit" run app.py \
      --server.port "${UIPORT}" \
      --server.address 0.0.0.0 \
      --server.fileWatcherType none \
      --logger.level debug \
      > "${UI_LOG}" 2>&1 &
  echo $! > "${ROOT}/.pids/ui.pid"
  cd "${ROOT}"
  color_echo green "✅ UI started (PID=$(cat "${ROOT}/.pids/ui.pid")) | log: ${UI_LOG}"
fi

# ───────────────────────────────────────────────
# STATUS SUMMARY
# ───────────────────────────────────────────────
echo "----------------------------------------------------"
color_echo blue "🎯 All services running!"
color_echo blue "📘 Swagger: http://localhost:${APIPORT}/docs"
color_echo blue "🌐 Web UI:  http://localhost:${UIPORT}"
color_echo blue "📂 Logs:    ${LOGDIR}"
echo "   - API:      ${API_LOG}"
echo "   - UI:       ${UI_LOG}"
echo "   - Combined: ${COMBINED_LOG}"
echo "   - Unified:  ${ERR_LOG}"
echo "----------------------------------------------------"

# ───────────────────────────────────────────────
# LIVE LOG MONITOR
# ───────────────────────────────────────────────
color_echo blue "🧩 Starting live log monitor..."
nohup bash -c "tail -n +1 -F '${API_LOG}' '${UI_LOG}' \
  | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), \"[STREAM]\", \$0 }' \
  | tee -a '${COMBINED_LOG}' \
  | tee -a '${ERR_LOG}' >/dev/null" >/dev/null 2>&1 &
LOG_MONITOR_PID=$!
echo $LOG_MONITOR_PID > "${ROOT}/.pids/logmonitor.pid"
color_echo green "✅ Live log monitor running (PID=${LOG_MONITOR_PID})"
color_echo blue "📄 Combined → ${COMBINED_LOG}"
color_echo blue "🧾 Unified  → ${ERR_LOG}"

# ───────────────────────────────────────────────
# SHOW ERRORS IN REAL TIME
# ───────────────────────────────────────────────
color_echo yellow "👁  Real-time ERROR view (Ctrl+C to exit)…"
tail -n 50 -f "${ERR_LOG}" 2>/dev/null || true
