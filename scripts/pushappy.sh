#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
REPO_DIR="$HOME/credit-appraisal-agent-poc"
TARGET_FILE="services/ui/app.py"
BRANCH="main"
COMMIT_MSG="🔥 Force push app.py ($(date '+%Y-%m-%d %H:%M:%S'))"

# ─────────────────────────────────────────────
# EXECUTION
# ─────────────────────────────────────────────
cd "$REPO_DIR" || { echo "❌ Repo not found: $REPO_DIR"; exit 1; }

echo "🧩 Adding $TARGET_FILE ..."
git add "$TARGET_FILE"

echo "💾 Committing..."
git commit -m "$COMMIT_MSG" || echo "⚠️ No changes to commit."

echo "🚀 Force pushing to GitHub..."
git push origin "$BRANCH" --force

echo "✅ app.py pushed (force overwrite remote)"
