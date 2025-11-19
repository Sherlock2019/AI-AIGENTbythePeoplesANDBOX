#!/bin/bash
# Test all Ollama models directly (standalone, no API)

OLLAMA_URL="http://localhost:11434"
TEST_PROMPT="What is credit appraisal? Answer in one sentence."
TIMEOUT=30

echo "🧪 Testing All Ollama Models Directly"
echo "======================================"
echo ""
echo "Ollama URL: $OLLAMA_URL"
echo "Test Prompt: $TEST_PROMPT"
echo "Timeout: ${TIMEOUT}s per model"
echo ""
echo "======================================"
echo ""

# Step 1: Get list of available models
echo "📋 Step 1: Fetching available models..."
MODELS_JSON=$(curl -s --max-time 5 "$OLLAMA_URL/api/tags")

if [ $? -ne 0 ] || [ -z "$MODELS_JSON" ]; then
    echo "❌ Failed to connect to Ollama at $OLLAMA_URL"
    echo "   Make sure Ollama is running: ollama serve"
    exit 1
fi

# Extract model names
MODELS=$(echo "$MODELS_JSON" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    for m in models:
        print(m.get('name', ''))
except:
    pass
" 2>/dev/null)

if [ -z "$MODELS" ]; then
    echo "❌ No models found or error parsing model list"
    exit 1
fi

MODEL_COUNT=$(echo "$MODELS" | wc -l)
echo "✅ Found $MODEL_COUNT model(s)"
echo ""

# Step 2: Test each model
echo "🚀 Step 2: Testing each model..."
echo ""

SUCCESS_COUNT=0
FAIL_COUNT=0
TIMEOUT_COUNT=0
RESULTS=()

for MODEL in $MODELS; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing: $MODEL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    START_TIME=$(date +%s.%N)
    
    # Test the model
    RESPONSE=$(timeout $TIMEOUT curl -s -X POST "$OLLAMA_URL/api/generate" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$MODEL\",
            \"prompt\": \"$TEST_PROMPT\",
            \"stream\": false,
            \"options\": {
                \"num_predict\": 50,
                \"temperature\": 0.7
            }
        }" 2>&1)
    
    EXIT_CODE=$?
    END_TIME=$(date +%s.%N)
    DURATION=$(echo "$END_TIME - $START_TIME" | bc)
    
    if [ $EXIT_CODE -eq 124 ]; then
        echo "⏱️  TIMEOUT after ${TIMEOUT}s"
        TIMEOUT_COUNT=$((TIMEOUT_COUNT + 1))
        RESULTS+=("$MODEL|TIMEOUT|${TIMEOUT}s")
    elif [ $EXIT_CODE -ne 0 ]; then
        echo "❌ ERROR (exit code: $EXIT_CODE)"
        echo "   Response: ${RESPONSE:0:100}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        RESULTS+=("$MODEL|ERROR|$EXIT_CODE")
    else
        # Parse response
        RESPONSE_TEXT=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    response = data.get('response', '')
    done = data.get('done', False)
    if response:
        print(f'✅ SUCCESS')
        print(f'Response: {response[:200]}')
        print(f'Done: {done}')
        print(f'Duration: {sys.argv[1]:.2f}s' if len(sys.argv) > 1 else '')
    else:
        print('⚠️  NO RESPONSE TEXT')
        print(f'Keys: {list(data.keys())}')
except Exception as e:
    print(f'❌ PARSE ERROR: {e}')
    print(f'Raw: {sys.stdin.read()[:200]}')
" "$DURATION" 2>/dev/null)
        
        if echo "$RESPONSE_TEXT" | grep -q "✅ SUCCESS"; then
            echo "$RESPONSE_TEXT"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
            RESULTS+=("$MODEL|SUCCESS|${DURATION}s")
        else
            echo "$RESPONSE_TEXT"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            RESULTS+=("$MODEL|FAILED|Parse error")
        fi
    fi
    
    echo ""
done

# Step 3: Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 TEST SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Total Models Tested: $MODEL_COUNT"
echo "✅ Successful: $SUCCESS_COUNT"
echo "❌ Failed: $FAIL_COUNT"
echo "⏱️  Timeouts: $TIMEOUT_COUNT"
echo ""

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo "✅ Working Models:"
    for result in "${RESULTS[@]}"; do
        MODEL=$(echo "$result" | cut -d'|' -f1)
        STATUS=$(echo "$result" | cut -d'|' -f2)
        TIME=$(echo "$result" | cut -d'|' -f3)
        if [ "$STATUS" = "SUCCESS" ]; then
            echo "   - $MODEL ($TIME)"
        fi
    done
    echo ""
fi

if [ $TIMEOUT_COUNT -gt 0 ]; then
    echo "⏱️  Timed Out Models:"
    for result in "${RESULTS[@]}"; do
        MODEL=$(echo "$result" | cut -d'|' -f1)
        STATUS=$(echo "$result" | cut -d'|' -f2)
        if [ "$STATUS" = "TIMEOUT" ]; then
            echo "   - $MODEL"
        fi
    done
    echo ""
fi

if [ $FAIL_COUNT -gt 0 ]; then
    echo "❌ Failed Models:"
    for result in "${RESULTS[@]}"; do
        MODEL=$(echo "$result" | cut -d'|' -f1)
        STATUS=$(echo "$result" | cut -d'|' -f2)
        if [ "$STATUS" != "SUCCESS" ] && [ "$STATUS" != "TIMEOUT" ]; then
            echo "   - $MODEL ($STATUS)"
        fi
    done
    echo ""
fi

# Exit code based on results
if [ $SUCCESS_COUNT -eq 0 ]; then
    echo "❌ No models working - check Ollama service"
    exit 1
elif [ $FAIL_COUNT -gt 0 ] || [ $TIMEOUT_COUNT -gt 0 ]; then
    echo "⚠️  Some models have issues"
    exit 2
else
    echo "✅ All models working correctly!"
    exit 0
fi
