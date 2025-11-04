#!/usr/bin/env bash
set -e

git add -A
git commit -m "auto: $(date -Is)" || true
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git push -f origin "$BRANCH"

echo "✅ Pushed to origin/$BRANCH"
