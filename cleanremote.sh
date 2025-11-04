#!/usr/bin/env bash
set -euo pipefail

# ────────────────────────────────────────────────
# CLEAN REMOTE SCRIPT — remove .log and .bak files
# (keeps local files intact)
# Author: Dzoan (AI by the People)
# ────────────────────────────────────────────────

echo "🌍 Cleaning .log and .bak files from remote (GitHub)..."

# Step 1. Fetch latest
git fetch origin main

# Step 2. Remove matching files from the index only (not from disk)
git rm --cached $(git ls-files | grep -E "\.log$|\.bak$") 2>/dev/null || true

# Step 3. Commit the cleanup
if git diff --cached --quiet; then
  echo "ℹ️ No .log or .bak files found on remote index."
else
  COMMIT_MSG="chore(remote): remove .log and .bak files ($(date '+%Y-%m-%d %H:%M:%S'))"
  git commit -m "${COMMIT_MSG}"
  echo "⬆️ Pushing cleanup to origin/main..."
  git push origin main
  echo "🚀 Remote cleanup completed successfully."
fi

echo "✅ Done — .log and .bak files are removed from GitHub (remote) only."
