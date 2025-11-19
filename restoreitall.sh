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

<<<<<<< HEAD
# Find both .bak files and directories ending with .bak
mapfile -t BAK_FILES < <(find "$ROOT" -type f -name '*.bak' -print 2>/dev/null | sort)
mapfile -t BAK_DIRS < <(find "$ROOT" -type d -name '*.bak' -print 2>/dev/null | sort)

if [[ ${#BAK_FILES[@]} -eq 0 ]] && [[ ${#BAK_DIRS[@]} -eq 0 ]]; then
  echo "No .bak files or directories found."
  exit 0
fi

# Combine files and directories for suffix detection
BAK_ITEMS=("${BAK_FILES[@]}" "${BAK_DIRS[@]}")

declare -A SUFFIX_COUNTS=()
declare -A SUFFIX_FILES=()
declare -A SUFFIX_DIRS=()

for bak in "${BAK_ITEMS[@]}"; do
=======
mapfile -t BAK_FILES < <(find "$ROOT" -type f -name '*.bak' -print 2>/dev/null | sort)

if [[ ${#BAK_FILES[@]} -eq 0 ]]; then
  echo "No .bak files found."
  exit 0
fi

declare -A SUFFIX_COUNTS=()
declare -A SUFFIX_FILES=()

for bak in "${BAK_FILES[@]}"; do
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
  suffix=".bak"
  if [[ "$bak" =~ (\.dynamic\.ok\.[0-9-]+[^/]*)$ ]]; then
    suffix="${BASH_REMATCH[1]}"
  elif [[ "$bak" =~ (\.ok\.[0-9-]+[^/]*)$ ]]; then
    suffix="${BASH_REMATCH[1]}"
  fi
  SUFFIX_COUNTS["$suffix"]=$(( ${SUFFIX_COUNTS["$suffix"]:-0} + 1 ))
<<<<<<< HEAD
  if [[ -f "$bak" ]]; then
    SUFFIX_FILES["$suffix"]+="${bak}"$'\n'
  elif [[ -d "$bak" ]]; then
    SUFFIX_DIRS["$suffix"]+="${bak}"$'\n'
  fi
=======
  SUFFIX_FILES["$suffix"]+="${bak}"$'\n'
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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
<<<<<<< HEAD
declare -A RESTORE_DIR_DATA=()
TOTAL_FILES=0
TOTAL_DIRS=0
for suffix in "${SELECTED_SUFFIXES[@]}"; do
  IFS=$'\n' read -r -d '' -a tmp_files <<< "${SUFFIX_FILES[$suffix]:-}" || true
  IFS=$'\n' read -r -d '' -a tmp_dirs <<< "${SUFFIX_DIRS[$suffix]:-}" || true
  if [[ ${#tmp_files[@]} -gt 0 ]]; then
    TOTAL_FILES=$((TOTAL_FILES + ${#tmp_files[@]}))
    RESTORE_DATA["$suffix"]="$(printf "%s\n" "${tmp_files[@]}")"
  fi
  if [[ ${#tmp_dirs[@]} -gt 0 ]]; then
    TOTAL_DIRS=$((TOTAL_DIRS + ${#tmp_dirs[@]}))
    RESTORE_DIR_DATA["$suffix"]="$(printf "%s\n" "${tmp_dirs[@]}")"
  fi
done

if [[ $TOTAL_FILES -eq 0 ]] && [[ $TOTAL_DIRS -eq 0 ]]; then
  echo "No files or directories found for the selected backup set(s)."
  exit 0
fi

echo "About to restore ${#SELECTED_SUFFIXES[@]} backup set(s):"
echo "  • Files: $TOTAL_FILES"
echo "  • Directories: $TOTAL_DIRS"
=======
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
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
read -rp "Proceed? [y/N] " confirm
confirm="${confirm:-N}"
[[ $confirm =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

for suffix in "${SELECTED_SUFFIXES[@]}"; do
  echo
  echo "Restoring suffix: $suffix"
<<<<<<< HEAD
  
  # Restore files
  if [[ -n "${RESTORE_DATA[$suffix]:-}" ]]; then
    IFS=$'\n' read -r -d '' -a files <<< "${RESTORE_DATA[$suffix]}" || true
    for bak in "${files[@]}"; do
      [[ -n "$bak" ]] || continue
      original="${bak%"$suffix"}"
      if [[ -z "$original" ]]; then
        echo "  ⚠️  Skipping malformed path: $bak"
        continue
      fi
      echo "  ↩︎ $original (file)"
      cp -f "$bak" "$original"
    done
  fi
  
  # Restore directories
  if [[ -n "${RESTORE_DIR_DATA[$suffix]:-}" ]]; then
    IFS=$'\n' read -r -d '' -a dirs <<< "${RESTORE_DIR_DATA[$suffix]}" || true
    for bak_dir in "${dirs[@]}"; do
      [[ -n "$bak_dir" ]] || continue
      original_dir="${bak_dir%"$suffix"}"
      if [[ -z "$original_dir" ]]; then
        echo "  ⚠️  Skipping malformed path: $bak_dir"
        continue
      fi
      echo "  ↩︎ $original_dir (directory)"
      # Remove existing directory if it exists, then copy backup
      [[ -d "$original_dir" ]] && rm -rf "$original_dir"
      cp -r "$bak_dir" "$original_dir"
    done
  fi
=======
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
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
done

echo
echo "✅ Restore complete."
<<<<<<< HEAD
echo "   • Files restored: $TOTAL_FILES"
echo "   • Directories restored: $TOTAL_DIRS"
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
