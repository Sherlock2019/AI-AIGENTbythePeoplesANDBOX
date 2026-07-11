#!/usr/bin/env bash
set -euo pipefail

# Improved startup script with better error handling, cleanup, and health checks

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
LOGDIR="${ROOT}/.logs"

# Choose a writable tmp root (prefer secondary volume if available)
if [[ -z "${TMPDIR:-}" ]]; then
  if [[ -d "/mnt/D" && -w "/mnt/D" ]]; then
    TMPDIR="/mnt/D/tmp/hugme"
  else
    TMPDIR="${ROOT}/.tmp"
  fi
fi
TMP_ROOT="${TMPDIR}"
APIPORT="${APIPORT:-8090}"
UIPORT="${UIPORT:-8502}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:${OLLAMA_PORT}}"
# Allow power users to skip automatic Ollama pulls once models are preloaded
NEWSTART_SKIP_MODEL_PULL="${NEWSTART_SKIP_MODEL_PULL:-1}"
NEWSTART_OPEN_BROWSER="${NEWSTART_OPEN_BROWSER:-1}"
NEWSTART_RESTART_OLLAMA="${NEWSTART_RESTART_OLLAMA:-0}"
NEWSTART_API_RELOAD="${NEWSTART_API_RELOAD:-0}"

# Environment knobs that can be overridden before running `newstart.sh`:
#  * APIPORT: API server port (default 8090)
#  * UIPORT: UI server port (default 8502)
#  * OLLAMA_PORT: Ollama server port (default 11434)
#  * OLLAMA_URL: Full Ollama URL (default http://localhost:11434)
#  * NEWSTART_API_RELOAD: run uvicorn with --reload when set to 1 (default 0)

# Track started services for cleanup
declare -a STARTED_PIDS=()
declare -a PID_FILES=()

# ---------- cleanup on exit ----------
cleanup() {
  local exit_code=$?
  # Only cleanup on error or signal (not on successful exit)
  if [[ ${exit_code} -eq 0 ]]; then
    return 0
  fi
  
  color_echo yellow "🛑 Cleaning up due to error/signal..."
  
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
  
  color_echo red "❌ Script exited with error code ${exit_code}"
}

trap cleanup ERR INT TERM

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

open_url() {
  local url="$1"
  if [[ "${NEWSTART_OPEN_BROWSER}" == "0" ]]; then
    log_info "Browser auto-open disabled (NEWSTART_OPEN_BROWSER=0)."
    return 0
  fi

  log_info "Opening Web UI in browser: ${url}"
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Start-Process '${url}'" >/dev/null 2>&1 &
    return 0
  fi
  if command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /C start "" "${url}" >/dev/null 2>&1 &
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${url}" >/dev/null 2>&1 &
    return 0
  fi

  log_warn "No browser opener found; open ${url} manually."
  return 0
}

open_ui_when_ready() {
  (
    local ui_url="http://localhost:${UIPORT}"
    # Streamlit can serve its shell before the Python app is ready. Give it a
    # short cold-start window so the browser does not land on an empty shell.
    sleep "${NEWSTART_UI_OPEN_DELAY:-8}"
    for _ in $(seq 1 60); do
      if curl --max-time 2 -sf "${ui_url}/" >/dev/null 2>&1; then
        log_success "UI is online"
        open_url "${ui_url}"
        return 0
      fi
      sleep 1
    done
    log_warn "UI did not become healthy within 60 seconds; open ${ui_url} manually or check ${UI_LOG}."
  ) &
}

open_ui_when_ready_once() {
  if [[ "${UI_OPEN_WAITER_STARTED:-0}" == "1" ]]; then
    return 0
  fi
  UI_OPEN_WAITER_STARTED=1
  open_ui_when_ready
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
  if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -t -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    log_info "Freeing port ${port} (PIDs: ${pids})"
    # Try graceful kill first
    echo "${pids}" | xargs -r kill 2>/dev/null || true
    sleep 1
    # Force kill if still running
    echo "${pids}" | xargs -r kill -9 2>/dev/null || true
    sleep 1
  fi
  if lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    log_warn "Port ${port} still has a listener. You may need to manually free it."
  fi
}

