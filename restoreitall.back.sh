#!/usr/bin/env bash
set -euo pipefail

# restoreitall.sh — interactive restoration of .bak snapshots
# Lists available backup suffixes and restores all files/directories
# that share the chosen suffix.

usage() {
  cat <<'USAGE'
Usage: ./restoreitall.sh [--root DIR]
USAGE
}

ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  done

if [[ -z "$ROOT" ]]; then
  if command -v git >/dev/null 2>&1 && GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    ROOT="$GIT_ROOT"
  else
    ROOT="$(pwd)"
  fi
fi

echo "==> Restore root: $ROOT"

mapfile -t BAK_FILES < <(find "$ROOT" -type f -name '*.bak' -print 2>/dev/null | sort)

if [[ ${#BAK_FILES[@]} -eq 0 ]]; then
  echo "No .bak files found."
  exit 0
fi

declare -A SUFFIX_COUNTS=()
declare -A SUFFIX_FILES=()

for bak in "${BAK_FILES[@]}"; do
  suffix=".bak"
  if [[ "$bak" =~ (\.dynamic\.ok\.[0-9-]+[^/]*)$ ]]; then
    suffix="${BASH_REMATCH[1]}"
  elif [[ "$bak" =~ (\.ok\.[0-9-]+[^/]*)$ ]]; then
    suffix="${BASH_REMATCH[1]}"
  fi
  SUFFIX_COUNTS["$suffix"]=$(( ${SUFFIX_COUNTS["$suffix"]:-0} + 1 ))
  SUFFIX_FILES["$suffix"]+="${bak}"$'\n'
done

echo
echo "Available backup sets:"
idx=1
declare -a SUFFIX_LIST=()
while IFS= read -r key; do
  [[ -n "$key" ]] || continue
  printf "  [%d] %s (%d files)\n" "$idx" "$key" "${SUFFIX_COUNTS[$key]}"
  SUFFIX_LIST[$idx]="$key"
  ((idx++))
done < <(printf "%s\n" "${!SUFFIX_COUNTS[@]}" | sort)

read -rp "Select backup set number (or 'a' to restore all): " choice
declare -a SELECTED_SUFFIXES=()
if [[ "$choice" =~ ^[aA]$ ]]; then
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    SELECTED_SUFFIXES+=("$key")
  done < <(printf "%s\n" "${!SUFFIX_COUNTS[@]}" | sort)
elif [[ "$choice" =~ ^[0-9]+$ ]] && [[ -n "${SUFFIX_LIST[$choice]:-}" ]]; then
  SELECTED_SUFFIXES+=("${SUFFIX_LIST[$choice]}")
else
  echo "Invalid selection."
  exit 1
fi

declare -A RESTORE_DATA=()
TOTAL_FILES=0
for suffix in "${SELECTED_SUFFIXES[@]}"; do
  IFS=$'\n' read -r -d '' -a tmp <<< "${SUFFIX_FILES[$suffix]}" || true
  if [[ ${#tmp[@]} -eq 0 ]]; then
    continue
  fi
  TOTAL_FILES=$((TOTAL_FILES + ${#tmp[@]}))
  RESTORE_DATA["$suffix"]="$(printf "%s\n" "${tmp[@]}")"
done

if [[ $TOTAL_FILES -eq 0 ]]; then
  echo "No files found for the selected backup set(s)."
  exit 0
fi

echo "About to restore ${#SELECTED_SUFFIXES[@]} backup set(s) totaling $TOTAL_FILES file(s)."
read -rp "Proceed? [y/N] " confirm
confirm="${confirm:-N}"
[[ $confirm =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

for suffix in "${SELECTED_SUFFIXES[@]}"; do
  echo
  echo "Restoring suffix: $suffix"
  IFS=$'\n' read -r -d '' -a files <<< "${RESTORE_DATA[$suffix]}" || true
  for bak in "${files[@]}"; do
    [[ -n "$bak" ]] || continue
    original="${bak%"$suffix"}"
    if [[ -z "$original" ]]; then
      echo "  ⚠️  Skipping malformed path: $bak"
      continue
    fi
    echo "  ↩︎ $original"
    cp -f "$bak" "$original"
  done
done

echo
echo "✅ Restore complete."
