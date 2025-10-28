#!/usr/bin/env bash
set -e
echo "🛑 Stopping all AI services..."
pkill -f "uvicorn.*8090" || true
pkill -f "uvicorn.*8091" || true
pkill -f "uvicorn.*8092" || true
echo "✅ All stopped."