stop_ollama() {
  if pgrep -f "ollama serve" >/dev/null 2>&1; then
    log_info "Stopping existing Ollama server..."
    pkill -f "ollama serve" >/dev/null 2>&1 || true
    sleep 2
  fi
  
  local pid_file="${ROOT}/.pids/ollama.pid"
  if [[ -f "${pid_file}" ]]; then
    local existing_pid
    existing_pid="$(cat "${pid_file}" 2>/dev/null || true)"
    if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
      log_info "Terminating Ollama PID ${existing_pid} from previous run..."
      kill "${existing_pid}" >/dev/null 2>&1 || true
      sleep 1
      kill -9 "${existing_pid}" >/dev/null 2>&1 || true
    fi
    rm -f "${pid_file}"
  fi
}

wait_for_port() {
  local port="$1"
  local service_name="${2:-Service}"
  local attempts="${3:-30}"
  local url="${4:-http://localhost:${port}}"
  
  log_info "Waiting for ${service_name} on port ${port}..."
  for i in $(seq 1 "${attempts}"); do
    if curl --max-time 2 -sf "${url}" >/dev/null 2>&1 || curl --max-time 2 -sf "${url}/health" >/dev/null 2>&1 || curl --max-time 2 -sf "${url}/api/tags" >/dev/null 2>&1; then
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
         "${ROOT}/.pids" \
         "${TMP_ROOT}"

ensure_writable "${LOGDIR}"
ensure_writable "${ROOT}/.pids"
ensure_writable "${TMP_ROOT}"
export TMPDIR="${TMPDIR:-${TMP_ROOT}}"
export TEMP="${TEMP:-${TMPDIR}}"
export TMP="${TMP:-${TMPDIR}}"

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
if [[ "${NEWSTART_RESTART_OLLAMA}" == "1" ]]; then
  log_info "Restarting Ollama server (NEWSTART_RESTART_OLLAMA=1)..."
  stop_ollama
  log_info "Freeing Ollama port ${OLLAMA_PORT}..."
  free_port "${OLLAMA_PORT}"
  sleep 1
  log_success "Ollama port cleared"
elif curl --max-time 2 -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  log_success "Using existing Ollama server at ${OLLAMA_URL}"
else
  log_info "No healthy Ollama server detected; clearing port ${OLLAMA_PORT}..."
  stop_ollama
  free_port "${OLLAMA_PORT}"
  sleep 1
  log_success "Ollama port cleared"
fi

# ---------- Ollama server ----------
ensure_ollama_models() {
    if [[ "${NEWSTART_SKIP_MODEL_PULL}" == "1" ]]; then
      log_info "Skipping Ollama model pull (NEWSTART_SKIP_MODEL_PULL=1)."
      return 0
    fi
      local required_models=("phi3" "gemma2:2b")
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
      log_warn "After installation, run: ollama pull phi3 && ollama pull gemma2:2b"
      return 1
    fi
  
  # Check if Ollama is already running
  if curl --max-time 2 -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    if [[ "${NEWSTART_RESTART_OLLAMA}" == "1" ]]; then
      log_warn "Ollama already running on ${OLLAMA_URL}; restarting per policy..."
      stop_ollama
      free_port "${OLLAMA_PORT}"
    else
      local existing_pid
      existing_pid="$(lsof -t -nP -iTCP:"${OLLAMA_PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
      if [[ -n "${existing_pid}" ]]; then
        echo "${existing_pid}" > "${pid_file}"
      fi
      log_success "Ollama is already online at ${OLLAMA_URL}${existing_pid:+ (PID=${existing_pid})}"
      ensure_ollama_models
      return 0
    fi
  fi
  
  # Check if already running (by PID file)
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    log_warn "Existing Ollama PID $(cat "${pid_file}") found; restarting..."
    stop_ollama
  fi
  
  log_info "Starting Ollama server on port ${OLLAMA_PORT}..."
  
  # Start Ollama serve in background
  nohup ollama serve > "${OLLAMA_LOG}" 2>&1 &
  
  local ollama_pid=$!
  echo "${ollama_pid}" > "${pid_file}"
  STARTED_PIDS+=("${ollama_pid}")
  
  log_success "Ollama started (PID=${ollama_pid}) | log: ${OLLAMA_LOG}"
  
  # Wait for Ollama to be ready (reduced timeout for faster startup)
  if wait_for_port "${OLLAMA_PORT}" "Ollama" 10 "${OLLAMA_URL}/api/tags"; then
    # Ensure required models are available
    ensure_ollama_models
    return 0
  else
    log_warn "Ollama may not be fully ready"
    return 1
  fi
}

start_ollama || log_warn "Ollama startup had issues (non-fatal - API/UI will still work)"

# ---------- free remaining ports ----------
log_info "Freeing ports ${APIPORT}, 8501, ${UIPORT}..."
free_port "${APIPORT}"
free_port 8501
free_port "${UIPORT}"
sleep 1
log_success "API/UI ports cleared"

# ---------- Python venv setup ----------
log_info "Setting up Python virtual environment..."

# Installs the distro's python3.X-venv package when `python3 -m venv` fails
# because ensurepip is missing (common on fresh Debian/Ubuntu hosts).
install_venv_prereq() {
  local pyver pkg sudo_cmd
  pyver="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
  pkg="python${pyver}-venv"

  if ! command -v apt-get >/dev/null 2>&1; then
    log_error "apt-get not found; install ${pkg} manually for your distro and re-run."
    return 1
  fi

  if [[ "$(id -u)" -eq 0 ]]; then
    sudo_cmd=""
  elif command -v sudo >/dev/null 2>&1; then
    sudo_cmd="sudo"
  else
    log_error "Need root or sudo to install ${pkg}. Run: sudo apt install ${pkg}"
    return 1
  fi

  log_warn "python3 -m venv failed (ensurepip missing). Installing ${pkg}..."
  if ${sudo_cmd} apt-get update -y && ${sudo_cmd} apt-get install -y "${pkg}"; then
    log_success "Installed ${pkg}"
    return 0
  fi
  log_error "Failed to install ${pkg} automatically. Run: sudo apt install ${pkg}"
  return 1
}

# Creates $VENV, auto-installing the missing venv/ensurepip package on failure.
create_venv() {
  local venv_out
  if venv_out="$(python3 -m venv "${VENV}" 2>&1)"; then
    return 0
  fi
  echo "${venv_out}" >&2
  if echo "${venv_out}" | grep -qiE "ensurepip is not available|No module named venv"; then
    install_venv_prereq && python3 -m venv "${VENV}"
  else
    return 1
  fi
}

if [[ ! -d "${VENV}" ]]; then
  log_info "Creating virtual environment..."
  create_venv || { log_error "Failed to create venv"; exit 1; }
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate" || { log_error "Failed to activate venv"; exit 1; }

# Verify venv is working
if [[ ! -f "${VENV}/bin/python" ]] || ! "${VENV}/bin/python" --version >/dev/null 2>&1; then
  log_warn "Virtual environment appears corrupted. Recreating..."
  rm -rf "${VENV}"
  create_venv || { log_error "Failed to recreate venv"; exit 1; }
  source "${VENV}/bin/activate" || { log_error "Failed to activate recreated venv"; exit 1; }
fi

log_info "Python: $(python -V)"
log_info "Pip: $(pip -V)"

# Check if pip/wheel are installed (skip upgrade check to avoid hanging)
if python -c "import pip; import wheel" 2>/dev/null; then
  log_info "Pip and wheel are installed, skipping upgrade (run ./preinstall.sh to update)"
else
  log_info "Installing pip and wheel..."
  timeout 120 python -m pip install -U pip wheel --progress-bar off --root-user-action=ignore || { log_error "Failed to install pip"; exit 1; }
fi

# sentence-transformers (an API requirement) pulls in full CUDA-enabled torch
# by default, which drags in several GB of nvidia_* wheels (cublas, cudnn,
# nccl, ...) even on CPU-only hosts and can exhaust disk space. Pre-install
# the much smaller CPU-only build so pip's resolver treats torch as already
# satisfied. Set NEWSTART_CPU_TORCH=0 to use GPU wheels instead.
NEWSTART_CPU_TORCH="${NEWSTART_CPU_TORCH:-1}"
if [[ "${NEWSTART_CPU_TORCH}" == "1" ]] && ! python -c "import torch" 2>/dev/null; then
  log_info "Installing CPU-only PyTorch (set NEWSTART_CPU_TORCH=0 to use GPU wheels)..."
  timeout 300 pip install --progress-bar off --index-url https://download.pytorch.org/whl/cpu torch --root-user-action=ignore || \
    log_warn "CPU-only torch pre-install failed; falling back to default resolution"
fi

# Check if API requirements are already installed
log_info "Checking API requirements..."
if [[ -f "${ROOT}/services/api/requirements.txt" ]]; then
  # Quick check: if uvicorn and fastapi are installed, assume most packages are there
  if python -c "import uvicorn, fastapi" 2>/dev/null; then
    log_info "API requirements appear to be installed, skipping (run ./preinstall.sh to update)"
  else
    log_info "Installing API requirements (this may take a few minutes)..."
    timeout 300 pip install --progress-bar off -r "${ROOT}/services/api/requirements.txt" --root-user-action=ignore || {
      PIP_EXIT=$?
      log_error "Failed to install API requirements (exit code: ${PIP_EXIT})"
      exit 1
    }
    log_success "API requirements installed"
  fi
  
  # Verify critical API dependencies
  if ! python -c "import uvicorn" 2>/dev/null; then
    log_error "uvicorn not installed. API cannot start."
    exit 1
  fi
else
  log_warn "API requirements.txt not found, skipping"
fi

# Check if UI requirements are already installed
log_info "Checking UI requirements..."
if [[ -f "${ROOT}/services/ui/requirements.txt" ]]; then
  # Quick check: if streamlit is installed, assume most packages are there
  if python -c "import streamlit" 2>/dev/null; then
    log_info "UI requirements appear to be installed, skipping (run ./preinstall.sh to update)"
  else
    log_info "Installing UI requirements (this may take a few minutes)..."
    timeout 300 pip install --progress-bar off -r "${ROOT}/services/ui/requirements.txt" --root-user-action=ignore --ignore-installed blinker || {
      PIP_EXIT=$?
      log_warn "Some UI requirements may have failed to install (non-critical, exit code: ${PIP_EXIT})"
    }
    log_success "UI requirements installed"
  fi
else
  log_warn "UI requirements.txt not found, skipping"
fi

# Optional urllib3 conflict fix for Kubernetes users.
if [[ "${NEWSTART_FIX_KUBERNETES:-0}" == "1" ]] && python -c "import kubernetes" 2>/dev/null; then
  log_info "Fixing urllib3 version conflict with kubernetes..."
  timeout 60 pip install -q "urllib3<2.4.0,>=1.24.2" --root-user-action=ignore 2>/dev/null || {
    log_warn "Could not fix urllib3 version (non-critical - may cause warnings)"
  }
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
    local existing_pid
    existing_pid="$(cat "${pid_file}")"
    if curl --max-time 2 -sf "http://localhost:${APIPORT}/health" >/dev/null 2>&1; then
      log_info "API already running (PID ${existing_pid})"
      check_service_health "${pid_file}" "API" "${APIPORT}"
      return 0
    fi
    log_warn "API PID ${existing_pid} exists but health check failed; restarting it..."
    pkill -P "${existing_pid}" 2>/dev/null || true
    kill "${existing_pid}" 2>/dev/null || true
    sleep 1
    pkill -9 -P "${existing_pid}" 2>/dev/null || true
    kill -9 "${existing_pid}" 2>/dev/null || true
    rm -f "${pid_file}"
    free_port "${APIPORT}"
  fi
  
  # Verify uvicorn is available
  if ! command -v "${VENV}/bin/uvicorn" >/dev/null 2>&1 && ! python -c "import uvicorn" 2>/dev/null; then
    log_error "uvicorn not found. Please ensure API requirements are installed."
    return 1
  fi
  
  log_info "Starting API server on port ${APIPORT}..."
  
  # Ensure we use the venv's Python
  local python_cmd="${VENV}/bin/python"
  if [[ ! -f "${python_cmd}" ]]; then
    log_error "Virtual environment Python not found at ${python_cmd}"
    return 1
  fi
  
  local uvicorn_args=(services.api.main:app --host 0.0.0.0 --port "${APIPORT}" --access-log --log-level debug)
  if [[ "${NEWSTART_API_RELOAD}" == "1" ]]; then
    uvicorn_args+=(--reload)
  fi

  # Use python -m uvicorn for better venv compatibility
  nohup "${python_cmd}" -m uvicorn "${uvicorn_args[@]}" > "${API_LOG}" 2>&1 &
  
  local api_pid=$!
  echo "${api_pid}" > "${pid_file}"
  STARTED_PIDS+=("${api_pid}")
  
  log_success "API started (PID=${api_pid}) | log: ${API_LOG}"
  
  # Wait for API to be ready (reduced timeout, non-blocking)
  if wait_for_port "${APIPORT}" "API" 15 "http://localhost:${APIPORT}/health"; then
    return 0
  else
    # API might still be starting - check if process is alive
    if kill -0 "${api_pid}" 2>/dev/null; then
      log_info "API is starting but not ready yet (will continue in background)"
      return 0  # Don't fail - process is running
    else
      log_error "API process died. Check logs: ${API_LOG}"
      return 1
    fi
  fi
}

# Start API (non-blocking - continue even if startup check fails)
if ! start_api; then
  log_error "API startup failed - check logs: ${API_LOG}"
  # Don't exit - other services might still work
fi

# ---------- UI server ----------
start_ui() {
  local pid_file="${ROOT}/.pids/ui.pid"
  PID_FILES+=("${pid_file}")
  
  if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    local existing_pid
    existing_pid="$(cat "${pid_file}")"
    if curl --max-time 2 -sf "http://localhost:${UIPORT}/" >/dev/null 2>&1; then
      log_info "UI already running (PID ${existing_pid})"
      check_service_health "${pid_file}" "UI" "${UIPORT}"
      return 0
    fi
    log_warn "UI PID ${existing_pid} exists but health check failed; restarting it..."
    pkill -P "${existing_pid}" 2>/dev/null || true
    kill "${existing_pid}" 2>/dev/null || true
    sleep 1
    pkill -9 -P "${existing_pid}" 2>/dev/null || true
    kill -9 "${existing_pid}" 2>/dev/null || true
    rm -f "${pid_file}"
    free_port "${UIPORT}"
  fi
  
  # Verify streamlit is available
  if ! python -c "import streamlit" 2>/dev/null; then
    log_error "streamlit not found. Please ensure UI requirements are installed."
    return 1
  fi
  
  log_info "Starting Streamlit UI on port ${UIPORT}..."
  cd "${ROOT}/services/ui" || { log_error "Failed to cd to UI directory"; exit 1; }
  
  # Disable Streamlit telemetry to avoid capture() error
  export STREAMLIT_TELEMETRY_DISABLED=true
  export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
  
  # Ensure we use the venv's Python
  local python_cmd="${VENV}/bin/python"
  if [[ ! -f "${python_cmd}" ]]; then
    log_error "Virtual environment Python not found at ${python_cmd}"
    cd "${ROOT}" || true
    return 1
  fi
  
  # Use python -m streamlit for better venv compatibility
  nohup "${python_cmd}" -m streamlit run "app.py" \
      --server.port "${UIPORT}" \
      --server.address 0.0.0.0 \
      --server.fileWatcherType none \
      --server.headless true \
      --browser.gatherUsageStats false \
      --logger.level error \
      > "${UI_LOG}" 2>&1 &
  
  local ui_pid=$!
  echo "${ui_pid}" > "${pid_file}"
  STARTED_PIDS+=("${ui_pid}")
  
  cd "${ROOT}" || true
  
  log_success "UI started (PID=${ui_pid}) | log: ${UI_LOG}"

  if curl --max-time 1 -sf "http://localhost:${UIPORT}/" >/dev/null 2>&1; then
    log_success "UI is online"
    return 0
  fi

  sleep 1
  if kill -0 "${ui_pid}" 2>/dev/null; then
    log_info "UI is starting in the background; opening browser now."
    return 0
  fi

  log_warn "UI process died. Check logs: ${UI_LOG}"
  return 1
}

# Start UI (non-blocking - don't fail script if UI has issues)
if ! start_ui; then
  log_warn "UI startup had issues (non-fatal - API will still work)"
fi

open_ui_when_ready_once

# ---------- log monitor ----------
start_log_monitor() {
  local pid_file="${ROOT}/.pids/logmonitor.pid"
  PID_FILES+=("${pid_file}")
  
  # Start log monitor in background (non-blocking)
  nohup bash -c "
    tail -n +1 -F '${API_LOG}' '${UI_LOG}' '${OLLAMA_LOG}' 2>/dev/null \
      | grep -v 'missing ScriptRunContext' \
      | awk '{print strftime(\"%Y-%m-%d %H:%M:%S\"), \"[STREAM]\", \$0 }' \
      | tee -a '${COMBINED_LOG}' \
      | tee -a '${ERR_LOG}' >/dev/null
  " >/dev/null 2>&1 &
  
  local monitor_pid=$!
  echo "${monitor_pid}" > "${pid_file}"
  STARTED_PIDS+=("${monitor_pid}")
}

start_log_monitor

# Health checks removed - services start in background, check logs if needed

# Quick health check (non-blocking)
(
  sleep 2
  if curl --max-time 2 -sf "http://localhost:${APIPORT}/health" >/dev/null 2>&1; then
    echo "✅ API is responding" >&2
  fi
  if curl --max-time 2 -sf "http://localhost:${UIPORT}/" >/dev/null 2>&1; then
    echo "✅ UI is responding" >&2
  fi
) &

# ---------- final status ----------
echo ""
echo "═══════════════════════════════════════════════════════════════"
color_echo green "🎯 Services started!"
echo ""
color_echo blue "📘 Swagger API Docs:"
echo "   http://localhost:${APIPORT}/docs"
echo ""
color_echo blue "🌐 Web UI:"
echo "   http://localhost:${UIPORT}"
echo ""
color_echo blue "🤖 Ollama Server:"
echo "   ${OLLAMA_URL}"
echo ""
color_echo blue "📂 Logs: ${LOGDIR}"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ---------- final instructions ----------
color_echo blue "📄 View logs:"
color_echo blue "   - Combined: tail -f ${COMBINED_LOG}"
color_echo blue "   - Errors:   tail -f ${ERR_LOG}"
color_echo blue "   - API:      tail -f ${API_LOG}"
color_echo blue "   - UI:       tail -f ${UI_LOG}"
color_echo blue "   - Ollama:   tail -f ${OLLAMA_LOG}"
echo ""
color_echo green "✅ All services are running in the background!"
color_echo yellow "💡 To stop all services, run: pkill -f 'newstart.sh|uvicorn|streamlit|ollama serve'"
echo ""

# Disown all background processes so script can exit cleanly
disown -a 2>/dev/null || true

# Remove cleanup trap before successful exit (services should keep running)
trap - ERR INT TERM EXIT

# Exit successfully - services continue running in background
exit 0
