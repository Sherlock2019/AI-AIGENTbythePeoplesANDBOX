# Live Log Monitoring Guide

## 🎯 Overview

A comprehensive live log monitoring system has been created to track chatbot connections, troubleshoot timeout issues, and monitor performance in real-time.

## 📁 Components Created

### 1. **Logging Middleware** (`services/api/middleware/logging_middleware.py`)
- Captures all HTTP requests and responses
- Tracks response times
- Logs errors and exceptions
- Maintains in-memory buffer (last 1000 entries)

### 2. **Monitoring API** (`services/api/routers/monitoring.py`)
- `/v1/monitoring/logs` - Get recent log entries
- `/v1/monitoring/logs/stream` - Real-time log streaming (SSE)
- `/v1/monitoring/status` - System health status
- `/v1/monitoring/metrics` - Performance metrics
- `/v1/monitoring/chat/performance` - Chat-specific metrics
- `/v1/monitoring/logs/clear` - Clear log buffer

### 3. **Streamlit Dashboard** (`services/ui/pages/log_monitor.py`)
- Real-time log viewing
- System status monitoring
- Performance metrics visualization
- Chat endpoint debugging

## 🚀 Usage

### Access the Monitoring Dashboard

1. **Via Streamlit UI**:
   ```
   Navigate to: http://localhost:8502/log_monitor
   ```

2. **Via API Endpoints**:
   ```bash
   # Get system status
   curl http://localhost:8090/v1/monitoring/status
   
   # Get recent logs
   curl http://localhost:8090/v1/monitoring/logs?limit=50
   
   # Get chat performance
   curl http://localhost:8090/v1/monitoring/chat/performance
   
   # Stream logs (SSE)
   curl http://localhost:8090/v1/monitoring/logs/stream
   ```

### Dashboard Features

#### Tab 1: System Status
- API health check
- Ollama connection status
- Active connections count
- Recent errors count
- Available Ollama models
- Average response time

#### Tab 2: Live Logs
- Real-time request/response logs
- Color-coded by type (error/warning/success)
- Filterable by log type
- Expandable details for each log entry
- Auto-refresh capability

#### Tab 3: Performance Metrics
- Total requests/responses/errors
- Response time statistics (min/max/avg/p95/p99)
- Status code distribution
- Top endpoints by request count
- Errors by type

#### Tab 4: Chat Debug
- Chat-specific metrics
- Response time breakdown
- Slow requests (>1s) highlighted
- Recent errors with details
- RAG/LLM timing breakdown

## 🔍 Troubleshooting Timeout Issues

### Key Metrics to Monitor

1. **Response Times**:
   - Check average response time
   - Look for requests >1000ms (slow)
   - Monitor P95/P99 percentiles

2. **LLM Timeouts**:
   - Filter logs by `chat_llm_timeout`
   - Check LLM duration in chat responses
   - Verify Ollama connection status

3. **RAG Performance**:
   - Monitor `rag_time_ms` in chat responses
   - Check `retrieved_count` (should be >0)
   - Verify RAG store is loaded

4. **Error Patterns**:
   - Check `errors_by_type` in metrics
   - Look for connection errors
   - Monitor status code distribution

### Example Troubleshooting Workflow

1. **Check System Status**:
   ```bash
   curl http://localhost:8090/v1/monitoring/status
   ```
   - Verify API is healthy
   - Verify Ollama is connected
   - Check for recent errors

2. **Monitor Live Logs**:
   - Open dashboard: `http://localhost:8502/log_monitor`
   - Watch for slow requests (>1000ms)
   - Filter by `chat_llm_timeout` to see LLM issues

3. **Analyze Chat Performance**:
   ```bash
   curl http://localhost:8090/v1/monitoring/chat/performance
   ```
   - Check average response time
   - Review slow requests
   - Check recent errors

4. **Check Specific Request**:
   - Find request in logs
   - Expand details to see:
     - Total duration
     - RAG time
     - LLM time
     - Error details

## 📊 Log Entry Types

### Request Logs (`type: "request"`)
- Method, path, query params
- Client IP
- Request body (if available)

### Response Logs (`type: "response"`)
- Status code
- Duration in milliseconds
- Response body (if available)

### Error Logs (`type: "error"`)
- Error message
- Error type
- Duration before error

### Chat-Specific Logs
- `chat_request` - Chat request received
- `chat_response` - Chat response sent (with timing breakdown)
- `chat_llm_success` - LLM enhancement succeeded
- `chat_llm_timeout` - LLM call timed out
- `chat_llm_empty` - LLM returned empty response

## 🎨 Dashboard Controls

### Sidebar Options
- **Auto-refresh**: Enable/disable automatic refresh
- **Refresh interval**: Set refresh rate (1-10 seconds)
- **Log entries**: Number of logs to display (10-500)
- **Filter by type**: Filter logs by type
- **Clear Logs**: Clear the log buffer

## 🔧 API Integration

### Python Example
```python
import requests

# Get system status
status = requests.get("http://localhost:8090/v1/monitoring/status").json()
print(f"API Healthy: {status['api_healthy']}")
print(f"Ollama Connected: {status['ollama_healthy']}")

# Get chat performance
perf = requests.get("http://localhost:8090/v1/monitoring/chat/performance").json()
print(f"Average response time: {perf['response_times']['avg_ms']}ms")
print(f"Slow requests: {len(perf['slow_requests'])}")
```

### JavaScript Example (SSE Streaming)
```javascript
const eventSource = new EventSource('http://localhost:8090/v1/monitoring/logs/stream');
eventSource.onmessage = (event) => {
    const log = JSON.parse(event.data);
    console.log('New log:', log);
};
```

## 📈 Performance Benchmarks

### Expected Response Times
- **RAG Query**: <100ms
- **TF-IDF Fallback**: <300ms
- **LLM Enhancement**: 0-10s (optional)
- **Total Response**: <1s (with lightweight reply)

### Warning Thresholds
- Response time >1000ms: Slow request
- LLM timeout: Expected if Ollama is slow
- Error rate >5%: Investigate

## 🐛 Common Issues & Solutions

### Issue: High Response Times
**Check**:
- LLM timeout logs
- RAG query performance
- System load

**Solution**:
- Verify Ollama is running
- Check RAG store is loaded
- Monitor system resources

### Issue: LLM Timeouts
**Check**:
- Filter logs by `chat_llm_timeout`
- Ollama connection status
- Model availability

**Solution**:
- Verify Ollama is accessible
- Check model is loaded
- Consider reducing timeout or disabling LLM

### Issue: No Logs Appearing
**Check**:
- API is running
- Middleware is registered
- Log buffer is not cleared

**Solution**:
- Restart API server
- Verify middleware is added
- Check log buffer size

## ✅ Status

**Live log monitoring system is fully operational!**

- ✅ Logging middleware captures all requests
- ✅ Monitoring API provides metrics
- ✅ Streamlit dashboard for visualization
- ✅ Real-time log streaming
- ✅ Chat-specific debugging
- ✅ Performance metrics tracking

Access the dashboard at: `http://localhost:8502/log_monitor`
