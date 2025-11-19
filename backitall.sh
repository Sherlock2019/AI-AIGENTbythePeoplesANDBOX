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
read -rp "Optional short comment for this backup (e.g. unifiedtheme): " COMMENT_RAW
COMMENT_CLEAN="$(echo "${COMMENT_RAW:-}" | tr ' ' '_' | tr -cd '[:alnum:]_-')"
if [[ -n "$COMMENT_CLEAN" ]]; then
  BACKUP_EXT=".ok.${TS}.${COMMENT_CLEAN}.bak"
else
  BACKUP_EXT=".ok.${TS}.bak"
fi

<<<<<<< HEAD
echo "==> Starting curated backup for All Agents (Credit, Asset, Real Estate, etc.)"
=======
echo "==> Starting curated backup for Credit & Asset Appraisal Agent"
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
echo "==> Backup suffix: ${BACKUP_EXT}"
echo

# ───────────────────────────────────────────────────────────────
# Curated file list (all paths are now relative to $ROOT)
# ───────────────────────────────────────────────────────────────
FILES=(
  "$ROOT/services/ui/app.py"
  "$ROOT/services/ui/requirements.txt"
  "$ROOT/services/ui/runwebui.sh"
  "$ROOT/services/ui/theme_manager.py"
  "$ROOT/services/ui/utils/style.py"
  "$ROOT/docs/unified-theme.md"

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

  # Credit agent (core)
  "$ROOT/agents/credit_appraisal/__init__.py"
  "$ROOT/agents/credit_appraisal/agent.py"
  "$ROOT/agents/credit_appraisal/model_utils.py"
  "$ROOT/agents/credit_appraisal/runner.py"
  "$ROOT/agents/credit_appraisal/agent.yaml"

  # Asset agent (core)
  "$ROOT/agents/asset_appraisal/__init__.py"
  "$ROOT/agents/asset_appraisal/agent.py"
  "$ROOT/agents/asset_appraisal/runner.py"
  "$ROOT/agents/asset_appraisal/agent.yaml"
<<<<<<< HEAD

  # Real Estate Evaluator agent (core)
  "$ROOT/agents/real_estate_evaluator/__init__.py"
  "$ROOT/agents/real_estate_evaluator/agent.py"
  "$ROOT/agents/real_estate_evaluator/runner.py"
  "$ROOT/agents/real_estate_evaluator/scraper.py"
  "$ROOT/agents/real_estate_evaluator/agent.yaml"
  "$ROOT/agents/real_estate_evaluator/README.md"
  "$ROOT/agents/real_estate_evaluator/sample_data.csv"
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
)

# Model directories (recursive copy)
MODEL_DIRS=(
  "$ROOT/agents/credit_appraisal/models/production"
  "$ROOT/agents/credit_appraisal/models/trained"
  "$ROOT/agents/asset_appraisal/models/production"
  "$ROOT/agents/asset_appraisal/models/trained"
)

# ───────────────────────────────────────────────────────────────
# Dynamic additions: agent files + UI pages
# ───────────────────────────────────────────────────────────────
AGENT_BASE_DIRS=("$ROOT/agents")
[[ -d "$ROOT/anti-fraud-kyc-agent" ]] && AGENT_BASE_DIRS+=("$ROOT/anti-fraud-kyc-agent")
<<<<<<< HEAD
AGENT_FILE_PATTERNS=("agent.py" "runner.py" "model_utils.py" "scraper.py" "__init__.py" "agent.yaml" "README.md" "*.yml" "*.csv")
=======
AGENT_FILE_PATTERNS=("agent.py" "runner.py" "model_utils.py" "__init__.py" "agent.yaml" "README.md" "*.yml")
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
declare -a AGENT_DYNAMIC_FILES=()
declare -A seen_dyn=()

