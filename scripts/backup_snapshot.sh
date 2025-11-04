#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# RAX AI SANDBOX SNAPSHOT TOOL
# Creates a timestamped ZIP backup of your full working environment:
#   - agents/, services/, samples/, models/, .runs/, configs, logs
# Saved to ~/credit-appraisal-agent-poc/backups/rax_ai_sandbox_snapshot_YYYY-MM-DD_HH-MM.zip
#
# Usage:
#   chmod +x backup_snapshot.sh
#   ./backup_snapshot.sh
# ──────────────────────────────────────────────────────────────

ROOT="${ROOT:-$HOME/credit-appraisal-agent-poc}"
BACKUP_DIR="$ROOT/backups"
DATESTAMP=$(date '+%Y-%m-%d_%H-%M')
SNAPSHOT_FILE="$BACKUP_DIR/rax_ai_sandbox_snapshot_${DATESTAMP}.zip"

echo "📦 Creating snapshot of RAX AI Sandbox"
echo "→ Workspace : $ROOT"
echo "→ Output    : $SNAPSHOT_FILE"

mkdir -p "$BACKUP_DIR"

TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

# Define include paths
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

# Add optional config directories if present
for D in ".env" ".configs" ".runs" ".logs"; do
  [[ -d "$ROOT/$D" ]] && INCLUDE_PATHS+=("$D")
done

echo "• Collecting files..."
{
  echo "Snapshot created at $(date)"
  echo "Root: $ROOT"
  echo "Included paths:"
  for p in "${INCLUDE_PATHS[@]}"; do
    echo "  - $p"
  done
} > "$TMPFILE"

echo "• Writing ZIP archive..."
cd "$ROOT"
zip -r "$SNAPSHOT_FILE" "${INCLUDE_PATHS[@]}" -x "*.pyc" "__pycache__/*" "*.tmp" "*.log" > /dev/null

# Append manifest
zip -j "$SNAPSHOT_FILE" "$TMPFILE" >/dev/null

echo "✅ Snapshot complete"
echo "→ Saved: $SNAPSHOT_FILE"
echo
echo "To restore later:"
echo "  unzip $SNAPSHOT_FILE -d $ROOT"
