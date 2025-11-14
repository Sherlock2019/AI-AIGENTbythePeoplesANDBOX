#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"   # UI stays on 8502
GEMMA_2_CHATBOT_DIR="${GEMMA_2_CHATBOT_DIR:-${HOME}/chatbox/gemma2-chatbot-9b}"
GEMMA_2_CHATBOT_BACKEND_PORT="${GEMMA_2_CHATBOT_BACKEND_PORT:-9091}"
GEMMA_2_CHATBOT_UI_PORT="${GEMMA_2_CHATBOT_UI_PORT:-9062}"
GEMMA_2_CHATBOT_LOG_DIR="${GEMMA_2_CHATBOT_LOG_DIR:-${LOGDIR}/gemma2-chatbot}"

# Environment knobs that can be overridden before running `newstart.sh`:
#  * GEMMA_2_CHATBOT_DIR: location of the Gemma-2 chatbot repo (default ~/chatbox/gemma2-chatbot-9b)
#  * GEMMA_2_CHATBOT_BACKEND_PORT: port that the Gemma FastAPI backend uses (default 9091)
#  * GEMMA_2_CHATBOT_UI_PORT: port that the Gemma Streamlit UI exposes (default 9062)
#  * GEMMA_2_CHATBOT_LOG_DIR: where the launcher stores Gemma logs (default ${LOGDIR}/gemma2-chatbot)

mkdir -p "${LOGDIR}" \
         "${ROOT}/services/api/.runs" \
         "${ROOT}/agents/credit_appraisal/models/production" \
         "${ROOT}/.pids"

# ---------- helpers ----------
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
  if [[ ! -w "$d" ]]; then
    chmod u+rwx "$d" 2>/dev/null || true
    chown "$(id -u)":"$(id -g)" "$d" 2>/dev/null || true
  fi
  [[ -w "$d" ]] || { echo "❌ '$d' not writable"; exit 1; }
}

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -t -i :"${port}" 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then kill -9 ${pids} 2>/dev/null || true; fi
  if lsof -i :"${port}" >/dev/null 2>&1; then
    sudo -n fuser -k "${port}/tcp" 2>/dev/null || true
  fi
}

wait_for_port() {
  local port="$1"
  local attempts="${2:-30}"
  for i in $(seq 1 "${attempts}"); do
    if curl -s "http://localhost:${port}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_gemma2_9b_stack() {
  local start_script="${GEMMA_2_CHATBOT_DIR}/start.sh"
  if [[ ! -d "${GEMMA_2_CHATBOT_DIR}" ]]; then
    color_echo yellow "ℹ️ Gemma-2 9B directory '${GEMMA_2_CHATBOT_DIR}' not found; skipping."
    return 1
  fi
  if [[ ! -f "${start_script}" ]]; then
    color_echo red "❌ Gemma-2 9B start script '${start_script}' not found."
    return 1
  fi
  mkdir -p "${GEMMA_2_CHATBOT_LOG_DIR}"
  ensure_writable "${GEMMA_2_CHATBOT_LOG_DIR}"
  local pid_file="${ROOT}/.pids/gemma_2_9b.pid"
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    color_echo yellow "Gemma-2 9B stack already running (PID $(cat "${pid_file}"))"
    return
  fi
  local log="${GEMMA_2_9B_LOG}"
  nohup bash -c "
    set -euo pipefail
    cd '${GEMMA_2_CHATBOT_DIR}'
    export BACKEND_PORT='${GEMMA_2_CHATBOT_BACKEND_PORT}'
    export UI_PORT='${GEMMA_2_CHATBOT_UI_PORT}'
    export LOG_DIR='${GEMMA_2_CHATBOT_LOG_DIR}'
    bash '${start_script}'
  " > "${log}" 2>&1 &
  echo $! > "${pid_file}"
  color_echo green "✅ Gemma-2 9B stack started (PID=$(cat "${pid_file}")) | log: ${log}"
}

# ---------- preflight ----------
ensure_writable "${LOGDIR}"
ensure_writable "${ROOT}/.pids"

color_echo blue "🧹 Freeing ports ${APIPORT}, 8501, ${UIPORT}..."
free_port "${APIPORT}"
free_port 8501          # kill any stale default Streamlit
free_port "${UIPORT}"
sleep 1
color_echo green "✅ Ports cleared."

# ---------- logs ----------
TS="$(date +"%Y%m%d-%H%M%S")"
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
GEMMA_2_9B_LOG="${LOGDIR}/gemma2_9b_${TS}.log"
COMBINED_LOG="${LOGDIR}/live_combined_${TS}.log"
ERR_LOG="${LOGDIR}/err.log"
: > "${API_LOG}"; : > "${UI_LOG}"; : > "${GEMMA_2_9B_LOG}"; : > "${COMBINED_LOG}"; touch "${ERR_LOG}"

