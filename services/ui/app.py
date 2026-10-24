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
        page_title="AI Agent Market",
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
# PAGE: AI AGENT MARKET (landing + agents stages)
# ────────────────────────────────
MARKET_NAME = "AI Agent Market"


def _clean_label(label) -> str:
    """Strip leading emoji/punctuation so names read like product titles."""
    return re.sub(r"^[^\w]+", "", str(label)).strip()


def _svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()


# Line icons (24x24, stroke): one logo per vertical.
_VERTICAL_ICON_PATHS = {
    "ai tools": '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    "executive": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18"/>',
    "banking": '<path d="M12 3l9 5H3z"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18"/>',
    "information technology": '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    "energy": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "automobile": '<path d="M3 17v-4l2.5-5.5h13L21 13v4z"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/>',
    "legal": '<path d="M12 3v18M7 21h10M5 7h14"/><path d="M5 7l-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z"/>',
    "retail": '<path d="M6 7h12l1 14H5z"/><path d="M9 7a3 3 0 0 1 6 0"/>',
}
_DEFAULT_ICON_PATH = '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'
# Neon-blue family gradients so each vertical's tile is distinct but on-brand.
_VERTICAL_GRADIENTS = {
    "ai tools": ("#1a6dff", "#00c6ff"),
    "executive": ("#0b2a6b", "#1a6dff"),
    "banking": ("#1739c9", "#4f7bff"),
    "information technology": ("#0369a1", "#22d3ee"),
    "energy": ("#0e7490", "#2dd4bf"),
    "automobile": ("#1e3a8a", "#60a5fa"),
    "legal": ("#312e81", "#6d7cff"),
    "retail": ("#0c4a6e", "#38bdf8"),
}
_DEFAULT_GRADIENT = ("#1a6dff", "#00c6ff")


def _vertical_key(sector: str) -> str:
    s = _clean_label(sector).lower()
    for key in _VERTICAL_ICON_PATHS:
        if key in s:
            return key
    return ""


def vertical_logo(sector: str, size: int = 52) -> str:
    """Gradient tile with the vertical's white line icon, as an <img> tag."""
    key = _vertical_key(sector)
    c1, c2 = _VERTICAL_GRADIENTS.get(key, _DEFAULT_GRADIENT)
    path = _VERTICAL_ICON_PATHS.get(key, _DEFAULT_ICON_PATH)
    return icon_tile(path, c1, c2, size, gid=f"g{key.replace(' ', '') or 'default'}")


# Icons for the hero's "Try these tasks" cards.
TASK_ICON_COMPARE = '<rect x="3" y="4" width="7" height="16" rx="1.5"/><rect x="14" y="4" width="7" height="16" rx="1.5"/><path d="M5.5 9h2M16.5 9h2M5.5 13h2M16.5 13h2"/>'
TASK_ICON_BUILD = '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>'


def icon_tile(path: str, c1: str, c2: str, size: int, gid: str = "gt") -> str:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
        f'<rect width="48" height="48" rx="11" fill="url(#{gid})"/>'
        f'<g transform="translate(12 12)" fill="none" stroke="#ffffff" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{path}</g></svg>'
    )
    return f'<img src="{_svg_data_uri(svg)}" width="{size}" height="{size}" alt="" style="display:block;border-radius:{size // 4}px;"/>'


BRAND_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">'
    '<defs><linearGradient id="aam" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#e5133a"/><stop offset="0.55" stop-color="#7a3cff"/><stop offset="1" stop-color="#1a6dff"/></linearGradient></defs>'
    '<rect width="40" height="40" rx="10" fill="url(#aam)"/>'
    # three "agents" on a shelf, the last one leaning: a market of agents
    '<rect x="9" y="11" width="5" height="18" rx="1.5" fill="#ffffff"/>'
    '<rect x="16" y="8" width="5" height="21" rx="1.5" fill="#ffffff" fill-opacity="0.85"/>'
    '<rect x="23.5" y="10" width="5" height="19" rx="1.5" fill="#ffffff" fill-opacity="0.7" transform="rotate(14 26 29)"/>'
    '<rect x="8" y="30" width="24" height="2.2" rx="1.1" fill="#ffffff"/>'
    '</svg>'
)

STATUS_META = {
    # status -> (label, css class, is_live)
    "new": ("New", "aw-badge-new", True),
    "available": ("Available", "aw-badge-live", True),
    "wip": ("Preview", "aw-badge-soft", True),
    "being built": ("In development", "aw-badge-soft", True),
    "coming soon": ("Coming soon", "aw-badge-muted", False),
}

