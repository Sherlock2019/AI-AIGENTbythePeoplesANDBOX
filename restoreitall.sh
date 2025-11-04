#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# RAX AI SANDBOX — Restore All Agents (curated .bak only)
# - Reverses .ok.YYYYmmdd-HHMMSS.bak file copies
# - Restores model directories from their .bak directories
# - Supports: --suffix, --latest (default), --list, --dry-run, --yes
# - Prints per-bucket counts (common/credit/asset)
# ==========================================================

DRY_RUN=0
LIST_ONLY=0
ASSUME_YES=0
SUFFIX=""       # e.g. ".ok.20251103-201233.bak"

usage() {
  cat <<'EOF'
Usage: restoreitall.sh [--suffix ".ok.YYYYmmdd-HHMMSS.bak"] [--latest] [--list] [--dry-run] [--yes]

Options:
  --suffix S    Restore from this exact backup suffix (e.g. ".ok.20251103-201233.bak").
  --latest      Ignore --suffix and pick the newest .ok.*.bak per path (default).
  --list        Show what would be restored and exit.
  --dry-run     Show actions without writing.
  --yes         Do not prompt for confirmation.

Notes:
- Matches the curated file list and model dirs used by backitall.sh.
EOF
}

# ───────────────────────────────────────────────────────────────
# Parse args
# ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --suffix)  SUFFIX="${2:-}"; shift 2 ;;
    --latest)  SUFFIX=""; shift ;;
    --list)    LIST_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes)     ASSUME_YES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

# ───────────────────────────────────────────────────────────────
# Resolve repository root (env → git → script dir)
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
[[ -d "$ROOT" ]] || { echo "❌ Root not found"; exit 1; }

# ───────────────────────────────────────────────────────────────
# Curated file list (mirror of backitall.sh)
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

# Model directories (recursive)
MODEL_DIRS=(
  "$ROOT/agents/credit_appraisal/models/production"
  "$ROOT/agents/credit_appraisal/models/trained"
  "$ROOT/agents/asset_appraisal/models/production"
  "$ROOT/agents/asset_appraisal/models/trained"
)

# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────
SUDO_BIN="$(command -v sudo || true)"

