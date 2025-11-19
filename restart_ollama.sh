#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${ROOT}/.logs"
PIDDIR="${ROOT}/.pids"
mkdir -p "${LOGDIR}" "${PIDDIR}"

PORT="${1:-11434}"
OLLAMA_LOG="${LOGDIR}/ollama_restart.log"
OLLAMA_PID_FILE="${PIDDIR}/ollama_prestart.pid"

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

color_echo blue "🔍 Killing existing process on port ${PORT}..."
if command -v lsof >/dev/null 2>&1; then
  while read -r pid; do
    if [[ -n "$pid" ]]; then
      color_echo yellow "Stopping PID ${pid}"
      kill "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        color_echo yellow "Force killing PID ${pid}"
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
  done < <(lsof -ti tcp:"${PORT}" || true)
else
  fuser -k "${PORT}/tcp" 2>/dev/null || true
fi

if [[ -f "${OLLAMA_PID_FILE}" ]]; then
  pid="$(cat "${OLLAMA_PID_FILE}")"
  if kill -0 "$pid" 2>/dev/null; then
    color_echo yellow "Removing old Ollama PID ${pid}"
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "${OLLAMA_PID_FILE}"
fi

if ! command -v ollama >/dev/null 2>&1; then
  color_echo red "Ollama CLI not found. Install it from https://ollama.com/download"
  exit 1
fi

color_echo blue "🚀 Relaunching Ollama on port ${PORT}..."
nohup env OLLAMA_HOST="127.0.0.1" OLLAMA_PORT="${PORT}" ollama serve --port "${PORT}" \
  >"${OLLAMA_LOG}" 2>&1 &
echo $! > "${OLLAMA_PID_FILE}"
sleep 2

if curl -sf "http://127.0.0.1:${PORT}/api/tags" >/dev/null; then
  color_echo green "✅ Ollama running (PID $(cat "${OLLAMA_PID_FILE}")) | log: ${OLLAMA_LOG}"
else
  color_echo red "❌ Failed to start Ollama. Check ${OLLAMA_LOG}"
  exit 1
fi
