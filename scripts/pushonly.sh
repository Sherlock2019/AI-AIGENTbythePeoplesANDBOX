#!/usr/bin/env bash
set -euo pipefail

echo "⬆️ Pushing local changes to remote (origin/main)..."

# Auto-detect new/modified files and commit with timestamp
git add -A
git commit -m "auto: local update $(date +'%Y-%m-%d %H:%M:%S')" || echo "ℹ️ Nothing to commit."
git push origin main

echo "✅ Local changes pushed successfully."
