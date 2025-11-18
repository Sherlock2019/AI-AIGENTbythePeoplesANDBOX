#!/usr/bin/env bash
# -------------------------------------------------------------------------
# Unified Agents launcher (API + UI + Gemma control tower)
# Inspired by newstart.sh but upgraded with persona-ready defaults.
# -------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
PIDDIR="${ROOT}/.pids"
RUNS_DIR="${ROOT}/services/api/.runs"

APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"
GEMMA_PORT="${GEMMA_PORT:-7001}"

START_API=1
START_UI=1
START_GEMMA=1
RESET_PORTS=1
TAIL_LOGS=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]
Options:
  --no-api          Skip launching FastAPI backend
  --no-ui           Skip launching Streamlit UI
  --no-gemma        Skip launching Gemma control tower server
  --keep-ports      Do not free ports before starting
  --tail            Attach to unified log tail at the end
  -h, --help        Show this help
Env overrides: APIPORT, UIPORT, GEMMA_PORT, OLLAMA_URL, GEMMA_MODEL_ID
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-api) START_API=0 ;;
    --no-ui) START_UI=0 ;;
    --no-gemma) START_GEMMA=0 ;;
    --keep-ports) RESET_PORTS=0 ;;
    --tail) TAIL_LOGS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

mkdir -p "${LOGDIR}" "${PIDDIR}" "${RUNS_DIR}" \
         "${ROOT}/agents/credit_appraisal/models/production"

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

start_process() {
  local name="$1"
  local log="$2"
  local pid_file="$3"
  shift 3
  local cmd=("$@")

  nohup "${cmd[@]}" > "${log}" 2>&1 &
  local pid=$!
  echo "${pid}" > "${pid_file}"
  color_echo green "✅ ${name} started (PID=${pid}) | log: ${log}"
}

