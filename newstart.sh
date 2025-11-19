#!/usr/bin/env bash
set -euo pipefail

# Improved startup script with better error handling, cleanup, and health checks

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:${OLLAMA_PORT}}"

# Environment knobs that can be overridden before running `newstart.sh`:
#  * APIPORT: API server port (default 8090)
#  * UIPORT: UI server port (default 8502)
#  * OLLAMA_PORT: Ollama server port (default 11434)
#  * OLLAMA_URL: Full Ollama URL (default http://localhost:11434)

# Track started services for cleanup
declare -a STARTED_PIDS=()
declare -a PID_FILES=()

# ---------- cleanup on exit ----------
cleanup() {
  local exit_code=$?
  color_echo yellow "🛑 Cleaning up..."
  
  # Kill log monitor first
  if [[ -f "${ROOT}/.pids/logmonitor.pid" ]]; then
    local monitor_pid
    monitor_pid="$(cat "${ROOT}/.pids/logmonitor.pid" 2>/dev/null || true)"
    if [[ -n "${monitor_pid}" ]] && kill -0 "${monitor_pid}" 2>/dev/null; then
      kill "${monitor_pid}" 2>/dev/null || true
    fi
  fi
  
  # Kill all started processes
  for pid_file in "${PID_FILES[@]}"; do
    if [[ -f "${pid_file}" ]]; then
      local pid
      pid="$(cat "${pid_file}" 2>/dev/null || true)"
      if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
        color_echo yellow "   Stopping PID ${pid}..."
        kill "${pid}" 2>/dev/null || true
        sleep 1
        kill -9 "${pid}" 2>/dev/null || true
      fi
      rm -f "${pid_file}"
    fi
  done
  
  if [[ ${exit_code} -ne 0 ]]; then
    color_echo red "❌ Script exited with error code ${exit_code}"
  fi
}

trap cleanup EXIT INT TERM

# ---------- helpers ----------
color_echo() {
  local color="$1"; shift
  local msg="$*"
  case "$color" in
    red)    echo -e "\033[1;31m${msg}\033[0m" ;;
    green)  echo -e "\033[1;32m${msg}\033[0m" ;;
    yellow) echo -e "\033[1;33m${msg}\033[0m" ;;
    blue)   echo -e "\033[1;34m${msg}\033[0m" ;;
    cyan)   echo -e "\033[1;36m${msg}\033[0m" ;;
    *)      echo "${msg}" ;;
  esac
}

log_info() {
  color_echo cyan "[INFO] $*"
}

log_success() {
  color_echo green "[SUCCESS] $*"
}

log_warn() {
  color_echo yellow "[WARN] $*"
}

log_error() {
  color_echo red "[ERROR] $*"
}

ensure_writable() {
  local d="$1"
  if [[ ! -d "$d" ]]; then
    mkdir -p "$d" || { log_error "Failed to create directory: $d"; exit 1; }
  fi
  if [[ ! -w "$d" ]]; then
    chmod u+rwx "$d" 2>/dev/null || true
    chown "$(id -u)":"$(id -g)" "$d" 2>/dev/null || true
  fi
  [[ -w "$d" ]] || { log_error "Directory '$d' is not writable"; exit 1; }
}

check_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log_error "Required command '$1' not found. Please install it first."
    return 1
  fi
  return 0
}

check_port_free() {
  local port="$1"
  if lsof -i :"${port}" >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -t -i :"${port}" 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    log_info "Freeing port ${port} (PIDs: ${pids})"
    # Try graceful kill first
    echo "${pids}" | xargs -r kill 2>/dev/null || true
    sleep 1
    # Force kill if still running
    echo "${pids}" | xargs -r kill -9 2>/dev/null || true
    sleep 1
  fi
  # Try sudo fuser as last resort
  if lsof -i :"${port}" >/dev/null 2>&1; then
    sudo -n fuser -k "${port}/tcp" 2>/dev/null || {
      log_warn "Port ${port} still in use. You may need to manually free it."
    }
  fi
}

wait_for_port() {
  local port="$1"
  local service_name="${2:-Service}"
  local attempts="${3:-30}"
  local url="${4:-http://localhost:${port}}"
  
  log_info "Waiting for ${service_name} on port ${port}..."
  for i in $(seq 1 "${attempts}"); do
    if curl -sf "${url}" >/dev/null 2>&1 || curl -sf "${url}/health" >/dev/null 2>&1 || curl -sf "${url}/api/tags" >/dev/null 2>&1; then
      log_success "${service_name} is online"
      return 0
    fi
    if [[ $((i % 5)) -eq 0 ]]; then
      log_info "   Still waiting... (${i}/${attempts})"
    fi
    sleep 1
  done
  log_warn "${service_name} did not respond within ${attempts} seconds"
  return 1
}

