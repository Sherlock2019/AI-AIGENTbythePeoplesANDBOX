#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# RAX AI SANDBOX SNAPSHOT (zip if available, else tar.gz) + rotation
# Usage:
#   ./snapshot.sh                 # default ROOT=$HOME/credit-appraisal-agent-poc, KEEP=10
#   ./snapshot.sh --keep 12
#   ./snapshot.sh --root /path/to/repo
#   ./snapshot.sh --format zip    # force zip (requires 'zip')
#   ./snapshot.sh --format tar    # force tar.gz
#   ./snapshot.sh --dry-run
# Env overrides: ROOT, KEEP_SNAPSHOTS
# ──────────────────────────────────────────────────────────────

ROOT="${ROOT:-$HOME/credit-appraisal-agent-poc}"
KEEP_SNAPSHOTS="${KEEP_SNAPSHOTS:-10}"
FORMAT=""        # auto (zip -> tar fallback) unless --format given
DRY_RUN=0

# --- Parse args ---
while (( $# )); do
  case "$1" in
    --keep)        KEEP_SNAPSHOTS="${2:?}"; shift 2;;
    --root)        ROOT="${2:?}"; shift 2;;
    --format)      FORMAT="${2:?}"; shift 2;;
    --dry-run)     DRY_RUN=1; shift;;
    -h|--help)
      cat <<EOF
Usage: $0 [--keep N] [--root PATH] [--format zip|tar] [--dry-run]
EOF
      exit 0;;
    *)
      echo "Unknown option: $1" >&2; exit 1;;
  esac
done

BACKUP_DIR="$ROOT/backups"
DATESTAMP="$(date '+%Y-%m-%d_%H-%M')"
SNAP_PREFIX="rax_ai_sandbox_snapshot_"

# --- Decide archiver (zip preferred) ---
ARCHIVER=""
SNAPSHOT_FILE=""
if [[ -n "$FORMAT" ]]; then
  if [[ "$FORMAT" == "zip" ]]; then
    command -v zip >/dev/null 2>&1 || { echo "❌ 'zip' not found."; exit 1; }
    ARCHIVER="zip"
    SNAPSHOT_FILE="$BACKUP_DIR/${SNAP_PREFIX}${DATESTAMP}.zip"
  elif [[ "$FORMAT" == "tar" ]]; then
    command -v tar >/dev/null 2>&1 || { echo "❌ 'tar' not found."; exit 1; }
    ARCHIVER="tar"
    SNAPSHOT_FILE="$BACKUP_DIR/${SNAP_PREFIX}${DATESTAMP}.tar.gz"
  else
    echo "❌ --format must be 'zip' or 'tar'"; exit 1
  fi
else
  if command -v zip >/dev/null 2>&1; then
    ARCHIVER="zip"
    SNAPSHOT_FILE="$BACKUP_DIR/${SNAP_PREFIX}${DATESTAMP}.zip"
  elif command -v tar >/dev/null 2>&1; then
    ARCHIVER="tar"
    SNAPSHOT_FILE="$BACKUP_DIR/${SNAP_PREFIX}${DATESTAMP}.tar.gz"
  else
    echo "❌ Neither 'zip' nor 'tar' is available. Install one of them."; exit 1
  fi
fi

echo "📦 Creating snapshot of RAX AI Sandbox"
echo "→ Workspace : $ROOT"
echo "→ Output    : $SNAPSHOT_FILE"
echo "→ Keep last : $KEEP_SNAPSHOTS snapshots"
[[ $DRY_RUN -eq 1 ]] && echo "→ Mode      : DRY-RUN (no writes)" || true

# Ensure backup dir
if [[ $DRY_RUN -eq 0 ]]; then
  mkdir -p "$BACKUP_DIR"
fi

# What to include (relative to ROOT)
INCLUDE_PATHS=(
  "agents"
  "services"
  "samples"
  "models"
  "requirements.txt"
  "start.sh"
  "stop.sh"
  "save_and_push.sh"
)
# Optionally include if present
for D in ".env" ".configs" ".runs" ".logs"; do
  [[ -e "$ROOT/$D" ]] && INCLUDE_PATHS+=("$D")
done