categorize_path() {
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

latest_bak_for() {
  # prints the newest .bak path for a file
  local f="$1"
  # Expand safely (no match → empty)
  local arr=()
  while IFS= read -r -d '' hit; do arr+=("$hit"); done < <(find "$(dirname "$f")" -maxdepth 1 -type f -name "$(basename "$f").ok.*.bak" -print0 2>/dev/null | sort -z -r)
  [[ ${#arr[@]} -gt 0 ]] && echo "${arr[0]}" || true
}

given_suffix_for() {
  local f="$1" suf="$2"
  local target="${f}${suf}"
  [[ -f "$target" ]] && echo "$target" || true
}

copy_back() {
  local src="$1" dst="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: cp -f '$src' '$dst'"
    return 0
  fi
  local dir; dir="$(dirname "$dst")"
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

restore_dir_from_bak() {
  local dir="$1" suf="$2"
  local bak="${dir}${suf}"
  if [[ ! -d "$bak" ]]; then
    return 2
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: rsync -a --delete '$bak/' '$dir/'"
    return 0
  fi
  mkdir -p "$dir"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$bak/" "$dir/"
  else
    # Fallback to cp -r (no delete of extraneous files)
    cp -r "$bak/." "$dir/"
  fi
}

# ───────────────────────────────────────────────────────────────
# Build restoration plan
# ───────────────────────────────────────────────────────────────
declare -a PLAN_FILES_SRC PLAN_FILES_DST
declare -a PLAN_DIRS_SRC PLAN_DIRS_DST

for f in "${FILES[@]}"; do
  [[ -e "$f" || -e "$(dirname "$f")" ]] || continue
  bak=""
  if [[ -n "$SUFFIX" ]]; then
    bak="$(given_suffix_for "$f" "$SUFFIX" || true)"
  else
    bak="$(latest_bak_for "$f" || true)"
  fi
  [[ -n "$bak" ]] || continue
  PLAN_FILES_SRC+=("$bak")
  PLAN_FILES_DST+=("$f")
done

# directory backups use the same suffix rule
for d in "${MODEL_DIRS[@]}"; do
  [[ -d "$(dirname "$d")" ]] || continue
  if [[ -n "$SUFFIX" ]]; then
    [[ -d "${d}${SUFFIX}" ]] || continue
    PLAN_DIRS_SRC+=("${d}${SUFFIX}")
    PLAN_DIRS_DST+=("$d")
  else
    # pick newest dir backup
    mapfile -t CAND < <(find "$(dirname "$d")" -maxdepth 1 -type d -name "$(basename "$d").ok.*.bak" 2>/dev/null | sort -r || true)
    [[ ${#CAND[@]} -gt 0 ]] || continue
    PLAN_DIRS_SRC+=("${CAND[0]}")
    PLAN_DIRS_DST+=("$d")
  fi
done

echo "==> Planned file restores: ${#PLAN_FILES_SRC[@]}"
echo "==> Planned model dir restores: ${#PLAN_DIRS_SRC[@]}"
[[ $LIST_ONLY -eq 1 ]] && {
  echo "── Files:"
  for i in "${!PLAN_FILES_SRC[@]}"; do
    echo "  • ${PLAN_FILES_DST[$i]}  <=  ${PLAN_FILES_SRC[$i]}"
  done
  echo "── Model Dirs:"
  for i in "${!PLAN_DIRS_SRC[@]}"; do
    echo "  • ${PLAN_DIRS_DST[$i]}  <=  ${PLAN_DIRS_SRC[$i]}"
  done
  exit 0
}

# Confirm
if [[ $ASSUME_YES -ne 1 ]]; then
  read -p "Proceed with restore? [y/N] " -n 1 -r
  echo
  [[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

# ───────────────────────────────────────────────────────────────
# Execute restores + counts
# ───────────────────────────────────────────────────────────────
RESTORE_COUNT=0
RESTORE_COMMON=0
RESTORE_CREDIT=0
RESTORE_ASSET=0
SKIPPED_COUNT=0

for i in "${!PLAN_FILES_SRC[@]}"; do
  src="${PLAN_FILES_SRC[$i]}"
  dst="${PLAN_FILES_DST[$i]}"
  echo "────────────────────────────────────────────"
  echo "↩️  Restoring file:"
  echo "   $dst"
  echo "   from $src"
  if copy_back "$src" "$dst"; then
    ((RESTORE_COUNT++)) || true
    case "$(categorize_path "$dst")" in
      credit) ((RESTORE_CREDIT++)) || true ;;
      asset)  ((RESTORE_ASSET++))  || true ;;
      *)      ((RESTORE_COMMON++)) || true ;;
    esac
  else
    ((SKIPPED_COUNT++)) || true
  fi
done

DIRS_RESTORED=0
for i in "${!PLAN_DIRS_SRC[@]}"; do
  src="${PLAN_DIRS_SRC[$i]}"
  dst="${PLAN_DIRS_DST[$i]}"
  echo "────────────────────────────────────────────"
  echo "🏗️  Restoring model directory:"
  echo "   $dst"
  echo "   from $src"
  if restore_dir_from_bak "$dst" "${src#$dst}"; then
    ((DIRS_RESTORED++)) || true
  else
    echo "   ⚠️  Skipped directory restore: $dst"
    ((SKIPPED_COUNT++)) || true
  fi
done

# ───────────────────────────────────────────────────────────────
# Summary
# ───────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────────────"
echo "✅ Restore complete!"
echo "   • Files restored (total): $RESTORE_COUNT"
echo "     - Common: $RESTORE_COMMON"
echo "     - Credit agent: $RESTORE_CREDIT"
echo "     - Asset agent:  $RESTORE_ASSET"
echo "   • Model directories restored: $DIRS_RESTORED / ${#PLAN_DIRS_SRC[@]}"
echo "   • Skipped: $SKIPPED_COUNT"
if [[ -n "$SUFFIX" ]]; then
  echo "Suffix used: $SUFFIX"
else
  echo "Suffix used: (latest per file/dir)"
fi
echo "Repo root: $ROOT"
echo "────────────────────────────────────────────"
