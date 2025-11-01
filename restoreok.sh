#!/usr/bin/env bash
set -u  # keep -u only (avoid -e so one failure doesn't abort all)

ROOT="${ROOT:-$HOME/credit-appraisal-agent-poc}"

echo "🧩 Smart Restore Utility — Restore all files from a chosen backup date"
echo "Root: $ROOT"
echo "───────────────────────────────────────────────"

# Build menu (uses arrays, but only for listing)
mapfile -d '' -t all_backups < <(find "$ROOT" -type f -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak' -print0 2>/dev/null || true)
if (( ${#all_backups[@]} == 0 )); then
  echo "❌ No backup files found in $ROOT"
  exit 1
fi

mapfile -t DATES < <(
  printf '%s\0' "${all_backups[@]}" \
  | xargs -0 -n1 basename \
  | sed -nE 's/.*\.ok\.([0-9]{8}-[0-9]{6})\.bak/\1/p' \
  | sort -u
)

if (( ${#DATES[@]} == 0 )); then
  echo "⚠️  No valid backup timestamps found."
  exit 1
fi

# Count per date (display only)
declare -A DATE_COUNTS=()
for f in "${all_backups[@]}"; do
  ts="$(basename "$f" | sed -nE 's/.*\.ok\.([0-9]{8}-[0-9]{6})\.bak/\1/p' || true)"
  [[ -n "$ts" ]] && DATE_COUNTS["$ts"]=$(( ${DATE_COUNTS["$ts"]:-0} + 1 ))
done

echo "🗓️  Available backup dates:"
for (( i=0; i<${#DATES[@]}; i++ )); do
  ts="${DATES[$i]}"; cnt="${DATE_COUNTS[$ts]:-0}"
  printf "  [%2d]  %s  —  %d file(s)\n" "$((i+1))" "$ts" "$cnt"
done

echo "───────────────────────────────────────────────"
read -p "Select the backup date number to restore (or paste YYYYMMDD-HHMMSS): " -r choice

# Resolve selection
if [[ "$choice" =~ ^[0-9]+$ ]]; then
  (( choice>=1 && choice<=${#DATES[@]} )) || { echo "❌ Invalid selection."; exit 1; }
  SELECTED_DATE="${DATES[$((choice-1))]}"
elif [[ "$choice" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
  SELECTED_DATE="$choice"
else
  echo "❌ Invalid input."; exit 1
fi

# Count via find (authoritative)
EXPECT="$(find "$ROOT" -type f -name "*.ok.${SELECTED_DATE}.bak" | wc -l | tr -d ' ')"
echo
echo "✅ Restoring files from backup date: ${SELECTED_DATE}  (found: ${EXPECT} file(s))"
echo "───────────────────────────────────────────────"

RESTORED=0
FAILED=0

# Stream matches directly from find -print0 to avoid array/IFS pitfalls
while IFS= read -r -d '' bakfile; do
  # Exact suffix strip
  orig="${bakfile%.ok.${SELECTED_DATE}.bak}"

  # Ensure directory exists (ignore failure; keep going)
  mkdir -p "$(dirname "$orig")" 2>/dev/null || true

  # Pretty path
  relpath="$(realpath --relative-to="$ROOT" "$orig" 2>/dev/null || basename "$orig")"

  printf "↪️  Restoring: %s ... " "$relpath"
  if cp -f -- "$bakfile" "$orig" 2>/dev/null; then
    echo "✅ done"
    RESTORED=$((RESTORED+1))
  else
    echo "❌ failed"
    FAILED=$((FAILED+1))
  fi
done < <(find "$ROOT" -type f -name "*.ok.${SELECTED_DATE}.bak" -print0 2>/dev/null)

echo
echo "───────────────────────────────────────────────"
echo "🎯 Restore Summary:"
echo "   ✅ Restored : $RESTORED file(s)"
echo "   ❌ Failed   : $FAILED file(s)"
if [[ "$EXPECT" != "$((RESTORED+FAILED))" ]]; then
  echo "   ℹ️  Note: expected $EXPECT file(s); processed $((RESTORED+FAILED)). Some files may be unreadable or moved."
fi
echo "───────────────────────────────────────────────"
echo "✅ Done."
