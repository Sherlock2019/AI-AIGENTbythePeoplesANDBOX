
#!/usr/bin/env bash
set -e
cd /home/dzoan/AiLib/AI-AIGENTbythePeoplesANDBOX
git add .
git commit -m "🧠 Auto push at $(date '+%Y-%m-%d %H:%M:%S')"
git push -u origin main
EOF

chmod +x push.sh
