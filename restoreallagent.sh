#!/usr/bin/env bash
# Smart Restore Utility (files + directories) — repo-root agnostic
# Restores everything stamped with .ok.YYYYMMDD-HHMMSS.bak for a chosen date.
# Non-fatal on errors; summarizes per-bucket counts.

set -u  # keep -u only; don't exit on first failure

# ── Resolve ROOT (env → git → script dir)
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

echo "🧩 Smart Restore Utility — Restore all files/dirs from a chosen backup date"
echo "Root: $ROOT"
echo "───────────────────────────────────────────────"

# ── Collect backup timestamps from files and directories
mapfile -t DATES < <(
  (find "$ROOT" -type f -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak' -print 2>/dev/null; \
   find "$ROOT" -type d -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak' -print 2>/dev/null) \
  | sed -nE 's/.*\.ok\.([0-9]{8}-[0-9]{6})\.bak$/\1/p' \
  | sort -u
)

if (( ${#DATES[@]} == 0 )); then
  echo "❌ No backup stamps found under $ROOT"
  exit 1
fi

# ── Count files per date (display only)
declare -A DATE_FILE_COUNTS=()
while IFS= read -r -d '' f; do
  ts="$(basename "$f" | sed -nE 's/.*\.ok\.([0-9]{8}-[0-9]{6})\.bak$/\1/p' || true)"
  [[ -n "$ts" ]] && DATE_FILE_COUNTS["$ts"]=$(( ${DATE_FILE_COUNTS["$ts"]:-0} + 1 ))
done < <(find "$ROOT" -type f -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak' -print0 2>/dev/null || true)

# ── Count dirs per date (display only)
declare -A DATE_DIR_COUNTS=()
while IFS= read -r -d '' d; do
  ts="$(basename "$d" | sed -nE 's/.*\.ok\.([0-9]{8}-[0-9]{6})\.bak$/\1/p' || true)"
  [[ -n "$ts" ]] && DATE_DIR_COUNTS["$ts"]=$(( ${DATE_DIR_COUNTS["$ts"]:-0} + 1 ))
done < <(find "$ROOT" -type d -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak' -print0 2>/dev/null || true)

echo "🗓️  Available backup dates:"
for (( i=0; i<${#DATES[@]}; i++ )); do
  ts="${DATES[$i]}"
  fcnt="${DATE_FILE_COUNTS[$ts]:-0}"
  dcnt="${DATE_DIR_COUNTS[$ts]:-0}"
  printf "  [%2d]  %s  —  %d file(s), %d dir(s)\n" "$((i+1))" "$ts" "$fcnt" "$dcnt"
done

echo "───────────────────────────────────────────────"
read -p "Select the backup date number to restore (or paste YYYYMMDD-HHMMSS): " -r choice

# ── Resolve selection
if [[ "$choice" =~ ^[0-9]+$ ]]; then
  (( choice>=1 && choice<=${#DATES[@]} )) || { echo "❌ Invalid selection."; exit 1; }
  SELECTED_DATE="${DATES[$((choice-1))]}"
elif [[ "$choice" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
  SELECTED_DATE="$choice"
else
  echo "❌ Invalid input."; exit 1
fi

echo
echo "⚠️  This will overwrite files/dirs using backups stamped: $SELECTED_DATE"
read -p "Proceed? [y/N] " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

SUDO_BIN="$(command -v sudo || true)"

copy_file() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")" 2>/dev/null || true
  if cp -f -- "$src" "$dst" 2>/dev/null; then
    return 0
  elif [[ -n "$SUDO_BIN" ]]; then
    $SUDO_BIN cp -f -- "$src" "$dst" 2>/dev/null
    return $?
  fi
  return 1
}

copy_dir_contents() {
  local src_dir="$1" dst_dir="$2"
  mkdir -p "$dst_dir" 2>/dev/null || true
  if cp -r "$src_dir/"* "$dst_dir/" 2>/dev/null || true; then
    return 0
  elif [[ -n "$SUDO_BIN" ]]; then
    $SUDO_BIN cp -r "$src_dir/"* "$dst_dir/" 2>/dev/null || true
    return $?
  fi
  return 1
}

categorize_path() {
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

# ── Restore files
EXPECT_FILES="$(find "$ROOT" -type f -name "*.ok.${SELECTED_DATE}.bak" | wc -l | tr -d ' ')"
echo
echo "✅ Restoring FILES for date $SELECTED_DATE  (found: $EXPECT_FILES)"
echo "───────────────────────────────────────────────"

RESTORED=0; FAILED=0
COMMON_CNT=0; CREDIT_CNT=0; ASSET_CNT=0

while IFS= read -r -d '' bakfile; do
  orig="${bakfile%.ok.${SELECTED_DATE}.bak}"
  relpath="$(realpath --relative-to="$ROOT" "$orig" 2>/dev/null || echo "$orig")"
  printf "↪️  %s ... " "$relpath"
  if copy_file "$bakfile" "$orig"; then
    echo "✅"
    ((RESTORED++)) || true
    case "$(categorize_path "$orig")" in
      credit) ((CREDIT_CNT++)) || true ;;
      asset)  ((ASSET_CNT++))  || true ;;
      *)      ((COMMON_CNT++)) || true ;;
    esac
  else
    echo "❌"
    ((FAILED++)) || true
  fi
done < <(find "$ROOT" -type f -name "*.ok.${SELECTED_DATE}.bak" -print0 2>/dev/null)

# ── Restore directories (models/etc.)
EXPECT_DIRS="$(find "$ROOT" -type d -name "*.ok.${SELECTED_DATE}.bak" | wc -l | tr -d ' ')"
echo
echo "✅ Restoring DIRECTORIES for date $SELECTED_DATE  (found: $EXPECT_DIRS)"
echo "───────────────────────────────────────────────"

DIR_OK=0; DIR_FAIL=0
while IFS= read -r -d '' bakdir; do
  origd="${bakdir%.ok.${SELECTED_DATE}.bak}"
  rel="$(realpath --relative-to="$ROOT" "$origd" 2>/dev/null || echo "$origd")"
  printf "📁 %s ... " "$rel"
  if [[ -d "$bakdir" ]]; then
    if copy_dir_contents "$bakdir" "$origd"; then
      echo "✅"
      ((DIR_OK++)) || true
    else
      echo "❌"
      ((DIR_FAIL++)) || true
    fi
  else
    echo "⚠️  missing backup dir"
    ((DIR_FAIL++)) || true
  fi
done < <(find "$ROOT" -type d -name "*.ok.${SELECTED_DATE}.bak" -print0 2>/dev/null)

echo
echo "───────────────────────────────────────────────"
echo "🎯 Restore Summary for $SELECTED_DATE"
echo "  • Files expected:  $EXPECT_FILES"
echo "    - Restored:      $RESTORED"
echo "      · Common:      $COMMON_CNT"
echo "      · Credit:      $CREDIT_CNT"
echo "      · Asset:       $ASSET_CNT"
echo "    - Failed:        $FAILED"
echo "  • Dirs expected:   $EXPECT_DIRS"
echo "    - Restored:      $DIR_OK"
echo "    - Failed:        $DIR_FAIL"
TOTAL_PROCESSED=$((RESTORED+FAILED))
if [[ "$EXPECT_FILES" != "$TOTAL_PROCESSED" ]]; then
  echo "  ℹ️ Note: expected $EXPECT_FILES file(s); processed $TOTAL_PROCESSED."
fi
echo "Repo root: $ROOT"
echo "✅ Done."
