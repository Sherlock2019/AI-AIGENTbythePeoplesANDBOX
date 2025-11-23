#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST_BASE="/mnt/D"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ZIP_NAME="hugmesandbox-${TIMESTAMP}.zip"
DEST_PATH="${DEST_BASE}/${ZIP_NAME}"

echo "➡️  Backing up repository from: ${REPO_ROOT}"
echo "➡️  Destination directory: ${DEST_BASE}"

mkdir -p "${DEST_BASE}"

echo "📦 Creating archive: ${DEST_PATH}"
(cd "${REPO_ROOT}" && zip -r "${DEST_PATH}" .)

echo "✅ Backup complete: ${DEST_PATH}"
