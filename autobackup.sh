#!/usr/bin/env bash
set -euo pipefail

# Timestamped backup suffix
BACKUP_EXT=".ok.$(date +%Y%m%d-%H%M%S).bak"

echo "==> Starting auto-discovery backup for ALL agents"
echo "==> Backup suffix: ${BACKUP_EXT}"
echo

ROOT="/home/dzoan/credit-appraisal-agent-poc"

# Enable safe globbing
shopt -s nullglob globstar

# -----------------------------
# Core "platform" files (always)
# -----------------------------
CORE_FILES=(
  "$ROOT/services/ui/app.py"
  "$ROOT/services/ui/requirements.txt"
  "$ROOT/services/ui/runwebui.sh"

  "$ROOT/services/api/routers/agents.py"
  "$ROOT/services/api/routers/reports.py"
  "$ROOT/services/api/routers/settings.py"
  "$ROOT/services/api/routers/training.py"
  "$ROOT/services/api/routers/system.py"
  "$ROOT/services/api/routers/export.py"
  "$ROOT/services/api/routers/runs.py"
  "$ROOT/services/api/routers/admin.py"

  "$ROOT/services/api/main.py"
  "$ROOT/services/api/requirements.txt"
  "$ROOT/services/api/adapters/__init__.py"
  "$ROOT/services/api/adapters/llm_adapters.py"

  "$ROOT/agent_platform/agent_sdk/__init__.py"
  "$ROOT/agent_platform/agent_sdk/sdk.py"

  "$ROOT/scripts/run_e2e.sh"
  "$ROOT/infra/run_api.sh"
  "$ROOT/Makefile"
  "$ROOT/pyproject.toml"
)

# --- helper filters ---
should_skip() {
  local p="$1"
  [[ "$p" == *"/.git/"* ]] && return 0
  [[ "$p" == *"/.venv/"* ]] && return 0
  [[ "$p" == *"/__pycache__/"* ]] && return 0
  [[ "$p" == *.pyc ]] && return 0
  [[ "$p" == *.pyo ]] && return 0
  [[ "$p" == *.ok.*.bak ]] && return 0
  return 1
}

# Return alias tokens for an agent name, one per line
agent_aliases() {
  local a="$1"
  echo "$a"
  # strip common suffixes for filename affinity
  echo "${a%_agent}"
  echo "${a%_appraisal}"
}

# Produce patterns for an agent into a global array PATTERNS (append)
declare -a PATTERNS=()
add_patterns_for_agent() {
  local agent="$1"
  local alias
  # 1) agent package files (definitive)
  PATTERNS+=("$ROOT/agents/$agent/**/*")
  # 2) model/schema/data common places using aliases
  while read -r alias; do
    [[ -z "$alias" ]] && continue
    PATTERNS+=(
      "$ROOT/services/ui/**/${alias}.py"
      "$ROOT/services/ui/**/${alias}*.py"

      "$ROOT/services/api/**/${alias}.py"
      "$ROOT/services/api/**/${alias}*.py"

      "$ROOT/services/train/**/${alias}*.py"
      "$ROOT/scripts/**/${alias}*.py"

      "$ROOT/**/${alias}*schema*.json"
      "$ROOT/**/${alias}*schema*.yaml"
      "$ROOT/**/${alias}*schema*.yml"
      "$ROOT/**/${alias}*feature*.json"
      "$ROOT/**/${alias}*_sample*.csv"
      "$ROOT/**/${alias}*training*.csv"
    )
  done < <(agent_aliases "$agent" | awk 'NF' | sort -u)
}

