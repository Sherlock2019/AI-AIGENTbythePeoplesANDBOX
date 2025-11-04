#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# Paths & Ports
# ─────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
PIDDIR="${ROOT}/.pids"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"

mkdir -p "$LOGDIR" \
         "${ROOT}/services/api/.runs" \
         "${ROOT}/agents/credit_appraisal/models/production" \
         "$PIDDIR"

# ─────────────────────────────────────────────
# Pre-cleanup — free ports
# ─────────────────────────────────────────────
echo "🧹 Checking for existing processes on ports ${APIPORT} and ${UIPORT}..."
sudo fuser -k "${APIPORT}/tcp" 2>/dev/null || true
sudo fuser -k "${UIPORT}/tcp" 2>/dev/null || true
sleep 1
echo "✅ Old processes cleaned up."

# ─────────────────────────────────────────────
# Timestamps & log files
# ─────────────────────────────────────────────
TS="$(date +"%Y%m%d-%H%M%S")"
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
COMBINED_LOG="${LOGDIR}/live_combined_${TS}.log"
ERROR_LOG="${LOGDIR}/errors_${TS}.log"

# ─────────────────────────────────────────────
# Virtualenv & deps
# ─────────────────────────────────────────────
if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"

python -V
pip -V
python -m pip install -U pip wheel
pip install -r "${ROOT}/services/api/requirements.txt"
pip install -r "${ROOT}/services/ui/requirements.txt"

export PYTHONPATH="${ROOT}"

# ─────────────────────────────────────────────
# Color echo
# ─────────────────────────────────────────────
color_echo() {
  local color="$1"; shift
  local msg="$*"
  case "$color" in
    red)    echo -e "\033[1;31m$msg\033[0m" ;;
    green)  echo -e "\033[1;32m$msg\033[0m" ;;
    yellow) echo -e "\033[1;33m$msg\033[0m" ;;
    blue)   echo -e "\033[1;34m$msg\033[0m" ;;
    *)      echo "$msg" ;;
  esac
}

# ─────────────────────────────────────────────
# Line-buffer helper (stdbuf)
# ─────────────────────────────────────────────
STDBUF=""
if command -v stdbuf >/dev/null 2>&1; then
  # Force line buffering on stdout and stderr
  STDBUF="stdbuf -oL -eL"
fi

# ─────────────────────────────────────────────
# Start API (Uvicorn/FastAPI)
# ─────────────────────────────────────────────
if [[ -f "${PIDDIR}/api.pid" ]] && kill -0 "$(cat "${PIDDIR}/api.pid")" 2>/dev/null; then
  color_echo yellow "API already running (PID $(cat "${PIDDIR}/api.pid"))."
else
  # Stronger logging for API
  export UVICORN_ACCESS_LOG=true
  nohup bash -c "${STDBUF} '${VENV}/bin/uvicorn' services.api.main:app \
      --host 0.0.0.0 \
      --port '${APIPORT}' \
      --reload \
      --log-level info \
      --use-colors" \
      > "${API_LOG}" 2>&1 &
  echo $! > "${PIDDIR}/api.pid"
  color_echo green "✅ API started (PID=$(cat "${PIDDIR}/api.pid")) | log: ${API_LOG}"
fi

# ─────────────────────────────────────────────
# Start UI (Streamlit)
# ─────────────────────────────────────────────
if [[ -f "${PIDDIR}/ui.pid" ]] && kill -0 "$(cat "${PIDDIR}/ui.pid")" 2>/dev/null; then
  color_echo yellow "UI already running (PID $(cat "${PIDDIR}/ui.pid"))."
else
  color_echo blue "Starting Streamlit UI..."
  export STREAMLIT_LOG_LEVEL=debug
  cd "${ROOT}/services/ui"
  nohup bash -c "${STDBUF} '${VENV}/bin/streamlit' run 'app.py' \
      --server.port '${UIPORT}' \
      --server.address 0.0.0.0 \
      --server.fileWatcherType none" \
      > "${UI_LOG}" 2>&1 &
  echo $! > "${PIDDIR}/ui.pid"
  cd "${ROOT}"
  color_echo green "✅ UI started (PID=$(cat "${PIDDIR}/ui.pid")) | log: ${UI_LOG}"
fi

