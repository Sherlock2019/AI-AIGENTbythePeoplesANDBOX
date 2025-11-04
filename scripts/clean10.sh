#!/usr/bin/env bash
set -euo pipefail

# clean10.sh — keep only the last 10 backups per base path by modification time (mtime)
# Matches backups like: <base>.ok.YYYYMMDD-HHMMSS.bak*
# Usage:
#   ./clean10.sh [ROOT] [--dry-run]
# Examples:
#   ./clean10.sh
#   ./clean10.sh /home/dzoan/credit-appraisal-agent-poc
#   ./clean10.sh /home/dzoan/credit-appraisal-agent-poc --dry-run

ROOT="${1:-$PWD}"
DRY_RUN=0
if [[ "${2:-}" == "--dry-run" ]]; then DRY_RUN=1; fi

KEEP_LAST=10

echo "🧹 clean10.sh"
echo "Root: $ROOT"
echo "Policy: keep last $KEEP_LAST backups per base path (by mtime)"
echo "Dry-run: $([[ $DRY_RUN -eq 1 ]] && echo yes || echo no)"
echo "──────────────────────────────────────────────"

# ---- helpers ----

# Remove the backup suffix to recover the base path:
# .ok.YYYYMMDD-HHMMSS.bak (+ possible trailing chars)
strip_backup_suffix() {
  local p="$1"
  echo "${p%%.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak*}"
}

delete_path() {
  local target="$1"
  if [[ $DRY_RUN -eq 1 ]]; then
    if [[ -d "$target" ]]; then
      echo "   🧪 [dry-run] Would delete dir : $target"
    else
      echo "   🧪 [dry-run] Would delete file: $target"
    fi
    return 0
  fi

  local parent; parent="$(dirname "$target")"
  if [[ -w "$parent" ]]; then
    if [[ -d "$target" ]]; then rm -rf -- "$target"; else rm -f -- "$target"; fi
  else
    if command -v sudo >/dev/null 2>&1; then
      if [[ -d "$target" ]]; then sudo rm -rf -- "$target"; else sudo rm -f -- "$target"; fi
    else
      echo "   ❌ Cannot delete $target (no permission and sudo not available)"
      return 1
    fi
  fi
  return 0
}

mtime_epoch() {
  # prints epoch seconds (Linux/GNU stat)
  stat -c %Y -- "$1" 2>/dev/null || echo 0
}

# ---- find all backups ----
mapfile -d '' -t ALL_BACKUPS < <(find "$ROOT" \
  \( -type f -o -type d \) \
  -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak*' \
  -not -path '*/.git/*' -not -path '*/.venv/*' -not -path '*/__pycache__/*' \
  -print0 2>/dev/null)

if (( ${#ALL_BACKUPS[@]} == 0 )); then
  echo "No backup files/directories found."
  exit 0
fi

# Use a name that does NOT collide with bash's builtin GROUPS array
declare -A BACKUP_GROUPS  # base -> NUL-joined list of backups

for b in "${ALL_BACKUPS[@]}"; do
  base="$(strip_backup_suffix "$b")"
  if [[ -v BACKUP_GROUPS["$base"] ]]; then
    BACKUP_GROUPS["$base"]+=$'\0'"$b"
  else
    BACKUP_GROUPS["$base"]="$b"
  fi
done

TOTAL_GROUPS=${#BACKUP_GROUPS[@]}
TOTAL_DELETED=0

for base in "${!BACKUP_GROUPS[@]}"; do
  echo "📦 Base: $base"

  # Rehydrate the NUL-joined list into an array
  mapfile -d '' -t items < <(printf '%s\0' "${BACKUP_GROUPS[$base]}")

  # Build "epoch<TAB>path" lines, then sort by epoch desc
  tmpfile="$(mktemp)"
  for p in "${items[@]}"; do
    [[ -n "$p" ]] || continue
    printf '%s\t%s\n' "$(mtime_epoch "$p")" "$p" >> "$tmpfile"
  done

  mapfile -t sorted_lines < <(sort -t$'\t' -k1,1nr "$tmpfile")
  rm -f "$tmpfile"

  kept_paths=()
  delete_paths=()
  idx=0
  for line in "${sorted_lines[@]}"; do
    epoch="${line%%$'\t'*}"
    path="${line#*$'\t'}"
    if (( idx < KEEP_LAST )); then
      kept_paths+=("$path|$epoch")
    else
      delete_paths+=("$path")
    fi
    ((idx++))
  done

  # Delete older ones
  DELETED_THIS_BASE=0
  for old in "${delete_paths[@]}"; do
    [[ -n "$old" ]] || continue
    if delete_path "$old"; then
      ((DELETED_THIS_BASE++)) || true
      ((TOTAL_DELETED++)) || true
    fi
  done

  # Show what was kept
  if ((${#kept_paths[@]} > 0)); then
    printf "   Kept (latest %d by mtime):\n" "$KEEP_LAST"
    for kp in "${kept_paths[@]}"; do
      kpath="${kp%%|*}"
      kepoch="${kp##*|}"
      if command -v date >/dev/null 2>&1; then
        human="$(date -d @"$kepoch" '+%F %T' 2>/dev/null || echo "$kepoch")"
      else
        human="$kepoch"
      fi
      echo "     • $human — $kpath"
    done
  else
    echo "   Kept: (none)"
  fi

  echo "   Deleted items : $DELETED_THIS_BASE"
  echo
done

echo "──────────────────────────────────────────────"
echo "✅ Cleanup complete!"
echo "   • Groups processed : $TOTAL_GROUPS"
echo "   • Total deleted    : $TOTAL_DELETED"
echo "Tip: run with --dry-run first to preview deletions."
echo "──────────────────────────────────────────────"
