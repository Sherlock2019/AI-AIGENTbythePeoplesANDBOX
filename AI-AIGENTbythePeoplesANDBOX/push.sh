#!/usr/bin/env bash
set -e

if [ "$EUID" -eq 0 ]; then
  echo "🚫 Do not run as root. Please run as normal user (dzoan)."
  exit 1
fi

cd /home/dzoan/AiLib/AI-AIGENTbythePeoplesANDBOX
git add .
git commit -m "🧠 Auto push at $(date '+%Y-%m-%d %H:%M:%S')"
git push -u origin main
