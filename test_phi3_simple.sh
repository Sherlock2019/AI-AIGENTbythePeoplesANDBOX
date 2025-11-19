#!/bin/bash
# Simple test for phi3 LLM model

echo "🧪 Testing phi3 LLM Model"
echo "================================"
echo ""

# Test 1: Simple chat test
echo "Test 1: Chat API with phi3"
curl -s -X POST http://localhost:8090/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"test","page_id":"chatbot_assistant","model":"phi3"}' \
  --max-time 15 | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Reply:', d.get('reply','')[:200]); print('Length:', len(d.get('reply','')), 'chars')"

echo ""
echo ""

# Test 2: Direct Ollama test
echo "Test 2: Direct Ollama phi3 test"
curl -s -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"phi3","prompt":"Hello, what is credit appraisal?","stream":false,"options":{"num_predict":50}}' \
  --max-time 15 | python3 -c "import sys,json; d=json.load(sys.stdin); print('✅ Ollama Response:', d.get('response','')[:200])"

echo ""
echo ""

# Test 3: Check logs
echo "Test 3: Check if LLM was used"
sleep 2
curl -s "http://localhost:8090/v1/monitoring/logs?limit=5&type_filter=chat" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    logs = [l for l in data.get('logs', []) if 'chat' in l.get('type', '')]
    if logs:
        for log in reversed(logs[-2:]):
            if log.get('type') == 'chat_llm_success':
                print('✅ LLM SUCCESS:', log.get('duration_ms', 0), 'ms')
            elif log.get('type') == 'chat_llm_timeout':
                print('⏱️  LLM TIMEOUT:', log.get('duration_ms', 0), 'ms')
            elif log.get('type') == 'chat_response':
                llm_time = log.get('llm_time_ms', 0)
                if llm_time > 0:
                    print('✅ LLM used:', llm_time, 'ms')
                else:
                    print('⚠️  LLM not used (lightweight reply only)')
    else:
        print('No chat logs found')
except Exception as e:
    print('Error:', e)
"

echo ""
echo "✅ Test complete!"