# Build manifest (inside ROOT so both zip and tar can include it easily)
MAN_REL=".snapshot_manifest_${DATESTAMP}.txt"
MAN_PATH="$ROOT/$MAN_REL"
{
  echo "Snapshot created at $(date)"
  echo "Root: $ROOT"
  echo "Included paths:"
  for p in "${INCLUDE_PATHS[@]}"; do echo "  - $p"; done
} > "$MAN_PATH"
cleanup_manifest() { rm -f "$MAN_PATH" >/dev/null 2>&1 || true; }
trap cleanup_manifest EXIT

# Exclude patterns
EXCL_PATTERNS=(
  ".git"
  ".git/*"
  ".venv"
  ".venv/*"
  "venv"
  "venv/*"
  "node_modules"
  "node_modules/*"
  "datasets"
  "datasets/*"
  ".cache"
  ".cache/*"
  ".mypy_cache"
  ".mypy_cache/*"
  ".pytest_cache"
  ".pytest_cache/*"
  "__pycache__"
  "__pycache__/*"
  "*.pyc"
  "*.pyo"
  "*.tmp"
  "*.log"
)

echo "• Writing archive…"
if [[ "$ARCHIVER" == "zip" ]]; then
  cd "$ROOT"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY] zip -r -9 \"$SNAPSHOT_FILE\" (…includes ${#INCLUDE_PATHS[@]} paths + $MAN_REL, excludes ${#EXCL_PATTERNS[@]})"
  else
    # shellcheck disable=SC2046
    zip -r -9 "$SNAPSHOT_FILE" $(printf " %q" "${INCLUDE_PATHS[@]}") "$MAN_REL" \
      -x $(printf " %q" "${EXCL_PATTERNS[@]}") >/dev/null
  fi
else
  # tar.gz with pigz if available
  TAR_COMP=(-z)
  if command -v pigz >/dev/null 2>&1; then
    TAR_COMP=(--use-compress-program pigz)
  fi
  cd "$ROOT"
  # Only include existing paths to avoid warnings
  mapfile -t EXISTING < <(for p in "${INCLUDE_PATHS[@]}"; do [[ -e "$p" ]] && printf '%q\n' "$p"; done)
  # Assemble --exclude=
  EXCL_ARGS=()
  for pat in "${EXCL_PATTERNS[@]}"; do EXCL_ARGS+=(--exclude="$pat"); done
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[DRY] tar ${TAR_COMP[*]} -cf \"$SNAPSHOT_FILE\" ${EXCL_ARGS[*]} \"$MAN_REL\" ${EXISTING[*]}"
  else
    tar "${TAR_COMP[@]}" -cf "$SNAPSHOT_FILE" "${EXCL_ARGS[@]}" "$MAN_REL" "${EXISTING[@]}" 2>/dev/null
  fi
fi

# Rotation: keep newest N snapshots (both .zip and .tar.gz)
echo "• Rotating old snapshots (keep $KEEP_SNAPSHOTS)…"
shopt -s nullglob
SNAPS=( "$BACKUP_DIR"/${SNAP_PREFIX}*.zip "$BACKUP_DIR"/${SNAP_PREFIX}*.tar.gz )
shopt -u nullglob

# If no snapshots yet, handle gracefully
if (( ${#SNAPS[@]} == 0 )); then
  echo "  (no existing snapshots to rotate)"
  echo "✅ Snapshot complete"
  echo "→ Saved: $SNAPSHOT_FILE"
  exit 0
fi

# Newest first by mtime
mapfile -t SNAPS_SORTED < <(ls -1t "${SNAPS[@]}" 2>/dev/null || true)
TOTAL=${#SNAPS_SORTED[@]}
DELETED=0

if (( TOTAL > KEEP_SNAPSHOTS )); then
  for z in "${SNAPS_SORTED[@]:$KEEP_SNAPSHOTS}"; do
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "[DRY] rm -f -- \"$z\""
    else
      if ! rm -f -- "$z"; then
        echo "  ⚠️  Could not delete: $z (permission?)"
      else
        ((DELETED++)) || true
      fi
    fi
  done
fi

KEPT=$(( TOTAL - DELETED ))
echo "✅ Snapshot complete"
echo "→ Saved: $SNAPSHOT_FILE"
echo "→ Snapshots kept: $KEPT   deleted: $DELETED"
echo "→ Newest (up to 5):"
for s in "${SNAPS_SORTED[@]:0:$(( KEPT < 5 ? KEPT : 5 ))}"; do
  echo "   - $s"
done
