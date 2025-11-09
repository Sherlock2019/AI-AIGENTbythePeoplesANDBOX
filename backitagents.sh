have this cript backup all agents realted files and list a summy at the end list of files backup per agents and  count nb :dzoan@DESKTOP-KU8613L:~/AI-AIGENTbythePeoplesANDBOX/HUGKAG$ cat backitagents.sh
#!/usr/bin/env bash
set -euo pipefail

#
# Dynamic Agent Backup — inspired by backitall.sh
# Features:
#   • Currated + auto-discovered key files for each agent (UI, API, SDK, configs).
#   • Copies both production and trained model directories, including newly found agent dirs.
#   • Categorized counters & logging to highlight credit/asset/common backups.
# Improvements over the previous script:
#   1. Dynamically scans every `agents/*` (plus any standalone agent roots) for agent.py, runner.py, config, and README files.
#   2. Auto-includes all `services/ui/pages/*.py` modules tied to agent experiences.
#   3. Surfaces missing files early and warns when new agents add fresh assets that need protection.

# ───────────────────────────────────────────────────────────────
# Resolve repository root (respecting $ROOT env override)
# ───────────────────────────────────────────────────────────────
if [[ -n "${ROOT:-}" ]]; then
  ROOT="$(cd "$ROOT" && pwd)"
else
  if command -v git >/dev/null 2>&1 && GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    ROOT="$GIT_ROOT"
  else
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fi
fi

echo "==> Dynamic agent backup root: $ROOT"

TS="$(date +%Y%m%d-%H%M%S)"
read -rp "Optional short comment for this backup (spaces → underlines). Press ENTER to skip: " COMMENT_RAW
COMMENT_CLEAN="$(echo "${COMMENT_RAW:-}" | tr ' ' '_' | tr -cd '[:alnum:]_-')"
COMMENT_SEGMENT=""
if [[ -n "$COMMENT_CLEAN" ]]; then
  COMMENT_SEGMENT=".${COMMENT_CLEAN}"
fi
BACKUP_EXT=".dynamic.ok.${TS}${COMMENT_SEGMENT}.bak"

echo "Current features:"
echo "  • Curated file snapshot for UI, API, SDK, training, and agent configs."
echo "  • Model directory copies for trained/production artifacts."
echo "  • Categorized counters (common/credit/asset) for audit."
echo "Improvements in this version:"
echo "  • Scans every agent directory (agents/ + any standalone agents) for key scripts/configs."
echo "  • Collects UI page scripts dynamically and includes them in backups."
echo "  • Warns when new agents or files appear and reports missing resources early."
echo "Backup suffix: ${BACKUP_EXT}"
echo

# ───────────────────────────────────────────────────────────────
# Curated file list (carry over from backitall.sh)
# ───────────────────────────────────────────────────────────────
FILES=(
  "$ROOT/services/ui/app.py"
  "$ROOT/services/ui/requirements.txt"
  "$ROOT/services/ui/runwebui.sh"
  "$ROOT/services/ui/pages/asset_appraisal.py"
  "$ROOT/services/ui/pages/credit_appraisal.py"
  "$ROOT/services/api/main.py"
  "$ROOT/services/api/requirements.txt"
  "$ROOT/services/api/adapters/__init__.py"
  "$ROOT/services/api/adapters/llm_adapters.py"
  "$ROOT/services/api/routers/agents.py"
  "$ROOT/services/api/routers/reports.py"
  "$ROOT/services/api/routers/settings.py"
  "$ROOT/services/api/routers/training.py"
  "$ROOT/services/api/routers/system.py"
  "$ROOT/services/api/routers/export.py"
  "$ROOT/services/api/routers/runs.py"
  "$ROOT/services/api/routers/admin.py"
  "$ROOT/agent_platform/agent_sdk/__init__.py"
  "$ROOT/agent_platform/agent_sdk/sdk.py"
  "$ROOT/services/train/train_credit.py"
  "$ROOT/services/train/train_asset.py"
  "$ROOT/scripts/generate_training_dataset.py"
  "$ROOT/scripts/run_e2e.sh"
  "$ROOT/infra/run_api.sh"
  "$ROOT/Makefile"
  "$ROOT/pyproject.toml"
  "$ROOT/tests/test_api_e2e.py"
  "$ROOT/samples/credit/schema.json"
  "$ROOT/agents/credit_appraisal/sample_data/credit_sample.csv"
  "$ROOT/agents/credit_appraisal/sample_data/credit_training_sample.csv"
  "$ROOT/agents/credit_appraisal/__init__.py"
  "$ROOT/agents/credit_appraisal/agent.py"
  "$ROOT/agents/credit_appraisal/model_utils.py"
  "$ROOT/agents/credit_appraisal/runner.py"
  "$ROOT/agents/credit_appraisal/agent.yaml"
  "$ROOT/agents/asset_appraisal/__init__.py"
  "$ROOT/agents/asset_appraisal/agent.py"
  "$ROOT/agents/asset_appraisal/runner.py"
  "$ROOT/agents/asset_appraisal/agent.yaml"
)

