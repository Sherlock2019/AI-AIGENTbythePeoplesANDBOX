#!/usr/bin/env bash
set -e
echo "🚀 Starting AI Hub and all agents..."
uvicorn services.api.main:app --port 8090 --reload > .hub.log 2>&1 &
cd agents/credit-appraisal && uvicorn main:app --port 8091 --reload > ../../.credit.log 2>&1 &
cd ../asset-appraisal && uvicorn main:app --port 8092 --reload > ../../.asset.log 2>&1 &
echo "✅ All services running (hub:8090, credit:8091, asset:8092)"
