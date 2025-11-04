#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# 🔍 show_related_files.sh
# Show (cat) all connected files for a given main file
# Author: Nguyen Dzoan
# ─────────────────────────────────────────────

ROOT="${ROOT:-$HOME/credit-appraisal-agent-poc}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <main_file>"
  echo "Example: $0 services/ui/pages/asset_appraisal.py"
  exit 1
fi

MAIN_FILE="$1"
CONNECTION_FILE="$ROOT/.connections.yml"

# ─────────────────────────────────────────────
# Validate
# ─────────────────────────────────────────────
if [[ ! -f "$CONNECTION_FILE" ]]; then
  echo "❌ Missing: $CONNECTION_FILE"
  echo "Create one using: tools/update_connections.sh"
  exit 1
fi

if ! grep -q "$MAIN_FILE" "$CONNECTION_FILE"; then
  echo "⚠️ No connections listed for $MAIN_FILE"
  exit 0
fi

# ─────────────────────────────────────────────
# Extract and cat each related file
# ─────────────────────────────────────────────
echo "🧩 Connected files for: $MAIN_FILE"
echo "──────────────────────────────────────────────"
grep -A20 "$MAIN_FILE" "$CONNECTION_FILE" | grep "path:" | awk '{print $2}' | while read -r rel; do
  FILE="$ROOT/$rel"
  if [[ -f "$FILE" ]]; then
    echo -e "\n📄 $rel\n──────────────────────────────"
    cat "$FILE"
  else
    echo "⚠️ Missing: $FILE"
  fi
done