MODEL_DIRS=(
  "$ROOT/agents/credit_appraisal/models/production"
  "$ROOT/agents/credit_appraisal/models/trained"
  "$ROOT/agents/asset_appraisal/models/production"
  "$ROOT/agents/asset_appraisal/models/trained"
)

# ───────────────────────────────────────────────────────────────
# Dynamic agent discovery
# ───────────────────────────────────────────────────────────────
AGENT_BASE_DIRS=("$ROOT/agents")
if [[ -d "$ROOT/anti-fraud-kyc-agent" ]]; then
  AGENT_BASE_DIRS+=("$ROOT/anti-fraud-kyc-agent")
fi

AGENT_FILE_PATTERNS=("agent.py" "runner.py" "model_utils.py" "__init__.py" "agent.yaml" "README.md" "README.rst" "*.yml")
declare -a AGENT_DYNAMIC_FILES=()
declare -a AGENT_MODEL_DIRS=()
declare -A seen_agent_files=()
declare -A seen_model_dirs=()

for base in "${AGENT_BASE_DIRS[@]}"; do
  [[ -d "$base" ]] || continue
  for agent_dir in "$base"/*; do
    [[ -d "$agent_dir" ]] || continue
    for pattern in "${AGENT_FILE_PATTERNS[@]}"; do
      while IFS= read -r file; do
        [[ -f "$file" ]] || continue
        if [[ -z "${seen_agent_files[$file]:-}" ]]; then
          seen_agent_files["$file"]=1
          AGENT_DYNAMIC_FILES+=("$file")
        fi
      done < <(find "$agent_dir" -maxdepth 1 -type f -name "$pattern" 2>/dev/null)
    done
    for sub in "models/production" "models/trained"; do
      candidate="$agent_dir/$sub"
      if [[ -d "$candidate" ]] && [[ -z "${seen_model_dirs[$candidate]:-}" ]]; then
        seen_model_dirs["$candidate"]=1
        AGENT_MODEL_DIRS+=("$candidate")
      fi
    done
  done
done

PAGE_DIR="$ROOT/services/ui/pages"
if [[ -d "$PAGE_DIR" ]]; then
  while IFS= read -r page; do
    [[ -f "$page" ]] || continue
    if [[ -z "${seen_agent_files[$page]:-}" ]]; then
      seen_agent_files["$page"]=1
      AGENT_DYNAMIC_FILES+=("$page")
    fi
  done < <(find "$PAGE_DIR" -maxdepth 1 -type f -name '*.py' 2>/dev/null)
fi

if [[ ${#AGENT_DYNAMIC_FILES[@]} -gt 0 ]]; then
  echo "==> Discovered dynamic agent files to snapshot (${#AGENT_DYNAMIC_FILES[@]}):"
  printf "  • %s\n" "${AGENT_DYNAMIC_FILES[@]}"
  echo
fi

if [[ ${#AGENT_MODEL_DIRS[@]} -gt 0 ]]; then
  echo "==> Additional model directories discovered:"
  printf "  • %s\n" "${AGENT_MODEL_DIRS[@]}"
  echo
  MODEL_DIRS+=("${AGENT_MODEL_DIRS[@]}")
fi

# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────
copy_inplace() {
  local src="$1"
  local dst="$2"
  local dir
  dir="$(dirname "$dst")"
  if [[ -w "$dir" ]]; then
    cp -f "$src" "$dst"
  else
    if command -v sudo >/dev/null 2>&1; then
      sudo cp -f "$src" "$dst"
    else
      echo "   ❌ Cannot write to $dir and sudo is unavailable."
      return 1
    fi
  fi
}

backup_directory() {
  local src_dir="$1"
  local dest_dir="${src_dir}${BACKUP_EXT}"
  if [[ -d "$src_dir" ]]; then
    cp -r "$src_dir" "$dest_dir"
  else
    echo "   ⚠️  Directory not found: $src_dir"
  fi
}

categorize_path() {
  local path="$1"
  case "$path" in
    */services/ui/app.py|*/services/ui/app.*|*/services/ui/app??.py)
      echo "app" ;;
    */anti-fraud-kyc-agent/*|*/services/ui/pages/anti_fraud_*.py)
      echo "anti_fraud" ;;
    */agents/credit_appraisal/*|*/services/ui/pages/*credit_*.py)
      echo "credit" ;;
    */agents/asset_appraisal/*|*/services/ui/pages/*asset_*.py)
      echo "asset" ;;
    *)
      echo "common" ;;
  esac
}

# ───────────────────────────────────────────────────────────────
# Execute file backups
# ───────────────────────────────────────────────────────────────
declare -a ALL_FILES=("${FILES[@]}" "${AGENT_DYNAMIC_FILES[@]}")
declare -a EXISTING=()
declare -A seen_all=()
declare -A PLAN_COUNTS=( ["app"]=0 ["anti_fraud"]=0 ["credit"]=0 ["asset"]=0 ["common"]=0 )
missing=0

for f in "${ALL_FILES[@]}"; do
  [[ -n "$f" ]] || continue
  if [[ -n "${seen_all[$f]:-}" ]]; then
    continue
  fi
  seen_all["$f"]=1
  if [[ -f "$f" ]]; then
    EXISTING+=("$f")
    cat_key="$(categorize_path "$f")"
    PLAN_COUNTS["$cat_key"]=$(( PLAN_COUNTS["$cat_key"] + 1 ))
  else
    ((missing++))
    echo "  ⚠️ Missing file (skipped): $f"
  fi
done

if [[ ${#EXISTING[@]} -eq 0 ]]; then
  echo "⚠️ No files available to back up. Aborting."
  exit 1
fi

echo
if (( missing > 0 )); then
  echo "⚠️ $missing curated/dynamic file(s) were not found and will be skipped."
fi
echo "Planned file counts (pre-backup):"
printf "   • App shell:    %d\n" "${PLAN_COUNTS[app]}"
printf "   • Anti-fraud:   %d\n" "${PLAN_COUNTS[anti_fraud]}"
printf "   • Credit agent: %d\n" "${PLAN_COUNTS[credit]}"
printf "   • Asset agent:  %d\n" "${PLAN_COUNTS[asset]}"
printf "   • Common:       %d\n" "${PLAN_COUNTS[common]}"
printf "\nProceed with curated + dynamic backups and model dirs? [y/N] "
read -r -n 1 CONFIRM
printf "\n"
CONFIRM="${CONFIRM:-N}"
[[ $CONFIRM =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

# ───────────────────────────────────────────────────────────────
# Process files
# ───────────────────────────────────────────────────────────────
BACKUP_COUNT=0
SKIPPED_COUNT=0
COMMON_BACKUP=0
CREDIT_BACKUP=0
ASSET_BACKUP=0
APP_BACKUP=0
ANTI_BACKUP=0
declare -a COMMON_FILES=()
declare -a CREDIT_FILES=()
declare -a ASSET_FILES=()
declare -a APP_FILES=()
declare -a ANTI_FILES=()

for file in "${EXISTING[@]}"; do
  bak="${file}${BACKUP_EXT}"
  echo "────────────────────────────────────────────"
  echo "➡️  Processing: $file"
  if copy_inplace "$file" "$bak"; then
    echo "   ✅ Backed up → $bak"
    ((BACKUP_COUNT++))
    case "$(categorize_path "$file")" in
      credit)
        ((CREDIT_BACKUP++))
        CREDIT_FILES+=("$file")
        ;;
      asset)
        ((ASSET_BACKUP++))
        ASSET_FILES+=("$file")
        ;;
      app)
        ((APP_BACKUP++))
        APP_FILES+=("$file")
        ;;
      anti_fraud)
        ((ANTI_BACKUP++))
        ANTI_FILES+=("$file")
        ;;
      *)
        ((COMMON_BACKUP++))
        COMMON_FILES+=("$file")
        ;;
    esac
  else
    echo "   ⏭️  Skipped (write failed)"
    ((SKIPPED_COUNT++))
  fi
done

# ───────────────────────────────────────────────────────────────
# Backup model directories
# ───────────────────────────────────────────────────────────────
MODEL_DIRS_BACKED=0
for dir in "${MODEL_DIRS[@]}"; do
  if [[ -d "$dir" ]]; then
    backup_directory "$dir"
    ((MODEL_DIRS_BACKED++))
  else
    echo "   ⚠️  Model dir not found: $dir"
  fi
done

# ───────────────────────────────────────────────────────────────
# Summary
# ───────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────────────"
echo "✅ Backup complete!"
echo "   • Files backed up (total): $BACKUP_COUNT"
echo "     - App shell:    $APP_BACKUP"
echo "     - Anti-fraud:   $ANTI_BACKUP"
echo "     - Credit agent: $CREDIT_BACKUP"
echo "     - Asset agent:  $ASSET_BACKUP"
echo "     - Common:       $COMMON_BACKUP"
echo "   • Files skipped: $SKIPPED_COUNT"
echo "   • Model directories copied: $MODEL_DIRS_BACKED / ${#MODEL_DIRS[@]}"
if [[ -n "$COMMENT_CLEAN" ]]; then
  echo "   • Backup comment: $COMMENT_CLEAN"
fi
echo "Backup suffix used: ${BACKUP_EXT}"
echo
echo "Backed up files by category:"
echo "  - App shell (${APP_BACKUP}):"
for appf in "${APP_FILES[@]}"; do
  echo "      • ${appf}"
done
echo "  - Anti-fraud (${ANTI_BACKUP}):"
for aff in "${ANTI_FILES[@]}"; do
  echo "      • ${aff}"
done
echo "  - Credit agent (${CREDIT_BACKUP}):"
for cpf in "${CREDIT_FILES[@]}"; do
  echo "      • ${cpf}"
done
echo "  - Asset agent (${ASSET_BACKUP}):"
for apf in "${ASSET_FILES[@]}"; do
  echo "      • ${apf}"
done
echo "  - Common (${COMMON_BACKUP}):"
for cmf in "${COMMON_FILES[@]}"; do
  echo "      • ${cmf}"
done
echo "Repo root: $ROOT"
echo "────────────────────────────────────────────"
