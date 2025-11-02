#!/usr/bin/env bash
set -euo pipefail

echo "🔄 Force-updating local repo from remote (origin/main)..."
git fetch origin
git reset --hard origin/main
git clean -fdx
echo "✅ Local repo now matches remote main branch."
