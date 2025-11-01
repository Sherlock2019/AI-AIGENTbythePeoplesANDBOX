#!/usr/bin/env bash
set -euo pipefail

# Timestamped backup suffix
BACKUP_EXT=".ok.$(date +%Y%m%d-%H%M%S).bak"

echo "==> Starting backup for Credit & Asset Appraisal Agent PoC"
echo "==> Backup suffix: ${BACKUP_EXT}"
echo

ROOT="/home/dzoan/credit-appraisal-agent-poc"

# Enable safe globbing
shopt -s nullglob globstar

# ───────────────────────────────────────────────────────────────
# Core file list (existing)
# ───────────────────────────────────────────────────────────────
FILES=(
  "$ROOT/services/ui/app.py"
  "$ROOT/services/ui/requirements.txt"
  "$ROOT/services/ui/runwebui.sh"

  "$ROOT/services/api/routers/agents.py"
  "$ROOT/services/api/routers/reports.py"
  "$ROOT/services/api/routers/settings.py"
  "$ROOT/services/api/routers/training.py"
  "$ROOT/services/api/routers/system.py"
  "$ROOT/services/api/routers/export.py"
  "$ROOT/services/api/routers/runs.py"
  "$ROOT/services/api/routers/admin.py"

  "$ROOT/services/api/main.py"
  "$ROOT/services/api/requirements.txt"
  "$ROOT/services/api/adapters/__init__.py"
  "$ROOT/services/api/adapters/llm_adapters.py"

  "$ROOT/agents/credit_appraisal/agent.py"
  "$ROOT/agents/credit_appraisal/model_utils.py"
  "$ROOT/agents/credit_appraisal/__init__.py"
  "$ROOT/agents/credit_appraisal/agent.yaml"

  "$ROOT/agent_platform/agent_sdk/__init__.py"
  "$ROOT/agent_platform/agent_sdk/sdk.py"

  "$ROOT/services/train/train_credit.py"
  "$ROOT/scripts/generate_training_dataset.py"
  "$ROOT/scripts/run_e2e.sh"
  "$ROOT/infra/run_api.sh"
  "$ROOT/Makefile"
  "$ROOT/pyproject.toml"

  "$ROOT/tests/test_api_e2e.py"
  "$ROOT/samples/credit/schema.json"
  "$ROOT/agents/credit_appraisal/sample_data/credit_sample.csv"
  "$ROOT/agents/credit_appraisal/sample_data/credit_training_sample.csv"
)

# ───────────────────────────────────────────────────────────────
# Asset Appraisal — explicit files confirmed present
# ───────────────────────────────────────────────────────────────
FILES+=(
  "$ROOT/services/ui/asset_appraisal.py"
  "$ROOT/services/api/routers/asset_appraisal.py"
)

# ───────────────────────────────────────────────────────────────
# Asset Appraisal — dynamic discovery (future-proof) with filters
# ───────────────────────────────────────────────────────────────
ASSET_PATTERNS=(
  "$ROOT/services/ui/**/asset*.py"
  "$ROOT/services/ui/**/appraisal*.py"
  "$ROOT/services/api/**/asset*.py"
  "$ROOT/services/api/**/appraisal*.py"
  "$ROOT/agents/asset_appraisal/**/*"
  "$ROOT/services/train/**/asset*.py"
  "$ROOT/scripts/**/asset*.py"
  "$ROOT/**/asset*feature*.json"
  "$ROOT/**/asset*schema*.json"
  "$ROOT/**/asset*schema*.yaml"
  "$ROOT/**/asset*schema*.yml"
  "$ROOT/**/asset*_sample*.csv"
  "$ROOT/**/asset*training*.csv"
)

# ───────────────────────────────────────────────────────────────
# Model directories (recursive backup)
# ───────────────────────────────────────────────────────────────
MODEL_DIRS=(
  "$ROOT/agents/credit_appraisal/models/production"
  "$ROOT/agents/credit_appraisal/models/trained"
  "$ROOT/agents/asset_appraisal/models/production"
  "$ROOT/agents/asset_appraisal/models/trained"
)

