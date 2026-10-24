# services/ui/app.py
# ─────────────────────────────────────────────
# 🌐 OpenSource AI Agent Library + Credit Appraisal PoC by Dzoan
# ─────────────────────────────────────────────
from __future__ import annotations
import os

# Disable Streamlit telemetry to avoid capture() error
os.environ.setdefault("STREAMLIT_TELEMETRY_DISABLED", "true")
os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

import re
import io
import json
import html
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from urllib.parse import urlparse
import logging
import sys
import warnings
import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Suppress Streamlit ScriptRunContext warnings when running in background threads
# This warning is harmless and can be safely ignored in bare mode
class ScriptRunContextFilter(logging.Filter):
    """Filter out ScriptRunContext warnings from background threads."""
    def filter(self, record):
        # Filter out warnings about missing ScriptRunContext
        msg = str(record.getMessage())
        if "missing ScriptRunContext" in msg:
            return False
        if "ScriptRunContext" in msg and "bare mode" in msg:
            return False
        if "ScriptRunContext" in msg and "can be ignored" in msg:
            return False
        return True

# Apply filter to root logger and Streamlit loggers
logging.getLogger().addFilter(ScriptRunContextFilter())
# Suppress specific Streamlit loggers that may emit these warnings
for logger_name in [
    "streamlit.runtime.scriptrunner.script_runner",
    "streamlit.runtime.caching",
    "streamlit.runtime",
    "streamlit",
]:
    logger = logging.getLogger(logger_name)
    logger.addFilter(ScriptRunContextFilter())
    logger.setLevel(logging.ERROR)

# Also filter Python warnings that might contain ScriptRunContext messages
warnings.filterwarnings("ignore", message=".*ScriptRunContext.*")
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

# Try to use pandas json_normalize, fallback to compatibility wrapper
try:
    from pandas import json_normalize
except ImportError:
    try:
        from services.ui.utils.pandas_compat import ensure_json_normalize
        json_normalize = ensure_json_normalize()
    except ImportError:
        # Final fallback
        import pandas as pd
        json_normalize = pd.json_normalize

from services.ui.theme_manager import (
    get_palette,
    get_theme,
    init_theme,
    render_theme_toggle,
)
from services.ui.components.feedback import load_feedback_data
from services.ui.utils.agent_builder_utils import list_saved_blueprints

# Try to import global_chat component if available
try:
    from services.ui.components.global_chat import render_global_control_tower
except ImportError:
    render_global_control_tower = None
if "stage" not in st.session_state:
    st.session_state.stage = "landing"



# ─────────────────────────────────────────────
# CREDIT AGENT — HEADER (used in credit flow)
# ─────────────────────────────────────────────
# streamlit already imported above

def render_credit_header():
    ss = st.session_state

    # pick a display name if available
    user = (
        (ss.get("credit_user") or {}).get("name")
        or (ss.get("asset_user") or {}).get("name")
        or (ss.get("user_info") or {}).get("name")
        or "guest"
    )

    # use your theme switch (defaults to dark)
    theme = get_theme()
    brand = {
        "dark": {"text":"#e2e8f0","muted":"#94a3b8","accent":"#3b82f6"},
        "light":{"text":"#0f172a","muted":"#475569","accent":"#2563eb"},
    }[theme]

    st.title("🏦 Credit Appraisal Agent")
    st.caption(
        "A→H pipeline — Intake → Privacy → Credit Appraisal → Human Review → "
        "Training → Deployment → Monitoring → Reporting "
        f"| 👋 {user}"
    )

# ✅ JSON → DataFrame converter (final, unified, safe)
# ============================================================
def json_to_dataframe(payload) -> pd.DataFrame:
    """
    Convert arbitrary API JSON (dict/list/bytes/str) into a DataFrame.
    Prefers server 'artifacts.merged_csv' → fallback to json_normalize.
    """

    # -------------------------------
    # Case 1: payload is dict
    # -------------------------------
    if isinstance(payload, dict):

        # ✅ Try artifacts.merged_csv first
        res = payload.get("result") or payload
        artifacts = res.get("artifacts") or {}
        merged_csv = artifacts.get("merged_csv")

        if isinstance(merged_csv, str) and os.path.exists(merged_csv):
            try:
                return pd.read_csv(merged_csv)
            except Exception:
                pass

        # ✅ Embedded merged_df inside the JSON
        if "merged_df" in res:
            try:
                return pd.DataFrame(res["merged_df"])
            except Exception:
                pass

        # ✅ If result is list → DF
        if isinstance(res, list):
            try:
                return pd.DataFrame(res)
            except Exception:
                try:
                    return pd.json_normalize(res)
                except Exception:
                    pass

        # ✅ Try keys inside result
        for key in ("rows", "data", "result", "results", "items", "records"):
            if key in res:
                try:
                    return json_to_dataframe(res[key])
                except Exception:
                    pass

    # -------------------------------
    # Case 2: payload is list
    # -------------------------------
    if isinstance(payload, list):
        if len(payload) == 0:
            return pd.DataFrame()
        if all(isinstance(x, dict) for x in payload):
            try:
                return pd.DataFrame(payload)
            except:
                return pd.json_normalize(payload)
        return pd.DataFrame({"value": payload})

    # -------------------------------
    # Case 3: payload is bytes
    # -------------------------------
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8", errors="ignore")
        except:
            return pd.DataFrame({"value": [repr(payload)]})

    # -------------------------------
    # Case 4: payload is str → try JSON parse
    # -------------------------------
    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return pd.DataFrame()
        try:
            j = json.loads(payload)
            return json_to_dataframe(j)
        except:
            # Fallback → line-by-line DF
            lines = [ln for ln in payload.splitlines() if ln.strip()]
            return pd.DataFrame({"value": lines}) if lines else pd.DataFrame()

    # -------------------------------
    # Default fallback
    # -------------------------------
    return pd.DataFrame({"value": [payload]})



def _extract_run_fields(raw_json):  # ADD
    """
    Return (run_id, normalized_payload_dict).
    Ensures downstream code always receives a dict-like 'payload'.
    """
    run_id = extract_run_id(raw_json)

    # Normalize to dict payload so later code can access keys safely
    payload = raw_json
    if not isinstance(payload, dict):
        if isinstance(payload, list):
            first_dict = next((x for x in payload if isinstance(x, dict)), None)
            payload = first_dict if first_dict is not None else {"result": raw_json}
        else:
            payload = {"result": raw_json}
    return run_id, payload





