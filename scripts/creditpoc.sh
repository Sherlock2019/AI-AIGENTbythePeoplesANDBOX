#!/usr/bin/env bash
# creditpoc.sh — one-click launcher for the Credit Appraisal PoC (API + UI)
# Usage:
#   ./creditpoc.sh start        # start API and UI
#   ./creditpoc.sh stop         # stop both
#   ./creditpoc.sh status       # show status + ports
#   ./creditpoc.sh tail         # tail both logs
#   ./creditpoc.sh restart      # restart both
#
# Env overrides:
#   REPO=~/credit-appraisal-agent-poc API_PORT=8090 UI_PORT=8502 OLLAMA_HOST=http://localhost:11434 ./creditpoc.sh start

set -Eeuo pipefail

# ────────────────────────────────────────────────────────────────────────────────
# Config
REPO="${REPO:-$HOME/credit-appraisal-agent-poc}"
API_PORT="${API_PORT:-8090}"
UI_PORT="${UI_PORT:-8502}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"

API_DIR="$REPO/services/api"
UI_DIR="$REPO/services/ui"
VENV="$API_DIR/.venv"
LOG_DIR="$REPO/logs"
PID_DIR="$REPO/.pids"

API_PID="$PID_DIR/api.pid"
UI_PID="$PID_DIR/ui.pid"
API_LOG="$LOG_DIR/api.log"
UI_LOG="$LOG_DIR/ui.log"

PYTHON="${PYTHON:-python3}"

# ────────────────────────────────────────────────────────────────────────────────
# Helpers

msg()  { echo -e "[$(date +'%H:%M:%S')] $*"; }
die()  { echo -e "❌ $*" >&2; exit 1; }

port_busy() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP -sTCP:LISTEN -P -n | grep -q ":${port} "
  else
    ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":${port}\$" || return 1
  fi
}

find_free_port() {
  local start="$1"
  local max_incr="${2:-20}"
  local p="$start"
  for _ in $(seq 0 "$max_incr"); do
    if ! port_busy "$p"; then
      echo "$p"; return 0
    fi
    p=$((p+1))
  done
  return 1
}

ensure_dirs() {
  mkdir -p "$LOG_DIR" "$PID_DIR"
  mkdir -p "$REPO"
}

ensure_repo_layout() {
  [[ -d "$API_DIR" ]] || die "API dir not found: $API_DIR"
  [[ -d "$UI_DIR"  ]] || die "UI dir not found:  $UI_DIR"
}

ensure_venv() {
  if [[ ! -d "$VENV" ]]; then
    msg "📦 Creating venv at $VENV"
    "$PYTHON" -m venv "$VENV" || die "Could not create venv"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  python -m pip install --upgrade pip wheel setuptools >/dev/null
  # Core deps (API + UI share venv to simplify)
  msg "⬇️  Installing Python dependencies (API + UI)…"
  pip install -q \
    fastapi uvicorn[standard] pydantic pydantic-settings \
    numpy pandas scikit-learn lightgbm shap joblib fpdf requests \
    streamlit altair python-multipart
}

write_env_hint() {
  # Optional: write a small .env for the UI (streamlit will inherit env from nohup)
  export API_URL="http://localhost:$API_PORT"
  export OLLAMA_HOST
}

start_api() {
  # Auto-pick port if busy
  if port_busy "$API_PORT"; then
    local new_port; new_port="$(find_free_port "$API_PORT" 20)" || die "No free port for API near $API_PORT"
    msg "⚠️  API port $API_PORT busy → using $new_port"
    API_PORT="$new_port"
    export API_PORT
  fi

  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  export PYTHONPATH="$REPO"
  : > "$API_LOG"
  msg "▶️  Starting API (uvicorn) on :$API_PORT"
  nohup python -m uvicorn services.api.main:app \
        --host 0.0.0.0 --port "$API_PORT" --reload \
        >>"$API_LOG" 2>&1 &

  echo $! > "$API_PID"
  sleep 1
  if ! kill -0 "$(cat "$API_PID")" 2>/dev/null; then
    die "API failed to start; see $API_LOG"
  fi
  msg "✅ API up (PID $(cat "$API_PID")) → http://localhost:$API_PORT/docs"
}

start_ui() {
  # Auto-pick port if busy
  if port_busy "$UI_PORT"; then
    local new_port; new_port="$(find_free_port "$UI_PORT" 20)" || die "No free port for UI near $UI_PORT"
    msg "⚠️  UI port $UI_PORT busy → using $new_port"
    UI_PORT="$new_port"
    export UI_PORT
  fi

  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  export API_URL="http://localhost:$API_PORT"
  : > "$UI_LOG"
  msg "▶️  Starting UI (Streamlit) on :$UI_PORT  (API_URL=$API_URL)"
  nohup env API_URL="$API_URL" streamlit run "$UI_DIR/app.py" \
        --server.port "$UI_PORT" --browser.gatherUsageStats false \
        >>"$UI_LOG" 2>&1 &

  echo $! > "$UI_PID"
  sleep 1
  if ! kill -0 "$(cat "$UI_PID")" 2>/dev/null; then
    die "UI failed to start; see $UI_LOG"
  fi
  msg "✅ UI up (PID $(cat "$UI_PID")) → http://localhost:$UI_PORT"
}

stop_one() {
  local name="$1" pidfile="$2" log="$3"
  if [[ -f "$pidfile" ]]; then
    local pid; pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      msg "⏹  Stopping $name (PID $pid)…"
      kill "$pid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pid" 2>/dev/null; then
        msg "⚠️  SIGKILL $name (PID $pid)"
        kill -9 "$pid" 2>/dev/null || true
      fi
      msg "🧹 $name stopped"
    fi
    rm -f "$pidfile"
  else
    msg "ℹ️  $name not running (no pid file)"
  fi
}

status_one() {
  local label="$1" pidfile="$2" port="$3" log="$4"
  if [[ -f "$pidfile" ]]; then
    local pid; pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "• $label: RUNNING (PID $pid, port $port)  log: $log"
      return
    fi
  fi
  echo "• $label: STOPPED (port $port)"
}

# ────────────────────────────────────────────────────────────────────────────────
# Commands

cmd="${1:-start}"

case "$cmd" in
  start)
    ensure_dirs
    ensure_repo_layout
    ensure_venv
    write_env_hint
    start_api
    start_ui
    echo
    msg "🌐 Open UI → http://localhost:$UI_PORT"
    msg "📚 API docs → http://localhost:$API_PORT/docs"
    ;;

  stop)
    stop_one "API" "$API_PID" "$API_LOG"
    stop_one "UI"  "$UI_PID"  "$UI_LOG"
    ;;

  restart)
    "$0" stop
    "$0" start
    ;;

  status)
    echo "Credit Appraisal PoC status:"
    status_one "API" "$API_PID" "$API_PORT" "$API_LOG"
    status_one "UI"  "$UI_PID"  "$UI_PORT" "$UI_LOG"
    ;;

  tail)
    ensure_dirs
    echo "Tailing logs (Ctrl+C to exit)…"
    touch "$API_LOG" "$UI_LOG"
    tail -n 50 -f "$API_LOG" "$UI_LOG"
    ;;

  *)
    echo "Usage: $0 {start|stop|status|tail|restart}"
    exit 2
    ;;
esac

