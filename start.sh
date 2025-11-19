#!/usr/bin/env bash 
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma2:9b}"
export SANDBOX_CHATBOT_MODEL="${SANDBOX_CHATBOT_MODEL:-${OLLAMA_MODEL}}"

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
OLLAMA_LOG="${LOGDIR}/ollama_${TS}.log"

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

stop_if_running() {
  local label="$1"
  local pid_file="$2"
  if [[ -f "${pid_file}" ]]; then
    local pid
    pid="$(cat "${pid_file}")"
    if kill -0 "${pid}" 2>/dev/null; then
      color_echo yellow "Stopping existing ${label} (PID ${pid})..."
      kill "${pid}" 2>/dev/null || true
      sleep 1
      if kill -0 "${pid}" 2>/dev/null; then
        color_echo yellow "Force killing ${label} (PID ${pid})..."
        kill -9 "${pid}" 2>/dev/null || true
      fi
    fi
    rm -f "${pid_file}"
  fi
}

install_ollama_cli() {
  if command -v ollama >/dev/null 2>&1; then
    return
  fi
  color_echo yellow "Ollama CLI not detected. Installing..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://ollama.com/install.sh | sh
  else
    color_echo red "Neither curl nor wget available to install Ollama automatically."
    exit 1
  fi
  if ! command -v ollama >/dev/null 2>&1; then
    color_echo red "Ollama installation failed; install manually from https://ollama.com/download"
    exit 1
  fi
  color_echo green "Ollama CLI installed."
}

# ─────────────────────────────────────────────
# Ollama LLM backend
# ─────────────────────────────────────────────
ensure_ollama() {
  install_ollama_cli

  stop_if_running "Ollama" "${ROOT}/.pids/ollama.pid"
  if ! pgrep -f "ollama serve" >/dev/null 2>&1; then
    color_echo blue "Starting Ollama server..."
    nohup ollama serve > "${OLLAMA_LOG}" 2>&1 &
    echo $! > "${ROOT}/.pids/ollama.pid"
    sleep 2
  else
    color_echo yellow "Ollama server already running."
  fi

  color_echo blue "Ensuring model '${OLLAMA_MODEL}' is available..."
  if ! ollama list | grep -q "${OLLAMA_MODEL}"; then
    ollama pull "${OLLAMA_MODEL}"
  fi

  color_echo blue "Checking Ollama endpoint at ${OLLAMA_HOST}..."
  for i in {1..10}; do
    if curl -s "${OLLAMA_HOST}/api/tags" >/dev/null; then
      break
    fi
    color_echo yellow "Waiting for Ollama to accept connections (attempt ${i}/10)..."
    sleep 2
  done
  if ! curl -s "${OLLAMA_HOST}/api/tags" >/dev/null; then
    color_echo red "❌ Ollama endpoint ${OLLAMA_HOST} is unreachable. Check ${OLLAMA_LOG}."
    exit 1
  fi

  color_echo blue "Warming model '${OLLAMA_MODEL}'..."
  if ! curl -s -X POST "${OLLAMA_HOST}/api/chat" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${OLLAMA_MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"warm up\"}],\"stream\":false}" \
    >/dev/null; then
    color_echo yellow "Could not warm model automatically; it will load on first request."
  fi

  color_echo green "✅ Ollama ready (logs: ${OLLAMA_LOG})"
}

# Ensure Ollama backend (needs functions defined)
ensure_ollama

# ─────────────────────────────────────────────
# Start API
# ─────────────────────────────────────────────

stop_if_running "API" "${ROOT}/.pids/api.pid"
nohup "${VENV}/bin/uvicorn" services.api.main:app \
  --host 0.0.0.0 --port "${APIPORT}" --reload \
  > "${API_LOG}" 2>&1 &
echo $! > "${ROOT}/.pids/api.pid"
color_echo green "✅ API started (PID=$(cat "${ROOT}/.pids/api.pid")) | log: ${API_LOG}"

# ─────────────────────────────────────────────
# Start UI (Streamlit)
# ─────────────────────────────────────────────
stop_if_running "UI" "${ROOT}/.pids/ui.pid"
color_echo blue "Starting Streamlit UI..."
cd "${ROOT}/services/ui"
nohup "${VENV}/bin/streamlit" run "app.py" \
  --server.port "${UIPORT}" --server.address 0.0.0.0 \
  --server.fileWatcherType none \
  > "${UI_LOG}" 2>&1 &
echo $! > "${ROOT}/.pids/ui.pid"
cd "${ROOT}"
color_echo green "✅ UI started (PID=$(cat "${ROOT}/.pids/ui.pid")) | log: ${UI_LOG}"

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
# Health checks
# ─────────────────────────────────────────────
color_echo blue "🔎 Verifying service health..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${APIPORT}/v1/health" || true)
if [[ "${API_STATUS}" == "200" ]]; then
  color_echo green "API OK (HTTP 200) → http://localhost:${APIPORT}  (docs: http://localhost:${APIPORT}/docs)"
else
  color_echo red "API health check failed (status=${API_STATUS:-unreachable}) — check ${API_LOG}"
fi

UI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${UIPORT}" || true)
if [[ "${UI_STATUS}" == "200" ]]; then
  color_echo green "UI OK (HTTP 200) → http://localhost:${UIPORT}"
else
  color_echo yellow "UI check returned ${UI_STATUS:-unreachable} (Streamlit may still be starting) — monitor ${UI_LOG}"
fi

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
