#!/bin/bash
# Test phi3 LLM model

echo "🧪 Testing phi3 LLM Model"
echo "=" | head -c 60 && echo ""

API_URL="http://localhost:8090"
MODEL="phi3"

# Test 1: Simple question
echo ""
echo "Test 1: Simple question"
echo "-" | head -c 60 && echo ""
curl -s -X POST "$API_URL/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"What is credit appraisal?\",
    \"page_id\": \"credit_appraisal\",
    \"context\": {\"agent_type\": \"credit\"},
    \"model\": \"$MODEL\"
  }" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('✅ Response received!')
    print(f'Reply length: {len(data.get(\"reply\", \"\"))} chars')
    print(f'Mode: {data.get(\"mode\", \"\")}')
    print(f'Retrieved docs: {len(data.get(\"retrieved\", []))}')
    print('')
    print('Reply preview:')
    print(data.get('reply', '')[:300])
    print('...')
except Exception as e:
    print(f'❌ Error: {e}')
    print(sys.stdin.read()[:500])
"

# Test 2: Check if LLM was used
echo ""
echo "Test 2: Checking LLM usage in logs"
echo "-" | head -c 60 && echo ""
sleep 2
curl -s "$API_URL/v1/monitoring/logs?limit=5&type_filter=chat" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    logs = data.get('logs', [])
    chat_logs = [l for l in logs if 'chat' in l.get('type', '')]
    for log in reversed(chat_logs[-3:]):
        log_type = log.get('type', '')
        if log_type == 'chat_llm_success':
            print(f'✅ LLM SUCCESS: {log.get(\"duration_ms\", 0):.0f}ms')
        elif log_type == 'chat_llm_timeout':
            print(f'⏱️  LLM TIMEOUT: {log.get(\"duration_ms\", 0):.0f}ms')
        elif log_type == 'chat_response':
            llm_time = log.get('llm_time_ms', 0)
            if llm_time > 0:
                print(f'✅ LLM used: {llm_time:.0f}ms')
            else:
                print(f'⚠️  LLM not used (lightweight reply only)')
except Exception as e:
    print(f'Error checking logs: {e}')
"

# Test 3: Direct Ollama test
echo ""
echo "Test 3: Direct Ollama connection test"
echo "-" | head -c 60 && echo ""
curl -s -X POST "http://localhost:11434/api/generate" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"What is credit appraisal? Answer in one sentence.\",
    \"stream\": false,
    \"options\": {\"num_predict\": 50}
  }" --max-time 15 | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    response = data.get('response', '')
    if response:
        print(f'✅ Ollama $MODEL responding!')
        print(f'Response: {response[:200]}')
    else:
        print('⚠️  No response from Ollama')
except Exception as e:
    print(f'❌ Ollama error: {e}')
"

echo ""
echo "=" | head -c 60 && echo ""
echo "✅ Test complete!"