# ---------- Gemma-2 9B ----------
start_gemma2_9b_stack
color_echo blue "⏳ Waiting for Gemma-2 9B backend on port ${GEMMA_2_CHATBOT_BACKEND_PORT}..."
if wait_for_port "${GEMMA_2_CHATBOT_BACKEND_PORT}" 30; then
  color_echo green "✅ Gemma-2 9B backend online"
else
  color_echo red "⚠️ Gemma-2 9B backend did not respond in time"
fi

# ---------- venv ----------
if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -V
pip -V

python -m pip install -U pip wheel
pip install -r "${ROOT}/services/api/requirements.txt"
pip install -r "${ROOT}/services/ui/requirements.txt"
export PYTHONPATH="${ROOT}"
export GEMMA_URL="http://localhost:${GEMMA_2_CHATBOT_BACKEND_PORT}"
export API_URL="http://localhost:${APIPORT}"
# ---------- API (8090) with detailed access logs ----------
if [[ -f "${ROOT}/.pids/api.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/api.pid")" 2>/dev/null; then
  color_echo yellow "API already running (PID $(cat "${ROOT}/.pids/api.pid"))."
else
  nohup "${VENV}/bin/uvicorn" services.api.main:app \
      --host 0.0.0.0 --port "${APIPORT}" \
      --reload \
      --access-log \
      --log-level debug \
      > "${API_LOG}" 2>&1 &
  echo $! > "${ROOT}/.pids/api.pid"
  color_echo green "✅ API started (PID=$(cat "${ROOT}/.pids/api.pid")) | log: ${API_LOG}"
fi

# ---------- UI (8502) with DEBUG logs ----------
if [[ -f "${ROOT}/.pids/ui.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/ui.pid")" 2>/dev/null; then
  color_echo yellow "UI already running (PID $(cat "${ROOT}/.pids/ui.pid"))."
else
  color_echo blue "Starting Streamlit UI..."
  cd "${ROOT}/services/ui"
  nohup "${VENV}/bin/streamlit" run "app.py" \
      --server.port "${UIPORT}" \
      --server.address 0.0.0.0 \
      --server.fileWatcherType none \
      --logger.level debug \
      > "${UI_LOG}" 2>&1 &
  echo $! > "${ROOT}/.pids/ui.pid"
  cd "${ROOT}"
  color_echo green "✅ UI started (PID=$(cat "${ROOT}/.pids/ui.pid")) | log: ${UI_LOG}"
fi

# ---------- info ----------
echo "----------------------------------------------------"
color_echo blue "🎯 All services running!"
color_echo blue "📘 Swagger: http://localhost:${APIPORT}/docs"
color_echo blue "🌐 Web UI:  http://localhost:${UIPORT}"
color_echo blue "🤖 Gemma-2 9B backend: http://localhost:${GEMMA_2_CHATBOT_BACKEND_PORT}"
color_echo blue "🤖 Gemma-2 9B log: ${GEMMA_2_9B_LOG}"
color_echo blue "📂 Logs:    ${LOGDIR}"
echo "   - API:      ${API_LOG}"
echo "   - UI:       ${UI_LOG}"
echo "   - Gemma-2 9B: ${GEMMA_2_9B_LOG}"
echo "   - Combined: ${COMBINED_LOG}"
echo "   - Unified:  ${ERR_LOG}   (ALL activity from API+UI)"
echo "----------------------------------------------------"

# ---------- combined monitor (include existing + follow) ----------
color_echo blue "🧩 Starting live log monitor..."
nohup bash -c "tail -n +1 -F '${API_LOG}' '${UI_LOG}' '${GEMMA_2_9B_LOG}' \
  | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), \"[STREAM]\", \$0 }' \
  | tee -a '${COMBINED_LOG}' \
  | tee -a '${ERR_LOG}' >/dev/null" >/dev/null 2>&1 &
LOG_MONITOR_PID=$!
echo $LOG_MONITOR_PID > "${ROOT}/.pids/logmonitor.pid"
color_echo green "✅ Live log monitor running (PID=${LOG_MONITOR_PID})"
color_echo blue "📄 Combined → ${COMBINED_LOG}"
color_echo blue "🧾 Unified  → ${ERR_LOG}"

# ---------- live view (quiet stderr) ----------
color_echo yellow "👁  Real-time ERROR view (Ctrl+C to exit)…"
tail -n 50 -f "${ERR_LOG}" 2>/dev/null || true