LAUNCH_PATH_OVERRIDES = {
    "agent_builder": "/agent_builder",
    "hf_wrapper": "/hf_inspector",
    "hf_agent_wrapper": "/hf_inspector",
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
LAUNCH_PATH_OVERRIDES.update(CUSTOM_AGENT_LAUNCHES)
# "Coming soon" agents that already have a preview page.
PREVIEWABLE_ROUTES = {"chatbot_assistant", "ceo_driver_dashboard", "ceo_driver_seat"}
# Deploy menu targets: (query value, short tag, label).
DEPLOY_TARGETS = [
    ("openstack", "OSK", "OpenStack"),
    ("aws", "AWS", "Amazon Web Services"),
    ("gcp", "GCP", "Google Cloud"),
    ("azure", "AZ", "Microsoft Azure"),
    ("gpu_cloud", "GPU", "GPU Cloud (rent)"),
]


def build_catalog() -> list[dict]:
    catalog = []
    for agent_tuple in AGENTS:
        if len(agent_tuple) == 7:
            sector, industry, agent, desc, status, emoji, requires_login = agent_tuple
        else:
            sector, industry, agent, desc, status, emoji = agent_tuple
            requires_login = False  # Default to no login for old format
        status_norm = str(status).strip().lower()
        label, badge_cls, is_live = STATUS_META.get(status_norm, (str(status), "aw-badge-soft", True))
        route_name = compute_route_name(agent)
        launch_path = LAUNCH_PATH_OVERRIDES.get(route_name, f"/{route_name}")
        launchable = is_live or route_name in PREVIEWABLE_ROUTES
        url = f"?agent={route_name}&stage=login" if requires_login else _launch_href(launch_path)
        if not launchable:
            cta = "Coming soon"
        elif status_norm in {"wip", "coming soon", "being built"}:
            cta = "Preview"
        else:
            cta = "Launch free"
        fb = feedback_data.get(agent, {"rating": 0, "users": 0, "comments": []})
        catalog.append({
            "route": route_name,
            "name": _clean_label(agent),
            "industry": _clean_label(industry),
            "sector": _clean_label(sector) or "Other",
            "sector_raw": sector,
            "desc": str(desc),
            "status_label": label,
            "badge_cls": badge_cls,
            "live": is_live,
            "launchable": launchable,
            "url": url,
            "cta": cta,
            "requires_login": bool(requires_login),
            "rating": float(fb.get("rating", 0) or 0),
            "users": int(fb.get("users", 0) or 0),
        })
    return catalog


def _rating_html(item: dict) -> str:
    if not item["rating"]:
        return "<span class='aw-rating'><span class='aw-rating-none'>Not yet rated</span></span>"
    full = int(round(item["rating"]))
    return (
        "<span class='aw-rating'>"
        f"<b>{item['rating']:.1f}</b>"
        f"<span class='aw-stars'>{'★' * full}<span class='aw-stars-off'>{'★' * (5 - full)}</span></span>"
        f"<span class='aw-rating-n'>({item['users']})</span></span>"
    )


def _tags_html(item: dict) -> str:
    tags = "<span class='aw-tag aw-tag-free'>Free</span><span class='aw-tag'>Runs in sandbox</span>"
    if item["requires_login"]:
        tags += "<span class='aw-tag'>Sign-in required</span>"
    return f"<div class='aw-tags'>{tags}</div>"


def _detail_href(item: dict) -> str:
    return f"?view={html.escape(item['route'])}"


def _title_html(item: dict) -> str:
    """Product titles open the agent's detail page, like a marketplace listing."""
    return f"<a class='aw-title' href='{_detail_href(item)}' target='_self'>{html.escape(item['name'])}</a>"


def _cta_html(item: dict) -> str:
    e = html.escape
    if item["launchable"]:
        return f"<a class='aw-cta' href='{e(item['url'])}' target='_self'>{e(item['cta'])}</a>"
    return f"<span class='aw-cta aw-cta-off'>{e(item['cta'])}</span>"


def _deploy_html(item: dict) -> str:
    """Pure-HTML dropdown (<details>) listing the cloud deploy targets."""
    if not item["launchable"]:
        return ""
    links = "".join(
        f"<a href='{_launch_href('/deployment_in_production')}?agent={html.escape(item['route'])}&amp;target={value}' target='_self'>"
        f"<i>{tag}</i>{label}</a>"
        for value, tag, label in DEPLOY_TARGETS
    )
    return (
        "<details class='aw-deploy'><summary>Deploy ▾</summary>"
        f"<div class='aw-deploy-menu'><div class='aw-deploy-head'>Deploy to</div>{links}</div></details>"
    )


def top_card_html(item: dict, rank: int) -> str:
    """AWS-style 'most subscribed' card."""
    return (
        "<div class='aw-card'>"
        "<div class='aw-card-top'>"
        f"<div class='aw-logo'>{vertical_logo(item['sector_raw'], size=46)}</div>"
        f"<span class='aw-rank'>Top {rank}</span>"
        "</div>"
        f"<div class='aw-by'>Built by: Open AIgents · {html.escape(item['industry'])}</div>"
        f"{_title_html(item)}"
        f"{_rating_html(item)}"
        f"{_tags_html(item)}"
        f"<div class='aw-desc'>{html.escape(item['desc'])}</div>"
        f"<div class='aw-card-actions'>{_cta_html(item)}{_deploy_html(item)}</div>"
        "</div>"
    )


def list_row_html(item: dict) -> str:
    """AWS-style search-result row."""
    return (
        "<div class='aw-row'>"
        f"<div class='aw-logo'>{vertical_logo(item['sector_raw'], size=52)}</div>"
        "<div class='aw-row-main'>"
        f"{_title_html(item)}"
        f"<div class='aw-by'>By Open AIgents · {html.escape(item['industry'])}</div>"
        f"<div class='aw-desc aw-desc-row'>{html.escape(item['desc'])}</div>"
        f"{_tags_html(item)}"
        "</div>"
        "<div class='aw-row-side'>"
        f"<span class='aw-badge {item['badge_cls']}'>{html.escape(item['status_label'])}</span>"
        f"{_rating_html(item)}"
        f"<div class='aw-card-actions'>{_cta_html(item)}{_deploy_html(item)}</div>"
        "</div>"
        "</div>"
    )


def render_marketplace_css():
    accent = pal["accent"]
    st.markdown(
        f"""
<style>
.block-container, [data-testid="stMainBlockContainer"] {{ max-width: 1320px !important; padding-top: 0 !important; }}
[data-testid="stHeader"] {{ display: none !important; }}
[data-testid="stMain"] {{ overflow-x: hidden; }}
/* Rows that only inject <style> still take a flex gap; collapse them (the CSS still applies). */
[data-testid="stElementContainer"]:has(style) {{ display: none !important; }}
/* Full-bleed sections break out of the centered content column. */
.st-key-aw_header, .st-key-aw_hero {{ width: 100vw !important; max-width: 100vw !important; margin-left: calc(50% - 50vw) !important; }}
/* Two-tier dark top bar */
.st-key-aw_header {{
    background: #0a1428; padding: 1rem max(2rem, calc(50vw - 640px)) 0 max(2rem, calc(50vw - 640px)); gap: 0 !important;
    box-shadow: 0 10px 30px -18px rgba(10,20,40,0.9);
}}
.st-key-aw_header p, .st-key-aw_header span, .st-key-aw_header label {{ color:#e6edf7 !important; }}
.aw-brand {{ display:flex; align-items:center; gap:0.8rem; text-decoration:none !important; }}
.aw-word {{ font-size:1.75rem; font-weight:800; color:#ffffff !important; letter-spacing:-0.025em; line-height:1; }}
.aw-word b {{ color:{pal['red']} !important; font-weight:800; text-shadow:0 0 16px rgba(229,19,58,0.55); }}
.aw-word small {{ display:block; font-size:0.7rem; font-weight:600; color:#8fb3d9 !important; letter-spacing:0.12em; text-transform:uppercase; margin-top:6px; }}
.aw-head-actions {{ display:flex; justify-content:flex-end; gap:0.75rem; align-items:center; }}
.aw-head-actions a {{ font-size:0.9rem; font-weight:600; text-decoration:none !important; white-space:nowrap; }}
.aw-btn-red {{ background:{pal['red']}; color:#ffffff !important; padding:0.6rem 1.15rem; border-radius:8px; box-shadow:0 0 18px rgba(229,19,58,0.45); }}
.aw-btn-red:hover {{ filter:brightness(1.1); }}
.aw-btn-ghost {{ color:#e6edf7 !important; padding:0.55rem 1rem; border-radius:8px; border:1px solid rgba(255,255,255,0.28); }}
.aw-btn-ghost:hover {{ border-color:#3ea6ff; color:#3ea6ff !important; }}
.aw-nav {{
    display:flex; gap:1.9rem; flex-wrap:wrap; align-items:center;
    margin: 0.9rem calc(-1 * max(2rem, calc(50vw - 640px))) 0; padding: 0.7rem max(2rem, calc(50vw - 640px));
    background:#13213d; border-bottom: 4px solid transparent;
    border-image: linear-gradient(90deg, {pal['red']} 0%, {pal['red']} 35%, {accent} 65%, {accent} 100%) 1;
}}
.aw-nav a {{ color:#e6edf7 !important; font-size:0.95rem; font-weight:600; text-decoration:none !important; }}
.aw-nav a:hover {{ color:#3ea6ff !important; text-decoration:none; }}
.aw-nav .aw-nav-right {{ margin-left:auto; display:flex; gap:1.9rem; }}
/* Hero */
.st-key-aw_hero {{
    background:
        radial-gradient(700px 260px at 12% 0%, rgba(229,19,58,0.10), transparent 60%),
        radial-gradient(800px 300px at 88% 10%, rgba(26,109,255,0.16), transparent 60%),
        {pal['hero_bg']};
    padding: 3rem max(2rem, calc(50vw - 540px)) 2.5rem; margin-bottom: 1.5rem;
}}
.aw-eyebrow {{ text-align:center; font-weight:700; font-size:0.95rem; color:{pal['hero_text']} !important; letter-spacing:0.02em; }}
.aw-eyebrow i {{ color:{pal['red']}; font-style:normal; text-shadow:0 0 10px rgba(229,19,58,0.5); }}
.aw-hero-title, .aw-hero-title * {{ text-align:center; font-size:2.6rem !important; font-weight:800 !important; letter-spacing:-0.03em !important; color:{pal['hero_text']} !important; margin:0.4rem 0 0.4rem 0 !important; line-height:1.15 !important; }}
.aw-hero-title em {{ font-style:normal; color:{pal['red']} !important; }}
.aw-hero-sub {{ text-align:center; font-size:1.08rem; color:{pal['subtext']} !important; margin-bottom:1.5rem; }}
.st-key-aw_hero [data-baseweb="input"] {{
    border-radius: 10px !important; border: 1px solid {pal['hero_border']} !important; background:{pal['hero_card']} !important; overflow:hidden;
}}
.st-key-aw_hero [data-baseweb="input"]:focus-within {{ border-color:{accent} !important; box-shadow:0 0 0 3px rgba(26,109,255,0.18), 0 0 22px rgba(0,170,255,0.35); }}
.st-key-aw_hero [data-baseweb="input"] input {{
    height: 54px; font-size: 1rem !important; color:{pal['hero_text']} !important; background:{pal['hero_card']} !important; border:none !important; padding-left:1rem !important;
}}
.aw-disclaimer {{ font-size:0.76rem; color:{pal['muted']} !important; margin-top:0.3rem; }}
.aw-h3 {{ font-size:1.15rem; font-weight:700; color:{pal['hero_text']} !important; margin:1.4rem 0 0.7rem 0; }}
.aw-tasks {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
.aw-task {{ display:flex; gap:0.9rem; align-items:flex-start; background:{pal['hero_card']}; border:1px solid {pal['hero_border']}; border-radius:12px; padding:1rem 1.1rem; text-decoration:none !important; transition: border-color .15s, box-shadow .15s; }}
.aw-task:hover {{ border-color:{accent}; box-shadow:0 0 0 1px {accent}, 0 8px 24px -12px rgba(26,109,255,0.55); }}
.aw-task-icon {{ flex:none; border-radius:8px; box-shadow:0 0 12px rgba(0,170,255,0.5); }}
.aw-task b {{ display:block; color:{pal['hero_text']} !important; font-size:0.95rem; }}
.aw-task span {{ color:{pal['subtext']} !important; font-size:0.9rem; }}
.aw-task em {{ margin-left:auto; color:{accent} !important; font-size:0.78rem; white-space:nowrap; }}
/* Value proposition intro (What / Why / So what / For who / How / What now) */
.vp-eyebrow {{ text-align:center; font-size:0.78rem; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:{pal['red']} !important; margin-top:0.5rem; }}
.vp-title {{ text-align:center; font-size:1.9rem; font-weight:800; letter-spacing:-0.02em; color:{pal['text']} !important; margin:0.3rem 0 0.4rem 0; }}
.vp-sub {{ text-align:center; max-width:780px; margin:0 auto 1.6rem auto; font-size:1rem; line-height:1.6; color:{pal['subtext']} !important; }}
.vp-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; }}
.vp-card {{ background:{pal['card']}; border:1px solid {pal['border']}; border-top:3px solid {accent}; border-radius:12px; padding:1.1rem 1.2rem 1.2rem; display:flex; flex-direction:column; gap:0.45rem; }}
.vp-card:nth-child(odd) {{ border-top-color:{pal['red']}; }}
.vp-label {{ display:flex; align-items:center; gap:0.55rem; font-size:0.74rem; font-weight:800; letter-spacing:0.12em; text-transform:uppercase; color:{pal['red']} !important; }}
.vp-card:nth-child(even) .vp-label {{ color:{accent} !important; }}
.vp-card h4 {{ margin:0.2rem 0 0 0 !important; font-size:1.05rem !important; font-weight:700 !important; line-height:1.35 !important; color:{pal['text']} !important; }}
.vp-card p, .vp-card li {{ font-size:0.88rem; line-height:1.55; color:{pal['subtext']} !important; margin:0; }}
.vp-card ul {{ margin:0.1rem 0 0 0; padding-left:1rem; }}
.vp-card li {{ margin-bottom:0.25rem; }}
.vp-card li b, .vp-card p b {{ color:{pal['text']} !important; font-weight:600; }}
.vp-how {{ margin-top:16px; background:{pal['card']}; border:1px solid {pal['border']}; border-radius:12px; padding:1.2rem 1.4rem; }}
.vp-how-head {{ display:flex; align-items:center; gap:0.6rem; margin-bottom:0.9rem; }}
.vp-how-head h4 {{ margin:0 !important; font-size:1.05rem !important; font-weight:700 !important; color:{pal['text']} !important; }}
.vp-steps {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; position:relative; }}
.vp-step {{ position:relative; padding:0.85rem 0.9rem; border-radius:10px; background:{pal['bg']}; border:1px solid {pal['border']}; }}
.vp-step:not(:last-child)::after {{ content:"→"; position:absolute; right:-11px; top:50%; transform:translateY(-50%); color:{pal['muted']}; font-weight:700; z-index:1; }}
.vp-step i {{ font-style:normal; display:inline-flex; align-items:center; justify-content:center; width:1.6rem; height:1.6rem; border-radius:50%;
    background:linear-gradient(135deg,{pal['red']},{accent}); color:#fff !important; font-size:0.8rem; font-weight:800; margin-bottom:0.4rem; box-shadow:0 0 12px rgba(26,109,255,0.35); }}
.vp-step b {{ display:block; color:{pal['text']} !important; font-size:0.92rem; margin-bottom:0.15rem; }}
.vp-step span {{ display:block; font-size:0.8rem; line-height:1.45; color:{pal['subtext']} !important; }}
.vp-step em {{ display:table; margin-top:0.45rem; font-style:normal; font-size:0.68rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; color:{accent} !important; }}
.vp-now {{ margin-top:16px; display:flex; align-items:center; justify-content:space-between; gap:1.25rem; flex-wrap:wrap; padding:1.35rem 1.6rem; border-radius:12px;
    background:linear-gradient(110deg, #0a1428 0%, #13213d 55%, #14306b 100%); border-bottom:4px solid transparent;
    border-image: linear-gradient(90deg, {pal['red']} 0%, {accent} 100%) 1; }}
.vp-now .vp-label {{ color:#ff6b84 !important; }}
.vp-now h4, .vp-now h4 * {{ margin:0.25rem 0 0.2rem 0 !important; font-size:1.25rem !important; font-weight:800 !important; color:#ffffff !important; }}
.vp-now p {{ margin:0; color:#c9d6ea !important; font-size:0.92rem; }}
.vp-now-ctas {{ display:flex; gap:0.6rem; flex-wrap:wrap; }}
.vp-now-ctas a {{ font-size:0.9rem; font-weight:700; padding:0.6rem 1.1rem; border-radius:8px; text-decoration:none !important; white-space:nowrap; }}
.vp-cta-red {{ background:{pal['red']}; color:#ffffff !important; box-shadow:0 0 18px rgba(229,19,58,0.45); }}
.vp-cta-blue {{ background:{accent}; color:#ffffff !important; box-shadow:0 0 18px rgba(26,109,255,0.45); }}
.vp-cta-ghost {{ border:1px solid rgba(255,255,255,0.35); color:#ffffff !important; }}
.vp-now-ctas a:hover {{ filter:brightness(1.1); }}
@media (max-width: 1100px) {{ .vp-grid {{ grid-template-columns:repeat(2,1fr); }} .vp-steps {{ grid-template-columns:repeat(2,1fr); }} .vp-step::after {{ display:none; }} }}
@media (max-width: 700px) {{ .vp-grid, .vp-steps {{ grid-template-columns:1fr; }} }}
/* Section headings */
.aw-h2 {{ text-align:center; font-size:1.45rem; font-weight:700; color:{pal['text']} !important; margin:1.8rem 0 0.6rem 0; }}
/* Top cards */
.aw-cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:18px; margin-top:0.8rem; }}
.aw-card {{ background:{pal['card']}; border:1px solid {pal['border']}; border-radius:14px; padding:1.1rem 1.2rem; display:flex; flex-direction:column; gap:0.5rem; min-height:290px; transition: box-shadow .15s, border-color .15s; }}
.aw-card:hover {{ border-color:{accent}; box-shadow:0 10px 30px -14px rgba(26,109,255,0.55); }}
.aw-card-top {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.3rem; }}
.aw-logo {{ padding:4px; border:1px solid {pal['border']}; border-radius:12px; background:{pal['card']}; flex:none; }}
.aw-rank {{ background:{pal['red']}; color:#ffffff !important; font-size:0.75rem; font-weight:700; padding:2px 9px; border-radius:6px; box-shadow:0 0 12px rgba(229,19,58,0.45); }}
.aw-by {{ font-size:0.8rem; color:{pal['muted']} !important; }}
.aw-title {{ font-size:1.02rem; font-weight:700; color:{accent} !important; line-height:1.3; text-decoration:none !important; }}
a.aw-title:hover {{ text-decoration:underline !important; }}
.aw-title-off {{ color:{pal['text']} !important; }}
.aw-rating {{ display:flex; align-items:center; gap:6px; font-size:0.85rem; }}
.aw-rating b {{ color:{pal['text']} !important; }}
.aw-stars {{ color:{accent} !important; letter-spacing:1px; font-size:1rem; text-shadow:0 0 8px rgba(26,109,255,0.35); }}
.aw-stars-off {{ color:{pal['border']} !important; text-shadow:none; }}
.aw-rating-n {{ color:{accent} !important; font-size:0.8rem; }}
.aw-rating-none {{ color:{pal['muted']} !important; font-size:0.8rem; }}
.aw-tags {{ display:flex; gap:6px; flex-wrap:wrap; }}
.aw-tag {{ font-size:0.74rem; padding:2px 9px; border-radius:6px; border:1px solid {pal['input_border']}; color:{pal['subtext']} !important; }}
.aw-tag-free {{ border-color:{accent}; color:{accent} !important; font-weight:600; }}
.aw-desc {{ font-size:0.86rem; line-height:1.5; color:{pal['subtext']} !important; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }}
.aw-card .aw-desc {{ flex:1; }}
.aw-card-actions {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.aw-card .aw-card-actions {{ padding-top:0.7rem; border-top:1px solid {pal['border']}; }}
/* Deploy dropdown */
.aw-deploy {{ position:relative; }}
.aw-deploy > summary {{
    list-style:none; cursor:pointer; user-select:none; font-size:0.84rem; font-weight:600; padding:5px 12px; border-radius:8px;
    border:1px solid {accent}; color:{accent} !important; background:transparent; white-space:nowrap;
}}
.aw-deploy > summary::-webkit-details-marker {{ display:none; }}
.aw-deploy[open] > summary, .aw-deploy > summary:hover {{ background:rgba(26,109,255,0.08); box-shadow:0 0 14px rgba(26,109,255,0.35); }}
.aw-deploy-menu {{
    position:absolute; right:0; top:calc(100% + 6px); z-index:50; min-width:220px; padding:6px;
    background:{pal['card']}; border:1px solid {pal['border']}; border-radius:10px;
    box-shadow:0 18px 40px -14px rgba(15,23,42,0.45);
}}
.aw-deploy-head {{ font-size:0.7rem; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:{pal['muted']} !important; padding:4px 10px 6px; }}
.aw-deploy-menu a {{ display:flex; align-items:center; gap:10px; padding:7px 10px; border-radius:6px; color:{pal['text']} !important; font-size:0.86rem; text-decoration:none !important; }}
.aw-deploy-menu a:hover {{ background:rgba(26,109,255,0.08); color:{accent} !important; }}
.aw-deploy-menu i {{ font-style:normal; font-size:0.66rem; font-weight:700; width:36px; text-align:center; padding:2px 0; border-radius:4px; background:rgba(26,109,255,0.10); color:{accent} !important; }}
/* Vertical groups (collapsible) */
.aw-vgroup {{ margin-top:0.9rem; }}
.aw-vgroup > summary {{
    list-style:none; cursor:pointer; display:flex; align-items:center; gap:0.75rem; padding:0.75rem 1.1rem;
    background:{pal['card']}; border:1px solid {pal['border']}; border-radius:12px; transition:border-color .15s, box-shadow .15s;
}}
.aw-vgroup > summary::-webkit-details-marker {{ display:none; }}
.aw-vgroup > summary:hover {{ border-color:{accent}; }}
.aw-vgroup > summary h3 {{ margin:0 !important; font-size:1.08rem !important; }}
.aw-vgroup > summary .aw-vcount {{ color:{pal['muted']} !important; font-size:0.84rem; margin-left:auto; }}
.aw-vgroup > summary::after {{ content:"▾"; color:{pal['muted']}; font-size:1rem; transition:transform .15s; }}
.aw-vgroup[open] > summary {{ border-radius:12px 12px 0 0; border-color:{pal['border']}; box-shadow:inset 0 -2px 0 {accent}; }}
.aw-vgroup[open] > summary::after {{ transform:rotate(180deg); color:{accent}; }}
/* List rows */
.aw-list {{ background:{pal['card']}; border:1px solid {pal['border']}; border-top:none; border-radius:0 0 12px 12px; }}
.aw-row {{ display:flex; gap:1rem; align-items:flex-start; padding:1rem 1.2rem; border-bottom:1px solid {pal['border']}; }}
.aw-row:last-child {{ border-bottom:none; border-radius:0 0 12px 12px; }}
.aw-row:hover {{ background:{pal['table_hover_bg']}; }}
.aw-row-main {{ flex:1; display:flex; flex-direction:column; gap:0.3rem; min-width:0; }}
.aw-desc-row {{ -webkit-line-clamp:2; }}
.aw-row-side {{ display:flex; flex-direction:column; align-items:flex-end; gap:0.5rem; flex:none; min-width:150px; }}
.aw-badge {{ font-size:0.72rem; font-weight:600; padding:2px 9px; border-radius:999px; }}
.aw-badge-new {{ background:rgba(0,190,255,0.12); color:#0891d1 !important; border:1px solid rgba(0,190,255,0.4); }}
.aw-badge-live {{ background:rgba(26,109,255,0.10); color:{accent} !important; border:1px solid rgba(26,109,255,0.35); }}
.aw-badge-soft {{ background:{pal['bg']}; color:{pal['subtext']} !important; border:1px solid {pal['border']}; }}
.aw-badge-muted {{ color:{pal['muted']} !important; border:1px dashed {pal['input_border']}; }}
.aw-cta {{ font-size:0.84rem; font-weight:600; padding:6px 14px; border-radius:8px; white-space:nowrap; background:{pal['red']}; color:#ffffff !important; text-decoration:none !important; box-shadow:0 0 14px rgba(229,19,58,0.35); }}
.aw-cta:hover {{ filter:brightness(1.08); }}
.aw-cta-off {{ background:transparent; color:{pal['muted']} !important; border:1px solid {pal['border']}; box-shadow:none; }}
.st-key-aw_filters {{ position: sticky; top: 1rem; }}
.aw-quote {{ background:{pal['card']}; border:1px solid {pal['border']}; border-left:3px solid {accent}; border-radius:8px; padding:0.7rem 0.9rem; margin-bottom:0.6rem; font-size:0.88rem; }}
.aw-visitors {{ font-size:0.8rem; color:{pal['muted']} !important; text-align:center; margin-top:1.5rem; }}
@media (max-width: 1100px) {{ .aw-cards {{ grid-template-columns:repeat(2,1fr); }} }}
@media (max-width: 700px) {{ .aw-cards, .aw-tasks {{ grid-template-columns:1fr; }} .aw-row {{ flex-wrap:wrap; }} .aw-row-side {{ align-items:flex-start; }} }}
</style>
""",
        unsafe_allow_html=True,
    )


def _visitor_stats() -> dict:
    """Get visitor stats or create mock data for demonstration."""
    try:
        response = requests.get(f"{API_URL}/v1/monitoring/visitors/stats", timeout=2)
        if response.status_code == 200:
            stats = response.json()
            # Only use real data if we have visitors
            if stats.get("total_visitors", 0) > 0:
                return stats
    except Exception:
        pass
    return {
        "total_visitors": 42,
        "total_visits": 156,
        "countries": {"United States": 25, "Canada": 8, "United Kingdom": 5, "Germany": 4, "France": 3},
    }


GENERAL_FEEDBACK_FILE = Path(TMP_FEEDBACK_DIR) / "general_feedback.json"


def load_general_feedback() -> list:
    try:
        if GENERAL_FEEDBACK_FILE.exists():
            with open(GENERAL_FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("comments", [])
    except Exception:
        pass
    return []


def save_general_feedback(comments: list) -> None:
    try:
        with open(GENERAL_FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump({"comments": comments}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")


def _popularity(item: dict):
    return (not item["launchable"], -item["rating"], -item["users"], item["status_label"] != "New", item["name"])


def render_market_header():
    """Dark top bar shared by the market and agent detail pages."""
    with st.container(key="aw_header"):
        brand, actions, tog = st.columns([5, 3, 0.8], vertical_alignment="center")
        with brand:
            st.markdown(
                f"<a class='aw-brand' href='/' target='_self'><img src='{_svg_data_uri(BRAND_LOGO_SVG)}' width='52' height='52' alt=''/>"
                "<span class='aw-word'>ai agent <b>market</b><small>Free agents for every vertical</small></span></a>",
                unsafe_allow_html=True,
            )
        with actions:
            st.markdown(
                "<div class='aw-head-actions'>"
                "<a class='aw-btn-ghost' href='/deployment_in_production' target='_self'>Deploy to production</a>"
                "<a class='aw-btn-red' href='/agent_builder' target='_self'>Publish an agent</a>"
                "</div>",
                unsafe_allow_html=True,
            )
        with tog:
            render_theme_toggle(label="Dark", key="aw_theme_toggle")
        st.markdown(
            "<nav class='aw-nav'>"
            "<a href='/#browse-agents' target='_self'>All verticals</a>"
            "<a href='/#most-popular' target='_self'>Most popular</a>"
            "<a href='/agent_builder' target='_self'>Agent Builder</a>"
            "<a href='/hf_inspector' target='_self'>Agent Manager</a>"
            "<a href='/ceo_driver_dashboard' target='_self'>CEO Dashboard</a>"
            "<span class='aw-nav-right'><a href='/deployment_in_production' target='_self'>Multi-cloud deploy</a>"
            "<a href='https://github.com/Sherlock2019/AI-AIGENTbythePeoplesANDBOX' target='_blank'>Open source</a></span>"
            "</nav>",
            unsafe_allow_html=True,
        )


# Icons for the value-proposition cards (24x24 stroke paths).
VP_ICONS = {
    "what": '<path d="M4 5h6v14H4zM14 5h6v6h-6zM14 15h6v4h-6z"/>',
    "why": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17h.01"/>',
    "so_what": '<path d="M4 17l5-5 4 4 7-8"/><path d="M15 8h5v5"/>',
    "for_who": '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2A5 5 0 0 1 21 19"/>',
    "how": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><circle cx="12" cy="12" r="4"/>',
    "what_now": '<path d="M5 12h12M13 6l6 6-6 6"/>',
}


def _vp_label(key: str, text: str, red: bool = True) -> str:
    c1, c2 = ("#e5133a", "#ff5a76") if red else ("#1a6dff", "#00c6ff")
    return f"<div class='vp-label'>{icon_tile(VP_ICONS[key], c1, c2, 26, gid=f'vp{key}')}{text}</div>"


def render_value_intro(n_agents: int, n_verticals: int, n_live: int):
    """What / Why / So what / For who / How / What now: the pitch for newcomers."""
    st.markdown(
        "<div class='vp-eyebrow'>Why AI Agent Market</div>"
        "<div class='vp-title'>A ready-to-use, no-code AI agent library</div>"
        "<div class='vp-sub'>Discover what AI agents can do for real human tasks, use them as copilots, "
        "and take the ones that work from proof of concept to production. No code, no licence fees.</div>"
        "<div class='vp-grid'>"
        # WHAT
        "<div class='vp-card'>"
        f"{_vp_label('what', 'What', red=True)}"
        f"<h4>{n_agents} ready-to-run agents across {n_verticals} verticals</h4>"
        f"<p>Each agent is a working copilot for a specific human task: credit appraisal, KYC and fraud checks, "
        f"legal compliance, IT troubleshooting, executive dashboards. {n_live} run today, straight from your browser.</p>"
        "</div>"
        # WHY
        "<div class='vp-card'>"
        f"{_vp_label('why', 'Why', red=False)}"
        "<h4>Most people don't know what AI agents can actually do</h4>"
        "<p>Newcomers face hype, blank prompts and costly pilots. Seeing a working agent on a real task is the fastest "
        "way to learn where AI helps, and where a human must stay in charge.</p>"
        "</div>"
        # SO WHAT
        "<div class='vp-card'>"
        f"{_vp_label('so_what', 'So what', red=True)}"
        "<h4>From idea to proof in minutes, not months</h4>"
        "<p>Every agent explains its reasoning and keeps a <b>human in the loop</b>, so a POC can be trusted, measured "
        "and promoted. <b>No CAPEX</b>, open source, and your data stays in your sandbox.</p>"
        "</div>"
        # FOR WHO
        "<div class='vp-card'>"
        f"{_vp_label('for_who', 'For who', red=False)}"
        "<h4>Anyone with a task AI could help with</h4>"
        "<ul>"
        "<li><b>Newcomers</b> exploring AI for the first time</li>"
        "<li><b>Business experts</b>: bankers, analysts, legal, IT ops</li>"
        "<li><b>Builders and data teams</b> who want a head start</li>"
        "<li><b>Leaders</b> deciding where AI pays off</li>"
        "</ul>"
        "</div>"
        "</div>"
        # HOW: the POC-to-production journey
        "<div class='vp-how'>"
        f"<div class='vp-how-head'>{_vp_label('how', 'How', red=True)}<h4>From proof of concept to production in five steps</h4></div>"
        "<div class='vp-steps'>"
        "<div class='vp-step'><i>1</i><b>Discover</b><span>Browse agents by vertical and pick a human task to improve.</span><em>Explore</em></div>"
        "<div class='vp-step'><i>2</i><b>Try</b><span>Launch it free with sample data. A working POC in minutes.</span><em>POC</em></div>"
        "<div class='vp-step'><i>3</i><b>Customize</b><span>Adapt data, rules and models in the no-code Agent Builder.</span><em>No code</em></div>"
        "<div class='vp-step'><i>4</i><b>Co-pilot</b><span>Run it alongside your team. People review, correct and approve.</span><em>Pilot</em></div>"
        "<div class='vp-step'><i>5</i><b>Deploy</b><span>Ship to OpenStack, AWS, GCP, Azure or GPU cloud.</span><em>Production</em></div>"
        "</div></div>"
        # WHAT NOW
        "<div class='vp-now'>"
        "<div>"
        f"{_vp_label('what_now', 'What now', red=True)}"
        "<h4>Pick a task. Launch your first agent free. Ship what works.</h4>"
        "<p>Start with a vertical you know, see the agent work, then build your own or deploy it.</p>"
        "</div>"
        "<div class='vp-now-ctas'>"
        "<a class='vp-cta-red' href='#browse-agents' target='_self'>Browse agents</a>"
        "<a class='vp-cta-blue' href='/agent_builder' target='_self'>Build your own</a>"
        "<a class='vp-cta-ghost' href='/deployment_in_production' target='_self'>Deploy to production</a>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def group_by_vertical(catalog: list[dict]) -> tuple[dict[str, list[dict]], list[str]]:
    """Return {vertical: items} and the verticals ordered by most live agents."""
    verticals: dict[str, list[dict]] = {}
    for item in catalog:
        verticals.setdefault(item["sector"], []).append(item)
    return verticals, sorted(verticals, key=lambda v: (-sum(i["live"] for i in verticals[v]), v))


def render_marketplace():
    render_marketplace_css()
    catalog = build_catalog()
    verticals, vertical_names = group_by_vertical(catalog)
    render_market_header()

    # ── Hero: search + suggested tasks ──
    with st.container(key="aw_hero"):
        st.markdown(
            "<div class='aw-eyebrow'><i>✦</i> Agent mode</div>"
            f"<h1 class='aw-hero-title'>Find your perfect match from <em>{len(catalog)} free</em> AI agents</h1>"
            "<div class='aw-hero-sub'>Launch in one click, then deploy on OpenStack, AWS, GCP, Azure or GPU cloud.</div>",
            unsafe_allow_html=True,
        )
        query = st.text_input(
            "Search agents",
            placeholder="Describe the agent you're looking for, e.g. \"credit risk\", \"fraud\", \"IT incidents\"…",
            key="aw_search",
            label_visibility="collapsed",
        )
        st.markdown(
            "<div class='aw-disclaimer'>Every agent is free and runs inside your sandbox. Do not paste confidential data into demo agents.</div>"
            "<div class='aw-h3'>Try these tasks</div>"
            "<div class='aw-tasks'>"
            f"<a class='aw-task' href='#browse-agents' target='_self'><div class='aw-task-icon'>{icon_tile(TASK_ICON_COMPARE, '#1a6dff', '#00c6ff', 32, gid='tc')}</div>"
            "<div><b>Compare agents</b><span>Browse every agent in a vertical side by side.</span></div><em>By vertical</em></a>"
            f"<a class='aw-task' href='/agent_builder' target='_self'><div class='aw-task-icon'>{icon_tile(TASK_ICON_BUILD, '#3a5bff', '#00c6ff', 32, gid='tb')}</div>"
            "<div><b>Build your own agent</b><span>Compose reusable functions into a new agent.</span></div><em>Agent Builder</em></a>"
            "</div>",
            unsafe_allow_html=True,
        )

    q = (query or "").strip().lower()

    # ── Value proposition (hidden while searching so results come first) ──
    if not q:
        render_value_intro(len(catalog), len(vertical_names), sum(i["live"] for i in catalog))

    def matches_query(item: dict) -> bool:
        if not q:
            return True
        hay = " ".join([item["name"], item["industry"], item["sector"], item["desc"]]).lower()
        return all(term in hay for term in q.split())

    # ── Most popular, tabbed by vertical (hidden while searching) ──
    if not q:
        st.markdown("<div id='most-popular' class='aw-h2'>The most popular agents this month</div>", unsafe_allow_html=True)
        tab_verticals = [v for v in vertical_names if any(i["launchable"] for i in verticals[v])][:6]
        tabs = st.tabs(["All agents"] + tab_verticals)
        for tab, scope in zip(tabs, [catalog] + [verticals[v] for v in tab_verticals]):
            with tab:
                top = sorted(scope, key=_popularity)[:4]
                st.markdown(
                    f"<div class='aw-cards'>{''.join(top_card_html(i, n) for n, i in enumerate(top, 1))}</div>",
                    unsafe_allow_html=True,
                )

    # ── Agents listed per vertical, with refine panel ──
    st.markdown(
        f"<div id='browse-agents' class='aw-h2' style='margin-top:2.5rem;'>{'Search results' if q else 'Browse agents by vertical'}</div>",
        unsafe_allow_html=True,
    )
    # Breadcrumb links from a detail page arrive as ?vertical=<name>.
    qp_vertical = st.query_params.get("vertical")
    if qp_vertical in vertical_names and "aw_vertical" not in st.session_state:
        st.session_state["aw_vertical"] = qp_vertical
    side, main = st.columns([1, 3.4], gap="large")
    with side:
        with st.container(key="aw_filters", border=True):
            st.markdown("**Refine results**")
            vertical_choice = st.selectbox(
                "Vertical",
                ["All verticals"] + vertical_names,
                format_func=lambda v: v if v == "All verticals" else f"{v} ({len(verticals[v])})",
                key="aw_vertical",
            )
            live_only = st.checkbox("Ready to run only", key="aw_live_only")
            sort_by = st.selectbox("Sort by", ["Popularity", "Rating", "Name"], key="aw_sort")

    sort_key = {
        "Popularity": _popularity,
        "Rating": lambda i: (-i["rating"], -i["users"], i["name"]),
        "Name": lambda i: i["name"].lower(),
    }[sort_by]

    with main:
        # Collapsible dropdown per vertical: the first group starts open, and
        # every group opens while a search or vertical filter is active.
        filtering = bool(q) or vertical_choice != "All verticals" or live_only
        groups_html = ""
        shown = 0
        for vertical in vertical_names:
            if vertical_choice != "All verticals" and vertical != vertical_choice:
                continue
            items = [i for i in verticals[vertical] if matches_query(i) and (i["live"] or not live_only)]
            if not items:
                continue
            items.sort(key=sort_key)
            is_open = filtering or shown == 0
            shown += len(items)
            groups_html += (
                f"<details class='aw-vgroup'{' open' if is_open else ''}>"
                "<summary>"
                f"{vertical_logo(items[0]['sector_raw'], size=32)}"
                f"<h3>{html.escape(vertical)}</h3>"
                f"<span class='aw-vcount'>{len(items)} agent{'s' if len(items) != 1 else ''} · {sum(i['live'] for i in items)} ready</span>"
                "</summary>"
                f"<div class='aw-list'>{''.join(list_row_html(i) for i in items)}</div>"
                "</details>"
            )
        if groups_html:
            st.markdown(groups_html, unsafe_allow_html=True)
        if not shown:
            st.info("No agents match your filters. Try another keyword or vertical.")

    # ── Community feedback ──
    st.markdown("<div class='aw-h2' style='margin-top:3rem;'>From the community</div>", unsafe_allow_html=True)
    all_comments = load_general_feedback()
    left, right = st.columns([3, 2], gap="large")
    with left:
        recent = list(reversed(all_comments))[:3] or ["No feedback yet. Be the first."]
        st.markdown(
            "".join(f"<div class='aw-quote'>&ldquo;{html.escape(c)}&rdquo;</div>" for c in recent),
            unsafe_allow_html=True,
        )
    with right:
        with st.form("aw_feedback_form", clear_on_submit=True, border=False):
            feedback_text = st.text_area("Share your feedback", placeholder="Which agent should we list next?", height=100)
            if st.form_submit_button("Send feedback", type="primary", use_container_width=True):
                if feedback_text.strip():
                    all_comments.append(feedback_text.strip())
                    save_general_feedback(all_comments)
                    st.success("Thanks, your feedback was recorded.")
                else:
                    st.warning("Please enter some feedback first.")

    stats = _visitor_stats()
    countries = sorted((stats.get("countries") or {}).items(), key=lambda x: x[1], reverse=True)[:5]
    countries_str = " · ".join(f"{html.escape(str(c))} ({n})" for c, n in countries) or "No visitors yet"
    st.markdown(
        f"<div class='aw-visitors'>{stats.get('total_visitors', 0)} visitors · {stats.get('total_visits', 0)} visits · {countries_str}</div>"
        f"<footer>{MARKET_NAME} · Open AIgents Sandbox Initiative · DzoanNguyenTran@gmail.com</footer>",
        unsafe_allow_html=True,
    )


def render_agent_detail_css():
    accent = pal["accent"]
    st.markdown(
        f"""
<style>
.ad-crumbs {{ font-size:0.88rem; margin:1.1rem 0 1rem 0; color:{pal['muted']} !important; }}
.ad-crumbs a {{ color:{accent} !important; text-decoration:underline !important; }}
.ad-crumbs span {{ margin:0 0.45rem; color:{pal['muted']} !important; }}
.ad-head {{ display:flex; gap:1.1rem; align-items:center; margin-bottom:0.9rem; }}
.ad-logo {{ padding:10px; border:1px solid {pal['border']}; border-radius:14px; background:{pal['card']}; }}
.ad-title, .ad-title > span:first-child {{ font-size:1.65rem !important; font-weight:700 !important; margin:0 !important; color:{pal['text']} !important; }}
.ad-title small {{ font-size:0.75rem; color:{accent} !important; font-weight:600; margin-left:0.4rem; vertical-align:middle; }}
.ad-by {{ font-size:0.9rem; color:{pal['subtext']} !important; margin-top:0.2rem; }}
.ad-by a {{ color:{accent} !important; text-decoration:underline !important; }}
.ad-summary {{ font-size:0.95rem; line-height:1.6; margin:0.7rem 0; max-width:760px; }}
.ad-actions {{ display:flex; flex-direction:column; gap:10px; }}
.ad-btn {{ display:block; text-align:center; font-weight:600; font-size:0.92rem; padding:0.55rem 1rem; border-radius:999px;
    border:1.5px solid {accent}; color:{accent} !important; text-decoration:none !important; background:{pal['card']}; }}
.ad-btn:hover {{ background:rgba(26,109,255,0.08); }}
.ad-btn-primary {{ background:{pal['red']}; border-color:{pal['red']}; color:#ffffff !important; box-shadow:0 0 18px rgba(229,19,58,0.4); }}
.ad-btn-primary:hover {{ background:{pal['red']}; filter:brightness(1.08); }}
.ad-btn-off {{ border-style:dashed; color:{pal['muted']} !important; border-color:{pal['input_border']}; box-shadow:none; background:transparent; }}
.ad-actions .aw-deploy > summary {{ display:block; text-align:center; border-radius:999px; padding:0.55rem 1rem; font-size:0.92rem; border-width:1.5px; }}
.ad-actions .aw-deploy-menu {{ left:0; right:0; }}
.ad-panel {{ background:{pal['card']}; border:1px solid {pal['border']}; border-radius:14px; padding:1.2rem 1.4rem; margin-bottom:1.2rem; }}
.ad-panel h3 {{ margin:0 0 0.8rem 0 !important; font-size:1.2rem !important; }}
.ad-panel ul {{ margin:0; padding-left:1.1rem; }}
.ad-panel li {{ margin-bottom:0.5rem; line-height:1.55; font-size:0.92rem; }}
.ad-media {{ border:1px solid {pal['border']}; border-radius:14px; overflow:hidden; background:{pal['card']}; margin-bottom:1.2rem; }}
.ad-media-stage {{ height:290px; display:flex; align-items:center; justify-content:center; gap:1.5rem;
    background: radial-gradient(500px 220px at 70% 20%, rgba(0,212,255,0.25), transparent 60%), linear-gradient(135deg,#050f2c,#0a2a6e 55%,#1456e0); }}
.ad-media-stage span {{ color:#ffffff !important; font-size:1.5rem; font-weight:700; letter-spacing:-0.01em; text-shadow:0 0 22px rgba(0,190,255,0.55); max-width:320px; }}
.ad-media-cap {{ padding:0.8rem 1.2rem; font-weight:600; color:{pal['text']} !important; border-top:1px solid {pal['border']}; }}
.ad-dl {{ display:grid; grid-template-columns:160px 1fr; gap:0.55rem 1rem; font-size:0.9rem; }}
.ad-dl dt {{ color:{pal['muted']} !important; }}
.ad-dl dd {{ margin:0; color:{pal['text']} !important; }}
.ad-clouds {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:14px; }}
.ad-cloud {{ background:{pal['card']}; border:1px solid {pal['border']}; border-radius:12px; padding:1rem; display:flex; flex-direction:column; gap:0.5rem; }}
.ad-cloud i {{ font-style:normal; font-size:0.72rem; font-weight:700; color:{accent} !important; background:rgba(26,109,255,0.1); border-radius:6px; padding:3px 8px; align-self:flex-start; }}
.ad-cloud b {{ color:{pal['text']} !important; }}
.ad-cloud span {{ font-size:0.84rem; }}
.ad-steps {{ counter-reset: step; list-style:none; padding:0 !important; }}
.ad-steps li {{ counter-increment: step; position:relative; padding-left:2.4rem !important; margin-bottom:0.9rem !important; }}
.ad-steps li::before {{ content: counter(step); position:absolute; left:0; top:0; width:1.7rem; height:1.7rem; border-radius:50%;
    background:{accent}; color:#fff; font-weight:700; font-size:0.85rem; display:flex; align-items:center; justify-content:center; box-shadow:0 0 12px rgba(26,109,255,0.45); }}
</style>
""",
        unsafe_allow_html=True,
    )


# Short descriptions for the Deployment tab, keyed like DEPLOY_TARGETS.
DEPLOY_TARGET_NOTES = {
    "openstack": "Private cloud or on-prem. Data stays inside your sovereign boundary.",
    "aws": "Amazon EKS / EC2 with GPU instances in the region of your choice.",
    "gcp": "GKE or Compute Engine with NVIDIA GPUs and Vertex AI integration.",
    "azure": "AKS or Azure VMs with Entra ID single sign-on.",
    "gpu_cloud": "Pay-per-hour GPU rental. No CAPEX, scale to zero when idle.",
}


def render_agent_detail(item: dict, catalog: list[dict]):
    render_marketplace_css()
    render_agent_detail_css()
    render_market_header()
    e = html.escape

    st.markdown(
        "<div class='ad-crumbs'>"
        f"<a href='/' target='_self'>{MARKET_NAME}</a><span>›</span>"
        f"<a href='/?vertical={e(item['sector'])}#browse-agents' target='_self'>{e(item['sector'])}</a><span>›</span>"
        f"{e(item['industry'])}<span>›</span><b>{e(item['name'])}</b>"
        "</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([2.6, 1], gap="large")
    with left:
        st.markdown(
            "<div class='ad-head'>"
            f"<div class='ad-logo'>{vertical_logo(item['sector_raw'], size=72)}</div>"
            "<div>"
            f"<h1 class='ad-title'>{e(item['name'])}<small>{e(item['status_label'])}</small></h1>"
            f"<div class='ad-by'>Built by: <a href='https://github.com/Sherlock2019/AI-AIGENTbythePeoplesANDBOX' target='_blank'>Open AIgents Sandbox</a></div>"
            "</div></div>"
            f"{_tags_html(item)}"
            f"<div class='ad-summary'>{e(item['desc'])}. Part of the {e(item['industry'])} suite in "
            f"{e(item['sector'])}: free to use, explainable by design, and deployable to the cloud of your choice.</div>"
            f"{_rating_html(item)}",
            unsafe_allow_html=True,
        )
    with right:
        if item["launchable"]:
            primary = f"<a class='ad-btn ad-btn-primary' href='{e(item['url'])}' target='_self'>{e(item['cta'])}</a>"
        else:
            primary = "<span class='ad-btn ad-btn-off'>Coming soon</span>"
        st.markdown(
            "<div class='ad-actions'>"
            f"{primary}"
            f"{_deploy_html(item)}"
            "<a class='ad-btn' href='mailto:DzoanNguyenTran@gmail.com?subject=Demo%20request' target='_blank'>Request demo</a>"
            "<a class='ad-btn' href='#ask-question' target='_self'>Ask question</a>"
            "</div>",
            unsafe_allow_html=True,
        )

    overview, features, deployment, usage, support, compare = st.tabs(
        ["Overview", "Features", "Deployment", "Usage", "Support", "Product comparison"]
    )

    with overview:
        media, info = st.columns([1, 1.1], gap="large")
        with media:
            st.markdown(
                "<div class='ad-media'>"
                f"<div class='ad-media-stage'>{vertical_logo(item['sector_raw'], size=96)}<span>{e(item['name'])}</span></div>"
                f"<div class='ad-media-cap'>{e(item['name'])} · {e(item['industry'])}</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        with info:
            st.markdown(
                "<div class='ad-panel'><h3>Highlights</h3><ul>"
                f"<li><b>Purpose-built:</b> {e(item['desc'])}.</li>"
                "<li><b>Explainable:</b> every output ships with a reasoning trail you can audit.</li>"
                "<li><b>Human in the loop:</b> review and approve decisions before they take effect.</li>"
                "<li><b>Portable:</b> run it on OpenStack, AWS, GCP, Azure or rented GPU cloud.</li>"
                "</ul></div>"
                "<div class='ad-panel'><h3>Details</h3><dl class='ad-dl'>"
                f"<dt>Vertical</dt><dd>{e(item['sector'])}</dd>"
                f"<dt>Category</dt><dd>{e(item['industry'])}</dd>"
                f"<dt>Status</dt><dd>{e(item['status_label'])}</dd>"
                f"<dt>Access</dt><dd>{'Sign-in required' if item['requires_login'] else 'Open access'}</dd>"
                "<dt>Pricing</dt><dd>Free · open source</dd>"
                f"<dt>Active users</dt><dd>{item['users']}</dd>"
                "</dl></div>",
                unsafe_allow_html=True,
            )

    with features:
        st.markdown(
            "<div class='ad-panel'><h3>Features</h3><ul>"
            "<li>Ready-to-run agent template with sample data, so you can evaluate it in minutes.</li>"
            "<li>Pluggable models: Hugging Face, Ollama or local models, with automatic failover.</li>"
            "<li>Built-in feedback loop: ratings and comments feed retraining.</li>"
            "<li>Audit logs for every run, dataset and model version.</li>"
            "<li>Exportable as code once it is production-ready.</li>"
            "</ul></div>",
            unsafe_allow_html=True,
        )

    with deployment:
        clouds = "".join(
            "<div class='ad-cloud'>"
            f"<i>{tag}</i><b>{label}</b><span>{DEPLOY_TARGET_NOTES.get(value, '')}</span>"
            f"<a class='aw-cta' style='text-align:center;' href='{_launch_href('/deployment_in_production')}?agent={e(item['route'])}&amp;target={value}' target='_self'>Deploy on {tag}</a>"
            "</div>"
            for value, tag, label in DEPLOY_TARGETS
        ) if item["launchable"] else "<div class='ad-panel'>Deployment opens once this agent is available.</div>"
        st.markdown(
            "<div class='ad-panel'><h3>Deploy this agent</h3>"
            "<p style='margin-bottom:1rem;'>Choose a target cloud. Each option opens the production deployment workflow with this agent pre-selected.</p>"
            f"<div class='ad-clouds'>{clouds}</div></div>",
            unsafe_allow_html=True,
        )

    with usage:
        st.markdown(
            "<div class='ad-panel'><h3>Getting started</h3><ol class='ad-steps'>"
            f"<li><b>Launch</b> the agent from this page{' (sign in when prompted)' if item['requires_login'] else ''}.</li>"
            "<li><b>Load data</b>: start with the bundled sample data or upload your own CSV.</li>"
            "<li><b>Run and review</b>: inspect the outputs and their explanations, then approve or correct them.</li>"
            "<li><b>Deploy</b> to OpenStack, AWS, GCP, Azure or GPU cloud when you are ready for production.</li>"
            "</ol></div>",
            unsafe_allow_html=True,
        )

    with support:
        st.markdown(
            "<div id='ask-question' class='ad-panel'><h3>Support</h3>"
            "<p>Community support from the Open AIgents Sandbox Initiative. "
            "Email <a href='mailto:DzoanNguyenTran@gmail.com'>DzoanNguyenTran@gmail.com</a> or open an issue on "
            "<a href='https://github.com/Sherlock2019/AI-AIGENTbythePeoplesANDBOX/issues' target='_blank'>GitHub</a>.</p></div>",
            unsafe_allow_html=True,
        )

    with compare:
        peers = sorted((i for i in catalog if i["sector"] == item["sector"]), key=_popularity)
        st.markdown(
            f"<div class='ad-panel'><h3>Other agents in {e(item['sector'])}</h3>"
            f"<div class='aw-list' style='border-top:1px solid {pal['border']};border-radius:12px;'>"
            f"{''.join(list_row_html(i) for i in peers)}</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown(f"<footer>{MARKET_NAME} · Open AIgents Sandbox Initiative · DzoanNguyenTran@gmail.com</footer>", unsafe_allow_html=True)


if st.session_state.stage in ("landing", "agents"):
    _view = st.query_params.get("view")
    if _view:
        _catalog = build_catalog()
        _item = next((i for i in _catalog if i["route"] == _view), None)
        if _item:
            render_agent_detail(_item, _catalog)
            st.stop()
    render_marketplace()
    st.stop()


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
