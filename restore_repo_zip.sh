#!/usr/bin/env bash
set -euo pipefail

# ============================
# Simple Repo ZIP Restore
# ============================

SNAP_ROOT="${HOME}/repobackup"
USE_LATEST=0
SNAPSHOT_NAME=""     # e.g., REPO_YYYYmmdd-HHMMSS
DEST=""              # default: ${PWD}/<SNAPSHOT_NAME>
DRY_RUN=0
OVERWRITE=0
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --latest) USE_LATEST=1; shift ;;
    --snapshot) SNAPSHOT_NAME="${2:?}"; shift 2 ;;
    --to) DEST="${2:?}"; shift 2 ;;
    --dry-run|-n) DRY_RUN=1; shift ;;
    --overwrite) OVERWRITE=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --list)
      echo "Available zips under ${SNAP_ROOT}:"
      ls -1t "${SNAP_ROOT}"/*.zip 2>/dev/null || true
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      echo "Usage: $0 [--latest | --snapshot <name>] [--to <dest>] [--overwrite] [--dry-run] [--yes] [--list]"
      exit 2
      ;;
  esac
done

# Resolve repo name to filter latest intelligently
if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
  ROOT="$(git rev-parse --show-toplevel)"
else
  ROOT="$(pwd)"
fi
REPO_NAME="$(basename "$ROOT")"

# Pick ZIP
ZIP_PATH=""
if (( USE_LATEST )); then
  ZIP_PATH="$(ls -1t "${SNAP_ROOT}/${REPO_NAME}"_*.zip 2>/dev/null | head -n 1 || true)"
  if [[ -z "$ZIP_PATH" ]]; then
    echo "❌ No zip snapshots for '${REPO_NAME}' in ${SNAP_ROOT}"
    exit 1
  fi
else
  if [[ -z "$SNAPSHOT_NAME" ]]; then
    echo "❌ Provide --latest or --snapshot <name>"
    exit 2
  fi
  # Allow user to pass either bare name or full path to zip
  if [[ -f "$SNAPSHOT_NAME" ]]; then
    ZIP_PATH="$SNAPSHOT_NAME"
  else
    # assume name without extension (created by backup script)
    CAND="${SNAP_ROOT}/${SNAPSHOT_NAME}.zip"
    if [[ -f "$CAND" ]]; then
      ZIP_PATH="$CAND"
    else
      echo "❌ Zip not found: $CAND"
      exit 1
    fi
  fi
fi

BASENAME="$(basename "$ZIP_PATH" .zip)"
DEFAULT_DEST="${PWD}/${BASENAME}"
if [[ -z "$DEST" ]]; then
  DEST="$DEFAULT_DEST"
fi

echo "==> Zip file : $ZIP_PATH"
echo "==> Restore to: $DEST"
echo "==> Options   : DRY_RUN=${DRY_RUN}, OVERWRITE=${OVERWRITE}"
echo

# Integrity check
echo "🔎 Testing zip integrity…"
if ! unzip -t "$ZIP_PATH" >/dev/null 2>&1; then
  echo "❌ Zip integrity test failed."
  exit 1
fi
echo "✅ Zip integrity OK"

# Create destination / check overwrite
if [[ -e "$DEST" ]]; then
  if (( OVERWRITE == 0 )); then
    # Require empty directory, otherwise block
    if [[ -d "$DEST" ]] && [[ -z "$(ls -A "$DEST")" ]]; then
      : # ok, empty directory
    else
      echo "⚠️ Destination exists and is not empty. Use --overwrite to force."
      exit 1
    fi
  fi
else
  mkdir -p "$DEST"
fi

if (( DRY_RUN )); then
  echo "👁  Dry-run: showing zip contents (top 60 entries)…"
  unzip -l "$ZIP_PATH" | head -n 60
  echo "… (dry-run; no files written)"
  exit 0
fi

# Confirm
if (( ASSUME_YES == 0 )); then
  read -p "Proceed to restore into '$DEST'? [y/N] " -r
  echo
  [[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

# Extract
if (( OVERWRITE )); then
  echo "📦 Restoring (overwrite enabled)…"
  unzip -o "$ZIP_PATH" -d "$DEST" >/dev/null
else
  echo "📦 Restoring…"
  unzip -n "$ZIP_PATH" -d "$DEST" >/dev/null
fi

echo "✅ Restore complete → $DEST"
