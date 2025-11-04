#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./cleanbackup_agents.sh [ROOT] [--dry-run]
# Defaults:
#   ROOT=$HOME/credit-appraisal-agent-poc
#
# Policy: keep the last 5 timestamps for every agent (uniform).

ROOT="${1:-$HOME/credit-appraisal-agent-poc}"
DRY_RUN=0
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=1

DEFAULT_KEEP=5

echo "🧹 Per-agent backup cleanup"
echo "Root: $ROOT"
echo "Keep: last $DEFAULT_KEEP timestamps per agent"
echo "Dry-run: $([[ $DRY_RUN -eq 1 ]] && echo yes || echo no)"
echo "──────────────────────────────────────────────"

# ---- helpers aligned with your backup script ----

# Extract timestamp: YYYYMMDD-HHMMSS
ts_from_path() {
  local p="$1"
  basename -- "$p" | sed -nE 's/.*\.ok\.([0-9]{8}-[0-9]{6})\.bak.*/\1/p'
}

# Remove the backup suffix to recover original path
strip_backup_suffix() {
  local p="$1"
  echo "${p%%.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak*}"
}

# Categorize (same rules as your backup script)
categorize_file_like_backup() {
  local path="$1"
  local rel="${path#$ROOT/}"

  if [[ "$rel" =~ ^agents/([^/]+)/ ]]; then
    echo "${BASH_REMATCH[1]}"; return
  fi

  case "$rel" in
    services/ui/asset_appraisal.py) echo "asset_appraisal"; return ;;
    services/api/routers/asset_appraisal.py) echo "asset_appraisal"; return ;;
    services/train/train_credit.py) echo "credit_appraisal"; return ;;
    samples/credit/*)               echo "credit_appraisal"; return ;;
    agents/credit_appraisal/*)      echo "credit_appraisal"; return ;;
  esac

  echo "_core"
}

# Find all backups (files or dirs), ignore VCS/venv
find_backups() {
  find "$ROOT" \
    \( -type f -o -type d \) \
    -name '*.ok.[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].bak*' \
    -not -path '*/.git/*' -not -path '*/.venv/*' \
    -print 2>/dev/null
}

# Discover agents (informational)
mapfile -t AGENTS < <(find "$ROOT/agents" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort)
if (( ${#AGENTS[@]} > 0 )); then
  echo "==> Discovered agents:"
  for a in "${AGENTS[@]}"; do echo "  • $a"; done
  echo
fi

# Load all backups
mapfile -t ALL_BACKUPS < <(find_backups)
if (( ${#ALL_BACKUPS[@]} == 0 )); then
  echo "No backup files/directories found."
  exit 0
fi

# Build map: agent -> list of backup paths
declare -A AGENT_TO_BACKUPS=()
for b in "${ALL_BACKUPS[@]}"; do
  orig="$(strip_backup_suffix "$b")"
  agent="$(categorize_file_like_backup "$orig")"
  AGENT_TO_BACKUPS["$agent"]+="$b"$'\n'
done

TOTAL_DELETED=0

for agent in "${!AGENT_TO_BACKUPS[@]}"; do
  echo "📦 Agent: $agent  (keep: $DEFAULT_KEEP)"
  mapfile -t AB_LIST <<< "${AGENT_TO_BACKUPS[$agent]}"

  if (( ${#AB_LIST[@]} == 0 )); then
    echo "   ℹ️  No backups — skipping"
    echo
    continue
  fi

  # Collect unique timestamps for this agent
  declare -A TS_SEEN=()
  for p in "${AB_LIST[@]}"; do
    ts="$(ts_from_path "$p")"
    [[ -n "$ts" ]] && TS_SEEN["$ts"]=1
  done
  if (( ${#TS_SEEN[@]} == 0 )); then
    echo "   ⚠️  No valid timestamps — skipping"
    echo
    continue
  fi

  # newest first
  mapfile -t TS_SORTED_DESC < <(printf "%s\n" "${!TS_SEEN[@]}" | sort -r)

  KEEP_SET=("${TS_SORTED_DESC[@]:0:DEFAULT_KEEP}")
  declare -A KEEP_HASH=()
  for ts in "${KEEP_SET[@]}"; do KEEP_HASH["$ts"]=1; done

  DELETED_THIS_AGENT=0
  for p in "${AB_LIST[@]}"; do
    ts="$(ts_from_path "$p")"
    [[ -z "$ts" ]] && continue
    if [[ -z "${KEEP_HASH[$ts]:-}" ]]; then
      if [[ $DRY_RUN -eq 1 ]]; then
        [[ -d "$p" ]] && echo "   🧪 [dry-run] Would delete dir : $p" || echo "   🧪 [dry-run] Would delete file: $p"
      else
        if [[ -d "$p" ]]; then
          rm -rf -- "$p"
          echo "   🗑️  Deleted dir backup : $p"
        else
          rm -f -- "$p"
          echo "   🗑️  Deleted file backup: $p"
        fi
        ((DELETED_THIS_AGENT++)) || true
        ((TOTAL_DELETED++)) || true
      fi
    fi
  done

  printf "   ✅ Kept timestamps: "
  printf "%s " "${KEEP_SET[@]}"
  echo
  echo "   ➖ Deleted items : $DELETED_THIS_AGENT"
  echo
done

echo "──────────────────────────────────────────────"
echo "✅ Cleanup complete!"
echo "   • Total backups deleted: $TOTAL_DELETED"
echo "   • Kept last $DEFAULT_KEEP timestamps per agent"
echo "   • Use --dry-run to preview without deleting"
echo "──────────────────────────────────────────────"