# ─────────────────────────────────────────────
# Info banner
# ─────────────────────────────────────────────
echo "----------------------------------------------------"
color_echo blue "🎯 All services running!"
color_echo blue "📘 Swagger: http://localhost:${APIPORT}/docs"
color_echo blue "🌐 Web UI:  http://localhost:${UIPORT}"
color_echo blue "📂 Logs dir: ${LOGDIR}"
echo "   - API:      ${API_LOG}"
echo "   - UI:       ${UI_LOG}"
echo "   - Combined: ${COMBINED_LOG}"
echo "   - Errors:   ${ERROR_LOG}"
echo "----------------------------------------------------"

# ─────────────────────────────────────────────
# Live log combiner (API + UI → combined)
# ─────────────────────────────────────────────
color_echo blue "🧩 Starting live log combiner..."
nohup bash -c "tail -n 0 -F '${API_LOG}' '${UI_LOG}' | ${STDBUF:-cat} tee -a '${COMBINED_LOG}' >/dev/null" >/dev/null 2>&1 &
COMBINER_PID=$!
echo $COMBINER_PID > "${PIDDIR}/combiner.pid"
color_echo green "✅ Combiner running (PID=${COMBINER_PID})"

# ─────────────────────────────────────────────
# Error block extractor (full tracebacks)
# ─────────────────────────────────────────────
# Captures from a trigger line through the next blank line.
# Triggers on: ERROR | CRITICAL | Traceback | Exception
color_echo blue "🧪 Starting error extractor → ${ERROR_LOG}"
AWK_SCRIPT='
  BEGIN { inerr=0 }
  # Trigger lines that start a new error block
  /ERROR|CRITICAL|Traceback|Exception/ {
      if (inerr==0) {
          print "────────────────────────────────────────" > errfile
          printf("⏱  %s\n", strftime("%Y-%m-%d %H:%M:%S")) > errfile
          inerr=1
      }
      print $0 >> errfile
      fflush(errfile)
      next
  }
  # While in an error block, keep printing until a blank line separates blocks
  {
      if (inerr==1) {
          print $0 >> errfile
          fflush(errfile)
          if ($0 ~ /^[[:space:]]*$/) { inerr=0 }
      }
  }
'
nohup bash -c "
  errfile='${ERROR_LOG}';
  export errfile;
  tail -n 0 -F '${COMBINED_LOG}' | awk \"$AWK_SCRIPT\"
" >/dev/null 2>&1 &
EXTRACTOR_PID=$!
echo $EXTRACTOR_PID > "${PIDDIR}/errorextractor.pid"
color_echo green "✅ Error extractor running (PID=${EXTRACTOR_PID})"

# ─────────────────────────────────────────────
# Cleanup on exit
# ─────────────────────────────────────────────
cleanup() {
  color_echo yellow '🧽 Shutting down background monitors...'
  for f in combiner.pid errorextractor.pid logmonitor.pid; do
    if [[ -f "${PIDDIR}/${f}" ]]; then
      pid=$(cat "${PIDDIR}/${f}" || true)
      [[ -n "${pid:-}" ]] && kill "${pid}" 2>/dev/null || true
      rm -f "${PIDDIR}/${f}" || true
    fi
  done
  color_echo green '✅ Monitors stopped.'
}
trap cleanup EXIT

# ─────────────────────────────────────────────
# Interactive tail (choose mode via env)
#   LIVE=1        → show full combined stream
#   FOLLOW_ERROR=1→ show only error blocks as they are written
#   default       → show filtered real-time view of combined errors (legacy)
# ─────────────────────────────────────────────
touch "${COMBINED_LOG}" "${ERROR_LOG}"

if [[ "${LIVE:-0}" == "1" ]]; then
  color_echo yellow "👁  Real-time COMBINED view (Ctrl+C to exit)..."
  tail -n 100 -F "${COMBINED_LOG}"
elif [[ "${FOLLOW_ERROR:-1}" == "1" ]]; then
  color_echo red "👁  Real-time ERRORS view (full blocks) (Ctrl+C to exit)..."
  tail -n 50 -F "${ERROR_LOG}"
else
  color_echo yellow "👁  Real-time filtered ERROR view (line matches only) (Ctrl+C to exit)..."
  tail -n 20 -F "${COMBINED_LOG}" | grep --line-buffered -E --color=always "ERROR|Exception|Traceback|CRITICAL" || true
fi
