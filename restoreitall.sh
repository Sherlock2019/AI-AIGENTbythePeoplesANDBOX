#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# RAX AI SANDBOX — Restore All Agents (from .bak files)
# - Restores curated .bak copies to original locations
# - Handles model directory restores
# - Provides categorization and summary
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
echo

# ───────────────────────────────────────────────────────────────
# Find all backup files and group by backup suffix
# ───────────────────────────────────────────────────────────────
echo "==> Scanning for backup files..."

declare -a ALL_BAK_FILES=()
while IFS= read -r f; do
  [[ -f "$f" ]] && ALL_BAK_FILES+=("$f")
done < <(find "$ROOT" -type f -name "*.ok.*.bak" 2>/dev/null)

declare -a ALL_BAK_DIRS=()
while IFS= read -r d; do
  [[ -d "$d" ]] && ALL_BAK_DIRS+=("$d")
done < <(find "$ROOT" -type d -name "*.ok.*.bak" 2>/dev/null)

if (( ${#ALL_BAK_FILES[@]} == 0 && ${#ALL_BAK_DIRS[@]} == 0 )); then
  echo "⚠️  No backup files found. Exiting."
  exit 1
fi

# Extract unique backup suffixes (timestamp + optional comment)
declare -A BACKUP_GROUPS=()
for bak in "${ALL_BAK_FILES[@]}" "${ALL_BAK_DIRS[@]}"; do
  if [[ "$bak" =~ \.ok\.([0-9]{8}-[0-9]{6}(\.[^./]+)?)\.bak$ ]]; then
    suffix="${BASH_REMATCH[1]}"
    BACKUP_GROUPS["$suffix"]=1
  fi
done

if (( ${#BACKUP_GROUPS[@]} == 0 )); then
  echo "⚠️  No valid backup groups found. Exiting."
  exit 1
fi

# Count files for each backup group
declare -A GROUP_COUNTS=()
for suffix in "${!BACKUP_GROUPS[@]}"; do
  count=0
  for bak in "${ALL_BAK_FILES[@]}"; do
    if [[ "$bak" =~ \.ok\.${suffix}\.bak$ ]]; then
      ((count++)) || true
    fi
  done
  for bak in "${ALL_BAK_DIRS[@]}"; do
    if [[ "$bak" =~ \.ok\.${suffix}\.bak$ ]]; then
      ((count++)) || true
    fi
  done
  GROUP_COUNTS["$suffix"]=$count
done

# Display available backup sets (sorted by count, then by date)
echo "==> Found ${#BACKUP_GROUPS[@]} backup set(s):"
declare -a SORTED_SUFFIXES=()
for suffix in "${!BACKUP_GROUPS[@]}"; do
  count="${GROUP_COUNTS["$suffix"]}"
  # Parse timestamp and comment from suffix
  if [[ "$suffix" =~ ^([0-9]{8}-[0-9]{6})(\.(.+))?$ ]]; then
    timestamp="${BASH_REMATCH[1]}"
    comment="${BASH_REMATCH[3]:-}"
    if [[ -n "$comment" ]]; then
      display_name="${timestamp} [${comment}]"
    else
      display_name="${timestamp} [no comment]"
    fi
  else
    display_name="$suffix"
  fi
  SORTED_SUFFIXES+=("${count}|${suffix}|${display_name}")
done

printf '%s\n' "${SORTED_SUFFIXES[@]}" | sort -t'|' -k1 -rn -k2 -r | tac | head -20 | while IFS='|' read -r count suffix display_name; do
  echo "   • ${display_name} (${count} files)"
done

if (( ${#BACKUP_GROUPS[@]} > 20 )); then
  remaining=$(( ${#BACKUP_GROUPS[@]} - 20 ))
  echo "   ... and ${remaining} more backup sets"
fi
echo

# ───────────────────────────────────────────────────────────────
# User selection
# ───────────────────────────────────────────────────────────────
if (( ${#BACKUP_GROUPS[@]} > 1 )); then
  echo "==> Multiple backup sets found. Please select which one to restore:"
  declare -a GROUP_LIST=()
  for suffix in "${!BACKUP_GROUPS[@]}"; do
    count="${GROUP_COUNTS["$suffix"]}"
    # Parse timestamp and comment from suffix
    if [[ "$suffix" =~ ^([0-9]{8}-[0-9]{6})(\.(.+))?$ ]]; then
      timestamp="${BASH_REMATCH[1]}"
      comment="${BASH_REMATCH[3]:-}"
      if [[ -n "$comment" ]]; then
        display_name="${timestamp} [${comment}]"
      else
        display_name="${timestamp} [no comment]"
      fi
    else
      display_name="$suffix"
    fi
    GROUP_LIST+=("${count}|${suffix}|${display_name}")
  done
  
  # Sort and display with indices (latest at bottom)
  # Sort by count (descending), then by date (ascending) so newest is at bottom
  declare -a SORTED_KEYS=()
  declare -A DISPLAY_NAMES=()
  # First sort by count (desc) and date (desc), then reverse the entire list
  while IFS='|' read -r count suffix display_name; do
    SORTED_KEYS+=("$suffix")
    DISPLAY_NAMES["$suffix"]="$display_name"
  done < <(printf '%s\n' "${GROUP_LIST[@]}" | sort -t'|' -k1 -rn -k2 -r | tac)
  
  idx=1
  for suffix in "${SORTED_KEYS[@]}"; do
    count="${GROUP_COUNTS["$suffix"]}"
    display_name="${DISPLAY_NAMES["$suffix"]}"
    echo "   [$idx] ${display_name} (${count} files)"
    ((idx++)) || true
  done
  
  total=${#BACKUP_GROUPS[@]}
  read -p "Select backup set to restore [1-${total}]: " SELECTION
  if [[ ! "$SELECTION" =~ ^[0-9]+$ ]] || (( SELECTION < 1 || SELECTION > total )); then
    echo "❌ Invalid selection. Exiting."
    exit 1
  fi
  
  SELECTED_SUFFIX="${SORTED_KEYS[$((SELECTION-1))]}"
else
  SELECTED_SUFFIX="$(printf '%s\n' "${!BACKUP_GROUPS[@]}" | head -1)"
  count="${GROUP_COUNTS["$SELECTED_SUFFIX"]}"
  # Parse timestamp and comment for display
  if [[ "$SELECTED_SUFFIX" =~ ^([0-9]{8}-[0-9]{6})(\.(.+))?$ ]]; then
    timestamp="${BASH_REMATCH[1]}"
    comment="${BASH_REMATCH[3]:-}"
    if [[ -n "$comment" ]]; then
      display_name="${timestamp} [${comment}]"
    else
      display_name="${timestamp} [no comment]"
    fi
  else
    display_name="$SELECTED_SUFFIX"
  fi
  echo "==> Found backup set: ${display_name} (${count} files)"
  read -p "Restore this backup set? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

# Display selected backup with comment
if [[ "$SELECTED_SUFFIX" =~ ^([0-9]{8}-[0-9]{6})(\.(.+))?$ ]]; then
  timestamp="${BASH_REMATCH[1]}"
  comment="${BASH_REMATCH[3]:-}"
  if [[ -n "$comment" ]]; then
    display_name="${timestamp} [${comment}]"
  else
    display_name="${timestamp} [no comment]"
  fi
else
  display_name="$SELECTED_SUFFIX"
fi
echo "==> Selected backup set: ${display_name}"
echo

# ───────────────────────────────────────────────────────────────
# Filter files and directories for selected backup
# ───────────────────────────────────────────────────────────────
declare -a TO_RESTORE_FILES=()
declare -a TO_RESTORE_DIRS=()

for bak in "${ALL_BAK_FILES[@]}"; do
  if [[ "$bak" =~ \.ok\.${SELECTED_SUFFIX}\.bak$ ]]; then
    TO_RESTORE_FILES+=("$bak")
  fi
done

for bak in "${ALL_BAK_DIRS[@]}"; do
  if [[ "$bak" =~ \.ok\.${SELECTED_SUFFIX}\.bak$ ]]; then
    TO_RESTORE_DIRS+=("$bak")
  fi
done

if (( ${#TO_RESTORE_FILES[@]} == 0 && ${#TO_RESTORE_DIRS[@]} == 0 )); then
  echo "⚠️  No files found for backup set: ${SELECTED_SUFFIX}"
  exit 1
fi

echo "==> Found ${#TO_RESTORE_FILES[@]} file(s) and ${#TO_RESTORE_DIRS[@]} directory/directories to restore"
echo

read -p "Proceed with restore? [y/N] " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────
SUDO_BIN="$(command -v sudo || true)"

restore_inplace() {
  local bak_file="$1"
  local orig_file="${bak_file%.ok.*.bak}"
  local dir
  dir="$(dirname "$orig_file")"
  
  if [[ -w "$dir" ]]; then
    cp -f "$bak_file" "$orig_file"
  else
    if [[ -n "$SUDO_BIN" ]]; then
      echo "   (no write permission — using sudo)"
      $SUDO_BIN cp -f "$bak_file" "$orig_file"
    else
      echo "   ❌ Cannot write to $dir and sudo not available — skipping."
      return 1
    fi
  fi
  return 0
}

restore_directory() {
  local bak_dir="$1"
  local orig_dir="${bak_dir%.ok.*.bak}"
  
  if [[ -d "$bak_dir" ]]; then
    echo "🗂️  Restoring directory: $bak_dir → $orig_dir"
    if [[ -w "$(dirname "$orig_dir")" ]]; then
      rm -rf "$orig_dir"
      cp -r "$bak_dir" "$orig_dir"
    else
      if [[ -n "$SUDO_BIN" ]]; then
        echo "   (no write permission — using sudo)"
        $SUDO_BIN rm -rf "$orig_dir"
        $SUDO_BIN cp -r "$bak_dir" "$orig_dir"
      else
        echo "   ❌ Cannot write and sudo not available — skipping."
        return 1
      fi
    fi
  else
    echo "   ⚠️  Backup directory not found: $bak_dir"
    return 1
  fi
  return 0
}

categorize_path() {
  # Echo one of: app | anti_fraud | credit | asset | real_estate | common
  local p="$1"
  case "$p" in
    */services/ui/app*.py) echo "app"; return ;;
    */services/ui/theme_manager.py|*/services/ui/utils/style.py) echo "app"; return ;;
    */docs/unified-theme.md) echo "app"; return ;;
    */anti-fraud-kyc-agent/*|*/services/ui/pages/anti_fraud_*.py) echo "anti_fraud"; return ;;
    */agents/credit_appraisal/*) echo "credit"; return ;;
    */agents/asset_appraisal/*)  echo "asset";  return ;;
    */agents/real_estate_evaluator/*) echo "real_estate"; return ;;
    */services/ui/pages/credit_*.py) echo "credit"; return ;;
    */services/ui/pages/*credit*.py) echo "credit"; return ;;
    */services/ui/pages/asset_*.py)  echo "asset";  return ;;
    */services/ui/pages/*asset*.py)  echo "asset";  return ;;
    */services/ui/pages/real_estate_*.py) echo "real_estate"; return ;;
    */services/ui/pages/*real_estate*.py) echo "real_estate"; return ;;
    */services/train/train_credit.py) echo "credit"; return ;;
    */services/train/train_asset.py)  echo "asset";  return ;;
  esac
  echo "common"
}

# ───────────────────────────────────────────────────────────────
# Execute restores + category counting
# ───────────────────────────────────────────────────────────────
RESTORE_COUNT=0
SKIPPED_COUNT=0
COMMON_RESTORE=0
CREDIT_RESTORE=0
ASSET_RESTORE=0
REAL_ESTATE_RESTORE=0
APP_RESTORE=0
ANTI_RESTORE=0

for bak_file in "${TO_RESTORE_FILES[@]}"; do
  orig_file="${bak_file%.ok.*.bak}"
  echo "────────────────────────────────────────────"
  echo "➡️  Processing: $bak_file"
  if restore_inplace "$bak_file"; then
    echo "   ✅ Restored → $orig_file"
    ((RESTORE_COUNT++)) || true
    case "$(categorize_path "$orig_file")" in
      app)    ((APP_RESTORE++))    || true ;;
      anti_fraud) ((ANTI_RESTORE++)) || true ;;
      credit) ((CREDIT_RESTORE++)) || true ;;
      asset)  ((ASSET_RESTORE++))  || true ;;
      real_estate) ((REAL_ESTATE_RESTORE++)) || true ;;
      *)      ((COMMON_RESTORE++)) || true ;;
    esac
  else
    echo "   ⏭️  Skipped (restore failed)"
    ((SKIPPED_COUNT++)) || true
  fi
done

# ───────────────────────────────────────────────────────────────
# Restore model directories (recursive)
# ───────────────────────────────────────────────────────────────
MODEL_DIRS_RESTORED=0
for bak_dir in "${TO_RESTORE_DIRS[@]}"; do
  if restore_directory "$bak_dir"; then
    ((MODEL_DIRS_RESTORED++)) || true
  else
    ((SKIPPED_COUNT++)) || true
  fi
done

# ───────────────────────────────────────────────────────────────
# Summary (per-bucket totals)
# ───────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────────────"
echo "✅ Restore complete!"
echo "   • Files restored (total): $RESTORE_COUNT"
echo "     - App shell / theme: $APP_RESTORE"
echo "     - Anti-fraud agent:  $ANTI_RESTORE"
echo "     - Credit agent: $CREDIT_RESTORE"
echo "     - Asset agent:  $ASSET_RESTORE"
echo "     - Real Estate agent: $REAL_ESTATE_RESTORE"
echo "     - Common:       $COMMON_RESTORE"
echo "   • Files skipped:            $SKIPPED_COUNT"
echo "   • Model directories restored: $MODEL_DIRS_RESTORED / ${#TO_RESTORE_DIRS[@]}"
echo "Backup suffix used: .ok.${SELECTED_SUFFIX}.bak"
echo "Repo root: $ROOT"
echo "────────────────────────────────────────────"
