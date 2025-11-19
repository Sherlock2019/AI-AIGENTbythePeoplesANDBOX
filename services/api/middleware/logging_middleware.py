"""Request/response logging middleware for monitoring and troubleshooting."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

logger = logging.getLogger(__name__)

# In-memory log buffer for real-time monitoring (last 1000 entries)
_log_buffer: list[dict] = []
_MAX_BUFFER_SIZE = 1000


def add_log_entry(entry: dict) -> None:
    """Add log entry to buffer."""
    global _log_buffer
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    _log_buffer.append(entry)
    if len(_log_buffer) > _MAX_BUFFER_SIZE:
        _log_buffer.pop(0)


def get_recent_logs(limit: int = 100) -> list[dict]:
    """Get recent log entries."""
    return _log_buffer[-limit:]


def clear_logs() -> None:
    """Clear log buffer."""
    global _log_buffer
    _log_buffer.clear()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses with timing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Capture request body if available
        request_body = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body:
                    try:
                        request_body = json.loads(body)
                    except json.JSONDecodeError:
                        request_body = body.decode("utf-8", errors="ignore")[:500]
            except Exception:
                pass
        
        # Log request
        request_log = {
            "type": "request",
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "client": request.client.host if request.client else None,
            "headers": dict(request.headers),
            "body": request_body,
        }
        add_log_entry(request_log)
        logger.debug(f"Request: {request.method} {request.url.path}")
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log exception
            duration = time.time() - start_time
            error_log = {
                "type": "error",
                "method": request.method,
                "path": str(request.url.path),
                "error": str(exc),
                "error_type": type(exc).__name__,
                "duration_ms": round(duration * 1000, 2),
            }
            add_log_entry(error_log)
            logger.error(f"Request error: {request.method} {request.url.path} - {exc}")
            raise
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Capture response body if available
        response_body = None
        if hasattr(response, "body"):
            try:
                body_bytes = response.body
                if body_bytes:
                    try:
                        response_body = json.loads(body_bytes)
                    except (json.JSONDecodeError, TypeError):
                        response_body = body_bytes.decode("utf-8", errors="ignore")[:500]
            except Exception:
                pass
        
        # Log response
        response_log = {
            "type": "response",
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "body": response_body,
        }
        add_log_entry(response_log)
        
        # Log slow requests
        if duration > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {duration:.2f}s (status: {response.status_code})"
            )
        
        return response