write_gemma_server() {
  local script="${ROOT}/gemma_server.py"
  if [[ -f "${script}" ]]; then
    return
  fi
  cat > "${script}" <<'PY'
import os
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import uvicorn

MODEL_ID = os.getenv("GEMMA_MODEL_ID", "google/gemma-2-2b-it")
MAX_NEW_TOKENS = int(os.getenv("GEMMA_MAX_TOKENS", "200"))
TEMPERATURE = float(os.getenv("GEMMA_TEMPERATURE", "0.7"))
TOP_P = float(os.getenv("GEMMA_TOP_P", "0.95"))
PORT = int(os.getenv("GEMMA_PORT", "7001"))

print(f"✅ Loading {MODEL_ID} (this may take a minute)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float32,
    device_map="cpu"
)

app = FastAPI()

class ChatRequest(BaseModel):
    prompt: str

@app.post("/chat")
def chat(req: ChatRequest):
    inputs = tokenizer(req.prompt, return_tensors="pt")
    output = model.generate(
        **inputs,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=True,
        temperature=TEMPERATURE,
        top_p=TOP_P,
    )
    answer = tokenizer.decode(output[0], skip_special_tokens=True)
    return {"response": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
PY
}

setup_venv() {
  if [[ ! -d "${VENV}" ]]; then
    python3 -m venv "${VENV}"
  fi
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
  python -m pip install -U pip wheel
  pip install -r "${ROOT}/services/api/requirements.txt"
  pip install -r "${ROOT}/services/ui/requirements.txt"
  deactivate
}

start_gemma() {
  ensure_writable "${LOGDIR}"
  local ts="$1"
  local log="${LOGDIR}/gemma_${ts}.log"
  local pid_file="${PIDDIR}/gemma.pid"
  local env_dir="${ROOT}/gemma_env"

  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    color_echo yellow "Gemma server already running (PID $(cat "${pid_file}"))."
    return
  fi

  if [[ ! -d "${env_dir}" ]]; then
    python3 -m venv "${env_dir}"
  fi
  write_gemma_server
  # shellcheck disable=SC1091
  source "${env_dir}/bin/activate"
  pip install -U pip wheel
  pip install torch transformers accelerate fastapi uvicorn sentencepiece >/dev/null
  GEMMA_MODEL_ID="${GEMMA_MODEL_ID:-google/gemma-2-2b-it}" \
  GEMMA_PORT="${GEMMA_PORT}" \
    start_process "Gemma control tower" "${log}" "${pid_file}" \
      "${env_dir}/bin/python" "${ROOT}/gemma_server.py"
  deactivate
}

ensure_writable "${LOGDIR}"
ensure_writable "${PIDDIR}"

if (( RESET_PORTS )); then
  color_echo blue "🧹 Freeing ports ${APIPORT}, 8501, ${UIPORT}, ${GEMMA_PORT}..."
  free_port "${APIPORT}"
  free_port 8501
  free_port "${UIPORT}"
  free_port "${GEMMA_PORT}"
  sleep 1
  color_echo green "✅ Ports cleared."
fi

TS="$(date +"%Y%m%d-%H%M%S")"
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
GEMMA_LOG="${LOGDIR}/gemma_${TS}.log"
COMBINED_LOG="${LOGDIR}/live_combined_${TS}.log"
ERR_LOG="${LOGDIR}/err.log"
: > "${API_LOG}"; : > "${UI_LOG}"; : > "${COMBINED_LOG}"; touch "${ERR_LOG}"

if (( START_API || START_UI )); then
  setup_venv
fi

if (( START_GEMMA )); then
  start_gemma "${TS}"
fi

if (( START_API )); then
  if [[ -f "${PIDDIR}/api.pid" ]] && kill -0 "$(cat "${PIDDIR}/api.pid")" 2>/dev/null; then
    color_echo yellow "API already running (PID $(cat "${PIDDIR}/api.pid"))."
  else
    start_process "API" "${API_LOG}" "${PIDDIR}/api.pid" \
      "${VENV}/bin/uvicorn" services.api.main:app \
        --host 0.0.0.0 \
        --port "${APIPORT}" \
        --reload \
        --access-log \
        --log-level debug
  fi
fi

if (( START_UI )); then
  if [[ -f "${PIDDIR}/ui.pid" ]] && kill -0 "$(cat "${PIDDIR}/ui.pid")" 2>/dev/null; then
    color_echo yellow "UI already running (PID $(cat "${PIDDIR}/ui.pid"))."
  else
    pushd "${ROOT}/services/ui" >/dev/null
    start_process "UI" "${UI_LOG}" "${PIDDIR}/ui.pid" \
      "${VENV}/bin/streamlit" run "app.py" \
        --server.port "${UIPORT}" \
        --server.address 0.0.0.0 \
        --server.fileWatcherType none \
        --logger.level debug
    popd >/dev/null
  fi
fi

color_echo blue "----------------------------------------------------"
color_echo blue "🎯 Launch Summary"
color_echo blue "📘 Swagger: http://localhost:${APIPORT}/docs"
color_echo blue "🌐 Web UI:  http://localhost:${UIPORT}"
color_echo blue "🧠 Gemma API: http://localhost:${GEMMA_PORT}/chat"
color_echo blue "🧑‍🚀 Persona Room: http://localhost:${UIPORT}/persona_chatroom"
color_echo blue "📂 Logs @ ${LOGDIR}"
echo "   - API:      ${API_LOG}"
echo "   - UI:       ${UI_LOG}"
echo "   - Gemma:    ${GEMMA_LOG}"
echo "   - Combined: ${COMBINED_LOG}"
echo "   - Unified:  ${ERR_LOG}"
color_echo blue "----------------------------------------------------"

color_echo blue "🧩 Starting live log monitor..."
nohup bash -c "tail -n +1 -F '${API_LOG}' '${UI_LOG}' '${GEMMA_LOG}' \
  | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), \"[STREAM]\", \$0 }' \
  | tee -a '${COMBINED_LOG}' \
  | tee -a '${ERR_LOG}' >/dev/null" >/dev/null 2>&1 &
LOG_MONITOR_PID=$!
echo $LOG_MONITOR_PID > "${PIDDIR}/logmonitor.pid"
color_echo green "✅ Live log monitor running (PID=${LOG_MONITOR_PID})"

if (( TAIL_LOGS )); then
  color_echo yellow "👁  Real-time unified log view (Ctrl+C to exit)…"
  tail -n 50 -f "${ERR_LOG}" 2>/dev/null || true
fi
