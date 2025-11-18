#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${ROOT}/.logs"
PIDDIR="${ROOT}/.pids"
LOGDIR="${LOGDIR:-${ROOT}/.logs}"
mkdir -p "${LOGDIR}" "${PIDDIR}"

OLLAMA_LOG="${LOGDIR}/ollama_prestart.log"
OLLAMA_PID_FILE="${PIDDIR}/ollama_prestart.pid"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma2:9b}"
export SANDBOX_CHATBOT_MODEL="${SANDBOX_CHATBOT_MODEL:-${OLLAMA_MODEL}}"

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

install_ollama_cli() {
  if command -v ollama >/dev/null 2>&1; then
    return
  fi
  color_echo yellow "Ollama CLI missing. Installing..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://ollama.com/install.sh | sh
  else
    color_echo red "Neither curl nor wget is available to install Ollama."
    exit 1
 	fi
  if ! command -v ollama >/dev/null 2>&1; then
    color_echo red "Failed to install Ollama. Install manually."
    exit 1
  fi
  color_echo green "Ollama CLI installed."
}

ping_ollama() {
  curl -sf "${OLLAMA_HOST%/}/api/tags" >/dev/null
}

start_ollama() {
  install_ollama_cli

  if [[ -f "${OLLAMA_PID_FILE}" ]]; then
    pid=$(<"${OLLAMA_PID_FILE}")
    if kill -0 "$pid" 2>/dev/null; then
      color_echo yellow "Existing Ollama (pid=$pid) already managed by this script."
      return
    else
      rm -f "${OLLAMA_PID_FILE}"
    fi
  fi

  color_echo blue "Starting Ollama server..."
  nohup ollama serve >"${OLLAMA_LOG}" 2>&1 &
  echo $! >"${OLLAMA_PID_FILE}"

  for i in {1..15}; do
    if ping_ollama; then
      break
    fi
    color_echo yellow "Waiting for Ollama to respond (${i}/15)..."
    sleep 1
  done

  if ! ping_ollama; then
    color_echo red "Ollama did not start. Check ${OLLAMA_LOG}."
    exit 1
  fi

  color_echo blue "Pulling model ${OLLAMA_MODEL} if needed..."
  if ! ollama list | grep -q "${OLLAMA_MODEL}"; then
    ollama pull "${OLLAMA_MODEL}"
  fi

  color_echo green "Ollama ready on ${OLLAMA_HOST}."
}

start_ollama

color_echo blue "Launching platform via start.sh..."
exec "${ROOT}/start.sh" "$@"