check_service_health() {
  local pid_file="$1"
  local service_name="$2"
  local port="${3:-}"
  
  if [[ ! -f "${pid_file}" ]]; then
    log_error "${service_name} PID file not found: ${pid_file}"
    return 1
  fi
  
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    log_error "${service_name} PID file is empty"
    return 1
  fi
  
  if ! kill -0 "${pid}" 2>/dev/null; then
    log_error "${service_name} process (PID ${pid}) is not running"
    return 1
  fi
  
  if [[ -n "${port}" ]] && ! check_port_free "${port}"; then
    log_success "${service_name} is running (PID ${pid}, port ${port})"
  else
    log_success "${service_name} is running (PID ${pid})"
  fi
  
  return 0
}

# ---------- preflight checks ----------
log_info "Running preflight checks..."

# Check required commands
for cmd in python3 curl lsof; do
  check_command "${cmd}" || exit 1
done

# Check Ollama command
if ! command -v ollama >/dev/null 2>&1; then
  log_warn "Ollama command not found. Make sure Ollama is installed and in PATH."
  log_warn "Visit https://ollama.ai for installation instructions."
else
  log_success "Ollama found: $(ollama --version 2>&1 || echo 'version unknown')"
fi

# Check required directories/files
if [[ ! -d "${ROOT}/services/api" ]]; then
  log_error "API directory not found: ${ROOT}/services/api"
  exit 1
fi

if [[ ! -d "${ROOT}/services/ui" ]]; then
  log_error "UI directory not found: ${ROOT}/services/ui"
  exit 1
fi

if [[ ! -f "${ROOT}/services/api/main.py" ]]; then
  log_error "API main.py not found"
  exit 1
fi

if [[ ! -f "${ROOT}/services/ui/app.py" ]]; then
  log_error "UI app.py not found"
  exit 1
fi

# Create required directories
mkdir -p "${LOGDIR}" \
         "${ROOT}/services/api/.runs" \
         "${ROOT}/agents/credit_appraisal/models/production" \
         "${ROOT}/.pids"

ensure_writable "${LOGDIR}"
ensure_writable "${ROOT}/.pids"

log_success "Preflight checks passed"

# ---------- setup logs ----------
TS="$(date +"%Y%m%d-%H%M%S")"
API_LOG="${LOGDIR}/api_${TS}.log"
UI_LOG="${LOGDIR}/ui_${TS}.log"
OLLAMA_LOG="${LOGDIR}/ollama_${TS}.log"
COMBINED_LOG="${LOGDIR}/live_combined_${TS}.log"
ERR_LOG="${LOGDIR}/err.log"

# Initialize log files
: > "${API_LOG}"
: > "${UI_LOG}"
: > "${OLLAMA_LOG}"
: > "${COMBINED_LOG}"
touch "${ERR_LOG}"

log_info "Log files initialized"

# ---------- free ports ----------
log_info "Freeing ports ${APIPORT}, 8501, ${UIPORT}, ${OLLAMA_PORT}..."
free_port "${APIPORT}"
free_port 8501
free_port "${UIPORT}"
free_port "${OLLAMA_PORT}"
sleep 2
log_success "Ports cleared"

