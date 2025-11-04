#!/usr/bin/env bash
set -euo pipefail

# ==== CONFIG (choose ONE remote) ====
# A) Push to the new repo:
# REMOTE_URL="git@github.com:Sherlock2019/banking-agent-liberty.git"
# B) Push to the original repo:
# REMOTE_URL="git@github.com:Sherlock2019/credit-appraisal-agent-poc.git"

# >>>>> CHOOSE your target:
REMOTE_URL="git@github.com:Sherlock2019/banking-agent-liberty.git"
# ====================================

EXPECTED_DIR="${EXPECTED_DIR:-$HOME/credit-appraisal-agent-poc}"
REPO_DIR="${REPO_DIR:-$(pwd)}"
REMOTE_NAME="${REMOTE_NAME:-origin}"
BRANCH="${BRANCH:-main}"

# ---- Guards ----
if [[ "$EUID" -eq 0 ]]; then
  echo "❌ Do not run with sudo. Re-run as your normal user."
  exit 1
fi
if [[ "$REPO_DIR" != "$EXPECTED_DIR" ]]; then
  echo "❌ You're in: $REPO_DIR"
  echo "   Expected: $EXPECTED_DIR"
  echo "   cd \"$EXPECTED_DIR\" and rerun."
  exit 1
fi
if [[ ! -d ".git" ]]; then
  echo "❌ Not a git repo: $REPO_DIR"
  exit 1
fi
if [[ ! -f "README.md" ]]; then
  echo "❌ README.md missing. Create or paste your README.md, then rerun."
  exit 1
fi

# ---- Heal perms from any past sudo use ----
if command -v sudo >/dev/null 2>&1; then
  sudo chown -R "$(id -un)":"$(id -gn)" .git README.md .gitignore 2>/dev/null || true
fi
find .git -name "*.lock" -delete 2>/dev/null || true
git config --global --add safe.directory "$REPO_DIR" || true

# ---- Ensure branch & remote ----
curr_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$curr_branch" != "$BRANCH" ]]; then
  git branch -M "$BRANCH"
fi
if git remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
  git remote set-url "$REMOTE_NAME" "$REMOTE_URL"
else
  git remote add "$REMOTE_NAME" "$REMOTE_URL"
fi

echo "==> Repo: $REPO_DIR"
echo "==> Branch: $BRANCH"
echo "==> Remote:"
git remote -v

# ---- Show diff for README before staging ----
echo "==> Working diff for README.md:"
git diff -- README.md || true

# ---- Stage files ----
git add README.md .gitignore docs/*.png 2>/dev/null || true

echo "==> Staged changes:"
if git diff --cached --quiet; then
  echo "(none)"
else
  git diff --cached --stat
fi

# ---- Commit if something is staged ----
if ! git diff --cached --quiet; then
  git commit -m "docs(README): update English-only readme; chore: ignores & docs"
else
  echo "ℹ️ Nothing to commit (README.md unchanged)."
fi

# ---- Push (safe). To overwrite: FORCE_PUSH=1 ./push.sh ----
set +e
git push -u "$REMOTE_NAME" "$BRANCH"
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  echo "⚠️ Normal push failed (divergent history?)."
  if [[ "${FORCE_PUSH:-0}" == "1" ]]; then
    git push --force-with-lease -u "$REMOTE_NAME" "$BRANCH"
  else
    echo "👉 If you intend to overwrite remote with local, rerun: FORCE_PUSH=1 $0"
    exit $rc
  fi
fi

echo "✅ Pushed to $REMOTE_URL ($BRANCH)"