# Discover agents as every directory directly under agents/
mapfile -t AGENTS < <(find "$ROOT/agents" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort)
if (( ${#AGENTS[@]} == 0 )); then
  echo "❌ No agents found under $ROOT/agents"
  exit 1
fi

echo "==> Discovered agents:"
for a in "${AGENTS[@]}"; do echo "  • $a"; done
echo

# Build patterns per agent + ensure model dirs exist list
declare -a MODEL_DIRS=()
for a in "${AGENTS[@]}"; do
  add_patterns_for_agent "$a"
  MODEL_DIRS+=("$ROOT/agents/$a/models/production")
  MODEL_DIRS+=("$ROOT/agents/$a/models/trained")
done

# Always include some common test/train/sample files if they exist and look agent-bound
OPTIONAL_FILES=(
  "$ROOT/services/train/train_credit.py"
  "$ROOT/samples/credit/schema.json"
  "$ROOT/agents/credit_appraisal/sample_data/credit_sample.csv"
  "$ROOT/agents/credit_appraisal/sample_data/credit_training_sample.csv"
)
# Also include any directly-known UI routers named exactly like agent (covers your asset_appraisal/router/ui case)
for a in "${AGENTS[@]}"; do
  OPTIONAL_FILES+=("$ROOT/services/api/routers/${a}.py")
  OPTIONAL_FILES+=("$ROOT/services/ui/${a}.py")
done

# -----------------------------
# Expand all file candidates
# -----------------------------
declare -A SEEN=()        # path -> 1
declare -a EXPANDED=()    # final candidate files
declare -A CATEGORY=()    # path -> agent key (_core or specific or _shared)

# 1) Add core files to list
for f in "${CORE_FILES[@]}"; do
  if [[ -e "$f" && -z "${SEEN[$f]:-}" ]]; then
    SEEN["$f"]=1
    EXPANDED+=("$f")
    CATEGORY["$f"]="_core"
  fi
done

# 2) Add optional single files (if exist)
for f in "${OPTIONAL_FILES[@]}"; do
  if [[ -e "$f" && -z "${SEEN[$f]:-}" ]]; then
    SEEN["$f"]=1
    EXPANDED+=("$f")
    # Heuristic: map to agent if path reveals it, else _core
    rel="${f#$ROOT/}"
    if [[ "$rel" =~ ^agents/([^/]+)/ ]]; then
      CATEGORY["$f"]="${BASH_REMATCH[1]}"
    else
      # try by filename stem matching an agent
      base="$(basename "$f")"
      agent_hit="_core"
      for a in "${AGENTS[@]}"; do
        if [[ "$base" == "$a.py" || "$base" == "$a"*"."* ]]; then agent_hit="$a"; break; fi
      done
      CATEGORY["$f"]="$agent_hit"
    fi
  fi
done

# 3) Expand per-agent patterns and map ownership; if multiple agents match => _shared
declare -A OWNER=()  # path -> agent (or _shared)
for a in "${AGENTS[@]}"; do
  # derive agent-specific pattern slice for this agent (re-generate small set)
  declare -a PATS_FOR_A=()
  PATS_FOR_A+=("$ROOT/agents/$a/**/*")
  while read -r alias; do
    [[ -z "$alias" ]] && continue
    PATS_FOR_A+=(
      "$ROOT/services/ui/**/${alias}.py" "$ROOT/services/ui/**/${alias}*.py"
      "$ROOT/services/api/**/${alias}.py" "$ROOT/services/api/**/${alias}*.py"
      "$ROOT/services/train/**/${alias}*.py"
      "$ROOT/scripts/**/${alias}*.py"
      "$ROOT/**/${alias}*schema*.json" "$ROOT/**/${alias}*schema*.yaml" "$ROOT/**/${alias}*schema*.yml"
      "$ROOT/**/${alias}*feature*.json"
      "$ROOT/**/${alias}*_sample*.csv"
      "$ROOT/**/${alias}*training*.csv"
    )
  done < <(agent_aliases "$a" | awk 'NF' | sort -u)

  for pat in "${PATS_FOR_A[@]}"; do
    for p in $pat; do
      [[ -f "$p" ]] || continue
      should_skip "$p" && continue
      if [[ -z "${SEEN[$p]:-}" ]]; then
        SEEN["$p"]=1
        EXPANDED+=("$p")
        OWNER["$p"]="$a"
      else
        # Already seen; mark shared if owned by another agent
        if [[ "${OWNER[$p]:-}" != "" && "${OWNER[$p]}" != "$a" ]]; then
          OWNER["$p"]="_shared"
        fi
      fi
    done
  done
done

# Apply owner to CATEGORY for agent files
for f in "${!OWNER[@]}"; do
  CATEGORY["$f"]="${OWNER[$f]}"
done

# -----------------------------
# Show final candidate list
# -----------------------------
missing=0
declare -a EXISTING=()

echo "==> Files to consider (after expansion):"
for f in "${EXPANDED[@]}"; do
  if [[ -f "$f" ]]; then
    echo "  • $f"
    EXISTING+=("$f")
  else
    echo "  • $f   (skip: not found)"
    ((missing++)) || true
  fi
done

if (( ${#EXISTING[@]} == 0 )); then
  echo "❌ None of the listed files exist. Exiting."
  exit 1
fi

echo
if (( missing > 0 )); then
  echo "⚠️  $missing file(s) were not found and will be skipped."
fi
echo

read -p "Proceed with backup of all files and models? [y/N] " -n 1 -r
echo
[[ $REPLY =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

# -----------------------------
# Backup helpers
# -----------------------------
SUDO_BIN="$(command -v sudo || true)"

copy_inplace() {
  local src="$1"
  local dst="$2"
  local dir; dir="$(dirname "$dst")"

  if [[ -w "$dir" ]]; then
    cp -f "$src" "$dst"
  else
    if [[ -n "$SUDO_BIN" ]]; then
      echo "   (no write permission — using sudo)"
      $SUDO_BIN cp -f "$src" "$dst"
    else
      echo "   ❌ Cannot write to $dir and sudo not available — skipping."
      return 1
    fi
  fi
  return 0
}

backup_directory() {
  local src_dir="$1"
  local dest_dir="${src_dir}${BACKUP_EXT}"
  if [[ -d "$src_dir" ]]; then
    echo "🗂️  Backing up directory: $src_dir → $dest_dir"
    cp -r "$src_dir" "$dest_dir"
  else
    echo "   ⚠️  Directory not found: $src_dir"
  fi
}

# Ensure model dirs exist (avoid warnings)
for d in "${MODEL_DIRS[@]}"; do
  mkdir -p "$d"
done

# -----------------------------
# Per-agent counters
# -----------------------------
declare -A AGENT_BACKED=()
declare -A AGENT_SKIPPED=()

BACKUP_COUNT=0
SKIPPED_COUNT=0

# -----------------------------
# Execute file backups
# -----------------------------
for file in "${EXISTING[@]}"; do
  bak="${file}${BACKUP_EXT}"
  agent="${CATEGORY[$file]:-_core}"
  echo "────────────────────────────────────────────"
  echo "➡️  Processing: $file"
  if copy_inplace "$file" "$bak"; then
    echo "   ✅ Backed up → $bak"
    ((BACKUP_COUNT++)) || true
    AGENT_BACKED["$agent"]=$(( ${AGENT_BACKED["$agent"]:-0} + 1 ))
  else
    echo "   ⏭️  Skipped (write failed)"
    ((SKIPPED_COUNT++)) || true
    AGENT_SKIPPED["$agent"]=$(( ${AGENT_SKIPPED["$agent"]:-0} + 1 ))
  fi
done

# -----------------------------
# Backup models (recursive)
# -----------------------------
declare -A MODELS_BACKED_DIRS=()
for d in "${MODEL_DIRS[@]}"; do
  backup_directory "$d"
  rel="${d#$ROOT/}"
  if [[ "$rel" =~ ^agents/([^/]+)/models/ ]]; then
    agent="${BASH_REMATCH[1]}"
    MODELS_BACKED_DIRS["$agent"]=$(( ${MODELS_BACKED_DIRS["$agent"]:-0} + 1 ))
  else
    MODELS_BACKED_DIRS["_core"]=$(( ${MODELS_BACKED_DIRS["_core"]:-0} + 1 ))
  fi
done

# -----------------------------
# Summary
# -----------------------------
echo
echo "────────────────────────────────────────────"
echo "✅ Backup complete!"
echo "   • Files backed up : $BACKUP_COUNT"
echo "   • Files skipped   : $SKIPPED_COUNT"
echo "   • Model dirs (all): ${#MODEL_DIRS[@]}"
echo "Backup suffix used: ${BACKUP_EXT}"
echo "────────────────────────────────────────────"

# Unique agent keys seen
declare -A ALL_AGENTS=()
for f in "${!CATEGORY[@]}"; do ALL_AGENTS["${CATEGORY[$f]}"]=1; done
for a in "${!MODELS_BACKED_DIRS[@]}"; do ALL_AGENTS["$a"]=1; done
ALL_AGENTS["_core"]=1

agents_sorted=($(printf "%s\n" "${!ALL_AGENTS[@]}" | sort))

echo "Per-agent breakdown:"
for a in "${agents_sorted[@]}"; do
  b="${AGENT_BACKED[$a]:-0}"
  s="${AGENT_SKIPPED[$a]:-0}"
  m="${MODELS_BACKED_DIRS[$a]:-0}"
  printf "  • %-18s  files: %4d  skipped: %3d  model_dirs: %2d\n" "$a" "$b" "$s" "$m"
done
