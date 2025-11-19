#!/bin/bash
# Fix stuck Ollama processes and test models

echo "🔧 Fixing Ollama and Testing Models"
echo "===================================="
echo ""

# Step 1: Find and kill stuck Ollama runner processes
echo "Step 1: Checking for stuck Ollama processes..."
STUCK_PIDS=$(ps aux | grep "ollama runner" | grep -v grep | awk '{print $2}')

if [ -n "$STUCK_PIDS" ]; then
    echo "⚠️  Found stuck Ollama runner processes:"
    ps aux | grep "ollama runner" | grep -v grep
    echo ""
    echo "Killing stuck processes..."
    for PID in $STUCK_PIDS; do
        echo "  Killing PID $PID..."
        kill -9 $PID 2>/dev/null
    done
    sleep 2
    echo "✅ Stuck processes killed"
else
    echo "✅ No stuck processes found"
fi

echo ""

# Step 2: Check Ollama service
echo "Step 2: Checking Ollama service..."
if curl -s --max-time 2 http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama service is responding"
else
    echo "❌ Ollama service not responding"
    echo "   Try: sudo systemctl restart ollama"
    echo "   OR: pkill ollama && ollama serve &"
    exit 1
fi

echo ""

# Step 3: Wait a bit for models to unload
echo "Step 3: Waiting for models to unload..."
sleep 3

# Step 4: Test models
echo "Step 4: Testing models..."
echo ""
python3 test_all_models.py
