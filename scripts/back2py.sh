#!/usr/bin/env bash
set -euo pipefail

# Restore every "*.bak.py" file back to "*.py"
# Example: app.bak.py → app.py

ROOT="/home/dzoan/credit-appraisal-agent-poc"

echo "🔄 Restoring all '*.bak.py' files under: $ROOT"
echo

mapfile -t BAK_FILES < <(find "$ROOT" -type f -name "*.bak.py")

if (( ${#BAK_FILES[@]} == 0 )); then
  echo "❌ No *.bak.py files found."
  exit 0
fi

for bak_file in "${BAK_FILES[@]}"; do
  orig_file="${bak_file%.bak.py}.py"
  echo "➡️  Found backup: $bak_file"
  echo "    Target restore path: $orig_file"

  if [[ -f "$orig_file" ]]; then
    read -p "   Overwrite existing $orig_file ? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      cp -f "$bak_file" "$orig_file"
      echo "   ✅ Restored → $orig_file"
    else
      echo "   ⏭️  Skipped"
    fi
  else
    read -p "   No existing file. Create new $orig_file from backup? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      cp "$bak_file" "$orig_file"
      echo "   ✅ Created new $orig_file"
    else
      echo "   ⏭️  Skipped"
    fi
  fi
  echo "────────────────────────────────────────────"
done

echo
echo "🎯 Restore process completed."

