#!/usr/bin/env python3
"""Live monitoring script for chatbot system."""
import sys
import time
import json
import requests
from datetime import datetime
from typing import Dict, Any

API_URL = "http://localhost:8090"
CHECK_INTERVAL = 2  # Check every 2 seconds

def print_header():
    """Print monitoring header."""
    print("=" * 80)
    print("🔍 LIVE CHATBOT MONITORING")
    print("=" * 80)
    print(f"Monitoring API: {API_URL}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print("Press Ctrl+C to stop")
    print("=" * 80)
    print()

def check_api_health() -> bool:
    """Check if API is responding."""
    try:
        resp = requests.get(f"{API_URL}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False

def get_system_status() -> Dict[str, Any] | None:
    """Get system status."""
    try:
        resp = requests.get(f"{API_URL}/v1/monitoring/status", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def get_recent_logs(limit: int = 10) -> list:
    """Get recent logs."""
    try:
        resp = requests.get(
            f"{API_URL}/v1/monitoring/logs",
            params={"limit": limit},
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json().get("logs", [])
    except Exception:
        pass
    return []

def get_chat_performance() -> Dict[str, Any] | None:
    """Get chat performance metrics."""
    try:
        resp = requests.get(f"{API_URL}/v1/monitoring/chat/performance", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def format_timestamp(ts: str) -> str:
    """Format timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return ts[:19]

def print_status(status: Dict[str, Any]):
    """Print system status."""
    print(f"\n📊 SYSTEM STATUS - {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 80)
    
    # API Health
    api_status = "✅ HEALTHY" if status.get("api_healthy") else "❌ UNHEALTHY"
    print(f"API Status:        {api_status}")
    
    # Ollama Status
    ollama_status = "✅ CONNECTED" if status.get("ollama_healthy") else "❌ DISCONNECTED"
    print(f"Ollama Status:     {ollama_status}")
    
    if status.get("ollama_models"):
        models = ", ".join(status.get("ollama_models", [])[:3])
        print(f"Ollama Models:     {models}")
    
    # Metrics
    print(f"Active Connections: {status.get('active_connections', 0)}")
    print(f"Recent Errors:      {status.get('recent_errors', 0)}")
    
    avg_time = status.get("avg_response_time_ms", 0)
    if avg_time > 1000:
        print(f"Avg Response Time:  ⚠️  {avg_time:.0f}ms (SLOW)")
    elif avg_time > 500:
        print(f"Avg Response Time:  ℹ️  {avg_time:.0f}ms")
    else:
        print(f"Avg Response Time:  ✅ {avg_time:.0f}ms")

def print_recent_logs(logs: list):
    """Print recent logs."""
    if not logs:
        return
    
    print(f"\n📝 RECENT LOGS ({len(logs)} entries)")
    print("-" * 80)
    
    # Show last 5 logs
    for log in reversed(logs[-5:]):
        log_type = log.get("type", "unknown")
        timestamp = format_timestamp(log.get("timestamp", ""))
        
        if log_type == "error":
            error = log.get("error", "Unknown error")
            print(f"❌ [{timestamp}] ERROR: {error[:60]}")
        elif log_type == "response":
            path = log.get("path", "")
            status = log.get("status_code", 0)
            duration = log.get("duration_ms", 0)
            if duration > 1000:
                print(f"⚠️  [{timestamp}] {path} - {status} ({duration:.0f}ms) SLOW")
            elif status >= 400:
                print(f"⚠️  [{timestamp}] {path} - {status} ({duration:.0f}ms)")
            else:
                print(f"✅ [{timestamp}] {path} - {status} ({duration:.0f}ms)")
        elif log_type == "chat_response":
            duration = log.get("duration_ms", 0)
            rag_time = log.get("rag_time_ms", 0)
            llm_time = log.get("llm_time_ms", 0)
            print(f"💬 [{timestamp}] Chat Response: {duration:.0f}ms (RAG: {rag_time:.0f}ms, LLM: {llm_time:.0f}ms)")
        elif log_type == "chat_llm_timeout":
            duration = log.get("duration_ms", 0)
            error = log.get("error", "")
            print(f"⏱️  [{timestamp}] LLM TIMEOUT: {duration:.0f}ms - {error[:50]}")
        elif log_type == "chat_request":
            message = log.get("message", "")[:40]
            print(f"📨 [{timestamp}] Chat Request: {message}...")
        else:
            print(f"ℹ️  [{timestamp}] {log_type}: {log.get('path', '')}")

def print_chat_performance(perf: Dict[str, Any]):
    """Print chat performance."""
    print(f"\n⚡ CHAT PERFORMANCE")
    print("-" * 80)
    
    print(f"Total Requests:    {perf.get('chat_requests', 0)}")
    print(f"Total Responses:   {perf.get('chat_responses', 0)}")
    print(f"Total Errors:      {perf.get('chat_errors', 0)}")
    
    rt = perf.get("response_times", {})
    print(f"\nResponse Times:")
    print(f"  Average: {rt.get('avg_ms', 0):.0f}ms")
    print(f"  Min:     {rt.get('min_ms', 0):.0f}ms")
    print(f"  Max:     {rt.get('max_ms', 0):.0f}ms")
    
    slow_requests = perf.get("slow_requests", [])
    if slow_requests:
        print(f"\n⚠️  SLOW REQUESTS (>1s): {len(slow_requests)}")
        for req in slow_requests[-3:]:
            ts = format_timestamp(req.get("timestamp", ""))
            duration = req.get("duration_ms", 0)
            print(f"  - {ts}: {duration:.0f}ms")
    
    recent_errors = perf.get("recent_errors", [])
    if recent_errors:
        print(f"\n🐛 RECENT ERRORS: {len(recent_errors)}")
        for err in recent_errors[-3:]:
            ts = format_timestamp(err.get("timestamp", ""))
            error_type = err.get("error_type", "Unknown")
            error_msg = err.get("error", "")[:50]
            print(f"  - {ts}: {error_type} - {error_msg}")

def main():
    """Main monitoring loop."""
    print_header()
    
    consecutive_failures = 0
    last_status_time = None
    
    try:
        while True:
            # Check if API is up
            if not check_api_health():
                consecutive_failures += 1
                if consecutive_failures == 1:
                    print(f"\n⏳ Waiting for API to start... ({datetime.now().strftime('%H:%M:%S')})")
                elif consecutive_failures % 5 == 0:
                    print(f"⏳ Still waiting... ({datetime.now().strftime('%H:%M:%S')})")
                time.sleep(CHECK_INTERVAL)
                continue
            
            # API is up
            if consecutive_failures > 0:
                print(f"\n✅ API is now ONLINE! ({datetime.now().strftime('%H:%M:%S')})")
                consecutive_failures = 0
            
            # Get status
            status = get_system_status()
            if status:
                print_status(status)
                last_status_time = time.time()
            
            # Get recent logs
            logs = get_recent_logs(limit=10)
            if logs:
                print_recent_logs(logs)
            
            # Get chat performance
            perf = get_chat_performance()
            if perf and perf.get("chat_requests", 0) > 0:
                print_chat_performance(perf)
            
            print("\n" + "=" * 80)
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Monitoring error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
