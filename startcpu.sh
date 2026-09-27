#!/usr/bin/env bash
set -euo pipefail

# CPU-only launcher: no Ollama, no GPU. For small cloud VMs (EC2 t3.*) and
# laptops without a GPU. Starts the API (FastAPI) and UI (Streamlit) through
# ./ministart.sh, with every LLM/GPU path switched off:
#
#   * GPU     -- CUDA is hidden, so torch.cuda.is_available() is False and every
#                model runs on CPU. ministart.sh installs the CPU-only torch
#                wheel instead of the multi-GB CUDA build.
#   * Ollama  -- never started or pulled. The app's Ollama client refuses
#                immediately (OLLAMA_DISABLED=1) instead of launching
#                `ollama serve`, and chat answers from retrieval only
#                (CHAT_USE_OLLAMA=0). Stop a system-wide Ollama service too if
#                one is installed (the script tells you how).
#
# Usage:  ./startcpu.sh                      (same knobs as ministart.sh)
#         APIPORT=8090 UIPORT=8502 ./startcpu.sh
#
# For the full stack with Ollama, use ./newstart.sh or ./start.sh.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

export CUDA_VISIBLE_DEVICES=""
export OLLAMA_DISABLED=1
export CHAT_USE_OLLAMA=0

echo -e "\033[1;36m[INFO] CPU-only mode: GPU hidden, Ollama disabled\033[0m"

# A failed earlier run (python3-venv missing) leaves .venv without
# bin/activate; ministart.sh would then try to activate it and stop.
if [[ -d "${ROOT}/.venv" && ! -f "${ROOT}/.venv/bin/activate" ]]; then
  echo -e "\033[1;33m[WARN] ${ROOT}/.venv is incomplete (a failed earlier setup) -- removing it\033[0m"
  rm -rf "${ROOT}/.venv"
fi

# Stop an Ollama this project started earlier -- it only takes memory here.
for pid_file in "${ROOT}/.pids/ollama.pid" "${ROOT}/.pids/ollama_autostart.pid"; do
  [[ -f "${pid_file}" ]] || continue
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    echo -e "\033[1;36m[INFO] Stopping Ollama started by this project (PID ${pid})\033[0m"
    kill "${pid}" 2>/dev/null || true
  fi
  rm -f "${pid_file}"
done
if pgrep -f "ollama serve" >/dev/null 2>&1; then
  echo -e "\033[1;33m[WARN] An Ollama server is still running (likely the system service). CPU mode does\033[0m"
  echo -e "\033[1;33m       not use it; to free its memory: sudo systemctl disable --now ollama\033[0m"
fi

# Through bash: ministart.sh is not always checked out executable.
exec bash "${ROOT}/ministart.sh" "$@"
