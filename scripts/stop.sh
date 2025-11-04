#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="${ROOT}/.pids"

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

# ─────────────────────────────────────────────
# Stop process helper
# ─────────────────────────────────────────────
stop_process() {
  local name="$1"
  local pidfile="${PID_DIR}/${name}.pid"

  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      color_echo yellow "Stopping $name (PID=$pid)..."
      kill "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        color_echo red "Force killing $name (PID=$pid)..."
        kill -9 "$pid" 2>/dev/null || true
      fi
      color_echo green "✅ $name stopped."
    else
      color_echo yellow "$name not running."
    fi
    rm -f "$pidfile"
  else
    color_echo yellow "No PID file found for $name."
  fi
}

# ─────────────────────────────────────────────
# Stop all services
# ─────────────────────────────────────────────
color_echo blue "🛑 Stopping all running services..."

stop_process "api"
stop_process "ui"
stop_process "logmonitor"

# ─────────────────────────────────────────────
# Clean up any orphaned ports
# ─────────────────────────────────────────────
color_echo blue "🧹 Checking for orphaned ports (8090 / 8502)..."
for port in 8090 8502; do
  pid=$(lsof -ti :${port} || true)
  if [[ -n "$pid" ]]; then
    color_echo yellow "Found process using port ${port} (PID=$pid). Killing..."
    kill -9 "$pid" || true
  fi
done

color_echo green "✅ All services stopped and ports released."
