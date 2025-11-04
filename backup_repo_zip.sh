#!/usr/bin/env bash
set -euo pipefail

# ============================
# Simple Repo ZIP Backup
# ============================

# Resolve repo root (env ROOT -> git toplevel -> script dir)
if [[ -n "${ROOT:-}" ]]; then
  ROOT="$(cd "$ROOT" && pwd)"
else
  if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fi
fi

REPO_NAME="$(basename "$ROOT")"
OUTDIR="${HOME}/repobackup"
TS="$(date +%Y%m%d-%H%M%S)"
ZIP_PATH="${OUTDIR}/${REPO_NAME}_${TS}.zip"

mkdir -p "$OUTDIR"

# Check zip availability
if ! command -v zip >/dev/null 2>&1; then
  echo "❌ 'zip' not found. Install it (e.g., 'sudo apt-get install zip') and retry."
  exit 1
fi

echo "==> Repo root : $ROOT"
echo "==> Output dir: $OUTDIR"
echo "==> ZIP file  : $ZIP_PATH"
echo

# Exclude heavy/derived folders
# Note: patterns are relative to $ROOT when using -r with path "."
EXCLUDES=(
  ".git/*"
  ".venv/*"
  "__pycache__/*"
  "node_modules/*"
  ".mypy_cache/*"
  ".pytest_cache/*"
  ".runs/*"
  ".tmp_runs/*"
  ".logs/*"
)

# Build -x args
XARGS=()
for pat in "${EXCLUDES[@]}"; do
  XARGS+=( -x "$pat" )
done

echo "🧳 Creating ZIP (highest compression, with excludes)…"
(
  cd "$ROOT"
  zip -r -9 "$ZIP_PATH" . "${XARGS[@]}"
)

# Verify the archive
echo "🔎 Verifying zip integrity…"
if unzip -t "$ZIP_PATH" >/dev/null 2>&1; then
  SIZE_HUMAN="$(du -h "$ZIP_PATH" | awk '{print $1}')"
  echo "✅ Backup created: $ZIP_PATH  (size: $SIZE_HUMAN)"
else
  echo "❌ Zip verification failed."
  exit 1
fi
