#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
# SMART FILE BACKUP TOOL
# Makes a timestamped .bak copy of each important file
# in its original directory.
#
# Example:
#   app.py → app.py.bak.2025-10-21_23-59
#   credit_model.pkl → credit_model.pkl.bak.2025-10-21_23-59
#
# Usage:
#   chmod +x smart_file_backup.sh
#   ./smart_file_backup.sh
# ──────────────────────────────────────────────

ROOT="${ROOT:-$HOME/credit-appraisal-agent-poc}"
DATESTAMP=$(date '+%Y-%m-%d_%H-%M')
echo "📦 Creating per-file backups with timestamp $DATESTAMP"
echo "→ Workspace: $ROOT"
echo

# Directories to scan for backup files
TARGET_DIRS=(
  "$ROOT/agents"
  "$ROOT/services"
  "$ROOT/samples"
  "$ROOT/models"
)

# File patterns to backup
PATTERNS=("*.py" "*.pkl" "*.json" "*.csv" "*.yaml" "*.yml" "*.ini" "*.cfg" "*.txt" "requirements.txt")

# Loop through directories and copy each file with .bak.<timestamp>
for DIR in "${TARGET_DIRS[@]}"; do
  [[ -d "$DIR" ]] || continue
  echo "📂 Scanning $DIR ..."
  for pattern in "${PATTERNS[@]}"; do
    shopt -s nullglob
    for file in "$DIR"/$pattern; do
      [[ -f "$file" ]] || continue
      backup_file="${file}.bak.${DATESTAMP}"
      cp -p "$file" "$backup_file"
      echo "  • $file → $(basename "$backup_file")"
    done
  done
done

echo
echo "✅ All backups created in-place."
echo "Each file now has its versioned .bak.$DATESTAMP copy."
echo
echo "🧠 Example restore:"
echo "  cp app.py.bak.${DATESTAMP} app.py"