# ---------- Ollama server ----------
ensure_ollama_models() {
  local required_models=("phi3" "mistral" "gemma2:2b" "gemma2:9b")
  local missing_models=()
  local available_models=()
  
  log_info "Checking for required Ollama models..."
  
  # Get list of available models
  if ! curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    log_warn "Cannot connect to Ollama API. Skipping model check."
    return 1
  fi
  
  local models_json
  models_json="$(curl -sf "${OLLAMA_URL}/api/tags" 2>/dev/null || echo "{}")"
  
  # Extract model names (with and without tags)
  while IFS= read -r model_name; do
    if [[ -n "${model_name}" ]]; then
      available_models+=("${model_name}")
      # Also add base name without tag (e.g., "phi3:latest" -> "phi3")
      if [[ "${model_name}" == *":"* ]]; then
        base_name="${model_name%%:*}"
        available_models+=("${base_name}")
      fi
    fi
  done < <(echo "${models_json}" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || true)
  
  # Check which required models are missing
  for model in "${required_models[@]}"; do
    local found=false
    for available in "${available_models[@]}"; do
      # Match exact name or base name (e.g., "phi3" matches "phi3:latest")
      if [[ "${available}" == "${model}" ]] || [[ "${available}" == "${model}:latest" ]] || [[ "${model}" == "${available%%:*}" ]]; then
        found=true
        break
      fi
    done
    if [[ "${found}" == "false" ]]; then
      missing_models+=("${model}")
    fi
  done
  
  # Show status
  if [[ ${#available_models[@]} -gt 0 ]]; then
    log_info "Available models: $(IFS=', '; echo "${available_models[*]}")"
  fi
  
  if [[ ${#missing_models[@]} -eq 0 ]]; then
    log_success "All required models are available!"
    return 0
  fi
  
  log_warn "Missing ${#missing_models[@]} required model(s): $(IFS=', '; echo "${missing_models[*]}")"
  log_info "Pulling missing models (this may take several minutes)..."
  
  # Pull missing models
  for model in "${missing_models[@]}"; do
    log_info "Pulling ${model}..."
    if ollama pull "${model}" >> "${OLLAMA_LOG}" 2>&1; then
      log_success "✅ Successfully pulled ${model}"
    else
      log_error "❌ Failed to pull ${model}. Check logs: ${OLLAMA_LOG}"
    fi
  done
  
  return 0
}

start_ollama() {
  local pid_file="${ROOT}/.pids/ollama.pid"
  PID_FILES+=("${pid_file}")
  
  # Check if Ollama command exists
  if ! command -v ollama >/dev/null 2>&1; then
    log_warn "Ollama command not found. Skipping Ollama startup."
    log_warn "Please install Ollama from https://ollama.ai"
    log_warn "After installation, run: ollama pull phi3 && ollama pull mistral && ollama pull gemma2:2b && ollama pull gemma2:9b"
    return 1
  fi
  
  # Check if Ollama is already running
  if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    log_info "Ollama is already running on ${OLLAMA_URL}"
    ensure_ollama_models
    return 0
  fi
  
  # Check if already running (by PID file)
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    log_info "Ollama already running (PID $(cat "${pid_file}"))"
    ensure_ollama_models
    return 0
  fi
  
  log_info "Starting Ollama server on port ${OLLAMA_PORT}..."
  
  # Start Ollama serve in background
  nohup ollama serve > "${OLLAMA_LOG}" 2>&1 &
  
  local ollama_pid=$!
  echo "${ollama_pid}" > "${pid_file}"
  STARTED_PIDS+=("${ollama_pid}")
  
  log_success "Ollama started (PID=${ollama_pid}) | log: ${OLLAMA_LOG}"
  
  # Wait for Ollama to be ready
  if wait_for_port "${OLLAMA_PORT}" "Ollama" 30 "${OLLAMA_URL}/api/tags"; then
    # Ensure required models are available
    ensure_ollama_models
    return 0
  else
    log_warn "Ollama may not be fully ready"
    return 1
  fi
}

start_ollama || log_warn "Ollama startup had issues (non-fatal - API/UI will still work)"

# ---------- Python venv setup ----------
log_info "Setting up Python virtual environment..."

if [[ ! -d "${VENV}" ]]; then
  log_info "Creating virtual environment..."
  python3 -m venv "${VENV}" || { log_error "Failed to create venv"; exit 1; }
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate" || { log_error "Failed to activate venv"; exit 1; }

log_info "Python: $(python -V)"
log_info "Pip: $(pip -V)"

log_info "Upgrading pip and wheel..."
python -m pip install -U pip wheel --quiet || { log_error "Failed to upgrade pip"; exit 1; }

log_info "Installing API requirements..."
if [[ -f "${ROOT}/services/api/requirements.txt" ]]; then
  pip install -q -r "${ROOT}/services/api/requirements.txt" || {
    log_warn "Some API requirements may have failed to install"
  }
else
  log_warn "API requirements.txt not found, skipping"
fi

log_info "Installing UI requirements..."
if [[ -f "${ROOT}/services/ui/requirements.txt" ]]; then
  pip install -q -r "${ROOT}/services/ui/requirements.txt" || {
    log_warn "Some UI requirements may have failed to install"
  }
else
  log_warn "UI requirements.txt not found, skipping"
fi

export PYTHONPATH="${ROOT}"
export OLLAMA_URL="${OLLAMA_URL}"
export API_URL="http://localhost:${APIPORT}"

log_success "Python environment ready"

# ---------- API server ----------
start_api() {
  local pid_file="${ROOT}/.pids/api.pid"
  PID_FILES+=("${pid_file}")
  
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    log_info "API already running (PID $(cat "${pid_file}"))"
    check_service_health "${pid_file}" "API" "${APIPORT}"
    return 0
  fi
  
  log_info "Starting API server on port ${APIPORT}..."
  nohup "${VENV}/bin/uvicorn" services.api.main:app \
      --host 0.0.0.0 --port "${APIPORT}" \
      --reload \
      --access-log \
      --log-level debug \
      > "${API_LOG}" 2>&1 &
  
  local api_pid=$!
  echo "${api_pid}" > "${pid_file}"
  STARTED_PIDS+=("${api_pid}")
  
  log_success "API started (PID=${api_pid}) | log: ${API_LOG}"
  
  # Wait for API to be ready
  if wait_for_port "${APIPORT}" "API" 30 "http://localhost:${APIPORT}/health"; then
    return 0
  else
    log_warn "API may not be fully ready"
    return 1
  fi
}

start_api || { log_error "API startup failed"; exit 1; }

# ---------- UI server ----------
start_ui() {
  local pid_file="${ROOT}/.pids/ui.pid"
  PID_FILES+=("${pid_file}")
  
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    log_info "UI already running (PID $(cat "${pid_file}"))"
    check_service_health "${pid_file}" "UI" "${UIPORT}"
    return 0
  fi
  
  log_info "Starting Streamlit UI on port ${UIPORT}..."
  cd "${ROOT}/services/ui" || { log_error "Failed to cd to UI directory"; exit 1; }
  
  nohup "${VENV}/bin/streamlit" run "app.py" \
      --server.port "${UIPORT}" \
      --server.address 0.0.0.0 \
      --server.fileWatcherType none \
      --logger.level debug \
      > "${UI_LOG}" 2>&1 &
  
  local ui_pid=$!
  echo "${ui_pid}" > "${pid_file}"
  STARTED_PIDS+=("${ui_pid}")
  
  cd "${ROOT}" || true
  
  log_success "UI started (PID=${ui_pid}) | log: ${UI_LOG}"
  
  # Wait for UI to be ready
  if wait_for_port "${UIPORT}" "UI" 30; then
    return 0
  else
    log_warn "UI may not be fully ready"
    return 1
  fi
}

start_ui || { log_error "UI startup failed"; exit 1; }

# ---------- log monitor ----------
start_log_monitor() {
  local pid_file="${ROOT}/.pids/logmonitor.pid"
  PID_FILES+=("${pid_file}")
  
  log_info "Starting live log monitor..."
  
  nohup bash -c "
    tail -n +1 -F '${API_LOG}' '${UI_LOG}' '${OLLAMA_LOG}' 2>/dev/null \
      | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), \"[STREAM]\", \$0 }' \
      | tee -a '${COMBINED_LOG}' \
      | tee -a '${ERR_LOG}' >/dev/null
  " >/dev/null 2>&1 &
  
  local monitor_pid=$!
  echo "${monitor_pid}" > "${pid_file}"
  STARTED_PIDS+=("${monitor_pid}")
  
  log_success "Live log monitor running (PID=${monitor_pid})"
}

start_log_monitor

# ---------- health checks ----------
test_all_services() {
  local all_ok=true
  local failed_services=()
  
  log_info "Running health checks for all services..."
  echo ""
  
  # Test Ollama
  log_info "Testing Ollama server..."
  if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    local models_json
    models_json="$(curl -sf "${OLLAMA_URL}/api/tags" 2>/dev/null || echo "{}")"
    local model_count
    model_count="$(echo "${models_json}" | grep -o '"name"' | wc -l || echo "0")"
    
    # Check for required models
    local required_models=("phi3" "mistral" "gemma2:2b" "gemma2:9b")
    local available_model_names
    available_model_names="$(echo "${models_json}" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 || true)"
    local missing_required=()
    
    for req_model in "${required_models[@]}"; do
      if ! echo "${available_model_names}" | grep -q "^${req_model}$"; then
        missing_required+=("${req_model}")
      fi
    done
    
    if [[ ${#missing_required[@]} -eq 0 ]]; then
      log_success "✅ Ollama: OK (${model_count} models available, all required models present)"
    else
      log_warn "⚠️  Ollama: OK but missing ${#missing_required[@]} required model(s): $(IFS=', '; echo "${missing_required[*]}")"
      log_info "   Run: ollama pull $(IFS=' && ollama pull '; echo "${missing_required[*]}")"
    fi
  else
    log_error "❌ Ollama: FAILED - Not responding on ${OLLAMA_URL}"
    all_ok=false
    failed_services+=("Ollama")
  fi
  
  # Test API
  log_info "Testing API server..."
  if curl -sf "http://localhost:${APIPORT}/health" >/dev/null 2>&1 || \
     curl -sf "http://localhost:${APIPORT}/docs" >/dev/null 2>&1; then
    log_success "✅ API: OK - Responding on port ${APIPORT}"
  else
    log_error "❌ API: FAILED - Not responding on port ${APIPORT}"
    all_ok=false
    failed_services+=("API")
  fi
  
  # Test UI
  log_info "Testing UI server..."
  if curl -sf "http://localhost:${UIPORT}" >/dev/null 2>&1; then
    log_success "✅ UI: OK - Responding on port ${UIPORT}"
  else
    log_error "❌ UI: FAILED - Not responding on port ${UIPORT}"
    all_ok=false
    failed_services+=("UI")
  fi
  
  echo ""
  if [[ "${all_ok}" == "true" ]]; then
    color_echo green "═══════════════════════════════════════════════════════════════"
    color_echo green "✅ All services are healthy and responding!"
    color_echo green "═══════════════════════════════════════════════════════════════"
    return 0
  else
    color_echo red "═══════════════════════════════════════════════════════════════"
    color_echo red "⚠️  Some services failed health checks:"
    for service in "${failed_services[@]}"; do
      color_echo red "   - ${service}"
    done
    color_echo red "═══════════════════════════════════════════════════════════════"
    log_warn "Check logs for details: ${LOGDIR}"
    return 1
  fi
}

# Run health checks
test_all_services
health_check_result=$?

# ---------- final status ----------
echo ""
echo "═══════════════════════════════════════════════════════════════"
if [[ ${health_check_result} -eq 0 ]]; then
  color_echo green "🎯 All services started successfully!"
else
  color_echo yellow "⚠️  Services started but some health checks failed"
fi
echo ""
color_echo blue "📘 Swagger API Docs:"
echo "   http://localhost:${APIPORT}/docs"
echo ""
color_echo blue "🌐 Web UI:"
echo "   http://localhost:${UIPORT}"
echo ""
color_echo blue "🤖 Ollama Server:"
echo "   ${OLLAMA_URL}"
echo "   API: ${OLLAMA_URL}/api/tags"
echo ""
color_echo blue "📂 Logs Directory: ${LOGDIR}"
echo "   - API:      ${API_LOG}"
echo "   - UI:       ${UI_LOG}"
echo "   - Ollama:   ${OLLAMA_LOG}"
echo "   - Combined: ${COMBINED_LOG}"
echo "   - Unified:  ${ERR_LOG}"
echo ""
color_echo yellow "💡 Tip: Press Ctrl+C to stop all services and exit"
echo "═══════════════════════════════════════════════════════════════"
echo ""

<<<<<<< HEAD
# ---------- live log view ----------
color_echo yellow "👁  Showing real-time logs (Ctrl+C to exit)…"
echo ""
tail -n 50 -f "${COMBINED_LOG}" 2>/dev/null || {
  log_warn "Could not tail log file. Showing last 50 lines instead:"
  tail -n 50 "${COMBINED_LOG}" 2>/dev/null || true
}
=======
# ---------- health/status probes ----------
color_echo blue "🔎 Verifying service health..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${APIPORT}/v1/health" || true)
if [[ "${API_STATUS}" == "200" ]]; then
  color_echo green "API OK (HTTP 200 from /v1/health) → http://localhost:${APIPORT}"
  color_echo blue "   ↪ Docs: http://localhost:${APIPORT}/docs"
else
  color_echo red "API check failed (status=${API_STATUS:-unreachable})"
fi

UI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${UIPORT}" || true)
if [[ "${UI_STATUS}" == "200" ]]; then
  color_echo green "UI OK (HTTP 200 at /) → http://localhost:${UIPORT}"
else
  color_echo yellow "UI check returned status=${UI_STATUS:-unreachable} (Streamlit may still be booting)"
fi

# ---------- combined monitor (include existing + follow) ----------
color_echo blue "🧩 Starting live log monitor..."
nohup bash -c "tail -n +1 -F '${API_LOG}' '${UI_LOG}' \
  | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), \"[STREAM]\", \$0 }' \
  | tee -a '${COMBINED_LOG}' \
  | tee -a '${ERR_LOG}' >/dev/null" >/dev/null 2>&1 &
LOG_MONITOR_PID=$!
echo $LOG_MONITOR_PID > "${ROOT}/.pids/logmonitor.pid"
color_echo green "✅ Live log monitor running (PID=${LOG_MONITOR_PID})"
color_echo blue "📄 Combined → ${COMBINED_LOG}"
color_echo blue "🧾 Unified  → ${ERR_LOG}"

# ---------- live view (quiet stderr) ----------
color_echo yellow "👁  Real-time ERROR view (Ctrl+C to exit)…"
tail -n 50 -f "${ERR_LOG}" 2>/dev/null || true
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
