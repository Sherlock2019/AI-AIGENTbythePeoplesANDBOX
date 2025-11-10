#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"   # UI stays on 8502
LLM_PORT="${LLM_PORT:-8001}"
MODEL_NAME="${MODEL_NAME:-mistral-7b-instruct.Q4_K_M.gguf}"
MODEL_URL="${MODEL_URL:-https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf}"
CHAT_USE_MISTRAL="${CHAT_USE_MISTRAL:-1}"
TEXTGEN_DIR="${ROOT}/text-generation-webui"

mkdir -p "${LOGDIR}" \
         "${ROOT}/services/api/.runs" \
         "${ROOT}/agents/credit_appraisal/models/production" \
         "${ROOT}/.pids"

# ---------- helper functions ----------
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
  [[ -w "$d" ]] || { color_echo red "❌ '$d' not writable"; exit 1; }
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

clone_textgen_webui() {
  if [[ -d "${TEXTGEN_DIR}" ]]; then
    color_echo yellow "text-generation-webui already present at ${TEXTGEN_DIR}"
    return
  fi
  color_echo blue "Cloning text-generation-webui..."
  git clone https://github.com/oobabooga/text-generation-webui.git "${TEXTGEN_DIR}"
  color_echo green "✅ text-generation-webui cloned."
}

setup_textgen_env() {
  clone_textgen_webui
  pushd "${TEXTGEN_DIR}" >/dev/null
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  source .venv/bin/activate
  pip install -U pip wheel
  pip install -r requirements.txt
  deactivate
  popd >/dev/null
}

download_llm_model() {
  mkdir -p "${TEXTGEN_DIR}/models"
  local target="${TEXTGEN_DIR}/models/${MODEL_NAME}"
  if [[ -f "${target}" ]]; then
    color_echo yellow "Model ${MODEL_NAME} already exists."
    return
  fi
  color_echo blue "Downloading ${MODEL_NAME}..."
  curl -L "${MODEL_URL}" -o "${target}"
  color_echo green "✅ Model downloaded to ${target}."
}

start_textgen_server() {
  ensure_writable "${LOGDIR}"
  local log="${LOGDIR}/llm_${TS}.log"
  if [[ -f "${ROOT}/.pids/llm.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/llm.pid")" 2>/dev/null; then
    color_echo yellow "LLM server already running (PID $(cat "${ROOT}/.pids/llm.pid"))."
    return
  fi
  pushd "${TEXTGEN_DIR}" >/dev/null
  source .venv/bin/activate
  nohup python server.py \
      --model "${MODEL_NAME}" \
      --cpu \
      --chat \
      --api \
      --api-port "${LLM_PORT}" \
      > "${log}" 2>&1 &
  echo $! > "${ROOT}/.pids/llm.pid"
  deactivate
  popd >/dev/null
  color_echo green "✅ LLM server started (PID=$(cat "${ROOT}/.pids/llm.pid")) | log: ${log}"
}

# ---------- main script ----------
ensure_writable "${LOGDIR}"
ensure_writable "${ROOT}/.pids"

color_echo blue "🧹 Freeing ports ${APIPORT}, 8501, ${UIPORT}, ${LLM_PORT}..."
free_port "${APIPORT}"
free_port 8501
free_port "${UIPORT}"
free_port "${LLM_PORT}"
sleep 1
color_echo green "✅ Ports cleared."

TS="$(date +"%Y%m%d-%H%M%S")"
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
COMBINED_LOG="${LOGDIR}/live_combined_${TS}.log"
ERR_LOG="${LOGDIR}/err.log"
: > "${API_LOG}"; : > "${UI_LOG}"; : > "${COMBINED_LOG}"; touch "${ERR_LOG}"

if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"
fi
source "${VENV}/bin/activate"
python -m pip install -U pip wheel
pip install -r "${ROOT}/services/api/requirements.txt"
pip install -r "${ROOT}/services/ui/requirements.txt"
export PYTHONPATH="${ROOT}"
export CHAT_USE_MISTRAL
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:${LLM_PORT}}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-mistral-openai}" # just a label

setup_textgen_env
 download_llm_model
start_textgen_server

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

if [[ -f "${ROOT}/.pids/ui.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/ui.pid")" 2>/dev/null; then
  color_echo yellow "UI already running (PID $(cat "${ROOT}/.pids/ui.pid"))."
else
  color_echo blue "Starting Streamlit UI..."
  pushd "${ROOT}/services/ui" >/dev/null
  nohup "${VENV}/bin/streamlit" run "app.py" \
      --server.port "${UIPORT}" \
      --server.address 0.0.0.0 \
      --server.fileWatcherType none \
      --logger.level debug \
      > "${UI_LOG}" 2>&1 &
  echo $! > "${ROOT}/.pids/ui.pid"
  popd >/dev/null
  color_echo green "✅ UI started (PID=$(cat "${ROOT}/.pids/ui.pid")) | log: ${UI_LOG}"
fi

echo "----------------------------------------------------"
color_echo blue "🎯 All services running!"
color_echo blue "📘 Swagger: http://localhost:${APIPORT}/docs"
color_echo blue "🌐 Web UI:  http://localhost:${UIPORT}"
color_echo blue "🧠 LLM API: http://localhost:${LLM_PORT}/v1/chat/completions"
color_echo blue "📂 Logs:    ${LOGDIR}"
echo "   - API:      ${API_LOG}"
echo "   - UI:       ${UI_LOG}"
echo "   - Combined: ${COMBINED_LOG}"
echo "   - Unified:  ${ERR_LOG}"
echo "----------------------------------------------------"

color_echo blue "🧩 Starting live log monitor..."
nohup bash -c "tail -n +1 -F '${API_LOG}' '${UI_LOG}' \
  | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), \"[STREAM]\", \$0 }' \
  | tee -a '${COMBINED_LOG}' \
  | tee -a '${ERR_LOG}' >/dev/null" >/dev/null 2>&1 &
LOG_MONITOR_PID=$!
echo $LOG_MONITOR_PID > "${ROOT}/.pids/logmonitor.pid"
color_echo green "✅ Live log monitor running (PID=${LOG_MONITOR_PID})"
color_echo yellow "👁  Real-time ERROR view (Ctrl+C to exit)…"
tail -n 50 -f "${ERR_LOG}" 2>/dev/null || true
