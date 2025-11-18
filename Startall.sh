#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"
GEMMA_PORT="${GEMMA_PORT:-7001}"
GEMMA_ENV="${ROOT}/gemma_env"
GEMMA_SCRIPT="${ROOT}/gemma_server.py"
GEMMA_MODEL_ID="${GEMMA_MODEL_ID:-google/gemma-2-2b-it}"
HF_TOKEN_FILE="${HOME}/.cache/huggingface/token"

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

write_gemma_server() {
  if [[ -f "${GEMMA_SCRIPT}" ]]; then
    return
  fi
  cat > "${GEMMA_SCRIPT}" <<'PY'
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

setup_gemma_env() {
  if [[ ! -d "${GEMMA_ENV}" ]]; then
    python3 -m venv "${GEMMA_ENV}"
  fi
  source "${GEMMA_ENV}/bin/activate"
  pip install -U pip wheel
  pip install torch transformers accelerate fastapi uvicorn sentencepiece
  deactivate
}

start_gemma_server() {
  ensure_writable "${LOGDIR}"
  local log="${LOGDIR}/gemma_${TS}.log"
  if [[ -f "${ROOT}/.pids/gemma.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/gemma.pid")" 2>/dev/null; then
    color_echo yellow "Gemma server already running (PID $(cat "${ROOT}/.pids/gemma.pid"))"
    return
  fi
  if [[ ! -f "${HF_TOKEN_FILE}" ]]; then
    color_echo yellow "⚠️ Hugging Face token not found at ${HF_TOKEN_FILE}. Ensure you've run 'hf auth login'."
  fi
  pushd "${ROOT}" >/dev/null
  source "${GEMMA_ENV}/bin/activate"
  GEMMA_MODEL_ID="${GEMMA_MODEL_ID}" GEMMA_PORT="${GEMMA_PORT}" nohup "${GEMMA_ENV}/bin/python" "${GEMMA_SCRIPT}" \
      > "${log}" 2>&1 &
  echo $! > "${ROOT}/.pids/gemma.pid"
  deactivate
  popd >/dev/null
  color_echo green "✅ Gemma server started (PID=$(cat "${ROOT}/.pids/gemma.pid")) | log: ${log}"
}

# ---------- main script ----------
ensure_writable "${LOGDIR}"
ensure_writable "${ROOT}/.pids"

color_echo blue "🧹 Freeing ports ${APIPORT}, 8501, ${UIPORT}, ${GEMMA_PORT}..."
free_port "${APIPORT}"
free_port 8501
free_port "${UIPORT}"
free_port "${GEMMA_PORT}"
sleep 1
color_echo green "✅ Ports cleared."

TS="$(date +"%Y%m%d-%H%M%S")"
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
GEMMA_LOG="${LOGDIR}/gemma_${TS}.log"
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
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:${GEMMA_PORT}}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma2b-local}"

deactivate

setup_gemma_env
write_gemma_server
start_gemma_server

# restart python env for app
source "${VENV}/bin/activate"
export PYTHONPATH="${ROOT}"
export CHAT_USE_MISTRAL
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:${GEMMA_PORT}}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-gemma2b-local}"

if [[ -f "${ROOT}/.pids/api.pid" ]] && kill -0 "$(cat "${ROOT}/.pids/api.pid")" 2>/dev/null; then
  color_echo yellow "API already running (PID $(cat "${ROOT}/.pids/api.pid"))"
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
  color_echo yellow "UI already running (PID $(cat "${ROOT}/.pids/ui.pid"))"
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
color_echo blue "🧠 Gemma API: http://localhost:${GEMMA_PORT}/chat"
color_echo blue "📂 Logs:    ${LOGDIR}"
echo "   - API:      ${API_LOG}"
echo "   - UI:       ${UI_LOG}"
echo "   - Gemma:    ${GEMMA_LOG}"
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