echo "==> Including model directories:"
for dir in "${MODEL_DIRS[@]}"; do
  echo "  • $dir"
done
echo

# ───────────────────────────────────────────────────────────────
# Expand patterns into files (dedup + strict filters)
# ───────────────────────────────────────────────────────────────
declare -A SEEN=()
declare -a EXPANDED=()

# Add explicit FILES first
for f in "${FILES[@]}"; do
  if [[ -e "$f" && -z "${SEEN[$f]:-}" ]]; then
    SEEN["$f"]=1
    EXPANDED+=("$f")
  fi
done

# Helper: returns 0 (true) if the path should be SKIPPED
should_skip() {
  local p="$1"
  [[ "$p" == *"/.git/"* ]] && return 0
  [[ "$p" == *"/.venv/"* ]] && return 0
  [[ "$p" == *"/__pycache__/"* ]] && return 0
  [[ "$p" == *.pyc ]] && return 0
  [[ "$p" == *.pyo ]] && return 0
  [[ "$p" == *.ok.*.bak ]] && return 0
  return 1
}

# Expand asset patterns with filters
for pat in "${ASSET_PATTERNS[@]}"; do
  for p in $pat; do
    if [[ -f "$p" && -z "${SEEN[$p]:-}" ]]; then
      if ! should_skip "$p"; then
        SEEN["$p"]=1
        EXPANDED+=("$p")
      fi
    fi
  done
done

# ───────────────────────────────────────────────────────────────
# Categorization helpers (per-agent rollups)
# ───────────────────────────────────────────────────────────────
# Map: file -> agent_key
declare -A CATEGORY=()

