#!/usr/bin/env bash
# assetagentcheck.sh
# Concatenate all files required for the Asset Appraisal Agent (or just list them).

set -euo pipefail

# ---------- Defaults ----------
ROOT="${ROOT:-$HOME/credit-appraisal-agent-poc}"
OUT_FILE=""
DRY_RUN="false"
INCLUDE_TESTS="false"
MAX_SIZE_MB="${MAX_SIZE_MB:-5}"   # skip files larger than this
HASH_BIN="$(command -v sha256sum || true)"
DATE_FMT="+%Y-%m-%d %H:%M:%S"

# ---------- Include patterns ----------
INCLUDE_PATTERNS=(
  "agents/asset_appraisal/**/*.py"
  "agents/asset_appraisal/**/requirements*.txt"
  "agents/asset_appraisal/**/README*"
  "agents/asset_appraisal/**/pyproject.toml"
  "agents/asset_appraisal/**/Pipfile*"

  "services/api/routers/asset*.py"
  "services/api/schemas/asset*.py"
  "services/api/**/models_asset*.py"
  "services/api/**/asset_*.py"
  "services/api/**/assets_*.py"

  "services/ui/**/asset*.py"
  "services/ui/**/valuation*.py"
  "services/ui/**/collateral*.py"

  "pyproject.toml"
  "requirements*.txt"
)

TEST_PATTERNS=(
  "tests/**/asset*.py"
  "tests/**/test_asset*.py"
)

# ---------- Exclude patterns (globs) ----------
EXCLUDE_GLOBS=(
  "*.joblib" "*.pkl" "*.onnx" "*.bin" "*.pt" "*.pth"
  "*.png" "*.jpg" "*.jpeg" "*.gif" "*.webp" "*.svg"
  "*.pdf" "*.csv" "*.parquet" "*.xlsx"
  "*.zip" "*.tar" "*.tar.gz" "*.tgz"
  ".venv/**" "venv/**" ".mypy_cache/**" ".pytest_cache/**" "__pycache__/**"
  ".runs/**" "agents/**/models/**" "agents/**/artifacts/**"
)

usage() {
  cat <<EOF
Usage: $(basename "$0") [--root PATH] [--out FILE] [--dry-run] [--include-tests] [--max-size-mb N]
EOF
}

# ---------- Args ----------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2;;
    --out) OUT_FILE="$2"; shift 2;;
    --dry-run) DRY_RUN="true"; shift;;
    --include-tests) INCLUDE_TESTS="true"; shift;;
    --max-size-mb) MAX_SIZE_MB="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

[[ -d "$ROOT" ]] || { echo "❌ ROOT not found: $ROOT" >&2; exit 1; }

# ---------- Globbing setup ----------
shopt -s globstar nullglob dotglob

# Returns 0 if $1 matches any EXCLUDE_GLOBS; else 1
is_excluded() {
  local rel="$1" pat
  for pat in "${EXCLUDE_GLOBS[@]}"; do
    # shellcheck disable=SC2053
    [[ "$rel" == $pat ]] && return 0
  done
  return 1
}

declare -A SEEN=()
declare -a FILES=()

add_matches() {
  local pattern="$1"
  local f
  for f in "$ROOT"/$pattern; do
    [[ -f "$f" ]] || continue
    local rel="${f#"$ROOT"/}"
    is_excluded "$rel" && continue
    [[ -n "${SEEN[$rel]:-}" ]] || { SEEN["$rel"]=1; FILES+=("$rel"); }
  done
}

for pat in "${INCLUDE_PATTERNS[@]}"; do add_matches "$pat"; done
if [[ "$INCLUDE_TESTS" == "true" ]]; then
  for pat in "${TEST_PATTERNS[@]}"; do add_matches "$pat"; done
fi

IFS=$'\n' FILES=($(sort -u <<<"${FILES[*]}")); unset IFS

# ---------- Output ----------
[[ -n "$OUT_FILE" ]] && exec >"$OUT_FILE"

echo "=== Asset Appraisal Agent Bundle ==="
echo "Generated: $(date "$DATE_FMT")"
echo "Root: $ROOT"
echo "Files matched: ${#FILES[@]}"
echo "Max file size: ${MAX_SIZE_MB}MB"
echo

if [[ "$DRY_RUN" == "true" ]]; then
  printf '%s\n' "${FILES[@]}"
  exit 0
fi

BYTES_LIMIT=$(( MAX_SIZE_MB * 1024 * 1024 ))

for rel in "${FILES[@]}"; do
  local_abs="$ROOT/$rel"
  size=$(stat -c%s "$local_abs" 2>/dev/null || stat -f%z "$local_abs" 2>/dev/null || echo 0)

  if (( size > BYTES_LIMIT )); then
    echo "----- SKIP (too large > ${MAX_SIZE_MB}MB): $rel ($size bytes)" >&2
    continue
  fi

  hash_val="(no sha256sum)"
  [[ -n "$HASH_BIN" ]] && hash_val="$("$HASH_BIN" "$local_abs" | awk '{print $1}')"

  echo "===== BEGIN FILE: $rel | size=${size} | sha256=${hash_val} ====="
  cat "$local_abs"
  tail -c1 "$local_abs" >/dev/null 2>&1 || echo
  echo "===== END FILE: $rel ====="
  echo
done

echo "=== End of Asset Appraisal Agent Bundle ==="