for base in "${AGENT_BASE_DIRS[@]}"; do
  [[ -d "$base" ]] || continue
  for agent_dir in "$base"/*; do
    [[ -d "$agent_dir" ]] || continue
    for pattern in "${AGENT_FILE_PATTERNS[@]}"; do
      while IFS= read -r f; do
        [[ -f "$f" ]] || continue
        if [[ -z "${seen_dyn[$f]:-}" ]]; then
          AGENT_DYNAMIC_FILES+=("$f")
          seen_dyn["$f"]=1
        fi
      done < <(find "$agent_dir" -maxdepth 1 -type f -name "$pattern" 2>/dev/null)
    done
  done
done

PAGE_DIR="$ROOT/services/ui/pages"
if [[ -d "$PAGE_DIR" ]]; then
  while IFS= read -r page; do
    [[ -f "$page" ]] || continue
    if [[ -z "${seen_dyn[$page]:-}" ]]; then
      AGENT_DYNAMIC_FILES+=("$page")
      seen_dyn["$page"]=1
    fi
  done < <(find "$PAGE_DIR" -maxdepth 1 -type f -name '*.py' 2>/dev/null)
fi

if [[ ${#AGENT_DYNAMIC_FILES[@]} -gt 0 ]]; then
  echo "==> Discovered agent/ui files to include (${#AGENT_DYNAMIC_FILES[@]}):"
  printf "  • %s\n" "${AGENT_DYNAMIC_FILES[@]}"
  echo
  FILES+=("${AGENT_DYNAMIC_FILES[@]}")
fi

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
declare -A SEEN_FILES=()
for f in "${FILES[@]}"; do
  [[ -n "$f" ]] || continue
  if [[ -n "${SEEN_FILES[$f]:-}" ]]; then
    continue
  fi
  SEEN_FILES["$f"]=1
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
<<<<<<< HEAD
  # Echo one of: app | anti_fraud | credit | asset | real_estate | common
=======
  # Echo one of: app | anti_fraud | credit | asset | common
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
  local p="$1"
  case "$p" in
    */services/ui/app*.py) echo "app"; return ;;
    */services/ui/theme_manager.py|*/services/ui/utils/style.py) echo "app"; return ;;
    */docs/unified-theme.md) echo "app"; return ;;
    */anti-fraud-kyc-agent/*|*/services/ui/pages/anti_fraud_*.py) echo "anti_fraud"; return ;;
    */agents/credit_appraisal/*) echo "credit"; return ;;
    */agents/asset_appraisal/*)  echo "asset";  return ;;
<<<<<<< HEAD
    */agents/real_estate_evaluator/*) echo "real_estate"; return ;;
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
    */services/ui/pages/credit_*.py) echo "credit"; return ;;
    */services/ui/pages/*credit*.py) echo "credit"; return ;;
    */services/ui/pages/asset_*.py)  echo "asset";  return ;;
    */services/ui/pages/*asset*.py)  echo "asset";  return ;;
<<<<<<< HEAD
    */services/ui/pages/real_estate_*.py) echo "real_estate"; return ;;
    */services/ui/pages/*real_estate*.py) echo "real_estate"; return ;;
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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
<<<<<<< HEAD
REAL_ESTATE_BACKUP=0
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
APP_BACKUP=0
ANTI_BACKUP=0

for file in "${EXISTING[@]}"; do
  bak="${file}${BACKUP_EXT}"
  echo "────────────────────────────────────────────"
  echo "➡️  Processing: $file"
  if copy_inplace "$file" "$bak"; then
    echo "   ✅ Backed up → $bak"
    ((BACKUP_COUNT++)) || true
    case "$(categorize_path "$file")" in
      app)    ((APP_BACKUP++))    || true ;;
      anti_fraud) ((ANTI_BACKUP++)) || true ;;
      credit) ((CREDIT_BACKUP++)) || true ;;
      asset)  ((ASSET_BACKUP++))  || true ;;
<<<<<<< HEAD
      real_estate) ((REAL_ESTATE_BACKUP++)) || true ;;
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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
echo "     - App shell / theme: $APP_BACKUP"
echo "     - Anti-fraud agent:  $ANTI_BACKUP"
echo "     - Credit agent: $CREDIT_BACKUP"
echo "     - Asset agent:  $ASSET_BACKUP"
<<<<<<< HEAD
echo "     - Real Estate agent: $REAL_ESTATE_BACKUP"
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
echo "     - Common:       $COMMON_BACKUP"
echo "   • Files skipped:           $SKIPPED_COUNT"
echo "   • Model directories copied: $MODEL_DIRS_BACKED / ${#MODEL_DIRS[@]}"
echo "Backup suffix used: ${BACKUP_EXT}"
echo "Repo root: $ROOT"
echo "────────────────────────────────────────────"
