"""Monitoring and log viewing endpoints."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.api.middleware.logging_middleware import (
    add_log_entry,
    clear_logs,
    get_recent_logs,
)
from services.api.middleware.visitor_tracker import (
    get_all_visitors,
    get_visitor_stats,
    load_visitor_data,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["monitoring"])

OLLAMA_URL = "http://localhost:11434"
API_URL = "http://localhost:8090"


class LogEntry(BaseModel):
    timestamp: str
    type: str
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    duration_ms: float | None = None
    error: str | None = None
    error_type: str | None = None
    body: Any = None


class SystemStatus(BaseModel):
    api_healthy: bool
    ollama_healthy: bool
    ollama_models: List[str]
    active_connections: int
    recent_errors: int
    avg_response_time_ms: float


@router.get("/v1/monitoring/logs")
def get_logs(limit: int = 100, type_filter: str | None = None) -> Dict[str, Any]:
    """Get recent log entries."""
    logs = get_recent_logs(limit=limit)
    
    if type_filter:
        logs = [log for log in logs if log.get("type") == type_filter]
    
    return {
        "logs": logs,
        "count": len(logs),
        "total_in_buffer": len(get_recent_logs(limit=10000)),
    }


@router.get("/v1/monitoring/logs/stream")
def stream_logs():
    """Stream logs in real-time using Server-Sent Events."""
    
    def generate():
        last_count = 0
        while True:
            logs = get_recent_logs(limit=1000)
            current_count = len(logs)
            
            # Send new logs
            if current_count > last_count:
                new_logs = logs[last_count:]
                for log in new_logs:
                    yield f"data: {json.dumps(log)}\n\n"
                last_count = current_count
            
            time.sleep(0.5)  # Check every 500ms
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/v1/monitoring/status")
def get_system_status() -> SystemStatus:
    """Get system status and health metrics."""
    # Check API health
    api_healthy = False
    try:
        resp = requests.get(f"{API_URL}/health", timeout=2)
        api_healthy = resp.status_code == 200
    except Exception:
        pass
    
    # Check Ollama health
    ollama_healthy = False
    ollama_models = []
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            ollama_healthy = True
            data = resp.json()
            ollama_models = [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass
    
    # Calculate metrics from logs
    logs = get_recent_logs(limit=1000)
    response_logs = [log for log in logs if log.get("type") == "response"]
    error_logs = [log for log in logs if log.get("type") == "error"]
    
    recent_errors = len([e for e in error_logs if time.time() - datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).timestamp() < 300])
    
    durations = [log.get("duration_ms", 0) for log in response_logs if log.get("duration_ms")]
    avg_response_time = sum(durations) / len(durations) if durations else 0.0
    
    # Count active connections (requests in last 5 seconds)
    now = time.time()
    active_connections = len([
        log for log in logs
        if log.get("type") == "request" and
        (now - datetime.fromisoformat(log["timestamp"].replace("Z", "+00:00")).timestamp()) < 5
    ])
    
    return SystemStatus(
        api_healthy=api_healthy,
        ollama_healthy=ollama_healthy,
        ollama_models=ollama_models,
        active_connections=active_connections,
        recent_errors=recent_errors,
        avg_response_time_ms=round(avg_response_time, 2),
    )


@router.get("/v1/monitoring/metrics")
def get_metrics() -> Dict[str, Any]:
    """Get detailed performance metrics."""
    logs = get_recent_logs(limit=1000)
    
    # Filter by type
    requests = [log for log in logs if log.get("type") == "request"]
    responses = [log for log in logs if log.get("type") == "response"]
    errors = [log for log in logs if log.get("type") == "error"]
    
    # Calculate metrics
    durations = [r.get("duration_ms", 0) for r in responses if r.get("duration_ms")]
    
    metrics = {
        "total_requests": len(requests),
        "total_responses": len(responses),
        "total_errors": len(errors),
        "response_times": {
            "min_ms": min(durations) if durations else 0,
            "max_ms": max(durations) if durations else 0,
            "avg_ms": sum(durations) / len(durations) if durations else 0,
            "p95_ms": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
            "p99_ms": sorted(durations)[int(len(durations) * 0.99)] if durations else 0,
        },
        "status_codes": {},
        "endpoints": {},
        "errors_by_type": {},
    }
    
    # Count status codes
    for resp in responses:
        status = resp.get("status_code", 0)
        metrics["status_codes"][status] = metrics["status_codes"].get(status, 0) + 1
    
    # Count by endpoint
    for req in requests:
        path = req.get("path", "unknown")
        metrics["endpoints"][path] = metrics["endpoints"].get(path, 0) + 1
    
    # Count errors by type
    for err in errors:
        err_type = err.get("error_type", "Unknown")
        metrics["errors_by_type"][err_type] = metrics["errors_by_type"].get(err_type, 0) + 1
    
    return metrics


@router.post("/v1/monitoring/logs/clear")
def clear_log_buffer() -> Dict[str, str]:
    """Clear the log buffer."""
    clear_logs()
    add_log_entry({
        "type": "system",
        "message": "Log buffer cleared",
    })
    return {"status": "cleared"}


@router.get("/v1/monitoring/chat/performance")
def get_chat_performance() -> Dict[str, Any]:
    """Get chat endpoint specific performance metrics."""
    logs = get_recent_logs(limit=1000)
    
    # Filter chat-related logs
    chat_requests = [
        log for log in logs
        if log.get("type") == "request" and "/v1/chat" in log.get("path", "")
    ]
    chat_responses = [
        log for log in logs
        if log.get("type") == "response" and "/v1/chat" in log.get("path", "")
    ]
    chat_errors = [
        log for log in logs
        if log.get("type") == "error" and "/v1/chat" in log.get("path", "")
    ]
    
    durations = [r.get("duration_ms", 0) for r in chat_responses if r.get("duration_ms")]
    
    return {
        "chat_requests": len(chat_requests),
        "chat_responses": len(chat_responses),
        "chat_errors": len(chat_errors),
        "response_times": {
            "min_ms": min(durations) if durations else 0,
            "max_ms": max(durations) if durations else 0,
            "avg_ms": sum(durations) / len(durations) if durations else 0,
        },
        "slow_requests": [
            {
                "timestamp": r.get("timestamp"),
                "duration_ms": r.get("duration_ms"),
                "path": r.get("path"),
            }
            for r in chat_responses
            if r.get("duration_ms", 0) > 1000
        ],
        "recent_errors": [
            {
                "timestamp": e.get("timestamp"),
                "error": e.get("error"),
                "error_type": e.get("error_type"),
            }
            for e in chat_errors[-10:]
        ],
    }


@router.get("/v1/monitoring/visitors")
def get_visitors() -> Dict[str, Any]:
    """Get all tracked visitors."""
    visitors = get_all_visitors()
    return {
        "visitors": visitors,
        "count": len(visitors),
    }


@router.get("/v1/monitoring/visitors/stats")
def get_visitor_statistics() -> Dict[str, Any]:
    """Get visitor statistics."""
    return get_visitor_stats()


@router.get("/v1/monitoring/visitors/{ip}")
def get_visitor_details(ip: str) -> Dict[str, Any]:
    """Get detailed information about a specific visitor IP."""
    visitors = load_visitor_data()
    
    if ip not in visitors:
        return {
            "error": f"No data found for IP: {ip}",
            "ip": ip,
        }
    
    return visitors[ip]
