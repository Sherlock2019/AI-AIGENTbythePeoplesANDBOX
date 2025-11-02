#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────
# cleanbackup.sh — keep only the last N backups
# Groups .ok.YYYYMMDD-HHMMSS.bak* by base path and
# keeps the newest N (by mtime), deletes older ones.
#
# Usage:
#   ./cleanbackup.sh [ROOT]
#   KEEP_COUNT=15 ./cleanbackup.sh [ROOT]   # non-interactive
# ───────────────────────────────────────────────

ROOT="${1:-$HOME/credit-appraisal-agent-poc}"

DEFAULT_KEEP=10
# Allow non-interactive override via env var
if [[ -n "${KEEP_COUNT:-}" ]]; then
  REQ_KEEP="$KEEP_COUNT"
else
  read -r -p "How many backups per file to keep? [${DEFAULT_KEEP}]: " REQ_KEEP || true
fi

# Validate keep count (positive integer), else fallback to default
if [[ -z "${REQ_KEEP:-}" ]]; then
  KEEP_COUNT="$DEFAULT_KEEP"
elif [[ "$REQ_KEEP" =~ ^[0-9]+$ ]] && (( REQ_KEEP > 0 )); then
  KEEP_COUNT="$REQ_KEEP"
else
  echo "⚠️  Invalid value '$REQ_KEEP'. Falling back to ${DEFAULT_KEEP}."
  KEEP_COUNT="$DEFAULT_KEEP"
fi

echo "🧹 Cleaning backups under: $ROOT"
echo "   (keeping $KEEP_COUNT most recent per file/directory by mtime)"
echo "──────────────────────────────────────────────"

# Find all .bak files and directories
mapfile -t BACKUPS < <(find "$ROOT" \( -type f -name "*.bak" -o -type d -name "*.bak" \) -print 2>/dev/null)

if (( ${#BACKUPS[@]} == 0 )); then
  echo "No backup files or directories found."
  exit 0
fi

TOTAL_DELETED=0

# Build unique base names by stripping the timestamp suffix:
#   .ok.YYYYMMDD-HHMMSS.bak  (and anything after .bak, e.g. nested zips)
BASES=$(printf "%s\n" "${BACKUPS[@]}" | sed -E 's/\.ok\.[0-9]{8}-[0-9]{6}\.bak.*$/.bak/' | sort -u)

while IFS= read -r base; do
  [[ -z "$base" ]] && continue
  echo "📁 Group: $base"

  # Collect all backups for this base (matching any timestamp)
  pattern="${base/.bak/}*.ok.*.bak*"
  mapfile -t GROUP < <(find "$ROOT" -path "$pattern" 2>/dev/null | sort)
  if (( ${#GROUP[@]} == 0 )); then
    echo "   ⚠️  No backups found for $base"
    continue
  fi

  # Sort by modification time (newest first)
  mapfile -t SORTED < <(ls -1t "${GROUP[@]}" 2>/dev/null)

  COUNT=${#SORTED[@]}
  if (( COUNT <= KEEP_COUNT )); then
    echo "   ✅ Nothing to delete ($COUNT ≤ $KEEP_COUNT)"
    continue
  fi

  # Determine deletions (everything after the first KEEP_COUNT)
  DELETE_LIST=("${SORTED[@]:$KEEP_COUNT}")

  for old in "${DELETE_LIST[@]}"; do
    if [[ -d "$old" ]]; then
      rm -rf -- "$old"
      echo "   🗑️  Deleted dir : $old"
    else
      rm -f -- "$old"
      echo "   🗑️  Deleted file: $old"
    fi
    ((TOTAL_DELETED++)) || true
  done

done <<< "$BASES"

echo "──────────────────────────────────────────────"
echo "✅ Cleanup complete"
echo "   • Total backups deleted: $TOTAL_DELETED"
echo "   • Kept per base:         $KEEP_COUNT"
echo "──────────────────────────────────────────────"
