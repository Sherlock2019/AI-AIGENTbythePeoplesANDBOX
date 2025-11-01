#!/usr/bin/env bash
set -euo pipefail

# Backup selected Python files to .bak
# - Prompts per file (always continues regardless of input)
# - Overwrites only on 'Y' or 'y'
# - Skips others but never aborts

BACKUP_EXT=".bak"

FILES=(
  "/home/dzoan/credit-appraisal-agent-poc/services/ui/app.py"
  "/home/dzoan/credit-appraisal-agent-poc/services/api/routers/agents.py"
  "/home/dzoan/credit-appraisal-agent-poc/services/api/routers/reports.py"
  "/home/dzoan/credit-appraisal-agent-poc/services/api/routers/settings.py"
  "/home/dzoan/credit-appraisal-agent-poc/agent_platform/agent_sdk/sdk.py"
  "/home/dzoan/credit-appraisal-agent-poc/agents/credit_appraisal/agent.py"
  "/home/dzoan/credit-appraisal-agent-poc/agents/credit_appraisal/model_utils.py"
  "/home/dzoan/credit-appraisal-agent-poc/app.py"
  "/home/dzoan/credit-appraisal-agent-poc/services/api/main.py"
)

echo "📋 Target files to back up:"
missing=0
declare -a EXISTING=()
for f in "${FILES[@]}"; do
  if [[ -f "$f" ]]; then
    echo "   • $f"
    EXISTING+=("$f")
  else
    echo "   • $f   (❌ not found)"
    (( ++missing ))   # pre-increment avoids set -e trap
  fi
done

if (( ${#EXISTING[@]} == 0 )); then
  echo "❌ None of the listed files exist. Exiting."
  exit 1
fi

echo
if (( missing > 0 )); then
  echo "⚠️  $missing file(s) above not found and will be skipped."
fi

read -p "Proceed with backup of the existing files listed above? [y/N] " -n 1 -r
echo

echo
echo "🚀 Starting selective backup process..."
echo

BACKUP_COUNT=0
SKIPPED_COUNT=0

for file in "${EXISTING[@]}"; do
  bak_file="${file}${BACKUP_EXT}"
  echo "➡️  Processing: $file"

  if [[ -f "$bak_file" ]]; then
    echo "   ⚠️  Backup already exists: $bak_file"
    read -p "   Overwrite it? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      cp -f "$file" "$bak_file"
      echo "   ✅ Overwritten → $bak_file"
      (( ++BACKUP_COUNT ))   # pre-increment (safe with set -e)
    else
      echo "   ⏭️  Skipped $file"
      (( ++SKIPPED_COUNT ))
    fi
  else
    read -p "   Create new backup? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      cp -f "$file" "$bak_file"
      echo "   ✅ Backed up → $bak_file"
      (( ++BACKUP_COUNT ))
    else
      echo "   ⏭️  Skipped $file"
      (( ++SKIPPED_COUNT ))
    fi
  fi

  echo "────────────────────────────────────────────"
done

echo
echo "🎯 Backup complete — $BACKUP_COUNT file(s) backed up, $SKIPPED_COUNT skipped."
echo "✅ Script finished successfully (never aborted)."
