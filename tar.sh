#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST_BASE="/mnt/D"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
TAR_NAME="hugmesandbox-${TIMESTAMP}.tar.gz"
DEST_PATH="${DEST_BASE}/${TAR_NAME}"

echo "➡️  Backing up repository from: ${REPO_ROOT}"
echo "➡️  Destination directory: ${DEST_BASE}"

mkdir -p "${DEST_BASE}"

echo "📦 Creating archive: ${DEST_PATH}"
(cd "${REPO_ROOT}" && tar -czf "${DEST_PATH}" .)

echo "✅ Backup complete: ${DEST_PATH}"
