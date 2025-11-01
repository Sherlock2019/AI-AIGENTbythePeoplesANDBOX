#!/usr/bin/env bash
set -euo pipefail
cd "/home/dzoan/credit-appraisal-agent-poc/services/api"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="phi3"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
nohup uvicorn services.api.main:app --host 0.0.0.0 --port 8080 --reload > api.out 2>&1 &
echo $! > api.pid
echo "API started on http://localhost:8080 (PID: $(cat api.pid))"
