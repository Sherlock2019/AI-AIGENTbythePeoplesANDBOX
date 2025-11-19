#!/bin/bash
# Quick monitoring script - shows current status

API_URL="http://localhost:8090"

echo "🔍 Quick Status Check"
echo "===================="
echo ""

# Check API health
echo "📡 API Health:"
if curl -s --max-time 2 "$API_URL/health" > /dev/null 2>&1; then
    echo "  ✅ API is ONLINE"
    curl -s "$API_URL/health" | python3 -m json.tool 2>/dev/null || echo "  Response received"
else
    echo "  ⏳ API is OFFLINE (waiting for restart...)"
fi

echo ""
echo "📊 System Status:"
if curl -s --max-time 5 "$API_URL/v1/monitoring/status" > /dev/null 2>&1; then
    curl -s "$API_URL/v1/monitoring/status" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  API Healthy: {'✅' if data.get('api_healthy') else '❌'}\")
    print(f\"  Ollama: {'✅ Connected' if data.get('ollama_healthy') else '❌ Disconnected'}\")
    print(f\"  Active Connections: {data.get('active_connections', 0)}\")
    print(f\"  Recent Errors: {data.get('recent_errors', 0)}\")
    print(f\"  Avg Response Time: {data.get('avg_response_time_ms', 0):.0f}ms\")
except:
    print('  Status available')
" 2>/dev/null || echo "  Status endpoint available"
else
    echo "  ⏳ Monitoring not ready yet"
fi

echo ""
echo "📝 Recent Activity:"
if curl -s --max-time 5 "$API_URL/v1/monitoring/logs?limit=5" > /dev/null 2>&1; then
    curl -s "$API_URL/v1/monitoring/logs?limit=5" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    logs = data.get('logs', [])
    if logs:
        print(f\"  Last {len(logs)} log entries:\")
        for log in reversed(logs[-3:]):
            log_type = log.get('type', 'unknown')
            ts = log.get('timestamp', '')[:19]
            if log_type == 'error':
                print(f\"    ❌ [{ts}] {log.get('error', '')[:50]}\")
            elif log_type == 'response':
                print(f\"    ✅ [{ts}] {log.get('path', '')} - {log.get('status_code', 0)} ({log.get('duration_ms', 0):.0f}ms)\")
            elif log_type == 'chat_response':
                print(f\"    💬 [{ts}] Chat response ({log.get('duration_ms', 0):.0f}ms)\")
    else:
        print('  No logs yet')
except:
    print('  Logs available')
" 2>/dev/null || echo "  Logs endpoint available"
else
    echo "  ⏳ No logs yet"
fi

echo ""
echo "💡 Full monitoring: python3 monitor_live.py"
echo "💡 Dashboard: http://localhost:8502/log_monitor"
