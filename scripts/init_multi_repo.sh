#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: init_multi_repo.sh [options]

Options:
  --workspace PATH             Root workspace directory (default: "${PWD}/rackspace-aisandbox")
  --credit-agent URL           Git URL for credit appraisal agent (optional)
  --credit-branch BRANCH       Branch/tag for credit agent (default: repo default)
  --asset-agent URL            Git URL for asset appraisal agent (optional)
  --asset-branch BRANCH        Branch/tag for asset agent (default: repo default)
  --with-shared-sdk            Include shared-agent-sdk scaffold
  --skip-hub                   Do not create the ai-agent-hub scaffold
  -h, --help                   Show this message
USAGE
}

WORKSPACE="${PWD}/rackspace-aisandbox"
CREDIT_AGENT_URL=""
CREDIT_AGENT_BRANCH=""
ASSET_AGENT_URL=""
ASSET_AGENT_BRANCH=""
WITH_SHARED_SDK=0
SKIP_HUB=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace)
      WORKSPACE="$2"; shift 2;;
    --credit-agent)
      CREDIT_AGENT_URL="$2"; shift 2;;
    --credit-branch)
      CREDIT_AGENT_BRANCH="$2"; shift 2;;
    --asset-agent)
      ASSET_AGENT_URL="$2"; shift 2;;
    --asset-branch)
      ASSET_AGENT_BRANCH="$2"; shift 2;;
    --with-shared-sdk)
      WITH_SHARED_SDK=1; shift;;
    --skip-hub)
      SKIP_HUB=1; shift;;
    -h|--help)
      usage; exit 0;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1;;
  esac
done

create_repo_dir() {
  local path="$1"
  if [[ -d "$path/.git" ]]; then
    echo "⚠️  Repo already initialized at $path (skipping)."
  else
    mkdir -p "$path"
  fi
}

echo "🚀  Creating AI agent workspace at $WORKSPACE"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

if [[ $WITH_SHARED_SDK -eq 1 ]]; then
  echo "📦  Seeding shared-agent-sdk"
  create_repo_dir "shared-agent-sdk"
  cat > shared-agent-sdk/README.md <<'DOC'
# 🧩 Shared Agent SDK

Common utilities for Rackspace AI agents (I/O helpers, anonymization, data loaders).
DOC
  mkdir -p shared-agent-sdk/shared_agent_sdk
  cat > shared-agent-sdk/shared_agent_sdk/__init__.py <<'PY'
"""Shared SDK utilities."""
import json
import os
from typing import Any

def save_json(data: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
PY
  cat > shared-agent-sdk/requirements.txt <<'REQ'
numpy
pandas
REQ
fi

if [[ $SKIP_HUB -eq 0 ]]; then
  echo "🧠  Seeding ai-agent-hub"
  create_repo_dir "ai-agent-hub"
  mkdir -p ai-agent-hub/services/api
  cat > ai-agent-hub/services/api/main.py <<'PY'
from fastapi import FastAPI, Request
import yaml
import httpx

app = FastAPI(title="AI Agent Hub")
registry = {}

@app.on_event("startup")
async def load_registry() -> None:
    global registry
    try:
        with open("agent_registry.yaml", "r", encoding="utf-8") as f:
            registry.update(yaml.safe_load(f) or {})
    except FileNotFoundError:
        registry.clear()

@app.get("/health")
async def health() -> dict:
    return {"status": "hub ok"}

@app.post("/run/{agent_name}")
async def run_agent(agent_name: str, request: Request) -> dict:
    if agent_name not in registry.get("agents", {}):
        return {"error": f"Unknown agent: {agent_name}"}
    payload = await request.json()
    agent_cfg = registry["agents"][agent_name]
    url = agent_cfg["url"].rstrip("/") + "/run"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()
PY
  cat > ai-agent-hub/requirements.txt <<'REQ'
fastapi
uvicorn[standard]
pyyaml
httpx
REQ
  cat > ai-agent-hub/README.md <<'DOC'
# 🧠 AI Agent Hub

FastAPI orchestrator that routes requests to registered agents defined in `agent_registry.yaml`.

## Quick Start
```bash
uvicorn services.api.main:app --reload --port 8090
```
DOC
  if [[ ! -f ai-agent-hub/agent_registry.yaml ]]; then
    cp "${OLDPWD}/infra/agent_registry.example.yaml" ai-agent-hub/agent_registry.yaml 2>/dev/null || true
  fi
fi

seed_agent_repo() {
  local dir="$1" url="$2" branch="$3"
  [[ -z "$url" ]] && return
  echo "🔗  Cloning $url into $dir"
  if [[ -d "$dir/.git" ]]; then
    echo "   Repo already exists, skipping clone"
  else
    git clone "$url" "$dir"
    if [[ -n "$branch" ]]; then
      (cd "$dir" && git checkout "$branch")
    fi
  fi
}

seed_agent_repo "agent-credit-appraisal" "$CREDIT_AGENT_URL" "$CREDIT_AGENT_BRANCH"
seed_agent_repo "agent-asset-appraisal" "$ASSET_AGENT_URL" "$ASSET_AGENT_BRANCH"

echo "✅  Workspace ready at $WORKSPACE"
