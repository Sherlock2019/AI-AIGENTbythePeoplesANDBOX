"""Live log monitoring dashboard for troubleshooting chatbot issues."""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Dict, List

import requests
import streamlit as st
from services.ui.theme_manager import apply_theme, render_theme_toggle

API_URL = "http://localhost:8090"

st.set_page_config(
    page_title="Live Log Monitor — Troubleshooting",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

st.title("🔍 Live Log Monitor")
st.caption("Real-time monitoring for chatbot connections and performance troubleshooting")

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Controls")
    
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_interval = st.slider("Refresh interval (seconds)", 1, 10, 2)
    
    log_limit = st.slider("Log entries", 10, 500, 100)
    log_filter = st.selectbox(
        "Filter by type",
        ["All", "request", "response", "error", "chat_request", "chat_response", "chat_llm_timeout"],
    )
    
    if st.button("Clear Logs", type="secondary"):
        try:
            resp = requests.post(f"{API_URL}/v1/monitoring/logs/clear", timeout=5)
            if resp.status_code == 200:
                st.success("Logs cleared!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to clear logs: {e}")
    
    st.markdown("---")
    render_theme_toggle(key="monitor_theme_toggle")

# Main content
tab1, tab2, tab3, tab4 = st.tabs(["📊 System Status", "📝 Live Logs", "⚡ Performance", "🐛 Chat Debug"])

with tab1:
    st.subheader("System Health Status")
    
    try:
        resp = requests.get(f"{API_URL}/v1/monitoring/status", timeout=5)
        if resp.status_code == 200:
            status = resp.json()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if status.get("api_healthy"):
                    st.success("✅ API Healthy")
                else:
                    st.error("❌ API Unhealthy")
            
            with col2:
                if status.get("ollama_healthy"):
                    st.success("✅ Ollama Connected")
                    st.caption(f"{len(status.get('ollama_models', []))} models")
                else:
                    st.error("❌ Ollama Disconnected")
            
            with col3:
                active = status.get("active_connections", 0)
                st.metric("Active Connections", active)
            
            with col4:
                errors = status.get("recent_errors", 0)
                if errors > 0:
                    st.error(f"⚠️ {errors} Recent Errors")
                else:
                    st.success("✅ No Recent Errors")
            
            st.markdown("---")
            
            # Ollama models
            if status.get("ollama_models"):
                st.subheader("Available Ollama Models")
                models = status.get("ollama_models", [])
                st.code("\n".join(models), language="text")
            
            # Average response time
            avg_time = status.get("avg_response_time_ms", 0)
            if avg_time > 1000:
                st.warning(f"⚠️ Average response time: {avg_time:.0f}ms (slow)")
            elif avg_time > 500:
                st.info(f"ℹ️ Average response time: {avg_time:.0f}ms")
            else:
                st.success(f"✅ Average response time: {avg_time:.0f}ms")
        else:
            st.error(f"Failed to get status: {resp.status_code}")
    except Exception as e:
        st.error(f"Error fetching status: {e}")

with tab2:
    st.subheader("Live Request/Response Logs")
    
    try:
        filter_type = None if log_filter == "All" else log_filter
        resp = requests.get(
            f"{API_URL}/v1/monitoring/logs",
            params={"limit": log_limit, "type_filter": filter_type},
            timeout=5,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            logs = data.get("logs", [])
            
            if logs:
                # Display logs in reverse order (newest first)
                for log in reversed(logs):
                    log_type = log.get("type", "unknown")
                    timestamp = log.get("timestamp", "")
                    
                    # Format timestamp
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        time_str = dt.strftime("%H:%M:%S.%f")[:-3]
                    except Exception:
                        time_str = timestamp
                    
                    # Color code by type
                    if log_type == "error":
                        st.error(f"**{time_str}** [{log_type}] {log.get('error', 'Unknown error')}")
                    elif log_type == "response":
                        status = log.get("status_code", 0)
                        duration = log.get("duration_ms", 0)
                        path = log.get("path", "")
                        
                        if status >= 500:
                            st.error(f"**{time_str}** [{log_type}] {path} - {status} ({duration:.0f}ms)")
                        elif status >= 400:
                            st.warning(f"**{time_str}** [{log_type}] {path} - {status} ({duration:.0f}ms)")
                        elif duration > 1000:
                            st.warning(f"**{time_str}** [{log_type}] {path} - {status} ({duration:.0f}ms) ⚠️ Slow")
                        else:
                            st.success(f"**{time_str}** [{log_type}] {path} - {status} ({duration:.0f}ms)")
                    elif log_type in ("chat_request", "chat_response", "chat_llm_timeout"):
                        duration = log.get("duration_ms", 0)
                        if log_type == "chat_llm_timeout":
                            st.error(f"**{time_str}** [LLM Timeout] {log.get('error', '')} ({duration:.0f}ms)")
                        elif log_type == "chat_response":
                            st.info(f"**{time_str}** [Chat Response] {duration:.0f}ms | RAG: {log.get('rag_time_ms', 0):.0f}ms | LLM: {log.get('llm_time_ms', 0):.0f}ms")
                        else:
                            st.info(f"**{time_str}** [{log_type}] {log.get('message', '')[:50]}")
                    else:
                        st.text(f"**{time_str}** [{log_type}] {log.get('path', '')}")
                    
                    # Expandable details
                    with st.expander("Details", expanded=False):
                        st.json(log)
            else:
                st.info("No logs available")
        else:
            st.error(f"Failed to fetch logs: {resp.status_code}")
    except Exception as e:
        st.error(f"Error fetching logs: {e}")
    
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

with tab3:
    st.subheader("Performance Metrics")
    
    try:
        resp = requests.get(f"{API_URL}/v1/monitoring/metrics", timeout=5)
        if resp.status_code == 200:
            metrics = resp.json()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Requests", metrics.get("total_requests", 0))
                st.metric("Total Responses", metrics.get("total_responses", 0))
                st.metric("Total Errors", metrics.get("total_errors", 0))
            
            with col2:
                rt = metrics.get("response_times", {})
                st.metric("Avg Response Time", f"{rt.get('avg_ms', 0):.0f}ms")
                st.metric("Min Response Time", f"{rt.get('min_ms', 0):.0f}ms")
                st.metric("Max Response Time", f"{rt.get('max_ms', 0):.0f}ms")
            
            with col3:
                st.metric("P95 Response Time", f"{rt.get('p95_ms', 0):.0f}ms")
                st.metric("P99 Response Time", f"{rt.get('p99_ms', 0):.0f}ms")
            
            st.markdown("---")
            
            # Status code distribution
            st.subheader("Status Code Distribution")
            status_codes = metrics.get("status_codes", {})
            if status_codes:
                st.bar_chart(status_codes)
            
            # Top endpoints
            st.subheader("Top Endpoints")
            endpoints = metrics.get("endpoints", {})
            if endpoints:
                # Sort by count
                sorted_endpoints = sorted(endpoints.items(), key=lambda x: x[1], reverse=True)[:10]
                endpoint_df = {"Endpoint": [e[0] for e in sorted_endpoints], "Requests": [e[1] for e in sorted_endpoints]}
                st.dataframe(endpoint_df, use_container_width=True)
            
            # Errors by type
            errors_by_type = metrics.get("errors_by_type", {})
            if errors_by_type:
                st.subheader("Errors by Type")
                st.bar_chart(errors_by_type)
        else:
            st.error(f"Failed to get metrics: {resp.status_code}")
    except Exception as e:
        st.error(f"Error fetching metrics: {e}")

with tab4:
    st.subheader("Chat Endpoint Debug")
    
    try:
        resp = requests.get(f"{API_URL}/v1/monitoring/chat/performance", timeout=5)
        if resp.status_code == 200:
            perf = resp.json()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Chat Requests", perf.get("chat_requests", 0))
            with col2:
                st.metric("Chat Responses", perf.get("chat_responses", 0))
            with col3:
                st.metric("Chat Errors", perf.get("chat_errors", 0))
            
            st.markdown("---")
            
            # Response times
            rt = perf.get("response_times", {})
            st.subheader("Chat Response Times")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Average", f"{rt.get('avg_ms', 0):.0f}ms")
            with col2:
                st.metric("Min", f"{rt.get('min_ms', 0):.0f}ms")
            with col3:
                st.metric("Max", f"{rt.get('max_ms', 0):.0f}ms")
            
            # Slow requests
            slow_requests = perf.get("slow_requests", [])
            if slow_requests:
                st.subheader("⚠️ Slow Requests (>1s)")
                for req in slow_requests:
                    st.warning(
                        f"{req.get('timestamp', '')} - {req.get('path', '')} - "
                        f"{req.get('duration_ms', 0):.0f}ms"
                    )
            
            # Recent errors
            recent_errors = perf.get("recent_errors", [])
            if recent_errors:
                st.subheader("🐛 Recent Errors")
                for err in recent_errors:
                    st.error(
                        f"{err.get('timestamp', '')} - {err.get('error_type', 'Unknown')}: "
                        f"{err.get('error', '')}"
                    )
        else:
            st.error(f"Failed to get chat performance: {resp.status_code}")
    except Exception as e:
        st.error(f"Error fetching chat performance: {e}")

# Auto-refresh
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