# Normalize to an agent key
categorize_file() {
  local path="$1"
  local rel="${path#$ROOT/}"

  # If under agents/<name>/
  if [[ "$rel" =~ ^agents/([^/]+)/ ]]; then
    echo "${BASH_REMATCH[1]}"
    return
  fi

  # UI/API router heuristics
  case "$rel" in
    services/ui/asset_appraisal.py) echo "asset_appraisal"; return ;;
    services/api/routers/asset_appraisal.py) echo "asset_appraisal"; return ;;
  esac

  # Credit heuristics
  case "$rel" in
    services/train/train_credit.py) echo "credit_appraisal"; return ;;
    samples/credit/*)               echo "credit_appraisal"; return ;;
    agents/credit_appraisal/*)      echo "credit_appraisal"; return ;;
  esac

  # Default bucket
  echo "_core"
}

# Build EXISTING list and categories
missing=0
declare -a EXISTING=()

echo "==> Files to consider (after expansion):"
for f in "${EXPANDED[@]}"; do
  if [[ -f "$f" ]]; then
    echo "  • $f"
    EXISTING+=("$f")
    CATEGORY["$f"]="$(categorize_file "$f")"
  else
    echo "  • $f   (skip: not found)"
    ((missing++)) || true
  fi
done

if (( ${#EXISTING[@]} == 0 )); then
  echo "❌ None of the listed files exist. Exiting."
  exit 1
fi

echo
if (( missing > 0 )); then
  echo "⚠️  $missing file(s) were not found and will be skipped."
fi
echo

read -p "Proceed with backup of all files and models? [y/N] " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

# ───────────────────────────────────────────────────────────────
# Backup helpers
# ───────────────────────────────────────────────────────────────
SUDO_BIN="$(command -v sudo || true)"

copy_inplace() {
  local src="$1"
  local dst="$2"
  local dir
  dir="$(dirname "$dst")"

  if [[ -w "$dir" ]]; then
    cp -f "$src" "$dst"
  else
    if [[ -n "$SUDO_BIN" ]]; then
      echo "   (no write permission — using sudo)"
      $SUDO_BIN cp -f "$src" "$dst"
    else
      echo "   ❌ Cannot write to $dir and sudo not available — skipping."
      return 1
    fi
  fi
  return 0
}

backup_directory() {
  local src_dir="$1"
  local dest_dir="${src_dir}${BACKUP_EXT}"
  if [[ -d "$src_dir" ]]; then
    echo "🗂️  Backing up directory: $src_dir → $dest_dir"
    cp -r "$src_dir" "$dest_dir"
  else
    echo "   ⚠️  Directory not found: $src_dir"
  fi
}

# ───────────────────────────────────────────────────────────────
# Per-agent counters
# ───────────────────────────────────────────────────────────────
declare -A AGENT_BACKED=()   # files successfully backed up
declare -A AGENT_SKIPPED=()  # files skipped due to write failure

BACKUP_COUNT=0
SKIPPED_COUNT=0

# ───────────────────────────────────────────────────────────────
# Execute file backups
# ───────────────────────────────────────────────────────────────
for file in "${EXISTING[@]}"; do
  bak="${file}${BACKUP_EXT}"
  agent="${CATEGORY[$file]}"
  echo "────────────────────────────────────────────"
  echo "➡️  Processing: $file"
  if copy_inplace "$file" "$bak"; then
    echo "   ✅ Backed up → $bak"
    ((BACKUP_COUNT++)) || true
    AGENT_BACKED["$agent"]=$(( ${AGENT_BACKED["$agent"]:-0} + 1 ))
  else
    echo "   ⏭️  Skipped (write failed)"
    ((SKIPPED_COUNT++)) || true
    AGENT_SKIPPED["$agent"]=$(( ${AGENT_SKIPPED["$agent"]:-0} + 1 ))
  fi
done

# ───────────────────────────────────────────────────────────────
# Backup models directories (recursive)
# Track per-agent model directory copies
# ───────────────────────────────────────────────────────────────
declare -A MODELS_BACKED_DIRS=()
for d in "${MODEL_DIRS[@]}"; do
  backup_directory "$d"
  # Attribute dir to agent if under agents/<name>/models/...
  rel="${d#$ROOT/}"
  if [[ "$rel" =~ ^agents/([^/]+)/models/ ]]; then
    agent="${BASH_REMATCH[1]}"
    MODELS_BACKED_DIRS["$agent"]=$(( ${MODELS_BACKED_DIRS["$agent"]:-0} + 1 ))
  else
    MODELS_BACKED_DIRS["_core"]=$(( ${MODELS_BACKED_DIRS["_core"]:-0} + 1 ))
  fi
done

# ───────────────────────────────────────────────────────────────
# Summary (with per-agent rollup)
# ───────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────────────"
echo "✅ Backup complete!"
echo "   • Files backed up : $BACKUP_COUNT"
echo "   • Files skipped   : $SKIPPED_COUNT"
echo "   • Model dirs (all): ${#MODEL_DIRS[@]}"
echo "Backup suffix used: ${BACKUP_EXT}"
echo "────────────────────────────────────────────"

# Collect unique agent keys seen
declare -A ALL_AGENTS=()
for f in "${!CATEGORY[@]}"; do
  ALL_AGENTS["${CATEGORY[$f]}"]=1
done
# Also include agents that only had model dirs
for a in "${!MODELS_BACKED_DIRS[@]}"; do
  ALL_AGENTS["$a"]=1
done

# Sort agent names
agents_sorted=($(printf "%s\n" "${!ALL_AGENTS[@]}" | sort))

echo "Per-agent breakdown:"
for a in "${agents_sorted[@]}"; do
  b="${AGENT_BACKED[$a]:-0}"
  s="${AGENT_SKIPPED[$a]:-0}"
  m="${MODELS_BACKED_DIRS[$a]:-0}"
  printf "  • %-18s  files: %4d  skipped: %3d  model_dirs: %2d\n" "$a" "$b" "$s" "$m"
done
