#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# CONFIG (env-overridable)
# ─────────────────────────────────────────────
REPO_PATH="${REPO_PATH:-$HOME/credit-appraisal-agent-poc}"
BRANCH="${BRANCH:-}"  # auto-detect current branch if empty

# Allowlisted extensions and core files for a fresh clone
ALLOWED_EXT_REGEX='^.*\.(py|sh|toml|ya?ml|json|md|txt)$'
ALWAYS_INCLUDE_REGEX='(^|.*/)(Makefile|requirements\.txt|pyproject\.toml|\.env\.example|README(\.md)?)$'
# CSVs: only keep sample CSVs for demo/training; skip runtime CSVs
CSV_OK_PATHS_REGEX='(^|.*/)(samples?/|agents/[^/]+/sample_data/)'

# Never stage: runtime artifacts / caches / logs / backups
DENY_PATHS_REGEX='(^|.*/)(\.git/|\.venv/|__pycache__/|\.mypy_cache/|\.pytest_cache/|\.cache/|\.logs?/|logs/|\.pids/|\.tmp_runs/|\.runs/)'
DENY_NAME_REGEX='(^|.*\.)((bak|log|pyc|tmp|swp)(\..*)?)$'

# Size thresholds (GitHub hard limit 100 MB)
MAX_BYTES=$((100 * 1024 * 1024))   # block above
WARN_BYTES=$((50 * 1024 * 1024))   # warn above

# ─────────────────────────────────────────────
# ENTER REPO + discover remote/branch
# ─────────────────────────────────────────────
cd "$REPO_PATH"
echo "📦 Repo: $REPO_PATH"

REMOTE_URL="$(git config --get remote.origin.url || true)"
if [[ -z "${REMOTE_URL:-}" ]]; then
  echo "❌ No 'origin' remote defined. Add one:  git remote add origin <URL>"
  exit 1
fi
echo "🔗 Remote origin: $REMOTE_URL"

if [[ -z "${BRANCH:-}" ]]; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
fi
echo "🌿 Branch: $BRANCH"

# ─────────────────────────────────────────────
# Collect candidates (NOT by mtime)
#  - Modified tracked files
#  - Untracked (non-ignored) files
# ─────────────────────────────────────────────
mapfile -t MODIFIED < <(git ls-files -m)
mapfile -t UNTRACKED < <(git ls-files --others --exclude-standard)

CANDIDATES=("${MODIFIED[@]}" "${UNTRACKED[@]}")

matches() { [[ "$1" =~ $2 ]]; }

FILTERED=()
for f in "${CANDIDATES[@]}"; do
  [[ -f "$f" ]] || continue
  [[ -L "$f" ]] && continue

  # Respect .gitignore
  if git check-ignore -q -- "$f"; then
    continue
  fi

  # Block junk paths and names
  if matches "$f" "$DENY_PATHS_REGEX"; then
    continue
  fi
  if matches "$f" "$DENY_NAME_REGEX"; then
    continue
  fi

  lower="${f,,}"

  # Always include core infra (Makefile, reqs, pyproject, env.example, README)
  if matches "$f" "$ALWAYS_INCLUDE_REGEX"; then
    FILTERED+=("$f"); continue
  fi

  # Include code/config/docs/script files
  if matches "$f" "$ALLOWED_EXT_REGEX"; then
    FILTERED+=("$f"); continue
  fi

  # Include sample CSVs only from approved paths
  if [[ "$lower" == *.csv ]] && matches "$f" "$CSV_OK_PATHS_REGEX"; then
    FILTERED+=("$f"); continue
  fi
done

if ((${#FILTERED[@]}==0)); then
  echo "✅ Nothing to stage (no eligible modified/untracked files)."
  exit 0
fi

echo "📝 Staging ${#FILTERED[@]} authorized file(s):"
for f in "${FILTERED[@]}"; do
  echo "  • $f"
  git add -- "$f"
done

echo "📚 Staged summary:"
git diff --cached --name-status || true
echo "──────────────────────────────"

# ─────────────────────────────────────────────
# Size safety (GitHub 100 MB hard limit)
# ─────────────────────────────────────────────
mapfile -t STAGED < <(git diff --cached --name-only --diff-filter=ACMR)
mapfile -t LFS_TRACKED < <(git lfs ls-files --name-only 2>/dev/null || true)
in_array(){ local n="$1"; shift; for x in "$@"; do [[ "$x" == "$n" ]] && return 0; done; return 1; }

TOTAL=0; BLOCKED=0
for f in "${STAGED[@]}"; do
  [[ -f "$f" ]] || continue
  sz=$(stat -c%s -- "$f" 2>/dev/null || echo 0)
  TOTAL=$((TOTAL+sz))
  if (( sz > MAX_BYTES )) && ! in_array "$f" "${LFS_TRACKED[@]}"; then
    echo "❌ $f is $(numfmt --to=iec $sz) > 100 MB and not tracked by Git LFS."
    echo "   Fix: git lfs install && git lfs track \"*.${f##*.}\" && git add .gitattributes \"$f\""
    BLOCKED=1
  elif (( sz > WARN_BYTES )) && ! in_array "$f" "${LFS_TRACKED[@]}"; then
    echo "⚠️  Large file staged: $f ($(numfmt --to=iec $sz)). Consider Git LFS."
  fi
done
echo "📦 Total staged size ≈ $(numfmt --to=iec $TOTAL)"
(( BLOCKED == 0 )) || { echo "⛔ Push aborted due to >100 MB file(s)."; exit 2; }

# ─────────────────────────────────────────────
# Commit & push
# ─────────────────────────────────────────────
COMMIT_MSG="🚀 Push modified & untracked authorized files (code+infra; no junk)"
echo "💬 Commit message: $COMMIT_MSG"
git commit -m "$COMMIT_MSG" || echo "⚠️ Nothing new to commit."

echo "⬆️ Pushing to origin $BRANCH …"
git push origin "$BRANCH"

echo "✅ Done."
