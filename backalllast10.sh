#!/usr/bin/env bash
set -euo pipefail

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

# Timestamped backup suffix
BACKUP_EXT=".ok.$(date +%Y%m%d-%H%M%S).bak"
KEEP_LAST=10

echo "==> Starting backup for Credit & Asset Appraisal Agent PoC"
echo "==> Backup suffix: ${BACKUP_EXT}"
echo "==> Cleanup policy after backup: keep last ${KEEP_LAST} backup dates per file/dir"
echo

# ───────────────────────────────────────────────────────────────
# Core file list (relative to $ROOT)
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
  "$ROOT/services/train/train_asset.py"        # optional/future
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
# Scan and prepare file list
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
  echo "❌ None of the listed files exist under $ROOT. Exiting."
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
    # Use rsync if available (faster/safer), else cp -r
    if command -v rsync >/dev/null 2>&1; then
      if [[ -w "$(dirname "$dest_dir")" ]]; then
        rsync -a --delete "$src_dir/" "$dest_dir/"
      else
        if [[ -n "$SUDO_BIN" ]]; then
          echo "   (no write permission — using sudo)"
          $SUDO_BIN rsync -a --delete "$src_dir/" "$dest_dir/"
        else
          echo "   ❌ Cannot write to $(dirname "$dest_dir") and sudo not available — skipping."
        fi
      fi
    else
      if [[ -w "$(dirname "$dest_dir")" ]]; then
        cp -r "$src_dir" "$dest_dir"
      else
        if [[ -n "$SUDO_BIN" ]]; then
          echo "   (no write permission — using sudo)"
          $SUDO_BIN cp -r "$src_dir" "$dest_dir"
        else
          echo "   ❌ Cannot write to $(dirname "$dest_dir") and sudo not available — skipping."
        fi
      fi
    fi
  else
    echo "   ⚠️  Directory not found: $src_dir"
  fi
}

categorize_path() {
  # Echo one of: credit | asset | common
  local p="$1"
  case "$p" in
    */agents/credit_appraisal/*) echo "credit"; return;;
    */agents/asset_appraisal/*)  echo "asset";  return;;
    */services/ui/pages/credit_*.py) echo "credit"; return;;
    */services/ui/pages/*credit*.py) echo "credit"; return;;
    */services/ui/pages/asset_*.py)  echo "asset";  return;;
    */services/ui/pages/*asset*.py)  echo "asset";  return;;
    */services/train/train_credit.py) echo "credit"; return;;
    */services/train/train_asset.py)  echo "asset";  return;;
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

TOTAL=${#EXISTING[@]}
idx=0
for file in "${EXISTING[@]}"; do
  ((idx++)) || true
  bak="${file}${BACKUP_EXT}"
  echo "────────────────────────────────────────────"
  printf "➡️  [%d/%d] Processing: %s\n" "$idx" "$TOTAL" "$file"
  if copy_inplace "$file" "$bak"; then
    echo "   ✅ Backed up → $bak"
    ((BACKUP_COUNT++)) || true
    case "$(categorize_path "$file")" in
      credit) ((CREDIT_BACKUP++)) || true;;
      asset)  ((ASSET_BACKUP++))  || true;;
      *)      ((COMMON_BACKUP++)) || true;;
    esac
  else
    echo "   ⏭️  Skipped (write failed)"
    ((SKIPPED_COUNT++)) || true
  fi
done

# ───────────────────────────────────────────────────────────────
# Backup models directories
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
# Cleanup: keep only the last $KEEP_LAST timestamps repo-wide
# ───────────────────────────────────────────────────────────────
echo
echo "🧹 Cleaning old backups (keeping last ${KEEP_LAST} timestamps per original path)..."

# Find all backup files/dirs matching *.ok.YYYYMMDD-HHMMSS.bak*
mapfile -t ALL_BACKUPS < <(find "$ROOT" \
  \( -type f -o -type d \) \
  -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak*' \
  -not -path '*/.git/*' -not -path '*/.venv/*' 2>/dev/null)

deleted_total=0

# group key: original path (without the .ok.TIMESTAMP.bak... suffix)
strip_backup_suffix() {
  local p="$1"
  echo "${p%%.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak*}"
}

# extract timestamp
ts_from_path() {
  local p="$1"
  basename -- "$p" | sed -nE 's/.*\.ok\.([0-9]{8}-[0-9]{6})\.bak.*/\1/p'
}

# Build map: base -> list of paths
declare -A GROUPS=()
for b in "${ALL_BACKUPS[@]}"; do
  base="$(strip_backup_suffix "$b")"
  GROUPS["$base"]+="$b"$'\n'
done

# Track kept timestamps (unique) for summary
declare -A KEPT_TS_SET=()

for base in "${!GROUPS[@]}"; do
  echo "• Cleaning group: $base"
  mapfile -t group_items <<< "${GROUPS[$base]}"

  # collect timestamps → map ts -> items
  declare -A TS_TO_ITEMS=()
  for p in "${group_items[@]}"; do
    [[ -n "$p" ]] || continue
    ts="$(ts_from_path "$p")"
    [[ -n "$ts" ]] || continue
    TS_TO_ITEMS["$ts"]+="$p"$'\n'
  done

  # sort timestamps desc, keep first $KEEP_LAST
  mapfile -t TS_SORTED_DESC < <(printf "%s\n" "${!TS_TO_ITEMS[@]}" | sort -r)
  # determine which to keep
  kept=("${TS_SORTED_DESC[@]:0:KEEP_LAST}")
  declare -A KEEP_HASH=()
  for ts in "${kept[@]}"; do KEEP_HASH["$ts"]=1; KEPT_TS_SET["$ts"]=1; done

  # delete items whose ts not in KEEP_HASH
  for ts in "${TS_SORTED_DESC[@]}"; do
    if [[ -z "${KEEP_HASH[$ts]:-}" ]]; then
      # delete all backups with this timestamp
      mapfile -t items <<< "${TS_TO_ITEMS[$ts]}"
      for old in "${items[@]}"; do
        [[ -n "$old" ]] || continue
        if [[ -w "$(dirname "$old")" ]]; then
          if [[ -d "$old" ]]; then rm -rf -- "$old"; else rm -f -- "$old"; fi
        else
          if [[ -n "$SUDO_BIN" ]]; then
            if [[ -d "$old" ]]; then $SUDO_BIN rm -rf -- "$old"; else $SUDO_BIN rm -f -- "$old"; fi
          else
            echo "   ❌ Cannot delete $old (no perms, no sudo)"
            continue
          fi
        fi
        ((deleted_total++)) || true
      done
    fi
  done

  printf "   Kept timestamps for this group: "
  if ((${#kept[@]} > 0)); then
    printf "%s " "${kept[@]}"
    echo
  else
    echo "(none)"
  fi
done

# Build final kept timestamp list (top 10 for display)
mapfile -t ALL_KEPT_TS < <(printf "%s\n" "${!KEPT_TS_SET[@]}" | sort -r)
KEPT_TS_PREVIEW=("${ALL_KEPT_TS[@]:0:10}")

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
echo "   • Old backups deleted:      $deleted_total"
echo "   • Kept timestamps (preview): ${KEPT_TS_PREVIEW[*]:-(none)}"
echo "Backup suffix used: ${BACKUP_EXT}"
echo "Repo root: $ROOT"
echo "────────────────────────────────────────────"
