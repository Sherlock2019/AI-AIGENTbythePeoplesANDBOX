#!/usr/bin/env bash
set -euo pipefail

# ============================================
# 🧹 Streamlit Page Cleanup Utility
# Keeps only main agent pages in /pages/
# Moves all others to /pages/_old/
# ============================================

# Define your base path
PAGES_DIR="services/ui/pages"
ARCHIVE_DIR="${PAGES_DIR}/_old"

# Ensure folder exists
mkdir -p "${ARCHIVE_DIR}"

# List of core production pages to KEEP
KEEP_FILES=(
  "asset_appraisal.py"
  "credit_appraisal.py"
)

echo "🧠 Scanning ${PAGES_DIR} for extra Streamlit pages..."

# Loop through all .py files
for f in "${PAGES_DIR}"/*.py; do
  fname=$(basename "$f")
  # Check if in KEEP list
  if [[ " ${KEEP_FILES[*]} " =~ " ${fname} " ]]; then
    echo "✅ Keeping: ${fname}"
  else
    echo "📦 Archiving: ${fname}"
    mv "$f" "${ARCHIVE_DIR}/" || echo "⚠️ Could not move ${fname}"
  fi
done

echo
echo "✨ Cleanup complete!"
echo "✅ Active pages: ${KEEP_FILES[*]}"
echo "📂 Archived old pages under: ${ARCHIVE_DIR}"
