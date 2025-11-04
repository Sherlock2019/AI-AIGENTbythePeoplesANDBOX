#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# RAX AI SANDBOX — Backup All Agents (curated .bak only)
# - Removes repo-wide tar/zip + repobackup + retention
# - Keeps curated .bak copies + model dir copies + counts
# ==========================================================

# ───────────────────────────────────────────────────────────────
# Resolve repository root (agnostic to absolute user paths)
# Priority: $ROOT env → git top-level → script directory
# ───────────────────────────────────────────────────────────────
if [[ -n "${ROOT:-}" ]]; then
  ROOT="$(cd "$ROOT" && pwd)"
else
  if command -v git >/dev/null 2>&1; then
    if GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
      ROOT="$GIT_ROOT"
    else
      SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
      ROOT="$SCRIPT_DIR"
    fi
  else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ROOT="$SCRIPT_DIR"
  fi
fi

echo "==> Using ROOT: $ROOT"

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_EXT=".ok.${TS}.bak"

echo "==> Starting curated backup for Credit & Asset Appraisal Agent"
echo "==> Backup suffix: ${BACKUP_EXT}"
echo

# ───────────────────────────────────────────────────────────────
# Curated file list (all paths are now relative to $ROOT)
# ───────────────────────────────────────────────────────────────
FILES=(
  "$ROOT/services/ui/app.py"
  "$ROOT/services/ui/requirements.txt"
  "$ROOT/services/ui/runwebui.sh"

  # UI pages
  "$ROOT/services/ui/pages/asset_appraisal.py"
  "$ROOT/services/ui/pages/credit_appraisal.py"

  # API
  "$ROOT/services/api/main.py"
  "$ROOT/services/api/requirements.txt"
  "$ROOT/services/api/adapters/__init__.py"
  "$ROOT/services/api/adapters/llm_adapters.py"

  # Routers
  "$ROOT/services/api/routers/agents.py"
  "$ROOT/services/api/routers/reports.py"
  "$ROOT/services/api/routers/settings.py"
  "$ROOT/services/api/routers/training.py"
  "$ROOT/services/api/routers/system.py"
  "$ROOT/services/api/routers/export.py"
  "$ROOT/services/api/routers/runs.py"
  "$ROOT/services/api/routers/admin.py"

  # SDK
  "$ROOT/agent_platform/agent_sdk/__init__.py"
  "$ROOT/agent_platform/agent_sdk/sdk.py"

  # Training / scripts / infra
  "$ROOT/services/train/train_credit.py"
  "$ROOT/services/train/train_asset.py"
  "$ROOT/scripts/generate_training_dataset.py"
  "$ROOT/scripts/run_e2e.sh"
  "$ROOT/infra/run_api.sh"
  "$ROOT/Makefile"
  "$ROOT/pyproject.toml"

  # Tests / samples
  "$ROOT/tests/test_api_e2e.py"
  "$ROOT/samples/credit/schema.json"
  "$ROOT/agents/credit_appraisal/sample_data/credit_sample.csv"
  "$ROOT/agents/credit_appraisal/sample_data/credit_training_sample.csv"

  # Credit agent
  "$ROOT/agents/credit_appraisal/__init__.py"
  "$ROOT/agents/credit_appraisal/agent.py"
  "$ROOT/agents/credit_appraisal/model_utils.py"
  "$ROOT/agents/credit_appraisal/runner.py"
  "$ROOT/agents/credit_appraisal/agent.yaml"

  # Asset agent
  "$ROOT/agents/asset_appraisal/__init__.py"
  "$ROOT/agents/asset_appraisal/agent.py"
  "$ROOT/agents/asset_appraisal/runner.py"
  "$ROOT/agents/asset_appraisal/agent.yaml"
)

# Model directories (recursive copy)
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
# Scan curated list
# ───────────────────────────────────────────────────────────────
missing=0
declare -a EXISTING=()
for f in "${FILES[@]}"; do
  if [[ -f "$f" ]]; then
    echo "  • $f"
    EXISTING+=("$f")
  else
    echo "  • $f   (skip: not found)"
    ((missing++)) || true
  fi
done

if (( ${#EXISTING[@]} == 0 )); then
  echo "⚠️ None of the curated FILES exist under $ROOT. Exiting."
  exit 1
fi

echo
if (( missing > 0 )); then
  echo "⚠️  $missing curated file(s) were not found and will be skipped."
fi
echo

read -p "Proceed with curated .bak backup + model dirs? [y/N] " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

# ───────────────────────────────────────────────────────────────
# Helpers
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

categorize_path() {
  # Echo one of: credit | asset | common
  local p="$1"
  case "$p" in
    */agents/credit_appraisal/*) echo "credit"; return ;;
    */agents/asset_appraisal/*)  echo "asset";  return ;;
    */services/ui/pages/credit_*.py) echo "credit"; return ;;
    */services/ui/pages/*credit*.py) echo "credit"; return ;;
    */services/ui/pages/asset_*.py)  echo "asset";  return ;;
    */services/ui/pages/*asset*.py)  echo "asset";  return ;;
    */services/train/train_credit.py) echo "credit"; return ;;
    */services/train/train_asset.py)  echo "asset";  return ;;
  esac
  echo "common"
}

# ───────────────────────────────────────────────────────────────
# Execute file backups + category counting
# ───────────────────────────────────────────────────────────────
BACKUP_COUNT=0
SKIPPED_COUNT=0
COMMON_BACKUP=0
CREDIT_BACKUP=0
ASSET_BACKUP=0

for file in "${EXISTING[@]}"; do
  bak="${file}${BACKUP_EXT}"
  echo "────────────────────────────────────────────"
  echo "➡️  Processing: $file"
  if copy_inplace "$file" "$bak"; then
    echo "   ✅ Backed up → $bak"
    ((BACKUP_COUNT++)) || true
    case "$(categorize_path "$file")" in
      credit) ((CREDIT_BACKUP++)) || true ;;
      asset)  ((ASSET_BACKUP++))  || true ;;
      *)      ((COMMON_BACKUP++)) || true ;;
    esac
  else
    echo "   ⏭️  Skipped (write failed)"
    ((SKIPPED_COUNT++)) || true
  fi
done

# ───────────────────────────────────────────────────────────────
# Backup model directories (recursive)
# ───────────────────────────────────────────────────────────────
MODEL_DIRS_BACKED=0
for d in "${MODEL_DIRS[@]}"; do
  if [[ -d "$d" ]]; then
    backup_directory "$d"
    ((MODEL_DIRS_BACKED++)) || true
  else
    echo "   ⚠️  Model dir not found: $d"
  fi
done

# ───────────────────────────────────────────────────────────────
# Summary (per-bucket totals)
# ───────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────────────"
echo "✅ Backup complete!"
echo "   • Files backed up (total): $BACKUP_COUNT"
echo "     - Common: $COMMON_BACKUP"
echo "     - Credit agent: $CREDIT_BACKUP"
echo "     - Asset agent:  $ASSET_BACKUP"
echo "   • Files skipped:           $SKIPPED_COUNT"
echo "   • Model directories copied: $MODEL_DIRS_BACKED / ${#MODEL_DIRS[@]}"
echo "Backup suffix used: ${BACKUP_EXT}"
echo "Repo root: $ROOT"
echo "────────────────────────────────────────────"
