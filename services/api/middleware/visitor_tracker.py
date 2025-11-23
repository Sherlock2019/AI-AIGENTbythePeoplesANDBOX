"""Visitor tracking middleware to capture IP addresses and country origins."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Storage file for visitor data
VISITOR_DATA_DIR = Path(os.getenv("VISITOR_DATA_DIR", "/root/WIP/data/visitors"))
VISITOR_DATA_DIR.mkdir(parents=True, exist_ok=True)
VISITOR_DATA_FILE = VISITOR_DATA_DIR / "visitors.json"

# Cache for IP lookups to avoid repeated API calls
_ip_cache: dict[str, dict] = {}


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request, handling proxies."""
    # Check for forwarded headers (common in production behind proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip
    
    # Check other common proxy headers
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    
    return None


def get_ip_geolocation(ip: str) -> dict:
    """
    Get geolocation information for an IP address.
    Uses ip-api.com (free, no API key required) with fallback to ipapi.co.
    """
    if not ip or ip == "127.0.0.1" or ip.startswith("192.168.") or ip.startswith("10."):
        return {
            "country": "Local",
            "country_code": "LOCAL",
            "region": "Local Network",
            "city": "Local",
            "org": "Local Network",
            "isp": "Local",
        }
    
    # Check cache first
    if ip in _ip_cache:
        return _ip_cache[ip]
    
    # Try ip-api.com first (free, no API key, 45 requests/minute)
    try:
        response = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,message,country,countryCode,region,regionName,city,org,isp,query"},
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                result = {
                    "country": data.get("country", "Unknown"),
                    "country_code": data.get("countryCode", "XX"),
                    "region": data.get("regionName", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "org": data.get("org", "Unknown"),
                    "isp": data.get("isp", "Unknown"),
                }
                _ip_cache[ip] = result
                return result
    except Exception as e:
        logger.debug(f"ip-api.com lookup failed for {ip}: {e}")
    
    # Fallback to ipapi.co (requires API key but has free tier)
    try:
        response = requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            if not data.get("error"):
                result = {
                    "country": data.get("country_name", "Unknown"),
                    "country_code": data.get("country_code", "XX"),
                    "region": data.get("region", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "org": data.get("org", "Unknown"),
                    "isp": data.get("org", "Unknown"),
                }
                _ip_cache[ip] = result
                return result
    except Exception as e:
        logger.debug(f"ipapi.co lookup failed for {ip}: {e}")
    
    # Default fallback
    result = {
        "country": "Unknown",
        "country_code": "XX",
        "region": "Unknown",
        "city": "Unknown",
        "org": "Unknown",
        "isp": "Unknown",
    }
    _ip_cache[ip] = result
    return result


def load_visitor_data() -> dict:
    """Load visitor data from JSON file."""
    if not VISITOR_DATA_FILE.exists():
        return {}
    
    try:
        with open(VISITOR_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading visitor data: {e}")
        return {}


def save_visitor_data(data: dict) -> None:
    """Save visitor data to JSON file."""
    try:
        with open(VISITOR_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving visitor data: {e}")


def track_visitor(ip: str, path: str, method: str, user_agent: Optional[str] = None) -> None:
    """Track a visitor visit."""
    if not ip:
        return
    
    # Load existing data
    visitors = load_visitor_data()
    
    # Get or create visitor entry
    if ip not in visitors:
        # First time seeing this IP - get geolocation
        geo = get_ip_geolocation(ip)
        visitors[ip] = {
            "ip": ip,
            "country": geo["country"],
            "country_code": geo["country_code"],
            "region": geo["region"],
            "city": geo["city"],
            "org": geo["org"],
            "isp": geo["isp"],
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "visit_count": 0,
            "paths_visited": [],
            "user_agents": [],
        }
    
    # Update visitor info
    visitor = visitors[ip]
    visitor["last_seen"] = datetime.now(timezone.utc).isoformat()
    visitor["visit_count"] = visitor.get("visit_count", 0) + 1
    
    # Track unique paths
    path_entry = f"{method} {path}"
    if path_entry not in visitor.get("paths_visited", []):
        if "paths_visited" not in visitor:
            visitor["paths_visited"] = []
        visitor["paths_visited"].append(path_entry)
    
    # Track user agents
    if user_agent and user_agent not in visitor.get("user_agents", []):
        if "user_agents" not in visitor:
            visitor["user_agents"] = []
        visitor["user_agents"].append(user_agent)
    
    # Save updated data
    save_visitor_data(visitors)


class VisitorTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware to track visitor IPs and country origins."""
    
    def __init__(self, app: ASGIApp, track_all_paths: bool = True):
        super().__init__(app)
        self.track_all_paths = track_all_paths
    
    async def dispatch(self, request: Request, call_next):
        # Extract client IP
        client_ip = get_client_ip(request)
        
        # Track visitor (non-blocking, fire and forget)
        if client_ip and self.track_all_paths:
            try:
                user_agent = request.headers.get("User-Agent")
                track_visitor(
                    ip=client_ip,
                    path=str(request.url.path),
                    method=request.method,
                    user_agent=user_agent
                )
            except Exception as e:
                logger.warning(f"Error tracking visitor: {e}")
        
        # Continue with request
        response = await call_next(request)
        return response


def get_all_visitors() -> list[dict]:
    """Get all tracked visitors."""
    visitors = load_visitor_data()
    return list(visitors.values())


def get_visitor_stats() -> dict:
    """Get visitor statistics."""
    visitors = load_visitor_data()
    
    if not visitors:
        return {
            "total_visitors": 0,
            "total_visits": 0,
            "countries": {},
            "top_ips": [],
        }
    
    total_visits = sum(v.get("visit_count", 0) for v in visitors.values())
    countries = {}
    
    for visitor in visitors.values():
        country = visitor.get("country", "Unknown")
        countries[country] = countries.get(country, 0) + 1
    
    # Top IPs by visit count
    top_ips = sorted(
        visitors.values(),
        key=lambda v: v.get("visit_count", 0),
        reverse=True
    )[:10]
    
    return {
        "total_visitors": len(visitors),
        "total_visits": total_visits,
        "countries": countries,
        "top_ips": [
            {
                "ip": v["ip"],
                "country": v.get("country", "Unknown"),
                "visit_count": v.get("visit_count", 0),
            }
            for v in top_ips
        ],
    }