# ─────────────────────────────────────────────
# GLOBAL PAGE CONFIG + HIDE SIDEBAR (only set once)
# ─────────────────────────────────────────────
if not hasattr(st, '_page_config_set'):
    st.set_page_config(
        page_title="AI Sandbox — By the People, For the People",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    st._page_config_set = True

# 💡 Hide multipage sidebar completely
st.markdown("""
    <style>
    [data-testid="stSidebar"],
    section[data-testid="stSidebar"],
    div[data-testid="stSidebarNav"],
    nav[data-testid="stSidebarNav"] {
        display: none !important;
        visibility: hidden !important;
    }
    [data-testid="stAppViewContainer"] {
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

init_theme()
pal = get_palette()


# ────────────────────────────────
# GLOBAL CONFIG (directories + API)
# ────────────────────────────────
BASE_DIR = os.path.expanduser("~/AI-AIGENTbythePeoplesANDBOX/HUGKAG/services/ui")
LANDING_IMG_DIR = os.path.join(BASE_DIR, "landing_images")
RUNS_DIR = os.path.join(BASE_DIR, ".runs")
TMP_FEEDBACK_DIR = os.path.join(BASE_DIR, ".tmp_feedback")

for d in (LANDING_IMG_DIR, RUNS_DIR, TMP_FEEDBACK_DIR):
    os.makedirs(d, exist_ok=True)

API_URL = os.getenv("API_URL", "http://localhost:8090")

LAUNCH_PORT = os.getenv("LAUNCH_PORT") or "8502"

# def _normalize_launch_base(raw_value: Optional[str]) -> str:
#     fallback = f"http://localhost:{LAUNCH_PORT}"
#     candidate = (raw_value or "").strip()
#     if not candidate:
#         return fallback
#     if not re.match(r"^https?://", candidate):
#         candidate = f"http://{candidate}"
#     candidate = candidate.rstrip("/")
#     parsed = urlparse(candidate)
#     if parsed.scheme and parsed.netloc:
#         host = f"{parsed.scheme}://{parsed.netloc}"
#         if parsed.port is None and LAUNCH_PORT:
#             host = f"{host}:{LAUNCH_PORT}"
#         return host
#     return fallback

#     # LAUNCH_BASE_URL = _normalize_launch_base(
#     #     os.getenv("LAUNCH_BASE_URL") or os.getenv("LAUNCH_HOST")
# LAUNCH_BASE_URL = _normalize_launch_base("http://aibyforthepeople.com")
    
def _normalize_launch_base(raw_value: Optional[str]) -> str:
    fallback = f"http://localhost:{LAUNCH_PORT}"
    candidate = (raw_value or "").strip()
    if not candidate:
        return fallback
    if not re.match(r"^https?://", candidate):
        candidate = f"http://{candidate}"
    candidate = candidate.rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.netloc:
        host = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.port is None and LAUNCH_PORT:
            host = f"{host}:{LAUNCH_PORT}"
        return host
    return fallback


# Agent Launch links: default to same-origin paths (/asset_appraisal, etc.) so local and
# deployed hosts work. Set LAUNCH_BASE_URL or LAUNCH_HOST only if Streamlit is served on a
# different origin than the page embedding these links.
_LAUNCH_BASE_RAW = (os.getenv("LAUNCH_BASE_URL") or os.getenv("LAUNCH_HOST") or "").strip()
if _LAUNCH_BASE_RAW:
    LAUNCH_BASE_URL = _normalize_launch_base(_LAUNCH_BASE_RAW).rstrip("/")
else:
    LAUNCH_BASE_URL = ""


def _launch_href(path: str) -> str:
    """Build href for Streamlit multipage routes; optional absolute base from env."""
    p = path if path.startswith("/") else f"/{path}"
    return f"{LAUNCH_BASE_URL}{p}" if LAUNCH_BASE_URL else p


# ────────────────────────────────
# UNIVERSAL TOP NAVIGATION
# ────────────────────────────────

def render_nav_bar_app():
    stage = st.session_state.get("stage", "landing")

    # visibility logic
    show_home   = stage in (
        "agents",
        "credit_agent",
        "asset_agent",
        "troubleshooter_agent",
        "credit_scoring_agent",
        "legal_compliance_agent",
        "ceo_driver_dashboard",
    )
    show_agents = stage not in ("landing", "agents")

    # nothing on landing
    if not (show_home or show_agents):
        return

    c1, c2, c3 = st.columns([1, 1, 2.5])

    with c1:
        if show_home and st.button("← Home", key=f"btn_home_{stage}"):
            st.session_state.stage = "landing"
            st.rerun()  # already in app.py → rerun only

    with c2:
        if show_agents and st.button("← Agents", key=f"btn_agents_{stage}"):
            st.session_state.stage = "agents"
            st.rerun()  # already in app.py → rerun only

    with c3:
        render_theme_toggle(
            label="Dark mode",
            key="app_theme_toggle",
            help="Toggle the shared UI palette",
        )

    st.markdown("---")



# # ────────────────────────────────
# # UNIVERSAL TOP NAVIGATION + THEME TOGGLE (fixed)
# # ────────────────────────────────
# def render_nav_bar_app():
#     import streamlit as st
#     ss = st.session_state  # ✅ define session alias

#     # --- stage & visibility
#     stage = ss.get("stage", "landing")
#     show_home   = stage in ("agents", "credit_agent", "asset_agent")
#     show_agents = stage not in ("landing", "agents")

#     # nothing to render on pure landing
#     if not (show_home or show_agents):
#         return

#     # --- theme state: migrate old key and set default
#     # Theme state
#     ss.setdefault("theme", "dark")

#     # if "theme" not in ss and "ui_theme" in ss:
#     #     ss["theme"] = ss["ui_theme"]
#     # ss.setdefault("theme", "dark")
#     # ss["ui_theme"] = ss.get("theme", "dark")  # keep both in sync

#     # three columns: home, agents, theme toggle
#     c1, c2, c3 = st.columns([1, 1, 2.5])

#     with c1:
#         if show_home and st.button("🏠 Back to Home", key=f"btn_home_{stage}"):
#             _go_stage("landing")
#             st.stop()

#     with c2:
#         if show_agents and st.button("🤖 Back to Agents", key=f"btn_agents_{stage}"):
#             _go_stage("agents")
#             st.stop()

#     with c3:
#         is_dark = (ss.get("theme", "dark") == "dark")
#         new_is_dark = st.toggle(
#             "🌙 Dark mode",
#             value=is_dark,
#             key="ui_theme_toggle",
#             help="Switch theme"
#         )
#         new_theme = "dark" if new_is_dark else "light"
#         if new_theme != ss.get("theme"):
#             ss["theme"] = new_theme      # ✅ primary key
#             ss["ui_theme"] = new_theme   # ✅ legacy key stays in sync
#             apply_theme(ss["theme"])     # your existing helper

#     st.markdown("---")






# ────────────────────────────────
# SESSION STATE INIT
# ────────────────────────────────
if "user_info" not in st.session_state:
    st.session_state.user_info = {"name": "", "email": "", "flagged": False}
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "flagged" not in st.session_state.user_info:
    st.session_state.user_info["flagged"] = False
if "timestamp" not in st.session_state.user_info:
    st.session_state.user_info["timestamp"] = datetime.now(timezone.utc).isoformat()

# ────────────────────────────────
# RENDER UNIVERSAL NAV BAR
# ────────────────────────────────
render_nav_bar_app()

# Inject the global control tower chat so it's accessible from every page.
# Suppress chatbot on landing and agents pages
stage = st.session_state.get("stage", "landing")
if stage not in ("landing", "agents"):
    try:
        render_global_control_tower()
    except Exception:
        pass

# ────────────────────────────────
# HELPERS
# ────────────────────────────────
def _extract_run_fields(res_json):
    """
    Return (run_id, result_dict) from API responses that may be dicts or lists.
    """
    run_id = None
    result_obj = {}

    if isinstance(res_json, dict):
        run_id = (
            res_json.get("run_id")
            or res_json.get("id")
            or (res_json.get("data") or {}).get("run_id")
        )
        result_obj = (
            res_json.get("result")
            or (res_json.get("data") or {}).get("result")
            or {}
        )

    elif isinstance(res_json, list):
        # Find first dict item that contains identifiers/results
        for item in res_json:
            if isinstance(item, dict):
                if not run_id:
                    run_id = item.get("run_id") or item.get("id")
                if not result_obj:
                    result_obj = item.get("result") or {}
                if run_id and result_obj != {}:
                    break
        # If still nothing and list[0] is a dict, use it as best-effort
        if not run_id and res_json and isinstance(res_json[0], dict):
            run_id = res_json[0].get("run_id") or res_json[0].get("id")
            result_obj = res_json[0].get("result") or {}

    # Ensure result is a dict
    if not isinstance(result_obj, dict):
        result_obj = {"value": result_obj}

    return run_id, result_obj


def _clear_qp():
    """Clear query params (modern Streamlit API)."""
    try:
        st.query_params.clear()
    except Exception:
        pass


def load_image(base: str) -> Optional[str]:
    for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]:
        p = os.path.join(LANDING_IMG_DIR, f"{base}{ext}")
        if os.path.exists(p):
            return p
    return None


def save_uploaded_image(uploaded_file, base: str):
    if not uploaded_file:
        return None
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".png"
    dest = os.path.join(LANDING_IMG_DIR, f"{base}{ext}")
    with open(dest, "wb") as f:
        f.write(uploaded_file.getvalue())
    return dest


def logo_display_path(saved_logo_path: str) -> str:
    """Return a lightweight logo file for the landing page."""
    src = Path(saved_logo_path)
    if not src.exists():
        return saved_logo_path
    if src.stat().st_size <= 256 * 1024:
        return saved_logo_path

    thumb = src.with_name(f"{src.stem}_thumb.jpg")
    try:
        if (
            thumb.exists()
            and thumb.stat().st_mtime >= src.stat().st_mtime
            and thumb.stat().st_size <= 96 * 1024
        ):
            return str(thumb)

        from PIL import Image

        with Image.open(src) as img:
            img = img.convert("RGB")
            img.thumbnail((320, 480))
            img.save(thumb, "JPEG", quality=78, optimize=True, progressive=True)
        return str(thumb)
    except Exception:
        return saved_logo_path


def render_image_tag(agent_id: str, industry: str, emoji_fallback: str) -> str:
    base = agent_id.lower().replace(" ", "_")
    img_path = load_image(base) or load_image(industry.replace(" ", "_"))
    if img_path:
        return (
            f'<img src="file://{img_path}" '
            f'style="width:48px;height:48px;border-radius:10px;object-fit:cover;">'
        )
    return f'<div style="font-size:32px;">{emoji_fallback}</div>'


def compute_route_name(agent_label: str) -> str:
    """Normalize agent label (with emoji) into route slug."""
    clean_agent = re.sub(r"[^\w\s-]", "", agent_label).strip().lower()
    route_name = re.sub(r"[-\s]+", "_", clean_agent).replace("_agent", "")
    route_name = re.sub(r"_+", "_", route_name).strip("_")
    return route_name or "agent"





# ────────────────────────────────
# DATA
# ────────────────────────────────
# BASE_AGENTS - fallback if JSON file doesn't exist (format: sector, industry, agent, desc, status, emoji, requires_login)
BASE_AGENTS = [
    ("🛠️ AI Tools & Infrastructure", "🧩 Agent Builder", "🧩 Agent Builder",
     "Build custom agents by combining functions from HF and existing agents like LEGO blocks", "NEW", "🧩", False),
    ("🛠️ AI Tools & Infrastructure", "🤖 Hugging Face Tools", "🤖 HF Agent Wrapper",
     "Pure HuggingFace operations — Local HF models + HF API. Lightweight, HF-focused solution for all HF tasks", "NEW", "🤖", False),
    ("🛠️ AI Tools & Infrastructure", "🎯 Agent Management", "🎯 Agent Manager",
     "Unified interface with automatic failover — HF + Ollama + Local models. Multi-engine support with intelligent selection", "NEW", "🎯", False),
    ("🏢 Executive Leadership", "🚗 Boardroom Intelligence", "🚗 CEO driver DASHBOARD",
     "Real-time AI cockpit for CEOs to steer revenue, cash, ops, and market moves", "WIP", "🚗", False),
    ("🏦 Banking & Finance", "🏠 Real Estate", "🏠 Real Estate Evaluator Agent",
     "Interactive map with market price comparison and zone analysis", "NEW", "🏠", False),
    # Retail Banking Suite - sorted in specified order
    ("🏦 Banking & Finance", "💰 Retail Banking Suite", "🛡️ Anti-Fraud & KYC Agent",
     "Streamlined onboarding with fraud scoring", "Available", "🛡️", True),
    ("🏦 Banking & Finance", "💰 Retail Banking Suite", "💳 Credit Score Agent",
     "Calculate credit scores (300-850) for loan applications", "Available", "💳", True),
    ("🏦 Banking & Finance", "💰 Retail Banking Suite", "🏦 Asset Appraisal Agent",
     "Market-driven collateral valuation", "Available", "🏦", False),
    ("🏦 Banking & Finance", "💰 Retail Banking Suite", "💳 Credit Appraisal Agent",
     "Explainable AI for loan decisioning", "Available", "💳", True),
    ("🏦 Banking & Finance", "💰 Retail Banking Suite", "⚖️ Legal Compliance Agent",
     "Regulatory compliance, sanctions, PEP, licensing checks", "Available", "⚖️", False),
    ("🏦 Banking & Finance", "💰 Retail Banking Suite", "🧩 Unified Risk Orchestration Agent",
     "Compounds asset+credit+fraud into one decision", "Available", "🧩", False),
    ("🏦 Banking & Finance", "💰 Retail Banking Suite", "💬 Chatbot Assistant",
     "Context-aware embedded assistant", "Available", "💬", False),
    ("💻 Information Technology", "🧠 Troubleshooting", "🧠 IT Troubleshooter Agent",
     "First-principles + case-memory incident solver", "Available", "🧠", False),
    ("🏦 Banking & Finance", "🩺 Insurance", "🩺 Claims Triage Agent",
     "Automated claims prioritization", "Coming Soon", "🩺", False),
    ("⚡ Energy & Sustainability", "🔋 EV & Charging", "⚡ EV Charger Optimizer",
     "Optimize charger deployment via AI", "Coming Soon", "⚡", False),
    ("⚡ Energy & Sustainability", "☀️ Solar", "☀️ Solar Yield Estimator",
     "Estimate solar ROI and efficiency", "Coming Soon", "☀️", False),
    ("🚗 Automobile & Transport", "🚙 Automobile", "🚗 Predictive Maintenance",
     "Prevent downtime via sensor analytics", "Coming Soon", "🚗", False),
    ("🚗 Automobile & Transport", "🔋 EV", "🔋 EV Battery Health Agent",
     "Monitor EV battery health cycles", "Coming Soon", "🔋", False),
    ("🚗 Automobile & Transport", "🚚 Ride-hailing / Logistics", "🛻 Fleet Route Optimizer",
     "Dynamic route optimization for fleets", "Coming Soon", "🛻", False),
    ("💻 Information Technology", "🧰 Support & Security", "🧩 IT Ticket Triage",
     "Auto-prioritize support tickets", "Coming Soon", "🧩", False),
    ("💻 Information Technology", "🛡️ Security", "🔐 SecOps Log Triage",
     "Detect anomalies & summarize alerts", "Coming Soon", "🔐", False),
    ("⚖️ Legal & Government", "⚖️ Law Firms", "⚖️ Contract Analyzer",
     "Extract clauses and compliance risks", "Coming Soon", "⚖️", False),
    ("⚖️ Legal & Government", "🏛️ Public Services", "🏛️ Citizen Service Agent",
     "Smart assistant for citizen services", "Coming Soon", "🏛️", False),
    ("🛍️ Retail / SMB / Creative", "🏬 Retail & eCommerce", "📈 Sales Forecast Agent",
     "Predict demand & inventory trends", "Coming Soon", "📈", False),
    ("🎬 Retail / SMB / Creative", "🎨 Media & Film", "🎬 Budget Cost Assistant",
     "Estimate, optimize, and track film & production costs using AI", "Coming Soon", "🎬", False),
]


def load_custom_agents_from_blueprints():
    custom_agents = []
    launch_overrides = {}
    try:
        blueprints = list_saved_blueprints()
    except Exception:
        blueprints = []
    for blueprint in blueprints:
        meta = blueprint.get("metadata", {})
        slug = blueprint.get("slug") or meta.get("slug")
        if not slug:
            continue
        sector = meta.get("sector") or "🛠️ AI Tools & Infrastructure"
        industry = meta.get("industry") or "🧩 Custom Blueprints"
        emoji = meta.get("emoji") or "✨"
        name = blueprint.get("agent_name") or slug.replace("-", " ").title()
        label = name if name.startswith(emoji) else f"{emoji} {name}"
        desc = meta.get("tagline") or meta.get("description") or blueprint.get("description") or "Custom agent blueprint."
        status = meta.get("status") or "NEW"
        requires_login = meta.get("requires_login", False)
        custom_agents.append((sector, industry, label, desc, status, emoji, requires_login))
        route_name = compute_route_name(label)
        # Only accept same-origin paths — a blueprint must not be able to point
        # the Launch button at "javascript:" or an external host.
        launch_path = str(meta.get("launch_path") or "")
        if not re.fullmatch(r"/[\w\-/]*(\?[\w\-=&%]*)?", launch_path):
            launch_path = f"/agent_builder?blueprint={slug}"
        launch_overrides[route_name] = launch_path
    return custom_agents, launch_overrides


CUSTOM_AGENTS, CUSTOM_AGENT_LAUNCHES = load_custom_agents_from_blueprints()

# Load agents from JSON file if it exists, otherwise use BASE_AGENTS
def load_agents_from_json():
    """Load agents from JSON file, fallback to BASE_AGENTS if file doesn't exist."""
    agents_json_path = Path(__file__).parent / "data" / "agents.json"
    if agents_json_path.exists():
        try:
            with open(agents_json_path, "r", encoding="utf-8") as f:
                agents_data = json.load(f)
                # Convert JSON format to tuple format: (sector, industry, agent, desc, status, emoji, requires_login)
                return [
                    (
                        agent.get("sector", ""),
                        agent.get("industry", ""),
                        agent.get("agent", ""),
                        agent.get("description", ""),
                        agent.get("status", "Available"),
                        agent.get("emoji", "🤖"),
                        agent.get("requires_login", False)
                    )
                    for agent in agents_data
                ]
        except Exception as e:
            print(f"Warning: Could not load agents from JSON: {e}. Using BASE_AGENTS.")
    return BASE_AGENTS

MANAGED_AGENTS = load_agents_from_json()
AGENTS = MANAGED_AGENTS + CUSTOM_AGENTS




# # ────────────────────────────────
# # STYLES
# # ────────────────────────────────

st.markdown(
    f"""
    <style>
    .block-container {{ max-width: 1440px !important; padding-left: 2rem !important; padding-right: 2rem !important; }}
    footer {{
        text-align:center; padding:1.5rem 0; margin-top:2rem;
        color:{pal['muted']}; font-size:0.85rem; font-weight:400;
        border-top:1px solid {pal['border']};
    }}
    .left-box {{ padding: 0.5rem 0.5rem 0 0; }}
    .eyebrow {{
        font-size:0.75rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase;
        color:{pal['muted']} !important; margin-bottom:0.6rem;
    }}
    .hero-title {{
        font-size:2rem !important; font-weight:600 !important; line-height:1.25 !important;
        color:{pal['text']} !important; margin:0 0 0.5rem 0 !important;
    }}
    .hero-sub {{
        font-size:1.05rem; color:{pal['subtext']} !important; margin-bottom:1.75rem; line-height:1.6;
    }}
    .hero-section {{
        border-top:1px solid {pal['border']}; padding:0.9rem 0;
    }}
    .hero-section .label {{
        display:block; font-size:0.75rem; font-weight:600; letter-spacing:0.06em; text-transform:uppercase;
        color:{pal['accent']} !important; margin-bottom:0.25rem;
    }}
    .hero-section p {{ margin:0; font-size:0.95rem; line-height:1.65; }}
    .hero-section b {{ color:{pal['text']} !important; font-weight:600; }}
    a.macbtn {{ padding:6px 14px; font-size:0.88rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)





# ────────────────────────────────
# QUERY PARAM ROUTING (agent first, then stage)
# ────────────────────────────────
try:
    qp = st.query_params
except Exception:
    qp = {}

# 1) Agent intent wins (direct actions)
if "launch" in qp or "agent" in qp:
    agent = qp.get("agent", [""])[0] if isinstance(qp.get("agent"), list) else qp.get("agent", "")
    
    # Check if this agent requires login by looking up in MANAGED_AGENTS
    requires_login = False
    agent_route = agent.lower()
    for agent_tuple in MANAGED_AGENTS:
        if len(agent_tuple) >= 7:
            sector, industry, agent_name, desc, status, emoji, login_req = agent_tuple
        else:
            sector, industry, agent_name, desc, status, emoji = agent_tuple
            login_req = False
        route_name = compute_route_name(agent_name)
        if route_name == agent_route:
            requires_login = login_req
            break
    
    if agent == "credit" or (requires_login and agent_route):
        st.session_state.stage = "login"
        st.session_state["selected_agent"] = agent_route
        st.session_state["login_target"] = agent_route
        _clear_qp()
        st.rerun()
    elif agent == "asset":
        _clear_qp()
        # Go straight to the Asset page (no extra reroute hops)
        try:
            st.switch_page("pages/asset_appraisal.py")
        except Exception as e:
            # Fallback: set stage so user stays in same app gracefully
            st.session_state.stage = "asset_agent"
            st.warning(f"Could not switch to asset page, stage set to asset_agent: {e}")
            st.rerun()
    elif agent in {"anti_fraud", "afk", "kyc"}:
        _clear_qp()
        try:
            st.switch_page("pages/anti_fraud_kyc.py")
        except Exception as e:
            st.warning(f"Could not open anti-fraud agent page: {e}")
            st.session_state.stage = "landing"
            st.rerun()
    elif agent in {"credit_score", "credit_scoring", "score", "scoring"}:
        _clear_qp()
        try:
            st.switch_page("pages/credit_scoring.py")
        except Exception as e:
            st.warning(f"Could not open credit scoring page: {e}")
            st.session_state.stage = "credit_scoring_agent"
            st.rerun()
    elif agent in {"legal_compliance", "compliance", "legal"}:
        _clear_qp()
        try:
            st.switch_page("pages/legal_compliance.py")
        except Exception as e:
            st.warning(f"Could not open legal compliance page: {e}")
            st.session_state.stage = "legal_compliance_agent"
            st.rerun()
    elif agent in {"persona_room", "persona_chatroom", "meeting_room"}:
        _clear_qp()
        try:
            st.switch_page("pages/persona_chatroom.py")
        except Exception as e:
            st.warning(f"Could not open persona chatroom page: {e}")
            st.session_state.stage = "persona_chatroom"
            st.rerun()
    elif agent in {"troubleshooter", "it_troubleshooter"}:
        _clear_qp()
        try:
            st.switch_page("pages/troubleshooter_agent.py")
        except Exception as e:
            st.warning(f"Could not open troubleshooter agent page: {e}")
            st.session_state.stage = "troubleshooter_agent"
            st.rerun()
    elif agent in {"real_estate", "real_estate_evaluator", "re_evaluator"}:
        _clear_qp()
        try:
            st.switch_page("pages/real_estate_evaluator.py")
        except Exception as e:
            st.warning(f"Could not open real estate evaluator agent page: {e}")
            st.session_state.stage = "real_estate_evaluator"
            st.rerun()
    elif agent in {"ceo", "ceo_driver", "driver_dashboard", "ceo_dashboard"}:
        _clear_qp()
        try:
            st.switch_page("pages/ceo_driver_dashboard.py")
        except Exception as e:
            st.warning(f"Could not open CEO driver dashboard: {e}")
            st.session_state.stage = "ceo_driver_dashboard"
            st.rerun()
    elif agent in {"hf_agent_wrapper", "hf_agent", "huggingface", "hf_wrapper"}:
        _clear_qp()
        try:
            st.switch_page("pages/hf_inspector.py")
        except Exception as e:
            st.warning(f"Could not open HF Agent Inspector: {e}")
            st.session_state.stage = "landing"
            st.rerun()
    elif agent in {"agent_manager", "manager", "agent_management"}:
        _clear_qp()
        try:
            st.switch_page("pages/hf_inspector.py")
        except Exception as e:
            st.warning(f"Could not open Agent Manager: {e}")
            st.session_state.stage = "landing"
            st.rerun()
    elif agent in {"agent_builder", "builder", "agent_build"}:
        _clear_qp()
        try:
            st.switch_page("pages/agent_builder.py")
        except Exception as e:
            st.warning(f"Could not open Agent Builder: {e}")
            st.session_state.stage = "landing"
            st.rerun()

# 2) Stage param (secondary)
if "stage" in qp:
    target = qp["stage"]
    if target in {
        "landing",
        "agents",
        "login",
        "credit_agent",
        "asset_agent",
        "troubleshooter_agent",
        "credit_scoring_agent",
        "legal_compliance_agent",
        "persona_chatroom",
        "real_estate_evaluator",
        "ceo_driver_dashboard",
    } and st.session_state.stage != target:
        st.session_state.stage = target
        _clear_qp()
        st.rerun()



# ────────────────────────────────
# STAGE: LANDING
# ────────────────────────────────
# Note: streamlit already imported above, no need to re-import
# Page config already set above, no need to set again

# ────────────────────────────────
# 💡 FORCE REMOVE SIDEBAR ENTIRELY
# ────────────────────────────────
st.markdown("""
    <style>
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        display: none !important;
    }
    [data-testid="stAppViewContainer"] {
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ────────────────────────────────
# INITIALIZE SESSION STATE (optimized - only set once)
# ────────────────────────────────
if "stage" not in st.session_state:
    st.session_state.stage = "landing"
# ────────────────────────────────
# DEFINE PATHS + FILES
# ────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ────────────────────────────────
# FEEDBACK LOADING + CACHE (OPTIMIZED)
# ────────────────────────────────
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_feedback() -> dict:
    """Load feedback data with caching to avoid repeated file I/O."""
    return load_feedback_data()

def render_stars(rating: float) -> str:
    """Render muted stars for rating."""
    full = int(round(rating))
    return "".join(
        [f"<span style='color:{pal['annotation']};font-size:14px;'>★</span>" for _ in range(full)]
        + [f"<span style='color:{pal['border']};font-size:14px;'>★</span>" for _ in range(5 - full)]
    )

# Cache feedback in session state (persists across reruns)
if "feedback_data" not in st.session_state:
    st.session_state["feedback_data"] = load_feedback()
feedback_data = st.session_state["feedback_data"]

# ────────────────────────────────
# PAGE: LANDING
# ────────────────────────────────
if st.session_state.stage == "landing":



    # ────────────────────────────────
    # Layout columns
    # ────────────────────────────────
    c1, c2 = st.columns([1.1, 1.9], gap="large")

    # LEFT PANEL
    with c1:
        st.markdown("<div class='left-box'>", unsafe_allow_html=True)

        # ────────────────────────────────
        # HERO LOGO — Tap to upload
        # ────────────────────────────────
        logo_dir = os.path.join(BASE_DIR, "assets")
        os.makedirs(logo_dir, exist_ok=True)
        saved_logo_path = os.path.join(logo_dir, "uploaded_logo.png")

        st.markdown(
            """
            <style>
            .logo-upload-placeholder {
                border: 1px dashed """ + pal['input_border'] + """;
                border-radius: 8px;
                width: 240px;
                height: 120px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: """ + pal['muted'] + """;
                margin: 0 0 8px 0;
            }
            .logo-upload-area [data-testid="stFileUploadDropzone"] {
                display: none !important;
            }
            #logo_upload { visibility:hidden; height:0; }
            .block-container input[type="file"] { display:none !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        if os.path.exists(saved_logo_path):
            display_logo_path = logo_display_path(saved_logo_path)
            with open(display_logo_path, "rb") as f:
                logo_base64 = base64.b64encode(f.read()).decode()
            logo_mime = "image/jpeg" if display_logo_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
            display_logo = f'<img src="data:{logo_mime};base64,{logo_base64}" style="width:220px;border-radius:8px;" />'
        else:
            display_logo = "<div class='logo-upload-placeholder' style='width:220px;height:110px;'>Upload logo</div>"

        st.markdown(
            f"""
            <div id="logo_click_area" style="cursor:pointer; text-align:left;">
                {display_logo}
                <p style='font-size:11px;color:{pal['muted']};margin-top:4px;'>Click to replace logo</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        upload_label = "logo_upload_portal"
        uploaded_logo = st.file_uploader(
            upload_label,
            type=["png", "jpg", "jpeg", "webp"],
            key="logo_upload",
            label_visibility="collapsed",
        )

        st.markdown(
            f"""
            <style>
            div[aria-label="{upload_label}"] {{
                height: 0 !important;
                opacity: 0 !important;
                overflow: hidden !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <script>
            const logoArea = document.getElementById("logo_click_area");
            if (logoArea) {
                logoArea.onclick = function() {
                    const hiddenWrapper = document.querySelector('div[aria-label="logo_upload_portal"]');
                    const hiddenInput = hiddenWrapper ? hiddenWrapper.querySelector('input[type="file"]') : null;
                    if (hiddenInput) hiddenInput.click();
                };
            }
            </script>
            """,
            unsafe_allow_html=True,
        )
        if uploaded_logo is not None:
            with open(saved_logo_path, "wb") as f:
                f.write(uploaded_logo.read())
            for thumb_path in Path(saved_logo_path).parent.glob(f"{Path(saved_logo_path).stem}_thumb.*"):
                thumb_path.unlink()
            st.success("✅ Logo updated!")
            st.rerun()

        # ────────────────────────────────
        # HERO + FOUNDATIONAL MESSAGE
        # ────────────────────────────────
        st.markdown(
            """
            <div class="eyebrow">Open AI Agent Sandbox</div>
            <h1 class="hero-title">An AI foundry, built by the people, for the people</h1>
            <div class="hero-sub">Take an agent from idea to production: explainable, open and privacy-first.</div>

            <div class="hero-section">
                <span class="label">What</span>
                <p>The <b>Open AI Agent Sandbox</b> is a foundry where AI ideas become explainable, open, working agents.</p>
            </div>
            <div class="hero-section">
                <span class="label">Why it matters</span>
                <p>No CAPEX and no gatekeepers: <b>GPU-for-rent compute</b>, <b>open-source models</b> and <b>privacy-first design</b>. Build faster and keep ownership of your data.</p>
            </div>
            <div class="hero-section">
                <span class="label">How</span>
                <p>Start from a <b>ready-to-use agent template</b>. Customize, test, improve, and export it once it is production-ready.</p>
            </div>
            <div class="hero-section">
                <span class="label">Where</span>
                <p>Inside your <b>GPU-for-rent cloud sandbox</b>, a secure, sovereign environment for building and evolving models.</p>
            </div>
            <div class="hero-section" style="margin-bottom:1.25rem;">
                <span class="label">For whom</span>
                <p>Builders, educators and enterprises who believe AI should serve the many, not the few.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # CTA
        cta1, cta2 = st.columns(2)
        with cta1:
            if st.button("Start building", key="btn_start_build_now", type="primary", use_container_width=True):
                st.session_state.stage = "agents"
                st.rerun()
        with cta2:
            if st.button(
                "CEO dashboard preview",
                key="btn_preview_ceo",
                help="Open CEO driver DASHBOARD",
                use_container_width=True,
            ):
                st.switch_page("pages/ceo_driver_dashboard.py")

        st.markdown("</div>", unsafe_allow_html=True)

    # RIGHT PANEL — Neon Interactive Agent List
    # ────────────────────────────────
    with c2:
        # Inject CSS once
        st.markdown(f"""
        <style>
        .neon-frame {{
            padding: 0.25rem 0 !important;
            margin-top: 0.5rem;
            margin-bottom: 2rem;
        }}
        .agent-card {{
            border-bottom: 1px solid {pal['border']};
            padding: 0.85rem 1.2rem;
            background: transparent;
            transition: background 0.15s ease;
        }}
        .agent-card:last-child {{ border-bottom: none; }}
        .agent-card:hover {{ background: {pal['table_hover_bg']}; }}
        .agent-header-bar {{
            display: flex;
            gap: 0;
            background: {pal['table_head_bg']};
            color: {pal['muted']};
            padding: 0.6rem 1.2rem;
            border-bottom: 1px solid {pal['border']};
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }}
        .agent-header-bar span {{ color: {pal['muted']} !important; }}
        .launchbtn {{ padding: 5px 14px; font-size: 0.85rem; white-space: nowrap; }}
        .stApp .launchbtn.launch-disabled {{
            cursor: not-allowed;
            border-style: dashed !important;
            color: {pal['muted']} !important;
            background: transparent !important;
        }}
        .status-pill {{
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 500;
            padding: 2px 8px;
            border-radius: 999px;
            border: 1px solid {pal['border']};
            white-space: nowrap;
        }}
        .agent-comments details {{
            cursor: pointer;
            color: {pal['subtext']};
            font-weight: 500;
            font-size: 0.85rem;
        }}
        .agent-comments summary {{
            list-style: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 48px;
        }}
        .agent-comments summary::-webkit-details-marker {{
            display: none;
        }}
        .agent-comments details[open] {{
            background: {pal['bg']};
            border: 1px solid {pal['border']};
            border-radius: 6px;
            padding: 0.35rem;
        }}
        .agent-comments .comment-list {{
            margin: 0.4rem 0 0;
            padding-left: 1rem;
            max-height: 180px;
            overflow-y: auto;
            font-size: 0.82rem;
            color: {pal['subtext']};
            text-align: left;
        }}
        .agent-comments .comment-list li {{
            margin-bottom: 0.4rem;
            border-left: 2px solid {pal['border']};
            padding: 0.2rem 0 0.2rem 0.5rem;
        }}
        </style>
        """, unsafe_allow_html=True)

        # ============================================================
        # Build all agent HTML dynamically into one single string
        # ============================================================
        import re

        # Column flex ratios shared by the header bar and every agent row.
        header_bar = (
            "<div class='agent-header-bar'>"
            "<span style='flex:1.2;'>Industry</span>"
            "<span style='flex:1.5;'>Agent</span>"
            "<span style='flex:3;'>Description</span>"
            "<span style='flex:1;text-align:center;'>Status</span>"
            "<span style='flex:0.6;text-align:center;'>Users</span>"
            "<span style='flex:1;text-align:center;'>Feedback</span>"
            "<span style='flex:0.9;text-align:center;'>Rating</span>"
            "<span style='flex:0.8;text-align:center;'></span>"
            "</div>"
        )

        html_agents = ""
        launch_path_overrides = {
            "agent_builder": "/agent_builder",
            "hf_wrapper": "/hf_inspector",
            "agent_manager": "/hf_inspector",
            "credit_appraisal": "/credit_appraisal",
            "credit_score": "/credit_score",
            "legal_compliance": "/legal_compliance",
            "asset_appraisal": "/asset_appraisal",
            "anti_fraud_kyc": "/anti_fraud_kyc",
            "it_troubleshooter": "/troubleshooter_agent",
            "unified_risk_orchestration": "/unified_risk",
            "chatbot_assistant": "/chatbot_assistant",
            "real_estate_evaluator": "/real_estate_evaluator",
            "ceo_driver_dashboard": "/ceo_driver_dashboard",
            "ceo_driver_seat": "/ceo_driver_dashboard",  # Map computed route to actual page
        }
        launch_path_overrides.update(CUSTOM_AGENT_LAUNCHES)
        # Handle both old tuple format (6 items) and new format (7 items with requires_login)
        for agent_tuple in AGENTS:
            if len(agent_tuple) == 7:
                sector, industry, agent, desc, status, emoji, requires_login = agent_tuple
            else:
                sector, industry, agent, desc, status, emoji = agent_tuple
                requires_login = False  # Default to no login for old format
            # Skip Agent Builder since it has its own featured frame
            if "Agent Builder" in agent:
                continue
            # ----- status color mapping (muted: accent for live, grey otherwise) -----
            if status == "NEW":
                status_label = "New"; status_color = pal["accent"]
            elif status == "Available":
                status_label = "Available"; status_color = pal["accent_alt"]
            elif status == "Coming Soon":
                status_label = "Coming soon"; status_color = pal["muted"]
            elif status == "Being Built":
                status_label = "In development"; status_color = pal["muted"]
            elif status == "WIP":
                status_label = "Preview"; status_color = pal["muted"]
            else:
                status_label = status; status_color = pal["muted"]

            # ----- feedback / usage data -----
            fb = feedback_data.get(agent, {"rating": 0, "users": 0, "comments": []})
            users = fb.get("users", 0)
            comments = fb.get("comments", [])
            comment_count = len(comments)
            rating = float(fb.get("rating", 0) or 0)
            rating_html = render_stars(rating) if rating else f"<span style='color:{pal['muted']};'>—</span>"
            rating_text = f"{rating:.1f}/5" if rating else "—"
            # Latest comment (most recent) - show under comment bubble
            latest_comment = html.escape(comments[-1]) if comments else "No feedback yet."
            # Comment list in dropdown (oldest to newest, reversed so newest shows first)
            comment_items = "".join(f"<li>{html.escape(c)}</li>" for c in reversed(comments))
            comment_list_html = comment_items or "<li>No feedback yet.</li>"

            # ----- build clean route name -----
            route_name = compute_route_name(agent)
            launch_path = launch_path_overrides.get(route_name, f"/{route_name}")
            
            # Check if login is required
            if requires_login:
                # Route through login page with agent info
                launch_url = f"?agent={route_name}&stage=login"
                # Store agent info for login redirect
                st.session_state[f"login_target_{route_name}"] = route_name
            else:
                launch_url = _launch_href(launch_path)
            
            status_norm = status.strip().lower()
            is_launchable = status_norm in {"available", "being built", "new"}
            if route_name == "it_troubleshooter":
                button_label = "Open"
            elif status_norm == "available":
                button_label = "Open"
            elif status_norm == "new":
                button_label = "Open"
            elif status_norm == "coming soon":
                # Special cases: Chatbot Assistant and CEO driver DASHBOARD have preview available
                if route_name == "chatbot_assistant":
                    button_label = "Preview"
                    launch_url = _launch_href("/chatbot_assistant")
                    is_launchable = True
                elif route_name in {"ceo_driver_dashboard", "ceo_driver_seat"}:
                    button_label = "Preview"
                    launch_url = _launch_href("/ceo_driver_dashboard")
                    is_launchable = True
                else:
                    button_label = "Coming soon"
                    is_launchable = False
            elif status_norm in {"wip"}:
                button_label = "Preview"
                if route_name in {"ceo_driver_dashboard", "ceo_driver_seat"}:
                    launch_url = _launch_href("/ceo_driver_dashboard")
                is_launchable = True
            else:
                button_label = "Preview"

            # Add login indicator to button if login required
            if requires_login and is_launchable:
                button_label = f"{button_label} · sign in"

            action_html = (
                f"<a class='launchbtn' href='{launch_url}'>{button_label}</a>"
                if is_launchable
                else "<span class='launchbtn launch-disabled'>Soon</span>"
            )

            # ----- append HTML for this agent card -----
            # Custom agents come from user-authored blueprints, so their text is
            # escaped before it reaches the card markup.
            industry_html = html.escape(str(industry))
            agent_html = html.escape(str(agent))
            desc_html = html.escape(str(desc))
            status_html = html.escape(str(status_label))
            html_agents += f"""
            <div class="agent-card">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;font-size:0.9rem;">
                    <div style="flex:1.2;color:{pal['muted']};">{industry_html}</div>
                    <div style="flex:1.5;font-weight:600;color:{pal['text']};">{agent_html}</div>
                    <div style="flex:3;color:{pal['subtext']};padding-right:1rem;">{desc_html}</div>
                    <div style="flex:1;text-align:center;"><span class="status-pill" style="color:{status_color};">{status_html}</span></div>
                    <div style="flex:0.6;text-align:center;color:{pal['subtext']};">{users}</div>
                    <div class="agent-comments" style="flex:1;text-align:center;">
                        <details>
                            <summary>{comment_count} comments</summary>
                            <ul class="comment-list">
                                {comment_list_html}
                            </ul>
                        </details>
                        <!-- Latest comment displayed under comment count -->
                        <div style="margin-top:0.35rem;font-size:0.75rem;color:{pal['muted']};max-width:200px;text-align:left;word-wrap:break-word;">
                            &ldquo;{latest_comment[:80]}{'...' if len(latest_comment) > 80 else ''}&rdquo;
                        </div>
                    </div>
                    <div style="flex:0.9;text-align:center;line-height:1.4;">
                        {rating_html}
                        <div style="font-size:0.78rem;color:{pal['muted']};">{rating_text}</div>
                    </div>
                    <div style="flex:0.8;text-align:center;">
                        {action_html}
                    </div>
                </div>
            </div>
            """

        # ============================================================
        # Agent Builder Featured Frame (separate neon frame)
        # ============================================================
        builder_tile = (
            f"background:{pal['bg']};border-radius:6px;padding:0.8rem 1rem;border:1px solid {pal['border']};"
        )
        st.markdown(f"""
        <div class="neon-header">Agent Builder</div>
        <div class="neon-frame" style="padding: 1.5rem; margin-bottom: 2.5rem;">
            <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 2rem; align-items: center;">
                <div>
                    <h3 style="font-size: 1.1rem; font-weight: 600; margin: 0 0 0.5rem 0;">
                        Compose custom agents from reusable functions
                    </h3>
                    <p style="font-size: 0.92rem; line-height: 1.65; margin-bottom: 1rem;">
                        Combine functions from Hugging Face agents, the Agent Manager and existing agents.
                        Select functions, configure the agent, and generate production-ready Python code.
                    </p>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-top: 1rem;">
                        <div style="{builder_tile}">
                            <div style="color:{pal['text']};font-weight:600;font-size:0.88rem;">17+ functions</div>
                            <div style="color:{pal['muted']};font-size:0.8rem;">HF, Manager and existing agents</div>
                        </div>
                        <div style="{builder_tile}">
                            <div style="color:{pal['text']};font-weight:600;font-size:0.88rem;">Visual builder</div>
                            <div style="color:{pal['muted']};font-size:0.8rem;">Point-and-click function selection</div>
                        </div>
                        <div style="{builder_tile}">
                            <div style="color:{pal['text']};font-weight:600;font-size:0.88rem;">Code generation</div>
                            <div style="color:{pal['muted']};font-size:0.8rem;">Production-ready Python</div>
                        </div>
                    </div>
                </div>
                <div style="text-align: center;">
                    <a href="/agent_builder" class="launchbtn" style="padding: 10px 24px; font-size: 0.95rem;">
                        Open Agent Builder
                    </a>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ============================================================
        # Render Agent Library Frame (separate)
        # ============================================================
        st.markdown(
            f"""
            <div class="neon-header">Agent Library</div>
            <div class="neon-frame" style="overflow:hidden;">
                {header_bar}
                {html_agents}
            </div>
            <footer>
                Open AIgents Sandbox Initiative · DzoanNguyenTran@gmail.com
            </footer>
            """,
            unsafe_allow_html=True
        )

        # ────────────────────────────────
        # Visitor Bar & Feedback Section (moved to bottom of landing page)
        # ────────────────────────────────
        # Initialize mock visitor data if needed
        def get_or_create_mock_visitors():
            """Get visitor stats or create mock data for demonstration."""
            try:
                api_url = os.getenv("API_URL", "http://localhost:8090")
                response = requests.get(f"{api_url}/v1/monitoring/visitors/stats", timeout=2)
                if response.status_code == 200:
                    stats = response.json()
                    # Only use real data if we have visitors
                    if stats.get("total_visitors", 0) > 0:
                        return stats
            except Exception:
                pass
            
            # Return mock data for demonstration
            return {
                "total_visitors": 42,
                "total_visits": 156,
                "countries": {
                    "United States": 25,
                    "Canada": 8,
                    "United Kingdom": 5,
                    "Germany": 4,
                    "France": 3,
                    "Australia": 2,
                    "Japan": 2,
                    "Brazil": 1,
                },
                "top_ips": []
            }

        visitor_stats = get_or_create_mock_visitors()
        
        # Load and manage general feedback (not agent-specific)
        GENERAL_FEEDBACK_FILE = Path(TMP_FEEDBACK_DIR) / "general_feedback.json"
        
        def load_general_feedback():
            """Load general feedback comments."""
            try:
                if GENERAL_FEEDBACK_FILE.exists():
                    with open(GENERAL_FEEDBACK_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return data.get("comments", [])
            except Exception:
                pass
            return []
        
        def save_general_feedback(comments):
            """Save general feedback comments."""
            try:
                data = {"comments": comments}
                with open(GENERAL_FEEDBACK_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Error saving feedback: {e}")
        
        # Initialize with 10 mock comments if empty
        all_comments = load_general_feedback()
        if not all_comments:
            mock_comments = [
                "🌟 Amazing platform! The AI agents are incredibly useful for our business.",
                "💡 Great work on the credit appraisal agent - it's saved us so much time!",
                "🚀 Love the real-time visitor tracking feature. Very insightful!",
                "⭐ The user interface is clean and intuitive. Well done!",
                "💬 Would love to see more agents added in the future.",
                "🎯 The fraud detection agent caught several suspicious cases for us.",
                "✨ Excellent documentation and easy to get started.",
                "🔥 The CEO dashboard is exactly what we needed for executive insights.",
                "💎 Open source approach is fantastic - transparency matters!",
                "👏 Keep up the great work! This platform has huge potential.",
            ]
            save_general_feedback(mock_comments)
            all_comments = mock_comments
        
        # Handle feedback submission from query params (set by JavaScript)
        if "feedback" in st.query_params:
            feedback_text = st.query_params["feedback"]
            if feedback_text.strip():
                all_comments.append(feedback_text.strip())
                save_general_feedback(all_comments)
                st.session_state["feedback_submitted"] = True
                # Clear query param and rerun
                st.query_params.clear()
                st.rerun()
        
        # Visitor status bar with feedback - now at bottom of page (not fixed)
        if visitor_stats:
            total_visitors = visitor_stats.get("total_visitors", 0)
            total_visits = visitor_stats.get("total_visits", 0)
            countries = visitor_stats.get("countries", {})
            
            # Format countries list (top 5)
            country_list = []
            if countries:
                sorted_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]
                country_list = [f"{country} ({count})" for country, count in sorted_countries]
            
            countries_str = " • ".join(country_list) if country_list else "No visitors yet"
            
            # Get current time for "live" indicator
            current_time = datetime.now().strftime("%H:%M:%S")
            
            # Escape comments for HTML
            escaped_comments = [html.escape(c) for c in all_comments]
            comments_json = json.dumps(escaped_comments)
            
            # Visitor bar and feedback section at bottom (not fixed position)
            st.markdown(
                f"""
                <!-- Rotating comments display -->
                <div id="comments-rotator" style="
                    background: {pal['card']};
                    border: 1px solid {pal['border']};
                    padding: 12px 20px;
                    margin-top: 3rem;
                    margin-bottom: 0.75rem;
                    min-height: 40px;
                    border-radius: 8px;
                ">
                    <div id="current-comment" style="
                        color: {pal['subtext']};
                        font-size: 0.9rem;
                        text-align: center;
                        transition: opacity 0.4s ease;
                    "></div>
                </div>

                <!-- Feedback input row -->
                <div id="feedback-input-row" style="
                    background: {pal['card']};
                    border: 1px solid {pal['border']};
                    padding: 12px 20px;
                    margin-bottom: 0.75rem;
                    border-radius: 8px;
                ">
                    <div style="display: flex; align-items: center; gap: 10px; max-width: 1200px; margin: 0 auto;">
                        <span style="color: {pal['text']}; font-weight: 500; font-size: 0.9rem; white-space: nowrap;">Feedback</span>
                        <input
                            type="text"
                            id="feedback-input-field"
                            placeholder="Share your thoughts..."
                            style="
                                flex: 1;
                                padding: 8px 14px;
                                background: {pal['input_bg']};
                                border: 1px solid {pal['input_border']};
                                border-radius: 6px;
                                color: {pal['text']};
                                font-size: 0.9rem;
                            "
                        />
                        <button
                            onclick="submitFeedback()"
                            style="
                                padding: 8px 18px;
                                background: {pal['accent']};
                                border: 1px solid {pal['accent']};
                                border-radius: 6px;
                                color: #ffffff;
                                font-weight: 500;
                                cursor: pointer;
                                font-size: 0.9rem;
                            "
                        >Submit</button>
                    </div>
                </div>

                <!-- Visitor status bar -->
                <div id="visitor-status-bar" style="
                    padding: 10px 20px;
                    font-size: 0.8rem;
                    color: {pal['muted']};
                    text-align: center;
                    margin-bottom: 2rem;
                ">
                    <div style="display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 14px;">
                        <span style="color: {pal['muted']};">Visitors <b style="color: {pal['text']}; font-weight: 600;">{total_visitors}</b></span>
                        <span style="color: {pal['border']};">|</span>
                        <span style="color: {pal['muted']};">Total visits <b style="color: {pal['text']}; font-weight: 600;">{total_visits}</b></span>
                        <span style="color: {pal['border']};">|</span>
                        <span style="color: {pal['muted']};">Countries: {countries_str}</span>
                        <span style="color: {pal['border']};">|</span>
                        <span id="refresh-time" style="color: {pal['muted']};">Updated {current_time}</span>
                    </div>
                </div>
                
                <script>
                    // Comments array
                    const comments = {comments_json};
                    let currentCommentIndex = 0;
                    
                    // Function to rotate comments
                    function rotateComment() {{
                        if (comments.length === 0) return;
                        const commentEl = document.getElementById('current-comment');
                        if (commentEl) {{
                            commentEl.style.opacity = '0';
                            setTimeout(function() {{
                                commentEl.textContent = '“' + comments[currentCommentIndex] + '”';
                                commentEl.style.opacity = '1';
                                currentCommentIndex = (currentCommentIndex + 1) % comments.length;
                            }}, 500);
                        }}
                    }}
                    
                    // Initialize first comment
                    if (comments.length > 0) {{
                        rotateComment();
                        // Rotate every 5 seconds
                        setInterval(rotateComment, 5000);
                    }}
                    
                    // Submit feedback function
                    function submitFeedback() {{
                        const input = document.getElementById('feedback-input-field');
                        if (input && input.value.trim()) {{
                            // Submit via URL query parameter
                            const feedback = encodeURIComponent(input.value.trim());
                            const currentUrl = window.location.href.split('?')[0];
                            window.location.href = currentUrl + '?feedback=' + feedback;
                        }} else {{
                            alert('Please enter your feedback before submitting.');
                        }}
                    }}
                    
                    // Allow Enter key to submit
                    document.addEventListener('DOMContentLoaded', function() {{
                        const input = document.getElementById('feedback-input-field');
                        if (input) {{
                            input.addEventListener('keypress', function(e) {{
                                if (e.key === 'Enter') {{
                                    submitFeedback();
                                }}
                            }});
                        }}
                    }});
                </script>
                """,
                unsafe_allow_html=True,
            )

        st.stop()

# ────────────────────────────────
# STAGE: AGENTS (Neon Styled)
# ────────────────────────────────
if st.session_state.stage == "agents":
    # Inject CSS once
    st.markdown(f"""
    <style>
    .neon-frame {{
        padding: 0 !important;
        margin: 0.5rem 0 3rem 0;
        overflow: hidden;
    }}
    .neon-table {{
        width: 100%;
        border-collapse: collapse;
        border: none !important;
    }}
    .neon-table th, .neon-table td {{
        padding: 12px 18px;
        border: none !important;
        border-bottom: 1px solid {pal['border']} !important;
        color: {pal['subtext']};
        text-align: left;
        font-size: 0.9rem;
    }}
    .neon-table tr:last-child td {{ border-bottom: none !important; }}
    .neon-table tbody tr:hover {{ background: {pal['table_hover_bg']}; }}
    .neon-table td:first-child {{ color: {pal['text']}; font-weight: 600; }}
    .neon-table th {{
        background: {pal['table_head_bg']};
        color: {pal['muted']};
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.72rem;
        font-weight: 600;
    }}
    </style>
    """, unsafe_allow_html=True)

    # Header section
    st.markdown("<div class='neon-header'>Available agents</div>", unsafe_allow_html=True)

    # Data - Retail Banking Suite agents sorted in specified order
    agent_rows = [
        {"Agent": "🚗 CEO driver DASHBOARD",
         "Description": "Executive cockpit with AI copilots, KPIs, and calendar automation",
         "Status": "🧪 WIP",
         "Action": '<a class="macbtn" href="/ceo_driver_dashboard" target="_self">👁️ Preview</a>'},
        {"Agent": "🏠 Real Estate Evaluator Agent",
         "Description": "Interactive map with market price comparison and zone analysis",
         "Status": "🆕 NEW",
         "Action": '<a class="macbtn" href="/real_estate_evaluator">🚀 Launch</a>'},
        {"Agent": "🛡️ Anti-Fraud & KYC Agent",
         "Description": "Streamlined onboarding with fraud scoring",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/anti_fraud_kyc">🚀 Launch</a>'},
        {"Agent": "💳 Credit Score Agent",
         "Description": "Calculate credit scores (300-850) for loan applications",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/credit_score">🚀 Launch</a>'},
        {"Agent": "🏦 Asset Appraisal Agent",
         "Description": "Market-driven collateral valuation",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/asset_appraisal">🚀 Launch</a>'},
        {"Agent": "💳 Credit Appraisal Agent",
         "Description": "Explainable AI for loan decisioning",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/credit_appraisal">🚀 Launch</a>'},
        {"Agent": "⚖️ Legal Compliance Agent",
         "Description": "Regulatory compliance, sanctions, PEP, licensing checks",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/legal_compliance">🚀 Launch</a>'},
        {"Agent": "🧩 Unified Risk Orchestration Agent",
         "Description": "Compounds asset+credit+fraud into one decision",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/unified_risk">🚀 Launch</a>'},
        {"Agent": "🧠 IT Troubleshooter Agent",
         "Description": "First-principles + case-memory incident solver",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/troubleshooter_agent">🚀 Launch</a>'},
        {"Agent": "💬 Chatbot Assistant",
         "Description": "Context-aware embedded assistant",
         "Status": "⏳ Coming Soon",
         "Action": '<a class="macbtn" href="/chatbot_assistant">👁️ Preview</a>'},
        {"Agent": "🧑‍🚀 Persona Strategy Room",
         "Description": "Invite multiple personas to a live meeting",
         "Status": "✅ Available",
         "Action": '<a class="macbtn" href="/persona_chatroom">🪩 Convene</a>'},
    ]
    df = pd.DataFrame(agent_rows)

    # Neon table frame
    html_table = df.to_html(escape=False, index=False, classes="neon-table")
    st.markdown(f"<div class='neon-frame'>{html_table}</div>", unsafe_allow_html=True)

    # Initialize mock visitor data if needed
    def get_or_create_mock_visitors():
        """Get visitor stats or create mock data for demonstration."""
        try:
            api_url = os.getenv("API_URL", "http://localhost:8090")
            response = requests.get(f"{api_url}/v1/monitoring/visitors/stats", timeout=2)
            if response.status_code == 200:
                stats = response.json()
                # Only use real data if we have visitors
                if stats.get("total_visitors", 0) > 0:
                    return stats
        except Exception:
            pass
        
        # Return mock data for demonstration
        return {
            "total_visitors": 42,
            "total_visits": 156,
            "countries": {
                "United States": 25,
                "Canada": 8,
                "United Kingdom": 5,
                "Germany": 4,
                "France": 3,
                "Australia": 2,
                "Japan": 2,
                "Brazil": 1,
            },
            "top_ips": []
        }

    visitor_stats = get_or_create_mock_visitors()
    
    # Load and manage general feedback (not agent-specific)
    GENERAL_FEEDBACK_FILE = Path(TMP_FEEDBACK_DIR) / "general_feedback.json"
    
    def load_general_feedback():
        """Load general feedback comments."""
        try:
            if GENERAL_FEEDBACK_FILE.exists():
                with open(GENERAL_FEEDBACK_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("comments", [])
        except Exception:
            pass
        return []
    
    def save_general_feedback(comments):
        """Save general feedback comments."""
        try:
            data = {"comments": comments}
            with open(GENERAL_FEEDBACK_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
    
    # Initialize with 10 mock comments if empty
    all_comments = load_general_feedback()
    if not all_comments:
        mock_comments = [
            "🌟 Amazing platform! The AI agents are incredibly useful for our business.",
            "💡 Great work on the credit appraisal agent - it's saved us so much time!",
            "🚀 Love the real-time visitor tracking feature. Very insightful!",
            "⭐ The user interface is clean and intuitive. Well done!",
            "💬 Would love to see more agents added in the future.",
            "🎯 The fraud detection agent caught several suspicious cases for us.",
            "✨ Excellent documentation and easy to get started.",
            "🔥 The CEO dashboard is exactly what we needed for executive insights.",
            "💎 Open source approach is fantastic - transparency matters!",
            "👏 Keep up the great work! This platform has huge potential.",
        ]
        save_general_feedback(mock_comments)
        all_comments = mock_comments
    
    # Handle feedback submission from query params (set by JavaScript)
    if "feedback" in st.query_params:
        feedback_text = st.query_params["feedback"]
        if feedback_text.strip():
            all_comments.append(feedback_text.strip())
            save_general_feedback(all_comments)
            st.session_state["feedback_submitted"] = True
            # Clear query param and rerun
            st.query_params.clear()
            st.rerun()
    
    # Visitor status bar with feedback - removed from agents page (now only on landing page)

    # Footer
    st.markdown(
        "<footer>Open AIgents Sandbox Initiative · DzoanNguyenTran@gmail.com</footer>",
        unsafe_allow_html=True
    )

    st.stop()




# # ────────────────────────────────
# # STAGE: AGENTS boring
# # ────────────────────────────────
# if st.session_state.stage == "agents":
#     top = st.columns([1, 6, 1])
#     with top[1]:
#         st.title("🤖 Available AI Agents")

#     df = pd.DataFrame([
#         {"Agent": "💳 Credit Appraisal Agent",
#          "Description": "Explainable AI for retail loan decisioning",
#          "Status": "✅ Available",
#          "Action": '<a class="macbtn" href="?agent=credit&stage=login">🚀 Launch</a>'},
#         {"Agent": "🏦 Asset Appraisal Agent",
#          "Description": "Market-driven collateral valuation",
#          "Status": "✅ Available",
#          "Action": '<a class="macbtn" href="?agent=asset&stage=asset_agent">🚀 Launch</a>'},
#     ])
#     st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
#     st.markdown(
#         "<footer>Made with ❤️ by DzoanNguyenTran@gmail.com — Open AIgents Sandbox Initiative</footer>",
#         unsafe_allow_html=True
#     )
#     st.stop()


# ────────────────────────────────
# STAGE: LOGIN
# ────────────────────────────────
if st.session_state.stage == "login":
    # Get target agent from session state
    login_target = st.session_state.get("login_target", "credit_agent")
    selected_agent = st.session_state.get("selected_agent", "credit")
    
    # Find agent name for display
    agent_display_name = "AI Credit Appraisal Platform"
    for agent_tuple in MANAGED_AGENTS:
        if len(agent_tuple) >= 7:
            sector, industry, agent_name, desc, status, emoji, login_req = agent_tuple
        else:
            sector, industry, agent_name, desc, status, emoji = agent_tuple
        route_name = compute_route_name(agent_name)
        if route_name == selected_agent or route_name == login_target:
            agent_display_name = agent_name
            break
    
    top = st.columns([1, 4, 1])
    with top[0]:
        if st.button("← Agents", key="btn_back_agents_from_login"):
            st.session_state.stage = "agents"
            st.rerun()
    with top[1]:
        st.title(f"Sign in to {agent_display_name}")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        user = st.text_input("Username", placeholder="e.g. dzoan")
    with c2:
        email = st.text_input("Email", placeholder="e.g. dzoan@demo.local")
    with c3:
        pwd = st.text_input("Password", type="password", placeholder="Enter any password")
    if st.button("Sign in", key="btn_login_submit", type="primary", use_container_width=True):
        if user.strip() and email.strip():
            st.session_state.user_info = {
                "name": user.strip(),
                "email": email.strip(),
                "flagged": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            st.session_state.logged_in = True
            # Route to the target agent after login
            route_name = login_target
            # Try to switch to the agent page
            try:
                st.switch_page(f"pages/{route_name}.py")
            except Exception:
                # Fallback: set stage based on route
                if route_name in ["credit_appraisal", "credit"]:
                    st.session_state.stage = "credit_agent"
                elif route_name in ["asset_appraisal", "asset"]:
                    st.session_state.stage = "asset_agent"
                else:
                    st.session_state.stage = route_name
                st.rerun()
        else:
            st.error("⚠️ Please fill all fields before continuing.")
    st.markdown("<footer>Open AIgents Sandbox Initiative · DzoanNguyenTran@gmail.com</footer>", unsafe_allow_html=True)
    st.stop()



#


# ────────────────────────────────
# STAGE: ASSET WORKFLOW (redirect to page)
# ────────────────────────────────
if  st.session_state.stage == "asset_agent":
    try:
        st.switch_page("pages/asset_appraisal.py")
    except Exception as e:
        st.error(f"Could not switch to asset appraisal page: {e}")
        st.info("Ensure file exists at services/ui/pages/asset_appraisal.py")

if  st.session_state.stage == "troubleshooter_agent":
    try:
        st.switch_page("pages/troubleshooter_agent.py")
    except Exception as e:
        st.error(f"Could not switch to troubleshooter agent page: {e}")
        st.info("Ensure file exists at services/ui/pages/troubleshooter_agent.py")

if  st.session_state.stage == "real_estate_evaluator":
    try:
        st.switch_page("pages/real_estate_evaluator.py")
    except Exception as e:
        st.error(f"Could not switch to real estate evaluator page: {e}")
        st.info("Ensure file exists at services/ui/pages/real_estate_evaluator.py")

if  st.session_state.stage == "ceo_driver_dashboard":
    try:
        st.switch_page("pages/ceo_driver_dashboard.py")
    except Exception as e:
        st.error(f"Could not switch to CEO driver DASHBOARD: {e}")
        st.info("Ensure file exists at services/ui/pages/ceo_driver_dashboard.py")
