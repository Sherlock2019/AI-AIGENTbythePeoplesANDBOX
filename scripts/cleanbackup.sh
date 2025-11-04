#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/dzoan/credit-appraisal-agent-poc}"
KEEP_COUNT=10

echo "🧹 Cleaning old backups under: $ROOT"
echo "   (keeping $KEEP_COUNT most recent per file/directory)"
echo "──────────────────────────────────────────────"

# Find all .bak files and directories
mapfile -t BACKUPS < <(find "$ROOT" \( -type f -name "*.bak" -o -type d -name "*.bak" \) -print 2>/dev/null)

if (( ${#BACKUPS[@]} == 0 )); then
  echo "No backup files or directories found."
  exit 0
fi

TOTAL_DELETED=0

# Process by unique base names
# Extract base names (remove timestamp patterns)
BASES=$(printf "%s\n" "${BACKUPS[@]}" | sed -E 's/\.ok\.[0-9]{8}-[0-9]{6}\.bak.*$/.bak/' | sort -u)

while IFS= read -r base; do
  [[ -z "$base" ]] && continue
  echo "📁 Processing group: $base"

  # Find all backups that belong to this base
  mapfile -t GROUP < <(find "$ROOT" -path "${base/.bak/}*.ok.*.bak*" 2>/dev/null | sort)
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

  DELETE_LIST=("${SORTED[@]:$KEEP_COUNT}")

  for old in "${DELETE_LIST[@]}"; do
    if [[ -d "$old" ]]; then
      rm -rf "$old"
      echo "   🗑️  Deleted old backup directory: $old"
    else
      rm -f "$old"
      echo "   🗑️  Deleted old backup file: $old"
    fi
    ((TOTAL_DELETED++)) || true
  done

done <<< "$BASES"

echo "──────────────────────────────────────────────"
echo "✅ Cleanup complete!"
echo "   • Total backups deleted: $TOTAL_DELETED"
echo "   • Old backups retained:  $KEEP_COUNT per file/directory"
echo "──────────────────────────────────────────────"
