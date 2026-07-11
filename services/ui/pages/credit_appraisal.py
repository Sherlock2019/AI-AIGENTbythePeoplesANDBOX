# services/ui/pages/credit_appraisal.py
from __future__ import annotations

import os
import io
import re
import json
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np
import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
import logging
import sys

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
    apply_theme as apply_global_theme,
    get_theme,
    render_theme_toggle,
)
from services.ui.components.operator_banner import render_operator_banner
from services.ui.components.telemetry_dashboard import render_telemetry_dashboard
from services.ui.components.feedback import render_feedback_tab
from services.ui.components.chat_assistant import render_chat_assistant
# Try to import LLM selector if available
try:
    from services.ui.utils.llm_selector import render_llm_selector
except ImportError:
    render_llm_selector = None






def apply_theme(theme: str | None = None):
    """Proxy to shared theme manager for credit page."""
    theme = theme or get_theme()
    apply_global_theme(theme)



# ─────────────────────────────────────────────
# CREDIT AGENT — HEADER (used in credit flow)
# ─────────────────────────────────────────────
import streamlit as st  # (no-op if already imported)

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
    theme = ss.get("theme", "dark")
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


def _coerce_minutes(value, fallback: float = 0.0) -> float:
    """Best-effort conversion of strings like '22 min' to minute floats."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch == ".")
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            pass
    return float(fallback)





# ──────────────────────────────────────────────────────────────
# PAGE CONFIG & THEME
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="💳 Credit Appraisal",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed",
)
#

apply_theme()

st.markdown(
    """
    > **Unified Risk Checklist**  
    > ✅ Is the borrower real & safe? (Fraud/KYC)  
    > ✅ Is the collateral worth enough? (Asset)  
    > ✅ Can they afford the loan? (this agent)  
    > ✅ Should the bank approve overall? (Unified agent)
    """
)



# ────────────────────────────────
# SESSION STATE INIT
# ────────────────────────────────
if "stage" not in st.session_state:
    st.session_state.stage = "credit_agent"
if "user_info" not in st.session_state:
    st.session_state.user_info = {"name": "", "email": "", "flagged": False}
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "flagged" not in st.session_state.user_info:
    st.session_state.user_info["flagged"] = False
if "timestamp" not in st.session_state.user_info:
    st.session_state.user_info["timestamp"] = datetime.now(timezone.utc).isoformat()
st.session_state.setdefault("credit_apps_in_review", 24)
st.session_state.setdefault("credit_flagged_cases", 5)
st.session_state.setdefault("credit_avg_decision_time", "9 min")
st.session_state.setdefault("credit_ai_performance", 0.92)
st.session_state.setdefault(
    "credit_user",
    {"name": "Operator", "email": "operator@demo.local", "timestamp": datetime.now(timezone.utc).isoformat()},
)
st.session_state.setdefault("credit_logged_in", True)
st.session_state["credit_logged_in"] = True
if not st.session_state.user_info.get("name"):
    st.session_state.user_info["name"] = st.session_state["credit_user"]["name"]
if st.session_state.get("credit_logged_in", False):
    st.session_state.stage = "credit_agent"

# ─────────────────────────────────────────────
# AUTO-LOAD DEMO DATA (if no results exist)
# ─────────────────────────────────────────────
if st.session_state.get("last_merged_df") is None and st.session_state.get("credit_scored_df") is None:
    # Auto-generate demo data on first load
    rng = np.random.default_rng(42)
    demo_df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, 51)],
        "customer_id": [f"CUST_{i:04d}" for i in range(1, 51)],
        "income": rng.integers(20000, 150000, 50),
        "DTI": rng.uniform(0.15, 0.65, 50).round(3),
        "LTV": rng.uniform(0.50, 0.95, 50).round(3),
        "credit_score": rng.integers(580, 820, 50),
        "credit_history_length": rng.integers(0, 25, 50),
        "num_delinquencies": rng.integers(0, 5, 50),
        "current_loans": rng.integers(0, 8, 50),
        "employment_years": rng.integers(0, 30, 50),
        "loan_amount": rng.integers(20000, 300000, 50),
    })
    
    # Run credit appraisal agent on demo data
    try:
        from agents.credit_appraisal.runner import run as run_credit_appraisal
        demo_params = {
            "rule_mode": "classic",
            "max_debt_to_income": 0.45,
            "salary_floor": 3000,
            "requested_amount_min": 1000,
            "requested_amount_max": 200000,
            "min_employment_years": 2,
            "min_credit_history_length": 3,
            "max_num_delinquencies": 2,
            "max_current_loans": 3,
            "threshold": 0.45,
            "random_band": False,
        }
        scored_df = run_credit_appraisal(demo_df, demo_params)
        st.session_state["last_merged_df"] = scored_df
        st.session_state["credit_scored_df"] = scored_df.copy()
        st.session_state["credit_demo_loaded"] = True
    except Exception as e:
        # If runner fails, at least store the input data
        st.session_state["credit_demo_loaded"] = False
        import logging
        logging.warning(f"Could not auto-run credit appraisal: {e}")


def _build_credit_chat_context() -> Dict[str, Any]:
    ss_local = st.session_state
    ctx = {
        "agent_type": "credit",
        "stage": ss_local.get("credit_stage") or ss_local.get("stage"),
        "user": (ss_local.get("credit_user") or {}).get("name"),
        "apps_in_review": ss_local.get("credit_apps_in_review"),
        "flagged_cases": ss_local.get("credit_flagged_cases"),
        "avg_decision_time": ss_local.get("credit_avg_decision_time"),
        "ai_performance": ss_local.get("credit_ai_performance"),
        "last_run_id": ss_local.get("credit_last_run_id"),
        "last_error": ss_local.get("credit_last_error"),
        "selected_model": ss_local.get("selected_model"),
    }
    return {k: v for k, v in ctx.items() if v not in (None, "", [])}


CREDIT_FAQ = [
    "Explain why this borrower was rejected.",
    "Summarize rule breaches for this loan.",
    "Compare PD vs NDI for this applicant.",
    "How can I rerun Stage D – Policy?",
]

def _build_credit_chat_context() -> Dict[str, Any]:
    ss_local = st.session_state
    ctx = {
        "agent_type": "credit",
        "stage": ss_local.get("credit_stage") or ss_local.get("stage"),
        "user": (ss_local.get("credit_user") or {}).get("name"),
        "apps_in_review": ss_local.get("credit_apps_in_review"),
        "flagged_cases": ss_local.get("credit_flagged_cases"),
        "avg_decision_time": ss_local.get("credit_avg_decision_time"),
        "ai_performance": ss_local.get("credit_ai_performance"),
        "last_run_id": ss_local.get("credit_last_run_id"),
        "last_error": ss_local.get("credit_last_error"),
        "selected_model": ss_local.get("selected_model"),
    }
    return {k: v for k, v in ctx.items() if v not in (None, "", [])}


CREDIT_FAQ = [
    "Explain why this borrower was rejected.",
    "Summarize rule breaches for this loan.",
    "Compare PD vs NDI for this applicant.",
    "How can I rerun Stage D – Policy?",
    "Show the last 10 loans approved with amount and stage notes.",
    "List the last 10 loans declined and which policy failed.",
    "What was the total loan volume approved in the past month?",
    "What was the total declined volume during the past month?",
    "List the last 10 manual overrides and their rationale.",
    "Where are the artifacts for the last 10 runs stored in .tmp_runs?",
]


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


def render_image_tag(agent_id: str, industry: str, emoji_fallback: str) -> str:
    base = agent_id.lower().replace(" ", "_")
    img_path = load_image(base) or load_image(industry.replace(" ", "_"))
    if img_path:
        return (
            f'<img src="file://{img_path}" '
            f'style="width:48px;height:48px;border-radius:10px;object-fit:cover;">'
        )
    return f'<div style="font-size:32px;">{emoji_fallback}</div>'




st.markdown(
    """
    <style>
    [data-testid="stSidebar"], section[data-testid="stSidebar"]{display:none!important}
    [data-testid="stAppViewContainer"]{margin-left:0!important;padding-left:0!important}
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────
# CONSTANTS / PATHS
# ──────────────────────────────────────────────────────────────
# You can point this to your FastAPI host
API_URL = os.environ.get("AGENT_API_URL", "http://localhost:8090")

_CHATBOT_REFRESH_STATE: Dict[str, float] = {"last_ts": 0.0}

def _ping_chatbot_refresh(reason: str = "credit", *, min_interval: float = 300.0) -> None:
    """Best-effort, throttled ping so the Gemma chatbot reindexes new CSV artifacts."""
    now = time.time()
    last_ts = _CHATBOT_REFRESH_STATE.get("last_ts", 0.0)
    if (now - last_ts) < min_interval:
        return
    _CHATBOT_REFRESH_STATE["last_ts"] = now

    def _fire():
        try:
            requests.post(f"{API_URL}/chatbot/refresh", json={"reason": reason}, timeout=5)
        except Exception:
            logging.getLogger(__name__).debug("Chatbot refresh skipped", exc_info=True)

    threading.Thread(target=_fire, daemon=True).start()

# Base & temp runs folder
BASE_DIR = os.path.abspath(".")
RUNS_DIR = os.path.join(BASE_DIR, ".tmp_runs")
os.makedirs(RUNS_DIR, exist_ok=True)



# ─────────────────────────────────────────────
# NAVIGATION — Reliable jump to Home / Agents
# ─────────────────────────────────────────────
def _set_query_params_safe(**kwargs):
    """Backwards-compatible setter for Streamlit versions before query_params."""
    try:
        for k, v in kwargs.items():
            st.query_params[k] = v
        return True
    except Exception:
        pass
    try:
        st.experimental_set_query_params(**kwargs)
        return True
    except Exception:
        return False


def _go_stage(target_stage: str):
    """Reliable navigation that returns to Home or Agents even from sub-pages."""
    st.session_state["stage"] = target_stage
    try:
        # Jump back to main app router (must exist in /services/ui/app.py)
        st.switch_page("app.py")
        return
    except Exception:
        pass
    _set_query_params_safe(stage=target_stage)
    st.rerun()


# ────────────────────────────────
# 🧭 NAVBAR + THEME SWITCHER
# ────────────────────────────────
def render_nav_bar_app():
    """Top navigation bar with Home, Agents, and Theme switch."""
    ss = st.session_state

    c1, c2, c3 = st.columns([1, 1, 2.5])

    with c1:
        if st.button("🏠 Back to Home", key=f"btn_home_{ss.get('stage','landing')}"):
            _go_stage("landing")
    with c2:
        if st.button("🤖 Back to Agents", key=f"btn_agents_{ss.get('stage','landing')}"):
            _go_stage("agents")
    with c3:
        render_theme_toggle(
            label="🌗 Dark mode",
            key="credit_theme_toggle",
            help="Switch theme",
        )

    st.markdown("---")


# ✅ Render navbar before showing login or main content
render_nav_bar_app()





# ────────────────────────────────
# 🔐 LOGIN GATE
# ────────────────────────────────
def login_block():
    st.title("🔐 Login to AI Credit Appraisal Platform")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        user = st.text_input("Username", placeholder="e.g. dzoan")
    with c2:
        email = st.text_input("Email", placeholder="e.g. dzoan@demo.local")
    with c3:
        pwd = st.text_input("Password", type="password", placeholder="Enter any password")

    if st.button("Login", key="btn_credit_login", use_container_width=True):
        if (user or "").strip() and (email or "").strip():
            st.session_state["user_info"] = {
                "name": user.strip(),
                "email": email.strip(),
                "flagged": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            st.session_state["credit_logged_in"] = True
            st.session_state["stage"] = "credit_agent"
            st.rerun()
        else:
            st.error("⚠️ Please fill all fields before continuing.")


# ✅ Always render navbar — and only then login
if not st.session_state.get("credit_logged_in", False):
    login_block()
    st.stop()

# Operator overview
operator_name = (
    st.session_state.get("user_info", {}).get("name")
    or st.session_state.get("credit_user", {}).get("name")
    or "Operator"
)

credit_ai_minutes = _coerce_minutes(st.session_state.get("credit_avg_decision_time"), 9.0)

render_operator_banner(
    operator_name=operator_name,
    title="Credit Appraisal Command",
    summary="Coordinate intake → anonymization → AI scoring → policy decisions inside one unified cockpit.",
    bullets=[
        "Collect borrower data once and auto-sanitize for analytics.",
        "Score risk with explainable AI plus policy/NDI overlays.",
        "Route exceptions to human reviewers and capture feedback for retraining.",
    ],
    metrics=[
        {
            "label": "Apps in Review",
            "value": st.session_state.get("credit_apps_in_review"),
            "delta": "+2 vs last week",
            "delta_color": "#34d399",
            "color": "#34d399",
            "percent": min(1.0, st.session_state.get("credit_apps_in_review", 0) / 40.0),
            "context": "Human queue avg: 41",
        },
        {
            "label": "Compliance Flags",
            "value": st.session_state.get("credit_flagged_cases"),
            "delta": "-1 cleared",
            "delta_color": "#f87171",
            "color": "#f87171",
            "percent": min(1.0, st.session_state.get("credit_flagged_cases", 0) / 15.0),
            "context": "Manual avg flags: 9",
        },
        {
            "label": "Avg AI Decision Time",
            "value": st.session_state.get("credit_avg_decision_time") or f"{credit_ai_minutes:.0f} min",
            "delta": "-3 min vs last cycle",
            "delta_color": "#60a5fa",
            "color": "#60a5fa",
            "percent": min(1.0, credit_ai_minutes / 45.0),
            "context": "AI adjudication speed",
        },
    ],
    icon="🏦",
)

# # ────────────────────────────────
# # LOGIN GATE
# # ────────────────────────────────
# def login_block():
#     st.title("🔐 Login to AI Credit Appraisal Platform")
#     c1, c2, c3 = st.columns([1, 1, 1])
#     with c1:
#         user = st.text_input("Username", placeholder="e.g. dzoan")
#     with c2:
#         email = st.text_input("Email", placeholder="e.g. dzoan@demo.local")
#     with c3:
#         pwd = st.text_input("Password", type="password", placeholder="Enter any password")

#     if st.button("Login", key="btn_credit_login", use_container_width=True):
#         if (user or "").strip() and (email or "").strip():
#             st.session_state["user_info"] = {
#                 "name": user.strip(),
#                 "email": email.strip(),
#                 "flagged": False,
#                 "timestamp": datetime.now(timezone.utc).isoformat(),
#             }
#             st.session_state["credit_logged_in"] = True
#             st.session_state["stage"] = "credit_agent"
#             st.rerun()
#         else:
#             st.error("⚠️ Please fill all fields before continuing.")


# if not st.session_state.get("credit_logged_in", False):
#     login_block()
#     st.stop()





# -----------------------------------------------------------
# CREDIT WORKFLOW ACTIVE ONLY IF CREDIT AGENT SELECTED
# -----------------------------------------------------------
ss = st.session_state
stage = ss.get("stage")

if stage == "credit_agent":

    # Header (from your render_credit_header() defined earlier)
    render_credit_header()


       
# ✅ CREDIT APPRAISAL WORKFLOW TABS (1 → 8)

    # ============================================================
    # 🌈 Colorized Tabs (Matches A→H badge palette exactly)
    # ============================================================
    st.markdown("""
    <style>
    /* --- Layout adjustments for clean alignment --- */
    .stTabs [data-baseweb="tab-list"] {
    border-bottom: 2px solid #1e293b;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: .25rem;
    }

    /* --- Base style for all tabs --- */
    .stTabs [data-baseweb="tab"] {
    border-radius: .6rem;
    padding: .45rem .9rem;
    font-weight: 600;
    color: #fff !important;
    border: none;
    opacity: 0.95;
    transition: all 0.2s ease-in-out;
    }

    /* Hover and active effects */
    .stTabs [data-baseweb="tab"]:hover {
    transform: translateY(-2px);
    filter: brightness(1.1);
    opacity: 1;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
    box-shadow: 0 0 8px rgba(255,255,255,0.15);
    transform: translateY(-1px);
    filter: brightness(1.1);
    }

    /* --- Tab Colors: A→H palette --- */
    .stTabs [data-baseweb="tab"]:nth-child(1) { background: #1d4ed8; }  /* A) Blue */
    .stTabs [data-baseweb="tab"]:nth-child(2) { background: #059669; }  /* B) Green */
    .stTabs [data-baseweb="tab"]:nth-child(3) { background: #d97706; }  /* C) Amber */
    .stTabs [data-baseweb="tab"]:nth-child(4) { background: #7c3aed; }  /* D) Violet */
    .stTabs [data-baseweb="tab"]:nth-child(5) { background: #a16207; }  /* E) Gold */
    .stTabs [data-baseweb="tab"]:nth-child(6) { background: #e11d48; }  /* F) Red */
    .stTabs [data-baseweb="tab"]:nth-child(7) { background: #0ea5e9; }  /* G) Cyan */
    .stTabs [data-baseweb="tab"]:nth-child(8) { background: #64748b; }  /* H) Slate */
    </style>
    """, unsafe_allow_html=True)


# TABSLIST =====================================================
    tab_howto, tab_input, tab_clean, tab_run, tab_review, tab_train, tab_deploy, tab_handoff, tab_feedback = st.tabs([
        "📘 How-To",
        "1️⃣ 🏦 Synthetic Data Generator",
        "2️⃣ 🧹 Anonymize & Sanitize Data",
        "3️⃣ 🤖 Credit appraisal by AI assistant",
        "4️⃣ 🧑‍⚖️ Human Review",
        "5️⃣ 🔁 Training (Feedback → Retrain)",
        "6️⃣ 🚀 Deployment of Credit Model",
        "7️⃣ 📦 Reporting & Handoff",
        "8️⃣ 🗣️ Feedback & Feature Requests"
    ])

    with tab_howto:
        st.title("📘 How to Use This Agent")
        st.markdown("""
### What
An AI-driven credit appraisal agent that evaluates borrower risk using explainable machine-learning models and policy rules.

### Goal
To help financial institutions automate loan decisioning while maintaining transparency, compliance, and human oversight.

### How
1. Upload borrower or loan data, or import datasets from Kaggle or Hugging Face.
2. The agent cleans and anonymizes data, detects target columns, and trains predictive models (LightGBM or HF tabular).
3. It applies business policies such as LTV, DTI, and score thresholds, generating real-time approve/reject/review decisions.
4. Outputs include explainable model charts, confidence scores, and decision summaries.

### So What (Benefits)
- Speeds up credit decisioning from hours to seconds.
- Reduces manual errors and human bias.
- Provides clear, auditable AI logic for regulators.
- Continuously learns from feedback to improve accuracy.

### What Next
1. Try it now—upload your dataset or choose a public sample.
2. Contact our team to tailor the rules and credit policies to your needs.
3. Once satisfied, import the trained model and decision engine into your production environment to power real-world loan approvals.
        """)

else:
    # Safe placeholders when not on the Credit Agent stage
    tab_input = st.container()
    tab_clean = st.container()
    tab_run = st.container()
    tab_review = st.container()
    tab_train = st.container()
    tab_deploy = st.container()
    tab_handoff = st.container()
    tab_feedback = st.container()




# ────────────────────────────────
# GLOBAL UTILS
# ────────────────────────────────

BANNED_NAMES = {"race", "gender", "religion", "ethnicity", "ssn", "national_id"}
PII_COLS = {"customer_name", "name", "email", "phone", "address", "ssn", "national_id", "dob"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{6,}\d")


def dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated(keep="last")]


def scrub_text_pii(s):
    if not isinstance(s, str):
        return s
    s = EMAIL_RE.sub("", s)
    s = PHONE_RE.sub("", s)
    return s.strip()


def drop_pii_columns(df: pd.DataFrame):
    original_cols = list(df.columns)
    keep_cols = [c for c in original_cols if all(k not in c.lower() for k in PII_COLS)]
    dropped = [c for c in original_cols if c not in keep_cols]
    out = df[keep_cols].copy()
    for c in out.select_dtypes(include="object"):
        out[c] = out[c].apply(scrub_text_pii)
    return dedupe_columns(out), dropped


def strip_policy_banned(df: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for c in df.columns:
        cl = c.lower()
        if cl in BANNED_NAMES:
            continue
        keep.append(c)
    return df[keep]


def append_user_info(df: pd.DataFrame) -> pd.DataFrame:
    meta = st.session_state["user_info"]
    out = df.copy()
    out["session_user_name"] = meta["name"]
    out["session_user_email"] = meta["email"]
    out["session_flagged"] = meta["flagged"]
    out["created_at"] = meta["timestamp"]
    return dedupe_columns(out)


def save_to_runs(df: pd.DataFrame, prefix: str) -> str:
    #ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
    flag_suffix = "_FLAGGED" if st.session_state["user_info"]["flagged"] else ""
    fname = f"{prefix}_{ts}{flag_suffix}.csv"
    fpath = os.path.join(RUNS_DIR, fname)
    dedupe_columns(df).to_csv(fpath, index=False)
    return fpath


def try_json(x):
    if isinstance(x, (dict, list)):
        return x
    if not isinstance(x, str):
        return None
    try:
        return json.loads(x)
    except Exception:
        return None


def _safe_json(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, str) and x.strip():
        try:
            return json.loads(x)
        except Exception:
            return {}
    return {}


def fmt_currency_label(base: str) -> str:
    sym = st.session_state.get("currency_symbol", "")
    return f"{base} ({sym})" if sym else base


# ─────────────────────────────────────────────
# CURRENCY CATALOG
CURRENCY_OPTIONS = {
    # code: (label, symbol, fx to apply on USD-like base generated numbers)
    "USD": ("USD $", "$", 1.0),
    "EUR": ("EUR €", "€", 0.93),
    "GBP": ("GBP £", "£", 0.80),
    "JPY": ("JPY ¥", "¥", 150.0),
    "VND": ("VND ₫", "₫", 24000.0),
}


def set_currency_defaults():
    if "currency_code" not in st.session_state:
        st.session_state["currency_code"] = "USD"
    label, symbol, fx = CURRENCY_OPTIONS[st.session_state["currency_code"]]
    st.session_state["currency_label"] = label
    st.session_state["currency_symbol"] = symbol
    st.session_state["currency_fx"] = fx


set_currency_defaults()


# ─────────────────────────────────────────────
# DASHBOARD HELPERS (Plotly, dark theme)
def _kpi_card(label: str, value: str, sublabel: str | None = None):
    st.markdown(
        f"""
        <div style="background:#0e1117;border:1px solid #2a2f3e;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
          <div style="font-size:12px;color:#9aa4b2;text-transform:uppercase;letter-spacing:.06em;">{label}</div>
          <div style="font-size:28px;font-weight:700;color:#e6edf3;line-height:1.1;margin-top:2px;">{value}</div>
          {f'<div style="font-size:12px;color:#9aa4b2;margin-top:6px;">{sublabel}</div>' if sublabel else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_credit_dashboard(df: pd.DataFrame, currency_symbol: str = ""):
    """
    Renders the whole dashboard (TOP-10s → Opportunities → KPIs & pies/bars → Mix table).
    Keeps decision filter in the table only.
    """
    if df is None or df.empty:
        st.info("No data to visualize yet.")
        return

    cols = df.columns

    # ─────────────── TOP 10s FIRST ───────────────
    st.markdown("## 🔝 Top 10 Snapshot")

    # Top 10 loans approved
    if {"decision", "loan_amount", "application_id"} <= set(cols):
        top_approved = df[df["decision"].astype(str).str.lower() == "approved"].copy()
        if not top_approved.empty:
            top_approved = top_approved.sort_values("loan_amount", ascending=False).head(10)
            fig = px.bar(
                top_approved,
                x="loan_amount",
                y="application_id",
                orientation="h",
                title="Top 10 Approved Loans",
                labels={"loan_amount": f"Loan Amount {currency_symbol}", "application_id": "Application"},
            )
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=420, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No approved loans available to show top 10.")

    # Top 10 collateral types by average value
    if {"collateral_type", "collateral_value"} <= set(cols):
        cprof = df.groupby("collateral_type", dropna=False).agg(
            avg_value=("collateral_value", "mean"),
            cnt=("collateral_type", "count")
        ).reset_index()
        if not cprof.empty:
            cprof = cprof.sort_values("avg_value", ascending=False).head(10)
            fig = px.bar(
                cprof,
                x="avg_value",
                y="collateral_type",
                orientation="h",
                title="Top 10 Collateral Types (Avg Value)",
                labels={"avg_value": f"Avg Value {currency_symbol}", "collateral_type": "Collateral Type"},
                hover_data=["cnt"]
            )
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=420, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Top 10 reasons for denial (from rule_reasons False flags)
    if "rule_reasons" in cols and "decision" in cols:
        denied = df[df["decision"].astype(str).str.lower() == "denied"].copy()
        reasons_count = {}
        for _, r in denied.iterrows():
            rr = _safe_json(r.get("rule_reasons"))
            if isinstance(rr, dict):
                for k, v in rr.items():
                    if v is False:
                        reasons_count[k] = reasons_count.get(k, 0) + 1
        if reasons_count:
            items = pd.DataFrame(sorted(reasons_count.items(), key=lambda x: x[1], reverse=True),
                                 columns=["reason", "count"]).head(10)
            fig = px.bar(
                items, x="count", y="reason", orientation="h",
                title="Top 10 Reasons for Denial",
                labels={"count": "Count", "reason": "Rule"},
            )
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=420, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No denial reasons detected.")

    # Top 10 loan officer performance (approval rate) if officer column present
    officer_col = None
    for guess in ("loan_officer", "officer", "reviewed_by", "session_user_name"):
        if guess in cols:
            officer_col = guess
            break
    if officer_col and "decision" in cols:
        perf = (
            df.assign(is_approved=(df["decision"].astype(str).str.lower() == "approved").astype(int))
              .groupby(officer_col, dropna=False)["is_approved"]
              .agg(approved_rate="mean", n="count")
              .reset_index()
        )
        if not perf.empty:
            perf["approved_rate_pct"] = (perf["approved_rate"] * 100).round(1)
            perf = perf.sort_values(["approved_rate_pct", "n"], ascending=[False, False]).head(10)
            fig = px.bar(
                perf, x="approved_rate_pct", y=officer_col, orientation="h",
                title="Top 10 Loan Officer Approval Rate (this batch)",
                labels={"approved_rate_pct": "Approval Rate (%)", officer_col: "Officer"},
                hover_data=["n"]
            )
            fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), height=420, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ─────────────── OPPORTUNITIES ───────────────
    st.markdown("## 💡 Opportunities")

    # Short-term loan opportunities (simple heuristic)
    opp_rows = []
    if {"income", "loan_amount"}.issubset(cols):
        term_col = "loan_term_months" if "loan_term_months" in cols else ("loan_duration_months" if "loan_duration_months" in cols else None)
        if term_col:
            for _, r in df.iterrows():
                inc = float(r.get("income", 0) or 0)
                amt = float(r.get("loan_amount", 0) or 0)
                term = int(r.get(term_col, 0) or 0)
                dti = float(r.get("DTI", 0) or 0)
                if (term >= 36) and (amt <= inc * 0.8) and (dti <= 0.45):
                    opp_rows.append({
                        "application_id": r.get("application_id"),
                        "suggested_term": 24,
                        "loan_amount": amt,
                        "income": inc,
                        "DTI": dti,
                        "note": "Candidate for short-term plan (<=24m) based on affordability."
                    })
    if opp_rows:
        st.markdown("#### 📎 Short-Term Loan Candidates")
        st.dataframe(pd.DataFrame(opp_rows).head(25), use_container_width=True, height=320)
    else:
        st.info("No short-term loan candidates identified in this batch.")

    st.markdown("#### 🔁 Buyback / Consolidation Beneficiaries")
    candidates = []
    need = {"decision", "existing_debt", "loan_amount", "DTI"}
    if need <= set(cols):
        for _, r in df.iterrows():
            dec = str(r.get("decision", "")).lower()
            debt = float(r.get("existing_debt", 0) or 0)
            loan = float(r.get("loan_amount", 0) or 0)
            dti = float(r.get("DTI", 0) or 0)
            proposal = _safe_json(r.get("proposed_consolidation_loan", {}))
            has_bb = bool(proposal)

            if dec == "denied" or dti > 0.45 or debt > loan:
                benefit_score = round((debt / (loan + 1e-6)) * 0.4 + dti * 0.6, 2)
                candidates.append({
                    "application_id": r.get("application_id"),
                    "customer_type": r.get("customer_type"),
                    "existing_debt": debt,
                    "loan_amount": loan,
                    "DTI": dti,
                    "collateral_type": r.get("collateral_type"),
                    "buyback_proposed": has_bb,
                    "buyback_amount": proposal.get("buyback_amount") if has_bb else None,
                    "benefit_score": benefit_score,
                    "note": proposal.get("note") if has_bb else None
                })
    if candidates:
        cand_df = pd.DataFrame(candidates).sort_values("benefit_score", ascending=False)
        st.dataframe(cand_df.head(25), use_container_width=True, height=380)
    else:
        st.info("No additional buyback beneficiaries identified.")

    st.markdown("---")

    # ─────────────── PORTFOLIO KPIs ───────────────
    st.markdown("## 📈 Portfolio Snapshot")
    c1, c2, c3, c4 = st.columns(4)

    # Approval rate
    if "decision" in cols:
        total = len(df)
        approved = int((df["decision"].astype(str).str.lower() == "approved").sum())
        rate = (approved / total * 100) if total else 0.0
        with c1: _kpi_card("Approval Rate", f"{rate:.1f}%", f"{approved} of {total}")

    # Avg approved loan amount
    if {"decision", "loan_amount"} <= set(cols):
        ap = df[df["decision"].astype(str).str.lower() == "approved"]["loan_amount"]
        avg_amt = ap.mean() if len(ap) else 0.0
        with c2: _kpi_card("Avg Approved Amount", f"{currency_symbol}{avg_amt:,.0f}")

    # Decision time (if present)
    if {"created_at", "decision_at"} <= set(cols):
        try:
            t = (pd.to_datetime(df["decision_at"]) - pd.to_datetime(df["created_at"])).dt.total_seconds() / 60.0
            avg_min = float(t.mean())
            with c3: _kpi_card("Avg Decision Time", f"{avg_min:.1f} min")
        except Exception:
            with c3: _kpi_card("Avg Decision Time", "—")

    # Non-bank share
    if "customer_type" in cols:
        nb = int((df["customer_type"].astype(str).str.lower() == "non-bank").sum())
        total = len(df)
        share = (nb / total * 100) if total else 0.0
        with c4: _kpi_card("Non-bank Share", f"{share:.1f}%", f"{nb} of {total}")

    # ─────────────── COMPOSITION & RISK ───────────────
    st.markdown("## 🧭 Composition & Risk")

    # Approval vs Denial (pie)
    if "decision" in cols:
        pie_df = df["decision"].value_counts().rename_axis("Decision").reset_index(name="Count")
        fig = px.pie(pie_df, names="Decision", values="Count", title="Decision Mix")
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10), height=360, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # Avg DTI / LTV by decision (grouped bars)
    have_dti = "DTI" in cols
    have_ltv = "LTV" in cols
    if "decision" in cols and (have_dti or have_ltv):
        agg_map = {}
        if have_dti: agg_map["avg_DTI"] = ("DTI", "mean")
        if have_ltv: agg_map["avg_LTV"] = ("LTV", "mean")
        grp = df.groupby("decision").agg(**agg_map).reset_index()
        melted = grp.melt(id_vars=["decision"], var_name="metric", value_name="value")
        fig = px.bar(melted, x="decision", y="value", color="metric",
                     barmode="group", title="Average DTI / LTV by Decision")
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10), height=360, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # Loan term mix (stacked)
    term_col = "loan_term_months" if "loan_term_months" in cols else ("loan_duration_months" if "loan_duration_months" in cols else None)
    if term_col and "decision" in cols:
        mix = df.groupby([term_col, "decision"]).size().reset_index(name="count")
        fig = px.bar(
            mix, x=term_col, y="count", color="decision", title="Loan Term Mix",
            labels={term_col: "Term (months)", "count": "Count"}, barmode="stack"
        )
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10), height=360, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # Collateral avg value by type (bar)
    if {"collateral_type", "collateral_value"} <= set(cols):
        cprof = df.groupby("collateral_type").agg(
            avg_col=("collateral_value", "mean"),
            cnt=("collateral_type", "count")
        ).reset_index()
        fig = px.bar(
            cprof.sort_values("avg_col", ascending=False),
            x="collateral_type", y="avg_col",
            title=f"Avg Collateral Value by Type ({currency_symbol})",
            hover_data=["cnt"]
        )
        fig.update_layout(margin=dict(l=10, r=10, t=60, b=10), height=360, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # Top proposed plans (horizontal bar)
    if "proposed_loan_option" in cols:
        plans = df["proposed_loan_option"].dropna().astype(str)
        if len(plans) > 0:
            plan_types = []
            for s in plans:
                p = _safe_json(s)
                plan_types.append(p.get("type") if isinstance(p, dict) and "type" in p else s)
            plan_df = pd.Series(plan_types).value_counts().head(10).rename_axis("plan").reset_index(name="count")
            fig = px.bar(
                plan_df, x="count", y="plan", orientation="h",
                title="Top 10 Proposed Plans"
            )
            fig.update_layout(margin=dict(l=10, r=10, t=60, b=10), height=360, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    # Customer mix table (bank vs non-bank)
    if "customer_type" in cols:
        mix = df["customer_type"].value_counts().rename_axis("Customer Type").reset_index(name="Count")
        mix["Ratio"] = (mix["Count"] / mix["Count"].sum()).round(3)
        st.markdown("### 👥 Customer Mix")
        st.dataframe(mix, use_container_width=True, height=220)




# DATA GENERATORS

def generate_raw_synthetic(n: int, non_bank_ratio: float) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    names = ["Alice Nguyen","Bao Tran","Chris Do","Duy Le","Emma Tran",
             "Felix Nguyen","Giang Ho","Hanh Vo","Ivan Pham","Julia Ngo"]
    emails = [f"{n.split()[0].lower()}.{n.split()[1].lower()}@gmail.com" for n in names]
    addrs = [
        "23 Elm St, Boston, MA","19 Pine Ave, San Jose, CA","14 High St, London, UK",
        "55 Nguyen Hue, Ho Chi Minh","78 Oak St, Chicago, IL","10 Broadway, New York, NY",
        "8 Rue Lafayette, Paris, FR","21 Königstr, Berlin, DE","44 Maple Dr, Los Angeles, CA","22 Bay St, Toronto, CA"
    ]
    is_non = rng.random(n) < non_bank_ratio
    cust_type = np.where(is_non, "non-bank", "bank")

    df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, n + 1)],
        "customer_name": np.random.choice(names, n),
        "email": np.random.choice(emails, n),
        "phone": [f"+1-202-555-{1000+i:04d}" for i in range(n)],
        "address": np.random.choice(addrs, n),
        "national_id": rng.integers(10_000_000, 99_999_999, n),
        "age": rng.integers(21, 65, n),
        "income": rng.integers(25_000, 150_000, n),
        "employment_length": rng.integers(0, 30, n),
        "loan_amount": rng.integers(5_000, 100_000, n),
        "loan_duration_months": rng.choice([12, 24, 36, 48, 60, 72], n),
        "collateral_value": rng.integers(8_000, 200_000, n),
        "collateral_type": rng.choice(["real_estate","car","land","deposit"], n),
        "co_loaners": rng.choice([0,1,2], n, p=[0.7, 0.25, 0.05]),
        "credit_score": rng.integers(300, 850, n),
        "existing_debt": rng.integers(0, 50_000, n),
        "assets_owned": rng.integers(10_000, 300_000, n),
        "current_loans": rng.integers(0, 5, n),
        "customer_type": cust_type,
    })
    eps = 1e-9
    df["DTI"] = df["existing_debt"] / (df["income"] + eps)
    df["LTV"] = df["loan_amount"] / (df["collateral_value"] + eps)
    df["CCR"] = df["collateral_value"] / (df["loan_amount"] + eps)
    df["ITI"] = (df["loan_amount"] / (df["loan_duration_months"] + eps)) / (df["income"] + eps)
    df["CWI"] = ((1 - df["DTI"]).clip(0, 1)) * ((1 - df["LTV"]).clip(0, 1)) * (df["CCR"].clip(0, 3))

    fx = st.session_state["currency_fx"]
    for c in ("income", "loan_amount", "collateral_value", "assets_owned", "existing_debt"):
        df[c] = (df[c] * fx).round(2)
    df["currency_code"] = st.session_state["currency_code"]
    return dedupe_columns(df)


def generate_anon_synthetic(n: int, non_bank_ratio: float) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    is_non = rng.random(n) < non_bank_ratio
    cust_type = np.where(is_non, "non-bank", "bank")

    df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, n + 1)],
        "age": rng.integers(21, 65, n),
        "income": rng.integers(25_000, 150_000, n),
        "employment_length": rng.integers(0, 30, n),
        "loan_amount": rng.integers(5_000, 100_000, n),
        "loan_duration_months": rng.choice([12, 24, 36, 48, 60, 72], n),
        "collateral_value": rng.integers(8_000, 200_000, n),
        "collateral_type": rng.choice(["real_estate","car","land","deposit"], n),
        "co_loaners": rng.choice([0,1,2], n, p=[0.7, 0.25, 0.05]),
        "credit_score": rng.integers(300, 850, n),
        "existing_debt": rng.integers(0, 50_000, n),
        "assets_owned": rng.integers(10_000, 300_000, n),
        "current_loans": rng.integers(0, 5, n),
        "customer_type": cust_type,
    })
    eps = 1e-9
    df["DTI"] = df["existing_debt"] / (df["income"] + eps)
    df["LTV"] = df["loan_amount"] / (df["collateral_value"] + eps)
    df["CCR"] = df["collateral_value"] / (df["loan_amount"] + eps)
    df["ITI"] = (df["loan_amount"] / (df["loan_duration_months"] + eps)) / (df["income"] + eps)
    df["CWI"] = ((1 - df["DTI"]).clip(0, 1)) * ((1 - df["LTV"]).clip(0, 1)) * (df["CCR"].clip(0, 3))

    fx = st.session_state["currency_fx"]
    for c in ("income", "loan_amount", "collateral_value", "assets_owned", "existing_debt"):
        df[c] = (df[c] * fx).round(2)
    df["currency_code"] = st.session_state["currency_code"]
    return dedupe_columns(df)


def to_agent_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Harmonize to the server-side agent’s expected schema.
    """
    out = df.copy()
    n = len(out)
    if "employment_years" not in out.columns:
        out["employment_years"] = out.get("employment_length", 0)
    if "debt_to_income" not in out.columns:
        if "DTI" in out.columns:
            out["debt_to_income"] = out["DTI"].astype(float)
        elif "existing_debt" in out.columns and "income" in out.columns:
            denom = out["income"].replace(0, np.nan)
            dti = (out["existing_debt"] / denom).fillna(0.0)
            out["debt_to_income"] = dti.clip(0, 10)
        else:
            out["debt_to_income"] = 0.0
    rng = np.random.default_rng(12345)
    if "credit_history_length" not in out.columns:
        out["credit_history_length"] = rng.integers(0, 30, n)
    if "num_delinquencies" not in out.columns:
        out["num_delinquencies"] = np.minimum(rng.poisson(0.2, n), 10)
    if "requested_amount" not in out.columns:
        out["requested_amount"] = out.get("loan_amount", 0)
    if "loan_term_months" not in out.columns:
        out["loan_term_months"] = out.get("loan_duration_months", 0)
    return dedupe_columns(out)


# ─────────────────────────────────────────────
# 🏦 TAB 1 — Synthetic Data Generator
with tab_input:
    st.subheader("🏦 Synthetic Credit Data Generator")

    # Currency selector (before generation)
    c1, c2 = st.columns([1, 2])
    with c1:
        code = st.selectbox(
            "Currency",
            list(CURRENCY_OPTIONS.keys()),
            index=list(CURRENCY_OPTIONS.keys()).index(st.session_state["currency_code"]),
            help="All monetary fields will be in this local currency."
        )
        if code != st.session_state["currency_code"]:
            st.session_state["currency_code"] = code
            set_currency_defaults()
    with c2:
        st.markdown(
            f"""
            <div style='background-color:#1e293b; padding:12px 16px; border-radius:8px;'>
                <span style='font-weight:600; color:#f8fafc;'>
                    💰 Amounts will be generated in
                    <span style='color:#4ade80;'>{st.session_state['currency_label']}</span>.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    rows = st.slider("Number of rows to generate", 50, 2000, 200, step=50)
    non_bank_ratio = st.slider("Share of non-bank customers", 0.0, 1.0, 0.30, 0.05)

    colA, colB = st.columns(2)
    with colA:
        if st.button("🔴 Generate RAW Synthetic Data (with PII)", use_container_width=True):
            raw_df = append_user_info(generate_raw_synthetic(rows, non_bank_ratio))
            st.session_state.synthetic_raw_df = raw_df
            raw_path = save_to_runs(raw_df, "synthetic_raw")
            st.success(f"Generated RAW (PII) dataset with {rows} rows in {st.session_state['currency_label']}. Saved to {raw_path}")
            st.dataframe(raw_df.head(10), use_container_width=True)
            st.download_button(
                "⬇️ Download RAW CSV",
                raw_df.to_csv(index=False).encode("utf-8"),
                os.path.basename(raw_path),
                "text/csv"
            )

    with colB:
        if st.button("🟢 Generate ANON Synthetic Data (ready for agent)", use_container_width=True):
            anon_df = append_user_info(generate_anon_synthetic(rows, non_bank_ratio))
            st.session_state.synthetic_df = anon_df
            anon_path = save_to_runs(anon_df, "synthetic_anon")
            st.success(f"Generated ANON dataset with {rows} rows in {st.session_state['currency_label']}. Saved to {anon_path}")
            st.dataframe(anon_df.head(10), use_container_width=True)
            st.download_button(
                "⬇️ Download ANON CSV",
                anon_df.to_csv(index=False).encode("utf-8"),
                os.path.basename(anon_path),
                "text/csv"
            )


# ─────────────────────────────────────────────
# 🧹 TAB 2 — Anonymize & Sanitize Data
with tab_clean:
    st.subheader("🧹 Upload & Anonymize Customer Data (PII columns will be DROPPED)")
    st.markdown("Upload your **real CSV**. We drop PII columns and scrub emails/phones in text fields.")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            st.stop()

        st.write("📊 Original Data Preview:")
        st.dataframe(dedupe_columns(df.head(5)), use_container_width=True)

        sanitized, dropped_cols = drop_pii_columns(df)
        sanitized = append_user_info(sanitized)
        sanitized = dedupe_columns(sanitized)
        st.session_state.anonymized_df = sanitized

        st.success(f"Dropped PII columns: {sorted(dropped_cols) if dropped_cols else 'None'}")
        st.write("✅ Sanitized Data Preview:")
        st.dataframe(sanitized.head(5), use_container_width=True)

        fpath = save_to_runs(sanitized, "anonymized")
        st.success(f"Saved anonymized file: {fpath}")
        st.download_button(
            "⬇️ Download Clean Data",
            sanitized.to_csv(index=False).encode("utf-8"),
            os.path.basename(fpath),
            "text/csv"
        )
    else:
        st.info("Choose a CSV to see the sanitize flow.", icon="ℹ️")


# ─────────────────────────────────────────────
# 🤖 TAB 3 — Credit appraisal by AI assistant
with tab_run:
    # Auto-display dashboard if demo data was loaded
    if st.session_state.get("credit_demo_loaded") and st.session_state.get("last_merged_df") is not None:
        merged_df = st.session_state["last_merged_df"]
        st.markdown("### 📄 Credit AI Agent Decisions Table")
        uniq_dec = sorted([d for d in merged_df.get("decision", pd.Series(dtype=str)).dropna().unique()]) \
                if "decision" in merged_df.columns else []
        chosen = st.multiselect("Filter decision", options=uniq_dec, default=uniq_dec, key="filter_decisions_auto")
        df_view = merged_df.copy()
        if "decision" in df_view.columns and chosen:
            df_view = df_view[df_view["decision"].isin(chosen)]
        st.dataframe(df_view, use_container_width=True)
        
        st.markdown("## 📊 Dashboard")
        render_credit_dashboard(merged_df, st.session_state.get("currency_symbol", ""))
        st.info("💡 Demo data loaded automatically. Dashboard shows results from auto-run.")
        st.markdown("---")
    
    st.subheader("🤖 Credit appraisal by AI assistant")
    # Anchor for loopback link from Training tab
    st.markdown('<a name="credit-appraisal-stage"></a>', unsafe_allow_html=True)
    st.markdown(
        """
        **How to use this stage**

        1. Pick a trained model (or promote a new one from Stage 5).
        2. Set the Local LLM + host flavor so narratives run on the right hardware.
        3. Choose your data source, then fine-tune rules and run the appraisal workflow.
        4. Export results or loop back into Stage 4/5 for review and retraining.
        """,
        help="Quick reference so operators can move from Intake → Review → Training without leaving this tab.",
    )

    # Production model banner (optional)
    try:
        resp = requests.get(f"{API_URL}/v1/training/production_meta", timeout=5)
        if resp.status_code == 200:
            meta = resp.json()
            if meta.get("has_production"):
                ver = (meta.get("meta") or {}).get("version", "1.x")
                src = (meta.get("meta") or {}).get("source", "production")
                st.success(f"🟢 Production model active — version: {ver} • source: {src}")
            else:
                st.warning("⚠️ No production model promoted yet — using baseline.")
        else:
            st.info("ℹ️ Could not fetch production model meta.")
    except Exception:
        st.info("ℹ️ Production meta unavailable.")

    # ─────────────────────────────────────────────
    # 🧩 Model Selection (list all trained models) — Hardcoded Stable Version
    # ─────────────────────────────────────────────
    from datetime import datetime
    import os, shutil, streamlit as st

    # Resolve from the running Streamlit app directory so the page follows the active workspace.
    trained_dir = str(Path("./agents/credit_appraisal/models/trained").resolve())
    production_dir = str(Path("./agents/credit_appraisal/models/production").resolve())

    st.caption(f"📦 Trained dir = `{trained_dir}`")
    st.caption(f"📦 Production dir = `{production_dir}`")

    # ── Refresh models list
    if st.button("↻ Refresh models", key="credit_refresh_models"):
        st.session_state.pop("selected_trained_model", None)
        st.rerun()

    # ── Collect models
    models = []
    if os.path.isdir(trained_dir):
        for f in os.listdir(trained_dir):
            if f.endswith(".joblib"):
                fpath = os.path.join(trained_dir, f)
                ctime = os.path.getctime(fpath)
                created = datetime.fromtimestamp(ctime).strftime("%b %d, %Y %H:%M")
                models.append((f, fpath, created))
    else:
        st.error(f"❌ Trained dir not found: {trained_dir}")

    # ── Show list if found
    if models:
        models.sort(key=lambda x: os.path.getctime(x[1]), reverse=True)
        display_names = [f"{m[0]} — {m[2]}" for m in models]
        preferred_display = st.session_state.get("credit_selected_display")
        default_index = 0
        if preferred_display in display_names:
            default_index = display_names.index(preferred_display)
        elif st.session_state.get("selected_trained_model"):
            selected_path = st.session_state["selected_trained_model"]
            for idx, (_, path, _) in enumerate(models):
                if path == selected_path:
                    default_index = idx
                    break

        selected_display = st.selectbox(
            "📦 Select trained model to use",
            display_names,
            index=default_index,
            key="credit_model_select",
        )
        selected_model = models[display_names.index(selected_display)][1]
        st.success(f"✅ Using model: {os.path.basename(selected_model)}")

        st.session_state["selected_trained_model"] = selected_model
        st.session_state["credit_selected_display"] = selected_display

        # ── Promote model
        if st.button("🚀 Promote this model to Production"):
            try:
                os.makedirs(production_dir, exist_ok=True)
                prod_path = os.path.join(production_dir, "model.joblib")
                shutil.copy2(selected_model, prod_path)
                st.success(f"✅ Model promoted to production: {prod_path}")
            except Exception as e:
                st.error(f"❌ Promotion failed: {e}")
    else:
        st.warning("⚠️ No trained models found — train one in Step 5 first.")

    OPENSTACK_FLAVORS = {
        "m4.medium": "4 vCPU / 8 GB RAM — CPU-only small",
        "m8.large": "8 vCPU / 16 GB RAM — CPU-only medium",
        "g1.a10.1": "8 vCPU / 32 GB RAM + 1×A10 24GB",
        "g1.l40.1": "16 vCPU / 64 GB RAM + 1×L40 48GB",
        "g2.a100.1": "24 vCPU / 128 GB RAM + 1×A100 80GB",
    }

    with st.expander("🧠 Local LLM & Hardware Profile", expanded=True):
        st.info(
            "Use CPU recommended LLMs first for quick narratives. Switch to GPU picks only when you need deeper reasoning or longer context.",
            icon="⚡",
        )
        # Use render_llm_selector if available, otherwise fall back to manual selection
        if render_llm_selector is not None:
            selected_llm = render_llm_selector(context="credit_appraisal")
            st.session_state["credit_llm_model_label"] = selected_llm["model"]
            st.session_state["credit_llm_model"] = selected_llm["value"]
            llm_value = selected_llm["value"]
        else:
            # Fallback: manual LLM selection
            LLM_MODELS = [
                {"label": "💻 CPU Recommended — Phi-3 Mini (3.8B)", "value": "phi3:3.8b", "hint": "CPU 8GB RAM (fast)", "tier": "cpu"},
                {"label": "💻 CPU Recommended — Mistral 7B Instruct", "value": "mistral:7b-instruct",
                 "hint": "CPU 16GB (slow) or GPU ≥8GB", "tier": "balanced"},
                {"label": "💻 CPU Recommended — Gemma-2 7B", "value": "gemma2:7b",
                 "hint": "CPU 16GB (slow) or GPU ≥8GB", "tier": "balanced"},
                {"label": "🧠 GPU Recommended — LLaMA-3 8B", "value": "llama3:8b-instruct",
                 "hint": "GPU ≥12GB (CPU very slow)", "tier": "gpu"},
                {"label": "🧠 GPU Recommended — Qwen2 7B", "value": "qwen2:7b-instruct",
                 "hint": "GPU ≥12GB (CPU very slow)", "tier": "gpu"},
                {"label": "🚀 GPU Heavy — Mixtral 8x7B", "value": "mixtral:8x7b-instruct",
                 "hint": "GPU 24–48GB", "tier": "gpu_large"},
            ]
            possible_sources = ["credit_train_df", "credit_scored_df", "credit_decision_df", "last_merged_df"]
            llm_row_count = None
            for key in possible_sources:
                df_candidate = st.session_state.get(key)
                if isinstance(df_candidate, pd.DataFrame) and not df_candidate.empty:
                    llm_row_count = len(df_candidate)
                    break

            def recommended_llms(row_count: int | None) -> list[str]:
                if row_count is None:
                    return ["💻 CPU Recommended — Mistral 7B Instruct", "💻 CPU Recommended — Gemma-2 7B"]
                if row_count <= 10_000:
                    return ["💻 CPU Recommended — Phi-3 Mini (3.8B)", "💻 CPU Recommended — Mistral 7B Instruct"]
                if row_count <= 40_000:
                    return ["💻 CPU Recommended — Mistral 7B Instruct", "💻 CPU Recommended — Gemma-2 7B"]
                return ["🚀 GPU Heavy — Mixtral 8x7B", "🧠 GPU Recommended — LLaMA-3 8B"]

            rec_labels = recommended_llms(llm_row_count)
            cpu_like = [m for m in LLM_MODELS if m["tier"] in {"cpu", "balanced"}]
            gpu_like = [m for m in LLM_MODELS if m["tier"] in {"gpu", "gpu_large"}]

            ordered_models = []
            seen = set()

            def append_unique(model):
                if model["label"] not in seen:
                    ordered_models.append(model)
                    seen.add(model["label"])

            for label in rec_labels:
                match = next((m for m in LLM_MODELS if m["label"] == label), None)
                if match:
                    append_unique(match)

            for model in cpu_like:
                append_unique(model)
            for model in gpu_like:
                append_unique(model)

            ordered_labels = [m["label"] for m in ordered_models]
            LLM_VALUE_BY_LABEL = {m["label"]: m["value"] for m in ordered_models}
            LLM_HINT_BY_LABEL = {m["label"]: m["hint"] for m in ordered_models}

            saved_llm = st.session_state.get("credit_llm_model_label", ordered_labels[0])
            if saved_llm not in ordered_labels:
                saved_llm = ordered_labels[0]
            model_label = st.selectbox(
                "🔥 Local LLM (used for narratives/explanations)",
                ordered_labels,
                index=ordered_labels.index(saved_llm),
                key="credit_llm_model_label",
                help="Recommended models are pinned to the top of this menu.",
            )
            llm_value = LLM_VALUE_BY_LABEL[model_label]
            st.caption(f"Hint: {LLM_HINT_BY_LABEL[model_label]}")
        
        flavor = st.selectbox(
            "OpenStack flavor / host profile",
            list(OPENSTACK_FLAVORS.keys()),
            index=0,
            key="credit_flavor",
        )
        st.caption(OPENSTACK_FLAVORS[flavor])
        st.caption("These are passed to the API as hints; your API can choose Ollama/Flowise backends accordingly.")

    # 2) Data Source
    data_choice = st.selectbox(
        "Select Data Source",
        [
            "Use synthetic (ANON)",
            "Use synthetic (RAW – auto-sanitize)",
            "Use anonymized dataset",
            "Upload manually",
        ],
    )
    # Stash the LLM toggle + default selection for downstream payload
    use_llm = st.checkbox("Use LLM narrative", value=False)
    if "credit_llm_model" not in st.session_state:
        st.session_state["credit_llm_model"] = llm_value if "llm_value" in locals() else None
    llm_value = st.session_state.get("credit_llm_model", llm_value if "llm_value" in locals() else None)
    agent_name = "credit_appraisal"

    if data_choice == "Upload manually":
        up = st.file_uploader("Upload your CSV", type=["csv"], key="manual_upload_run_file")
        if up is not None:
            st.session_state["manual_upload_name"] = up.name
            st.session_state["manual_upload_bytes"] = up.getvalue()
            st.success(f"File staged: {up.name} ({len(st.session_state['manual_upload_bytes'])} bytes)")

    # 3) Rules
    st.markdown("### ⚙️ Decision Rule Set")
    rule_mode = st.radio(
        "Choose rule mode",
        ["Classic (bank-style metrics)", "NDI (Net Disposable Income) — simple"],
        index=0,
        help="NDI = income - all monthly obligations. Approve if NDI and NDI ratio pass thresholds.",
    )

    CLASSIC_DEFAULTS = {
        "max_dti": 0.45,
        "min_emp_years": 2,
        "min_credit_hist": 3,
        "salary_floor": 3000,
        "max_delinquencies": 2,
        "max_current_loans": 3,
        "req_min": 1000,
        "req_max": 200000,
        "loan_terms": [12, 24, 36, 48, 60],
        "threshold": 0.45,
        "target_rate": None,
        "random_band": True,
        "min_income_debt_ratio": 0.35,
        "compounded_debt_factor": 1.0,
        "monthly_debt_relief": 0.50,
    }
    NDI_DEFAULTS = {"ndi_value": 800.0, "ndi_ratio": 0.50, "threshold": 0.45, "target_rate": None, "random_band": True}

    if "classic_rules" not in st.session_state:
        st.session_state.classic_rules = CLASSIC_DEFAULTS.copy()
    if "ndi_rules" not in st.session_state:
        st.session_state.ndi_rules = NDI_DEFAULTS.copy()

    def reset_classic(): st.session_state.classic_rules = CLASSIC_DEFAULTS.copy()
    def reset_ndi():     st.session_state.ndi_rules = NDI_DEFAULTS.copy()

    if rule_mode.startswith("Classic"):
        with st.expander("Classic Metrics (with Reset)", expanded=True):
            rc = st.session_state.classic_rules
            r1, r2, r3 = st.columns(3)
            with r1:
                rc["max_dti"] = st.slider("Max Debt-to-Income (DTI)", 0.0, 1.0, rc["max_dti"], 0.01)
                rc["min_emp_years"] = st.number_input("Min Employment Years", 0, 40, rc["min_emp_years"])
                rc["min_credit_hist"] = st.number_input("Min Credit History (years)", 0, 40, rc["min_credit_hist"])
            with r2:
                rc["salary_floor"] = st.number_input(
                    "Minimum Monthly Salary", 0, 1_000_000_000, rc["salary_floor"], step=1000, help=fmt_currency_label("in local currency")
                )
                rc["max_delinquencies"] = st.number_input("Max Delinquencies", 0, 10, rc["max_delinquencies"])
                rc["max_current_loans"] = st.number_input("Max Current Loans", 0, 10, rc["max_current_loans"])
            with r3:
                rc["req_min"] = st.number_input(fmt_currency_label("Requested Amount Min"), 0, 10_000_000_000, rc["req_min"], step=1000)
                rc["req_max"] = st.number_input(fmt_currency_label("Requested Amount Max"), 0, 10_000_000_000, rc["req_max"], step=1000)
                rc["loan_terms"] = st.multiselect("Allowed Loan Terms (months)", [12, 24, 36, 48, 60, 72], default=rc["loan_terms"])

            st.markdown("#### 🧮 Debt Pressure Controls")
            d1, d2, d3 = st.columns(3)
            with d1:
                rc["min_income_debt_ratio"] = st.slider(
                    "Min Income / (Compounded Debt) Ratio", 0.10, 2.00, rc["min_income_debt_ratio"], 0.01
                )
            with d2:
                rc["compounded_debt_factor"] = st.slider(
                    "Compounded Debt Factor (× requested)", 0.5, 3.0, rc["compounded_debt_factor"], 0.1
                )
            with d3:
                rc["monthly_debt_relief"] = st.slider("Monthly Debt Relief Factor", 0.10, 1.00, rc["monthly_debt_relief"], 0.05)

            st.markdown("---")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                use_target = st.toggle("🎯 Use target approval rate", value=(rc["target_rate"] is not None))
            with c2:
                rc["random_band"] = st.toggle(
                    "🎲 Randomize approval band (20–60%) when no target", value=rc["random_band"]
                )
            with c3:
                if st.button("↩️ Reset to defaults"):
                    reset_classic()
                    st.rerun()

            if use_target:
                rc["target_rate"] = st.slider("Target approval rate", 0.05, 0.95, rc["target_rate"] or 0.40, 0.01)
                rc["threshold"] = None
            else:
                rc["threshold"] = st.slider("Model score threshold", 0.0, 1.0, rc["threshold"], 0.01)
                rc["target_rate"] = None
    else:
        with st.expander("NDI Metrics (with Reset)", expanded=True):
            rn = st.session_state.ndi_rules
            n1, n2 = st.columns(2)
            with n1:
                rn["ndi_value"] = st.number_input(
                    fmt_currency_label("Min NDI (Net Disposable Income) per month"),
                    0.0,
                    1e12,
                    float(rn["ndi_value"]),
                    step=50.0,
                )
            with n2:
                rn["ndi_ratio"] = st.slider("Min NDI / Income ratio", 0.0, 1.0, float(rn["ndi_ratio"]), 0.01)
            st.caption("NDI = income - all monthly obligations (rent, food, loans, cards, etc.).")

            st.markdown("---")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                use_target = st.toggle("🎯 Use target approval rate", value=(rn["target_rate"] is not None))
            with c2:
                rn["random_band"] = st.toggle(
                    "🎲 Randomize approval band (20–60%) when no target", value=rn["random_band"]
                )
            with c3:
                if st.button("↩️ Reset to defaults (NDI)"):
                    reset_ndi()
                    st.rerun()

            if use_target:
                rn["target_rate"] = st.slider("Target approval rate", 0.05, 0.95, rn["target_rate"] or 0.40, 0.01)
                rn["threshold"] = None
            else:
                rn["threshold"] = st.slider("Model score threshold", 0.0, 1.0, rn["threshold"], 0.01)
                rn["target_rate"] = None

    # Helper used below (your function name later referenced as json_to_dataframe in the draft)
    def json_to_df(obj) -> pd.DataFrame:
        if obj is None:
            return pd.DataFrame()
        if isinstance(obj, pd.DataFrame):
            return obj
        if isinstance(obj, bytes):
            try:
                obj = obj.decode("utf-8", errors="ignore")
            except Exception:
                return pd.DataFrame({"value": [repr(obj)]})
        if isinstance(obj, str):
            obj = obj.strip()
            if not obj:
                return pd.DataFrame()
            try:
                j = json.loads(obj)
                return json_to_df(j)
            except Exception:
                lines = [ln for ln in obj.splitlines() if ln.strip()]
                return pd.DataFrame({"value": lines}) if lines else pd.DataFrame()
        if isinstance(obj, list):
            if len(obj) == 0:
                return pd.DataFrame()
            if all(isinstance(x, dict) for x in obj):
                try:
                    return pd.json_normalize(obj)
                except Exception:
                    return pd.DataFrame(obj)
            if all(isinstance(x, list) for x in obj):
                return pd.DataFrame({"row": obj})
            return pd.DataFrame({"value": obj})
        if isinstance(obj, dict):
            for key in ("rows", "data", "result", "results", "items", "records"):
                if key in obj and isinstance(obj[key], (list, dict)):
                    return json_to_df(obj[key])
            try:
                return pd.json_normalize(obj)
            except Exception:
                return pd.DataFrame([obj])
        return pd.DataFrame({"value": [obj]})

    # 4) Run
    if st.button("🚀 Run Agent", use_container_width=True):
        try:
            files = None
            data: Dict[str, Any] = {
                "use_llm_narrative": str(use_llm).lower(),
                "llm_model": llm_value,
                "hardware_flavor": flavor,
                "currency_code": st.session_state["currency_code"],
                "currency_symbol": st.session_state["currency_symbol"],
            }
            if rule_mode.startswith("Classic"):
                rc = st.session_state.classic_rules
                data.update(
                    {
                        "min_employment_years": str(rc["min_emp_years"]),
                        "max_debt_to_income": str(rc["max_dti"]),
                        "min_credit_history_length": str(rc["min_credit_hist"]),
                        "max_num_delinquencies": str(rc["max_delinquencies"]),
                        "max_current_loans": str(rc["max_current_loans"]),
                        "requested_amount_min": str(rc["req_min"]),
                        "requested_amount_max": str(rc["req_max"]),
                        "loan_term_months_allowed": ",".join(map(str, rc["loan_terms"])) if rc["loan_terms"] else "",
                        "min_income_debt_ratio": str(rc["min_income_debt_ratio"]),
                        "compounded_debt_factor": str(rc["compounded_debt_factor"]),
                        "monthly_debt_relief": str(rc["monthly_debt_relief"]),
                        "salary_floor": str(rc["salary_floor"]),
                        "threshold": "" if rc["threshold"] is None else str(rc["threshold"]),
                        "target_approval_rate": "" if rc["target_rate"] is None else str(rc["target_rate"]),
                        "random_band": str(rc["random_band"]).lower(),
                        "random_approval_band": str(rc["random_band"]).lower(),
                        "rule_mode": "classic",
                    }
                )
            else:
                rn = st.session_state.ndi_rules
                data.update(
                    {
                        "ndi_value": str(rn["ndi_value"]),
                        "ndi_ratio": str(rn["ndi_ratio"]),
                        "threshold": "" if rn["threshold"] is None else str(rn["threshold"]),
                        "target_approval_rate": "" if rn["target_rate"] is None else str(rn["target_rate"]),
                        "random_band": str(rn["random_band"]).lower(),
                        "random_approval_band": str(rn["random_band"]).lower(),
                        "rule_mode": "ndi",
                    }
                )

            def prep_and_pack(df: pd.DataFrame, filename: str):
                safe = dedupe_columns(df)
                safe, _ = drop_pii_columns(safe)
                safe = strip_policy_banned(safe)
                safe = to_agent_schema(safe)
                buf = io.StringIO()
                safe.to_csv(buf, index=False)
                return {"file": (filename, buf.getvalue().encode("utf-8"), "text/csv")}

            if data_choice == "Use synthetic (ANON)":
                if "synthetic_df" not in st.session_state:
                    st.warning("No ANON synthetic dataset found. Generate it in the first tab.")
                    st.stop()
                files = prep_and_pack(st.session_state.synthetic_df, "synthetic_anon.csv")

            elif data_choice == "Use synthetic (RAW – auto-sanitize)":
                if "synthetic_raw_df" not in st.session_state:
                    st.warning("No RAW synthetic dataset found. Generate it in the first tab.")
                    st.stop()
                files = prep_and_pack(st.session_state.synthetic_raw_df, "synthetic_raw_sanitized.csv")

            elif data_choice == "Use anonymized dataset":
                if "anonymized_df" not in st.session_state:
                    st.warning("No anonymized dataset found. Create it in the second tab.")
                    st.stop()
                files = prep_and_pack(st.session_state.anonymized_df, "anonymized.csv")

            elif data_choice == "Upload manually":
                up_name = st.session_state.get("manual_upload_name")
                up_bytes = st.session_state.get("manual_upload_bytes")
                if not up_name or not up_bytes:
                    st.warning("Please upload a CSV first.")
                    st.stop()
                try:
                    tmp_df = pd.read_csv(io.BytesIO(up_bytes))
                    files = prep_and_pack(tmp_df, up_name)
                except Exception:
                    files = {"file": (up_name, up_bytes, "text/csv")}
            else:
                st.error("Unknown data source selection.")
                st.stop()

            # ---- RUN REQUEST ----
            try:
                r = requests.post(
                    f"{API_URL}/v1/agents/{agent_name}/run",
                    data=data,
                    files=files,
                    timeout=180,
                )
            except requests.exceptions.RequestException as exc:
                st.error(
                    f"❌ Could not reach the agent API at {API_URL}. "
                    "Make sure the backend service is running (port 8090) and try again."
                )
                st.caption(f"Details: {exc}")
                st.stop()

            if r.status_code != 200:
                st.error(f"Run failed ({r.status_code}): {r.text}")
                st.stop()

            res = r.json()
            _ping_chatbot_refresh("credit_run")

            # ---- Robust run_id + data extraction ----
            run_id = None
            payload_rows = None  # fallback rows for rendering

            if isinstance(res, dict):
                run_id = res.get("run_id") or res.get("id")
                payload_rows = res.get("result") or res.get("data") or res.get("results") or res.get("rows")
            elif isinstance(res, list):
                payload_rows = res
            else:
                try:
                    maybe = json.loads(res)
                    if isinstance(maybe, dict):
                        run_id = maybe.get("run_id") or maybe.get("id")
                        payload_rows = maybe.get("result") or maybe.get("data") or maybe.get("results") or maybe.get("rows")
                    elif isinstance(maybe, list):
                        payload_rows = maybe
                except Exception:
                    pass

            # ---- Helper: turn any JSON-like into a DataFrame ----
            def json_to_df(obj) -> pd.DataFrame:
                if obj is None:
                    return pd.DataFrame()
                if isinstance(obj, pd.DataFrame):
                    return obj
                if isinstance(obj, bytes):
                    try:
                        obj = obj.decode("utf-8", errors="ignore")
                    except Exception:
                        return pd.DataFrame({"value": [repr(obj)]})
                if isinstance(obj, str):
                    obj = obj.strip()
                    if not obj:
                        return pd.DataFrame()
                    try:
                        j = json.loads(obj)
                        return json_to_df(j)
                    except Exception:
                        lines = [ln for ln in obj.splitlines() if ln.strip()]
                        return pd.DataFrame({"value": lines}) if lines else pd.DataFrame()
                if isinstance(obj, list):
                    if len(obj) == 0:
                        return pd.DataFrame()
                    if all(isinstance(x, dict) for x in obj):
                        try:
                            return pd.json_normalize(obj)
                        except Exception:
                            return pd.DataFrame(obj)
                    if all(isinstance(x, list) for x in obj):
                        return pd.DataFrame({"row": obj})
                    return pd.DataFrame({"value": obj})
                if isinstance(obj, dict):
                    for key in ("rows", "data", "result", "results", "items", "records"):
                        if key in obj and isinstance(obj[key], (list, dict)):
                            return json_to_df(obj[key])
                    try:
                        return pd.json_normalize(obj)
                    except Exception:
                        return pd.DataFrame([obj])
                return pd.DataFrame({"value": [obj]})

            # ---- Prefer server report via run_id; otherwise fall back to local JSON→DF ----
            
            # ============================================================
            # ✅ Prefer server CSV → fallback to JSON Parser
            # ============================================================
            if run_id:
                try:
                    rid = run_id
                    merged_url = f"{API_URL}/v1/runs/{rid}/report?format=csv"
                    merged_bytes = requests.get(merged_url, timeout=30).content
                    merged_df = pd.read_csv(io.BytesIO(merged_bytes))
                    st.session_state.last_run_id = rid
                    st.success(f"✅ Run succeeded! Run ID: {rid}")
                except Exception as e:
                    st.warning(f"Could not fetch CSV via run_id ({run_id}): {e}")
                    merged_df = json_to_dataframe(payload_rows)
            else:
                st.warning("⚠️ Backend did not return a run_id. Falling back to JSON.")
                merged_df = json_to_dataframe(payload_rows)

 

            if merged_df is None or merged_df.empty:
                st.error("No data available to render (both report and fallback JSON were empty).")
                st.write("Raw response:", res)
                st.stop()

            # Keep for later tabs
            st.session_state["last_merged_df"] = dedupe_columns(merged_df)
            
            # ✅ Make results available to Stage 7 (Reporting & Handoff)
            try:
                st.session_state["credit_scored_df"] = dedupe_columns(merged_df.copy())
                st.success("✅ Stage C outputs saved for Stage 7 (Reporting & Handoff).")
            except Exception as e:
                st.warning(f"Could not persist scored dataset for Stage 7: {e}")

            # ---- Decisions Table (with filter) ----
            st.markdown("### 📄 Credit AI Agent Decisions Table (filtered)")
            uniq_dec = sorted([d for d in merged_df.get("decision", pd.Series(dtype=str)).dropna().unique()]) \
                    if "decision" in merged_df.columns else []
            chosen = st.multiselect("Filter decision", options=uniq_dec, default=uniq_dec, key="filter_decisions")
            df_view = merged_df.copy()
            if "decision" in df_view.columns and chosen:
                df_view = df_view[df_view["decision"].isin(chosen)]
            st.dataframe(df_view, use_container_width=True)

            # ---- Dashboard ----
            st.markdown("## 📊 Dashboard")
            render_credit_dashboard(merged_df, st.session_state.get("currency_symbol", ""))
            
            # Auto-show dashboard if demo data was loaded
            if st.session_state.get("credit_demo_loaded") and st.session_state.get("last_merged_df") is not None:
                st.info("💡 Demo data loaded automatically. Dashboard shows results from auto-run.")

            # Add per-row metrics columns if present
            if "rule_reasons" in df_view.columns:
                rr = df_view["rule_reasons"].apply(try_json)
                df_view["metrics_met"] = rr.apply(lambda d: ", ".join(sorted([k for k, v in (d or {}).items() if v is True])) if isinstance(d, dict) else "")
                df_view["metrics_unmet"] = rr.apply(lambda d: ", ".join(sorted([k for k, v in (d or {}).items() if v is False])) if isinstance(d, dict) else "")

            cols_show = [c for c in [
                "application_id","customer_type","decision","score","loan_amount","income","metrics_met","metrics_unmet",
                "proposed_loan_option","proposed_consolidation_loan","top_feature","explanation"
            ] if c in df_view.columns]
            if cols_show:
                st.dataframe(df_view[cols_show].head(500), use_container_width=True)

            # ---- Download button (keep your large button style) ----
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            out_name = f"ai-appraisal-outputs-{ts}-{st.session_state['currency_code']}.csv"
            csv_data = merged_df.to_csv(index=False).encode("utf-8")

            st.markdown("""
            <style>
            div[data-testid="stDownloadButton"] button {
                font-size: 90px !important;
                font-weight: 900 !important;
                padding: 28px 48px !important;
                border-radius: 16px !important;
                background: linear-gradient(90deg, #2563eb, #1d4ed8) !important;
                color: white !important;
                border: none !important;
                box-shadow: 0 6px 18px rgba(0,0,0,0.35) !important;
                transition: all 0.3s ease-in-out !important;
            }
            div[data-testid="stDownloadButton"] button:hover {
                background: linear-gradient(90deg, #1e3a8a, #1d4ed8) !important;
                transform: scale(1.03);
            }
            </style>
            """, unsafe_allow_html=True)

            st.download_button(
                "⬇️ Download AI Outputs For Human Review (CSV)",
                csv_data,
                file_name=out_name,
                mime="text/csv",
                use_container_width=True
            )
            
            # ✅ CREATE TRAINING LABEL (Stage C → Stage F)
            train_df = merged_df.copy()

            # 1) Default probability → binary label
            if "default_probability" in train_df.columns:
                train_df["label"] = (train_df["default_probability"] >= 0.5).astype(int)

            # 2) Fallback: use score column if exists
            elif "score" in train_df.columns:
                train_df["label"] = (train_df["score"] >= 0.5).astype(int)

            # 3) Final fallback to avoid Stage F crash
            else:
                train_df["label"] = 0

            # ✅ SAVE FOR TRAINING PIPELINE
            try:
                st.session_state["credit_train_df"] = train_df.copy()
                st.success("✅ Stage C dataset prepared and saved for Stage F (training).")
            except Exception as e:
                st.error(f"Could not save training dataset for Stage F: {e}")

            
            # ✅ SAVE OUTPUT FOR STAGE F (Training)
            try:
                #st.session_state["credit_train_df"] = scored_df.copy()
                st.session_state["credit_train_df"] = merged_df.copy()

                st.success("✅ Stage C output saved for Stage F (training).")
            except Exception as e:
                st.error(f"Could not save Stage C dataset for training: {e}")

        except Exception as e:
            st.exception(e)

    # Re-download quick section
    if st.session_state.get("last_run_id"):
        st.markdown("---")
        st.subheader("📥 Download Latest Outputs")
        rid = st.session_state.last_run_id
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.markdown(f"[⬇️ PDF]({API_URL}/v1/runs/{rid}/report?format=pdf)")
        with col2: st.markdown(f"[⬇️ Scores CSV]({API_URL}/v1/runs/{rid}/report?format=scores_csv)")
        with col3: st.markdown(f"[⬇️ Explanations CSV]({API_URL}/v1/runs/{rid}/report?format=explanations_csv)")
        with col4: st.markdown(f"[⬇️ Merged CSV]({API_URL}/v1/runs/{rid}/report?format=csv)")
        with col5: st.markdown(f"[⬇️ JSON]({API_URL}/v1/runs/{rid}/report?format=json)")


# ─────────────────────────────────────────────
# 🧑‍⚖️ TAB 4 — Human Review
with tab_review:
    st.subheader("🧑‍⚖️ Human Review — Correct AI Decisions & Score Agreement > Drop your AI appraisal output CSV from previous Stage  below")

    # Allow loading AI output CSV back into review via dropdown upload
    uploaded_review = st.file_uploader("Load AI outputs CSV for review (optional)", type=["csv"], key="review_csv_loader")
    if uploaded_review is not None:
        try:
            st.session_state["last_merged_df"] = pd.read_csv(uploaded_review)
            st.success("Loaded review dataset from uploaded CSV.")
        except Exception as e:
            st.error(f"Could not read uploaded CSV: {e}")

    if "last_merged_df" not in st.session_state:
        st.info("Run the agent (previous tab) or upload an AI outputs CSV to load results for review.")
    else:
        dfm = st.session_state["last_merged_df"].copy()
        st.markdown("#### 1) Select rows to review and correct")

        editable_cols = []
        if "decision" in dfm.columns: editable_cols.append("decision")
        if "rule_reasons" in dfm.columns: editable_cols.append("rule_reasons")
        if "customer_type" in dfm.columns: editable_cols.append("customer_type")

        editable = dfm[["application_id"] + editable_cols].copy()
        editable.rename(columns={"decision": "ai_decision"}, inplace=True)
        editable["human_decision"] = editable.get("ai_decision", "approved")
        editable["human_rule_reasons"] = editable.get("rule_reasons", "")

        # ────────────────────────────────
        # LIGHTER EDITABLE CELL STYLING (improved)
        # ────────────────────────────────
        st.markdown("""
            <style>
            /* Bright background for editable cells */
            [data-testid="stDataFrameCellEditable"] textarea {
                background-color: #fefefe !important;   /* bright white background */
                color: #111 !important;                 /* dark text */
                border: 1px solid #cbd5e1 !important;   /* subtle gray border */
                border-radius: 6px !important;
                padding: 6px 8px !important;
                font-weight: 500 !important;
            }

            /* Hover and focus effect */
            [data-testid="stDataFrameCellEditable"]:focus-within textarea,
            [data-testid="stDataFrameCellEditable"]:hover textarea {
                background-color: #ffffff !important;
                border-color: #22c55e !important;        /* green glow */
                box-shadow: 0 0 0 2px rgba(34,197,94,0.4) !important;
            }

            /* Read-only cells: keep dark */
            [data-testid="stDataFrameCell"] {
                background-color: #1e293b !important;
                color: #e2e8f0 !important;
            }
            </style>
        """, unsafe_allow_html=True)


        # ────────────────────────────────
        # EDITOR
        # ────────────────────────────────

        edited = st.data_editor(
            editable,
            num_rows="dynamic",
            use_container_width=True,
            key="review_editor",
            column_config={
                "human_decision": st.column_config.SelectboxColumn(options=["approved", "denied"]),
                "customer_type": st.column_config.SelectboxColumn(options=["bank", "non-bank"], disabled=True)
            }
        )

        st.markdown("#### 2) Compute agreement score")

        if st.button("Compute agreement score"):
            if "ai_decision" in edited.columns and "human_decision" in edited.columns:
                agree = (edited["ai_decision"] == edited["human_decision"]).astype(int)
                score = float(agree.mean()) if len(agree) else 0.0
                st.session_state["last_agreement_score"] = score

                # 🌡️ BEAUTIFUL Gauge
                import plotly.graph_objects as go
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score * 100,
                    number={'suffix': "%", 'font': {'size': 72, 'color': "#f8fafc", 'family': "Arial Black"}},
                    title={'text': "AI ↔ Human Agreement", 'font': {'size': 28, 'color': "#93c5fd", 'family': "Arial"}},
                    gauge={
                        'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "#f8fafc"},
                        'bar': {'color': "#3b82f6", 'thickness': 0.3},
                        'bgcolor': "#1e293b",
                        'borderwidth': 2,
                        'bordercolor': "#334155",
                        'steps': [
                            {'range': [0, 50], 'color': "#ef4444"},
                            {'range': [50, 75], 'color': "#f59e0b"},
                            {'range': [75, 100], 'color': "#22c55e"},
                        ],
                    }
                ))
                fig.update_layout(
                    paper_bgcolor="#0f172a",
                    plot_bgcolor="#0f172a",
                    height=400,
                    margin=dict(t=60, b=20, l=60, r=60)
                )
                st.plotly_chart(fig, use_container_width=True)



            # 💡 Detailed disagreement table (AI vs Human + AI metrics explanation)
                mismatched = edited[edited["ai_decision"] != edited["human_decision"]].copy()
                total = len(edited)
                disagree = len(mismatched)

                if disagree > 0:
                    st.markdown(f"### ❌ {disagree} loans disagreed out of {total} ({(disagree/total)*100:.1f}% disagreement rate)")

                    import json

                    def parse_ai_reason(r: str):
                        """Parse AI rule_reasons and summarize which metrics passed or failed."""
                        if not isinstance(r, str):
                            return "No metrics available"
                        try:
                            data = json.loads(r.replace("'", "\""))
                            passed = [k for k, v in data.items() if v is True]
                            failed = [k for k, v in data.items() if v is False]
                            result = []
                            if passed:
                                result.append("✅ Pass: " + ", ".join(passed))
                            if failed:
                                result.append("❌ Fail: " + ", ".join(failed))
                            return " | ".join(result) if result else "No metrics recorded"
                        except Exception:
                            return "Unreadable metrics"

                    # Extract AI reasoning and Human reason columns
                    mismatched["ai_metrics"] = mismatched["rule_reasons"].apply(parse_ai_reason) if "rule_reasons" in mismatched else "No data"
                    mismatched["human_reason"] = mismatched.get("human_rule_reasons", "Manual review adjustment")

                    # 🟩🟥 Color styling for AI vs Human
                    def highlight_disagreement(row):
                        ai_color = "background-color: #ef4444; color: white;"      # red for AI decision
                        human_color = "background-color: #22c55e; color: black;"   # green for Human decision
                        return [
                            ai_color if col == "ai_decision" else
                            human_color if col == "human_decision" else
                            ""
                            for col in row.index
                        ]

                    # Columns: ID → AI Decision → Human Decision → AI Metrics → Human Reason
                    show_cols = [
                        c for c in ["application_id", "ai_decision", "human_decision", "ai_metrics", "human_reason"]
                        if c in mismatched.columns
                    ]
                    styled_df = mismatched[show_cols].style.apply(highlight_disagreement, axis=1)
                    st.dataframe(styled_df, use_container_width=True, height=420)
                else:
                    st.success("✅ Full agreement — no human-AI mismatches found.")



        # Export review CSV (manual loop into training)
        st.markdown("#### 3) Export Human review CSV for Next Step : Training and loopback ")
        model_used = "production"  # if you track specific model names, set it here
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        safe_user = st.session_state["user_info"]["name"].replace(" ", "").lower()
        review_name = f"creditappraisal.{safe_user}.{model_used}.{ts}.csv"
        csv_bytes = edited.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export review CSV", csv_bytes, review_name, "text/csv")
        st.caption(f"Saved file name pattern: **{review_name}**")


# -------------------------------------------------------------
# ✅ STAGE 5 — Credit Model Training (Executive Dashboard)
# -------------------------------------------------------------
with tab_train:
    import os, json, glob, shutil, zipfile
    from datetime import datetime, timezone
    from pathlib import Path
    import numpy as np
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        roc_auc_score, accuracy_score, precision_score, 
        recall_score, f1_score, confusion_matrix
    )

    import joblib
    import streamlit as st

    # ---------------------------------------------------------
    # ✅ HEADER
    # ---------------------------------------------------------
    st.markdown("""
    <h2>🧠 Stage 5 — Credit Model Training</h2>
    <p style='font-size:1.1rem'>
    Train → Compare → Evaluate → Promote<br>
    Build a robust, regulator-friendly credit scoring model.
    </p>
    """, unsafe_allow_html=True)

    # ---------------------------------------------------------
    # ✅ LOAD TRAINING DATA (from Stage C)
    # ---------------------------------------------------------
    train_df = st.session_state.get("credit_train_df")

    if train_df is None or train_df.empty:
        st.error("⚠️ Missing training dataset. Please run Stage C first.")
        st.stop()

    st.success(f"✅ Training dataset detected with {len(train_df):,} rows.")
    st.dataframe(train_df.head(), use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------
    # ✅ TRAINING DATA LOADING (Human feedback OR CSV upload)
    # ---------------------------------------------------------
    st.markdown("### 📥 Stage 5 Training Data Input")

    train_df = None
    source_label = None

    # ✅ Option A — Human Review Stage output is available
    if "credit_human_review_df" in st.session_state:
        df_human = st.session_state.get("credit_human_review_df")
        if isinstance(df_human, pd.DataFrame) and not df_human.empty:
            train_df = df_human.copy()
            source_label = "Human Review Stage (Session State)"

    # ✅ Option B — Model Inference Stage C merged_df output (fallback)
    elif "credit_train_df" in st.session_state:
        df_auto = st.session_state.get("credit_train_df")
        if isinstance(df_auto, pd.DataFrame) and not df_auto.empty:
            train_df = df_auto.copy()
            source_label = "Stage C auto-saved dataset"

    
    # ✅ Option C — User uploads CSV manually
    uploaded = st.file_uploader("Upload training CSV (optional)", type=["csv"])

    if uploaded is not None:
        try:
            train_df = pd.read_csv(uploaded)
            source_label = f"Uploaded CSV ({len(train_df)} rows)"
        except Exception as e:
            st.error(f"❌ Could not read uploaded CSV: {e}")

    # ✅ Hard stop if no dataset is available
    if train_df is None or train_df.empty:
        st.error("""
        ❌ No training data found.

        ✅ Provide training dataset by:
        • Completing Human Review Stage (Stage D)  
        • OR uploading a CSV here  
        • OR enabling Stage C to save merged output  
        """)
        st.stop()
    


    # ✅ Show dataset preview + source
    st.success(f"✅ Training dataset loaded from: **{source_label}**")
    st.dataframe(train_df.head(), use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------
    # ✅ MODEL SELECTION
    # ---------------------------------------------------------
    dataset_rows = len(train_df)
    feature_count = len(train_df.columns)
    numeric_cols = len(train_df.select_dtypes(include=["number"]).columns)

    def score_model(name: str) -> tuple[int, str]:
        """
        Returns (score, reason) for the recommended-model cards.
        Score is a simple heuristic driven by dataset size + feature mix.
        """
        reason = ""
        score = 0

        if name == "LogisticRegression":
            score = 3 if dataset_rows <= 10_000 else 1
            reason = "Best for <10k rows when regulators want fully explainable coefficients."
        elif name == "RandomForest":
            score = 4 if 10_000 < dataset_rows <= 60_000 else 2
            reason = "Solid all-rounder for midsize datasets with mixed feature types."
        elif name == "LightGBM":
            score = 5 if dataset_rows > 40_000 else 3
            reason = "Handles wide, imbalanced credit files efficiently — ideal for production retrains."
        elif name == "XGBoost":
            score = 4 if dataset_rows > 80_000 else 2
            reason = "Max accuracy when you can afford longer training time and need granular splits."

        # Small boost if we detected many numeric columns (helps tree boosters)
        if name in {"LightGBM", "XGBoost", "RandomForest"} and numeric_cols > feature_count * 0.6:
            score += 1
            reason += " Abundant numeric features favour boosted trees."

        return score, reason

    # Check which models are available
    available_models = ["RandomForest", "LogisticRegression"]  # Always available
    try:
        import lightgbm
        available_models.append("LightGBM")
    except ImportError:
        pass
    try:
        import xgboost
        available_models.append("XGBoost")
    except ImportError:
        pass
    
    model_profiles = []
    for candidate in ["LightGBM", "RandomForest", "LogisticRegression", "XGBoost"]:
        # Skip if model is not available
        if candidate not in available_models:
            continue
        score, reason = score_model(candidate)
        model_profiles.append(
            {
                "name": candidate,
                "score": score,
                "tagline": {
                    "LightGBM": "Enterprise-ready EQACh default",
                    "RandomForest": "Balanced accuracy + speed",
                    "LogisticRegression": "Audit-friendly baseline",
                    "XGBoost": "Max depth / max lift",
                }[candidate],
                "reason": reason,
            }
        )

    model_profiles.sort(key=lambda x: x["score"], reverse=True)
    top_profiles = model_profiles[:3]

    st.markdown("#### ⭐ Recommended models (EQACh signal)")
    st.caption(f"Based on {dataset_rows:,} rows · {feature_count} features · {numeric_cols} numeric")

    rec_cols = st.columns(len(top_profiles))
    for col, profile in zip(rec_cols, top_profiles):
        with col:
            st.markdown(f"**{profile['name']}**")
            st.caption(profile["tagline"])
            st.write(profile["reason"])
            if st.button(f"Use {profile['name']}", key=f"use_{profile['name']}"):
                st.session_state["credit_model_choice"] = profile["name"]

    st.subheader("🤖 Choose training model")

    # Filter model options to only include available models
    model_options = [m["name"] for m in model_profiles]  # Only show available models
    if not model_options:
        st.error("❌ No models available. Please install at least one ML library (scikit-learn is required).")
        st.stop()
    
    # Get recommended model from presets
    def _get_recommended_tabular_model(agent_context: str) -> str | None:
        """Get recommended tabular model for agent context."""
        try:
            import yaml
            from pathlib import Path
            config_path = Path(__file__).resolve().parents[3] / "config" / "agent_model_presets.yaml"
            if config_path.exists():
                with open(config_path, "r") as f:
                    presets = yaml.safe_load(f)
                    if presets and "tabular_models" in presets:
                        agent_config = presets["tabular_models"].get(agent_context)
                        if agent_config:
                            primary = agent_config.get("primary")
                            if primary and primary in available_models:
                                return primary
                            fallback = agent_config.get("fallback")
                            if fallback and fallback in available_models:
                                return fallback
        except Exception:
            pass
        return None
    
    recommended_model = _get_recommended_tabular_model("credit_appraisal")
    
    default_choice = st.session_state.get("credit_model_choice")
    if not default_choice or default_choice not in model_options:
        # Priority: recommended > first available
        if recommended_model and recommended_model in model_options:
            default_choice = recommended_model
            st.session_state["credit_model_choice"] = recommended_model
            st.info(f"✅ **Recommended for credit appraisal**: {recommended_model} (auto-selected)", icon="⭐")
        else:
            default_choice = model_options[0]  # Use first available model

    model_choice = st.selectbox(
        "Select model:",
        model_options,
        index=model_options.index(default_choice) if default_choice in model_options else 0
    )
    
    # Show info if LightGBM/XGBoost are not available
    missing_models = []
    if "LightGBM" not in available_models:
        missing_models.append("LightGBM")
    if "XGBoost" not in available_models:
        missing_models.append("XGBoost")
    
    if missing_models:
        with st.expander("💡 Install additional models (optional)", expanded=False):
            install_commands = []
            if "LightGBM" in missing_models:
                install_commands.append("`pip install lightgbm`")
            if "XGBoost" in missing_models:
                install_commands.append("`pip install xgboost`")
            st.info(
                f"To use {', '.join(missing_models)}, install them with: {', '.join(install_commands)}. "
                f"Current options ({', '.join(model_options)}) are sufficient for training."
            )
    st.session_state["credit_model_choice"] = model_choice

    # ---------------------------------------------------------
    # ✅ Smart Target Auto-Detection (BEFORE training)
    # ---------------------------------------------------------
    def detect_best_target(df):
        """
        Smart target auto-detection for credit scoring.
        Priority:
        1) AI numeric scores
        2) human decisions
        3) any suitable numeric predictive column
        """

        score_candidates = [
            "score", "default_probability", "risk_score",
            "pd", "probability_default"
        ]

        # ✅ 1. Direct AI numeric score column
        for col in score_candidates:
            if col in df.columns:
                return col, "numeric_score"

        # ✅ 2. Human decision labels
        decision_candidates = ["human_decision", "final_decision", "decision"]

        for col in decision_candidates:
            if col in df.columns:
                vals = df[col].dropna().astype(str).str.lower().unique()
                if any(v in ["approved", "rejected"] for v in vals):
                    return col, "decision_label"

        # ✅ 3. Numeric fallback
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

        # exclude leakage columns
        blacklist = ["loan_amount", "requested_amount", "income", "assets_owned"]
        numeric_cols = [c for c in numeric_cols if c not in blacklist]

        if numeric_cols:
            return numeric_cols[0], "numeric_fallback"

        return None, "none"


    # ---------------------------------------------------------
    # ✅ TRAINING LOGIC
    # ---------------------------------------------------------
    if st.button("🚀 Train Credit Model Now"):
        with st.spinner("Training model…"):

            # ✅ Smart Target Detection
            TARGET_COL, target_mode = detect_best_target(train_df)

            if TARGET_COL is None:
                st.error("❌ No suitable target column found in dataset.")
                st.stop()

            st.success(f"✅ Selected target: **{TARGET_COL}** ({target_mode})")

            # ✅ Clean and prepare target
            y_cont = pd.to_numeric(train_df[TARGET_COL], errors="coerce")
            df_clean = train_df.dropna(subset=[TARGET_COL]).copy()
            y_cont = df_clean[TARGET_COL].astype(float)

            # ---------------------------------------------------------
            # ✅ MODE 1: DECISION LABEL (approved / rejected → 1/0)
            # ---------------------------------------------------------
            if target_mode == "decision_label":
                y_bin = df_clean[TARGET_COL].astype(str).str.lower().map({
                    "approved": 1,
                    "rejected": 0
                })
                st.info("✅ Using human decisions converted to binary 0/1")

            # ---------------------------------------------------------
            # ✅ MODE 2 & 3: NUMERIC TARGET → BINARIZE USING MEDIAN
            # ---------------------------------------------------------
            else:
                threshold = float(y_cont.median())
                y_bin = (y_cont >= threshold).astype(int)
                st.info(f"✅ Numeric target → auto-threshold = {threshold:.4f}")

            # ---------------------------------------------------------
            # ✅ FEATURE SELECTION — remove target + leakage
            # ---------------------------------------------------------
            LEAKAGE_COLS = [
                TARGET_COL,
                "decision", "confidence",
                "top_feature", "explanation",
                "proposed_loan_option", "proposed_consolidation_loan",
                "rule_reasons"
            ]

            X = df_clean.drop(columns=[c for c in LEAKAGE_COLS if c in df_clean.columns])
            
            
            # ---------------------------------------------------------
            # ✅ Encode non-numeric columns for ML training
            # ---------------------------------------------------------
            X = X.copy()  # safe copy

            # Detect non-numeric columns
            non_numeric_cols = X.select_dtypes(include=["object"]).columns.tolist()
            
            if non_numeric_cols:
                st.warning(f"Encoding non-numeric columns: {non_numeric_cols}")

                # ✅ Safe label encoding for all models (LightGBM, XGBoost, RandomForest, LogisticRegression)
                # All models work correctly with label-encoded categorical features
                from sklearn.preprocessing import LabelEncoder

                for col in non_numeric_cols:
                    try:
                        le = LabelEncoder()
                        X[col] = le.fit_transform(X[col].astype(str))
                    except Exception as e:
                        st.error(f"❌ Failed to encode column '{col}': {e}")
                        st.stop()


            # ---------------------------------------------------------
            # ✅ TRAIN/TEST SPLIT
            # ---------------------------------------------------------
            from sklearn.model_selection import train_test_split
            Xtr, Xte, ytr, yte = train_test_split(
                X, y_bin, test_size=0.2, random_state=42
            )

            # ---------------------------------------------------------
            # ✅ MODEL SELECTION AND TRAINING
            # ---------------------------------------------------------
            if model_choice == "LogisticRegression":
                from sklearn.linear_model import LogisticRegression
                model = LogisticRegression(max_iter=2000)
            elif model_choice == "RandomForest":
                from sklearn.ensemble import RandomForestClassifier
                model = RandomForestClassifier(n_estimators=300)
            elif model_choice == "LightGBM":
                try:
                    from lightgbm import LGBMClassifier
                    # LightGBM works well with label-encoded categoricals
                    # Using 'auto' lets LightGBM detect categorical features automatically
                    model = LGBMClassifier(
                        verbose=-1,  # Suppress LightGBM output
                        random_state=42,
                        n_estimators=300,
                        learning_rate=0.05
                    )
                except ImportError:
                    st.error(
                        "❌ LightGBM is not installed. "
                        "Install it with `pip install lightgbm` or choose another model."
                    )
                    st.stop()
            elif model_choice == "XGBoost":
                try:
                    from xgboost import XGBClassifier
                    # XGBoost works well with label-encoded categoricals
                    # Can optionally enable tree_method='hist' for better performance
                    model = XGBClassifier(
                        tree_method='hist',  # Faster and handles categoricals better
                        eval_metric='logloss',
                        use_label_encoder=False  # Use native XGBoost evaluation
                    )
                except ImportError:
                    st.error(
                        "❌ XGBoost is not installed. "
                        "Install it with `pip install xgboost` or choose another model."
                    )
                    st.stop()
            else:
                st.error(f"❌ Unknown model choice: {model_choice}")
                st.stop()

            # Fit model with encoded features
            # All models (LR, RF, LightGBM, XGBoost) work with label-encoded categoricals
            model.fit(Xtr, ytr)

            # ---------------------------------------------------------
            # ✅ PREDICTIONS & METRICS
            # ---------------------------------------------------------
            preds_proba = model.predict_proba(Xte)[:, 1]
            preds = (preds_proba >= 0.5).astype(int)

            from sklearn.metrics import (
                roc_auc_score, accuracy_score, precision_score,
                recall_score, f1_score
            )

            metrics = {
                "AUC": roc_auc_score(yte, preds_proba),
                "Accuracy": accuracy_score(yte, preds),
                "Precision": precision_score(yte, preds),
                "Recall": recall_score(yte, preds),
                "F1": f1_score(yte, preds),
            }

            st.success("✅ Model trained successfully!")
            st.json(metrics)

        
    
            # -----------------------------------------------------
            # ✅ LOAD PRODUCTION BASELINE IF EXISTS
            # -----------------------------------------------------
            PROD_DIR = Path("./agents/credit_appraisal/models/production")
            prod_meta_path = PROD_DIR / "production_meta.json"
            prod_m = None
            
            # Try multiple possible paths
            possible_paths = [
                prod_meta_path,
                Path("services/ui/agents/credit_appraisal/models/production/production_meta.json"),
                Path(__file__).resolve().parents[2] / "agents" / "credit_appraisal" / "models" / "production" / "production_meta.json",
            ]
            
            loaded = False
            for meta_path in possible_paths:
                if meta_path.exists():
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Remove any merge conflict markers that might exist
                            if "<<<<<<< HEAD" in content or "=======" in content or ">>>>>>>" in content:
                                st.warning(f"⚠️ Found merge conflict markers in {meta_path}. Attempting to fix...")
                                # Backup corrupted file
                                try:
                                    backup_path = meta_path.with_suffix(".json.bak")
                                    import shutil
                                    shutil.copy2(meta_path, backup_path)
                                except Exception:
                                    pass
                                # Skip this file, try next one
                                continue
                            
                            prod_meta_data = json.loads(content)
                            prod_m = prod_meta_data.get("metrics")
                            loaded = True
                            break
                    except json.JSONDecodeError as e:
                        st.warning(f"⚠️ Production metadata file {meta_path} is corrupted (line {e.lineno}, col {e.colno}). Error: {e}")
                        # Try to backup corrupted file
                        try:
                            backup_path = meta_path.with_suffix(".json.bak")
                            import shutil
                            shutil.copy2(meta_path, backup_path)
                            st.info(f"Backed up corrupted file to {backup_path}")
                        except Exception:
                            pass
                        continue
                    except Exception as e:
                        # Skip this path, try next one
                        continue
            
            if not loaded:
                # No valid production metadata found - that's OK, will create new baseline
                pass

            st.markdown("---")
            st.subheader("📊 A/B Model Comparison")

            # ✅ COMPARISON TABLE
            cmp_df = pd.DataFrame({
                "Metric": list(metrics.keys()),
                "New Model": [f"{v:.4f}" for v in metrics.values()],
                "Production": [
                    f"{prod_m[k]:.4f}" if prod_m else "—"
                    for k in metrics.keys()
                ]
            })
            st.table(cmp_df)

            # -----------------------------------------------------
            # ✅ EXECUTIVE SUMMARY (WHAT → SO WHAT → NOW WHAT)
            # -----------------------------------------------------
            st.markdown("## 🧭 Executive Summary (WHAT → SO WHAT → NOW WHAT)")

            if prod_m:
                auc_delta = metrics["AUC"] - prod_m["AUC"]
                if auc_delta > 0:
                    st.success(f"✅ Model improves **AUC by {auc_delta:.4f}** — better discrimination.")
                else:
                    st.warning(f"⚠️ AUC dropped by {auc_delta:.4f} — further tuning required.")
            else:
                st.info("🟢 First model — will become baseline.")

            # -----------------------------------------------------
            # ✅ CONFUSION MATRIX
            # -----------------------------------------------------
            cm = confusion_matrix(yte, preds)
            cm_fig = px.imshow(
                cm, text_auto=True,
                title="Confusion Matrix",
                labels={"x": "Predicted", "y": "Actual"}
            )
            st.plotly_chart(cm_fig, use_container_width=True)

            # -----------------------------------------------------
            # ✅ FEATURE IMPORTANCE
            # -----------------------------------------------------
            st.subheader("🧠 Feature Importance")
            if hasattr(model, "feature_importances_"):
                imp = pd.DataFrame({"feature": X.columns, "importance": model.feature_importances_}).sort_values(
                    "importance", ascending=False
                )
                st.bar_chart(imp.set_index("feature"))
            elif hasattr(model, "coef_"):
                coef = pd.DataFrame({"feature": X.columns, "coef": np.ravel(model.coef_)}).sort_values(
                    "coef", key=np.abs, ascending=False
                )
                st.bar_chart(coef.set_index("feature"))
            else:
                st.info("This model does not expose importance metrics.")

            # -----------------------------------------------------
            # ✅ SAVE MODEL
            # -----------------------------------------------------
            TRAINED_DIR = Path("./agents/credit_appraisal/models/trained")
            TRAINED_DIR.mkdir(parents=True, exist_ok=True)

            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            model_path = TRAINED_DIR / f"{model_choice}_{ts}.joblib"
            joblib.dump(model, model_path)
            st.success(f"✅ Model saved → `{model_path}`")

            # ✅ SAVE REPORT
            RUNS_DIR = Path("./.tmp_runs")
            RUNS_DIR.mkdir(exist_ok=True)

            report = {
                "timestamp": ts,
                "model_choice": model_choice,
                "metrics": metrics,
                "model_path": str(model_path),
                "features": list(X.columns),
                "threshold": threshold,
            }

            rep_path = RUNS_DIR / f"credit_training_report_{ts}.json"
            json.dump(report, open(rep_path, "w"), indent=2)

            # store for next stage
            st.session_state["credit_last_model_path"] = str(model_path)
            st.session_state["credit_last_metrics"] = metrics
            st.session_state["credit_last_report"] = report

            st.caption(f"📄 Report saved → `{rep_path}`")

            # -----------------------------------------------------
            # ✅ PROMOTION BLOCK
            # -----------------------------------------------------
            st.markdown("## 📤 Promote This Model to Production")
            if st.button("✅ Promote to Production"):
                try:
                    PROD_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.copy(model_path, PROD_DIR / "model.joblib")
                    meta = {
                        "promoted_at": datetime.now(timezone.utc).isoformat(),
                        "metrics": metrics,
                        "model_path": str(model_path),
                        "model_choice": model_choice,
                    }
                    json.dump(meta, open(PROD_DIR / "production_meta.json", "w"), indent=2)
                    st.balloons()
                    st.success("✅ Model promoted successfully!")
                except Exception as e:
                    st.error(f"❌ Promotion failed: {e}")

            # -----------------------------------------------------
            # ✅ EXPORT ZIP
            # -----------------------------------------------------
            st.markdown("## 📦 Export Project ZIP")
            EXPORT_DIR = Path("./exports")
            EXPORT_DIR.mkdir(exist_ok=True)
            zip_name = f"credit_project_bundle_{ts}.zip"
            zip_path = EXPORT_DIR / zip_name

            if st.button("⬇️ Build ZIP Bundle"):
                try:
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:

                        # Runs
                        for root, dirs, files in os.walk(RUNS_DIR):
                            for f in files:
                                full = os.path.join(root, f)
                                arc = os.path.relpath(full, RUNS_DIR)
                                zf.write(full, f"runs/{arc}")

                        # Production models
                        if PROD_DIR.exists():
                            for f in PROD_DIR.glob("*"):
                                zf.write(f, f"production/{f.name}")

                        # Trained models
                        for f in TRAINED_DIR.glob("*.joblib"):
                            zf.write(f, f"trained/{f.name}")

                        # Training report
                        zf.write(rep_path, "training_report.json")

                    st.success("✅ ZIP created!")
                    with open(zip_path, "rb") as fp:
                        st.download_button(
                            "⬇️ Download ZIP",
                            data=fp,
                            file_name=zip_name,
                            mime="application/zip",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"❌ ZIP creation failed: {e}")


# -------------------------------------------------------------
# ✅ STAGE 6 — Deployment of Credit Scoring Model
# -------------------------------------------------------------
with tab_deploy:
    import os, json, shutil, zipfile
    from pathlib import Path
    from datetime import datetime, timezone

    st.title("🚀 Stage G — Deployment & Distribution")
    st.caption("Package → Verify → Upload → Release → Distribute to Credit / Legal / Risk units.")


    last_model = st.session_state.get("credit_last_model_path")
    metrics = st.session_state.get("credit_last_metrics")
    report = st.session_state.get("credit_last_report")

    if not last_model:
        trained_candidates = sorted(
            Path("./agents/credit_appraisal/models/trained").glob("*.joblib"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if trained_candidates:
            last_model = str(trained_candidates[0])
            report_path = trained_candidates[0].with_suffix(".json")
            if report_path.exists():
                try:
                    report = json.load(open(report_path, "r", encoding="utf-8"))
                    metrics = report.get("metrics", metrics)
                except Exception:
                    pass
            st.session_state["credit_last_model_path"] = last_model
            st.session_state["credit_last_metrics"] = metrics
            st.session_state["credit_last_report"] = report

    if not last_model:
        st.warning("⚠️ Train a model in Stage F before deploying.")
        st.stop()

    st.success(f"✅ Latest trained model detected:\n`{last_model}`")
    st.json(metrics)

    def _build_credit_project_bundle(export_dir: Path, model_path: str) -> Path:
        """Create a Stage F-compatible credit bundle from the latest model."""
        export_dir.mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        zip_path = export_dir / f"credit_project_bundle_{ts}.zip"
        model_file = Path(model_path)
        runs_dir = Path("./.tmp_runs")
        trained_dir = Path("./agents/credit_appraisal/models/trained")
        prod_dir = Path("./agents/credit_appraisal/models/production")
        prod_dir.mkdir(parents=True, exist_ok=True)

        prod_meta_path = prod_dir / "production_meta.json"
        if not prod_meta_path.exists():
            prod_meta = {
                "model_path": str(model_file),
                "promoted_at": datetime.now(timezone.utc).isoformat(),
                "metrics": metrics,
                "report": report,
                "source": "auto-created-by-stage-g",
            }
            json.dump(prod_meta, open(prod_meta_path, "w", encoding="utf-8"), indent=2)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if model_file.exists():
                zf.write(model_file, f"trained/{model_file.name}")
                model_report = model_file.with_suffix(".json")
                if model_report.exists():
                    zf.write(model_report, f"trained/{model_report.name}")

            if trained_dir.exists():
                for f in trained_dir.glob("*.joblib"):
                    if model_file.exists() and f.resolve() == model_file.resolve():
                        continue
                    zf.write(f, f"trained/{f.name}")

            for f in prod_dir.glob("*"):
                if f.is_file():
                    zf.write(f, f"production/{f.name}")

            if runs_dir.exists():
                for root, _, files in os.walk(runs_dir):
                    for filename in files:
                        full = Path(root) / filename
                        arc = full.relative_to(runs_dir)
                        zf.write(full, f"runs/{arc}")

            zf.writestr(
                "deployment_manifest.json",
                json.dumps(
                    {
                        "bundle_type": "credit_project_bundle",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "model_path": str(model_file),
                        "metrics": metrics,
                    },
                    indent=2,
                ),
            )

            if report:
                zf.writestr("training_report.json", json.dumps(report, indent=2))

        return zip_path
    

    # ---------------------------------------------
    # 1) Load the latest ZIP bundle created in Stage F
    # ---------------------------------------------
    st.markdown("## 📦 1) Project Package (Generated in Stage F)")
    
    EXPORT_DIR = Path("./exports")
    EXPORT_DIR.mkdir(exist_ok=True)

    # Find ZIP files
    zip_files = sorted(EXPORT_DIR.glob("credit_project_bundle_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zip_files:
        try:
            zip_files = [_build_credit_project_bundle(EXPORT_DIR, last_model)]
            st.info("No Stage F bundle found, so Stage G created one from the latest trained model.")
        except Exception as e:
            st.error(f"Could not create project ZIP: {e}")
    
    if not zip_files:
        st.warning("⚠️ No project ZIP found. Run Stage F and export a bundle first.")
        st.stop()

    latest_zip = zip_files[0]

    st.success(f"✅ Latest bundle detected: `{latest_zip.name}`")
    st.caption(f"Size: **{latest_zip.stat().st_size/1e6:.2f} MB**")
    

    # ---------------------------------------------
    # 3) Upload Targets (S3 / Swift / GitHub Release)
    # ---------------------------------------------
    st.markdown("## ☁️ 3) Upload / Publish Package")

    dest = st.radio(
        "Choose destination",
        ["AWS S3", "OpenStack Swift", "GitHub Release"],
        horizontal=True
    )

    if dest == "AWS S3":
        st.info("Upload to S3 (requires AWS credentials)")
        bucket = st.text_input("Bucket Name", "my-ai-models")
        key = st.text_input("Object Key", latest_zip.name)

        if st.button("⬆️ Upload to S3"):
            try:
                import boto3
                s3 = boto3.client("s3")
                s3.upload_file(str(latest_zip), bucket, key)
                st.success(f"✅ Uploaded to `s3://{bucket}/{key}`")
            except Exception as e:
                st.error(f"❌ Failed: {e}")

    elif dest == "OpenStack Swift":
        st.info("Upload to Swift (requires Swift credentials)")
        container = st.text_input("Container Name", "ai-models")
        if st.button("⬆️ Upload to Swift"):
            try:
                from swiftclient.service import SwiftService, SwiftUploadObject
                with SwiftService() as swift:
                    swift.upload(container, [SwiftUploadObject(str(latest_zip))])
                st.success(f"✅ Uploaded to Swift container `{container}`")
            except Exception as e:
                st.error(f"❌ Failed: {e}")

    elif dest == "GitHub Release":
        st.info("Publish as a GitHub release asset")
        repo = st.text_input("Repo (owner/repo)", "RackspaceAI/asset-appraisal-agent")
        token = st.text_input("GitHub Personal Access Token", type="password")
        tag = datetime.now().strftime("v%Y%m%d-%H%M%S")

        if st.button("⬆️ Publish Release on GitHub"):
            try:
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github+json",
                }

                # Create release
                r = requests.post(
                    f"https://api.github.com/repos/{repo}/releases",
                    headers=headers,
                    json={"tag_name": tag, "name": f"Release {tag}", 
                          "body": "Automated export from Stage G"}
                )
                r.raise_for_status()

                upload_url = r.json()["upload_url"].split("{")[0]

                # Upload asset
                with open(latest_zip, "rb") as f:
                    ur = requests.post(
                        f"{upload_url}?name={latest_zip.name}",
                        headers={**headers, "Content-Type": "application/zip"},
                        data=f,
                    )
                ur.raise_for_status()

                st.success(f"✅ GitHub Release `{tag}` published successfully!")
            except Exception as e:
                st.error(f"❌ Failed: {e}")




    # ---------------------------------------------
    # 5) Next Steps Checklist
    # ---------------------------------------------
    st.markdown("## ✅ 5) Next Steps for DevOps / IT")

    st.markdown("""
    ### ✔ For Credit Underwriting
    - Import CSV assets into the Credit Appraisal Agent  
    - Validate LTV, confidence, breaches  
    - Promote selected assets for loan approval  

    ### ✔ For Legal & Compliance
    - Use verification subset (ownership, encumbrances)  
    - Run through Legal Verification Agent  
    - Flag encumbrances & fraud paths  

    ### ✔ For Risk Management
    - Use realizable_value, condition_score, legal_penalty  
    - Re-run LTV stress tests  
    - Update risk dashboards monthly  

    ### ✔ For DevOps / Platform Teams
    - Push ZIP to GitHub / Swift / S3  
    - Deploy production model into RunAI / SageMaker / OpenStack MLOps  
    - Update production_meta.json  
    """)

    st.info("Stage G is complete — continue to Stage H for Inter-Department Handoff.")


    # ---------------------------------------------
    # 1) Load the latest ZIP bundle created in Stage F
    # ---------------------------------------------
    st.markdown("## 📦 1) Project Package (Generated in Stage F)")
    
    EXPORT_DIR = Path("./exports")
    EXPORT_DIR.mkdir(exist_ok=True)

    # Find ZIP files
    zip_files = sorted(EXPORT_DIR.glob("credit_project_bundle_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zip_files:
        try:
            zip_files = [_build_credit_project_bundle(EXPORT_DIR, last_model)]
            st.info("No Stage F bundle found, so Stage G created one from the latest trained model.")
        except Exception as e:
            st.error(f"Could not create project ZIP: {e}")
    
    if not zip_files:
        st.warning("⚠️ No project ZIP found. Run Stage F and export a bundle first.")
        st.stop()

    latest_zip = zip_files[0]

    st.success(f"✅ Latest bundle detected: `{latest_zip.name}`")
    st.caption(f"Size: **{latest_zip.stat().st_size/1e6:.2f} MB**")
    
    
    
    
    # ---------------------------------------------------------
    # ✅ Promote to production
    # ---------------------------------------------------------
    if st.button("✅ Promote This Model to Production"):
        prod_dir = Path("./agents/credit_appraisal/models/production")
        prod_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(last_model, prod_dir / "model.joblib")

        prod_meta = {
            "model_path": last_model,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "report": report,
        }
        json.dump(prod_meta, open(prod_dir / "production_meta.json", "w"), indent=2)

        st.balloons()
        st.success("✅ Model promoted to production successfully!")

    # ---------------------------------------------------------
    # ✅ Export deployment ZIP
    # ---------------------------------------------------------
    EXPORT_DIR = Path("./exports")
    EXPORT_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    if st.button("⬇️ Export Deployment Bundle"):
        zip_path = EXPORT_DIR / f"credit_deployment_{ts}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(last_model, arcname="trained_model.joblib")
            zf.write("./agents/credit_appraisal/models/production/production_meta.json",
                     arcname="production_meta.json")

        with open(zip_path, "rb") as f:
            st.download_button(
                "⬇️ Download Deployment ZIP",
                data=f,
                file_name=zip_path.name,
                mime="application/zip",
            )
        st.success("✅ Deployment bundle ready!")


# -------------------------------------------------------------
# ✅ STAGE 7 — Reporting & Handoff
# -------------------------------------------------------------
with tab_handoff:
    import os, json, zipfile
    import numpy as np
    import pandas as pd
    from pathlib import Path
    from datetime import datetime, timezone
    import streamlit as st
    import plotly.express as px

    st.markdown("## 📊 Stage 7 — Portfolio Reporting & Handoff")
    
    
    # ---------------------------------------------------------
    # ✅ Required outputs from earlier stages — MUST COME FIRST
    # ---------------------------------------------------------
    scored_df   = st.session_state.get("credit_scored_df")
    policy_df   = st.session_state.get("credit_policy_df")
    decision_df = st.session_state.get("credit_decision_df")

    # Helper
    import pandas as pd
    def is_nonempty_df(x) -> bool:
        return isinstance(x, pd.DataFrame) and not x.empty

    missing = []
    if not is_nonempty_df(scored_df):
        missing.append("Stage C — Credit AI Evaluation (credit_scored_df)")

    if missing:
        st.error("⚠️ Missing required data: " + ", ".join(missing))
        st.info("Please run the missing stages before returning to Stage H.")
        st.stop()

    # ✅ Only now is dfv allowed to be created
    # Prefer final decision table; fall back to Stage C scored output
    if is_nonempty_df(decision_df):
        dfv = decision_df.copy()
    else:
        dfv = scored_df.copy()

    # ---------------------------------------------------------
    # ✅ Load portfolio for Stage 7 visuals/exports
    # 1) Primary: dataset saved by Stage C/E
    # 2) Fallback: Stage C merged output (last_merged_df)
    # 3) Optional: user upload
    # ---------------------------------------------------------
    df = st.session_state.get("credit_scored_df")

    if not is_nonempty_df(df):
        df = st.session_state.get("last_merged_df")

    uploaded_scored = st.file_uploader(
        "⬆️ (Optional) Load scored CSV for reporting",
        type=["csv"], key="stage7_upload"
    )
    if uploaded_scored is not None:
        try:
            df = pd.read_csv(uploaded_scored)
            st.success(f"Loaded scored dataset from upload ({len(df)} rows).")
        except Exception as e:
            st.error(f"Could not read uploaded CSV: {e}")

    # Final guard
    if not is_nonempty_df(df):
        st.warning("⚠️ Missing scored dataset. Run Stage 3 (Credit appraisal) or upload a scored CSV above.")
        st.stop()

    st.session_state["credit_scored_df"] = df.copy()

    st.success("✅ Portfolio loaded.")
    st.dataframe(df.head(), use_container_width=True)

    # … (keep the rest of Stage 7: metrics, charts, handoff CSV/ZIP) …




    # ---------------------------------------------------------
    # ✅ Executive dashboard
    # ---------------------------------------------------------
    st.markdown("### 🧭 Executive Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Applications", len(df))
    with col2:
        st.metric("Approved", (df["decision"] == "approve").sum())
    with col3:
        st.metric("Rejected", (df["decision"] == "reject").sum())

    # ---------------------------------------------------------
    # new ✅ MARKET INSIGHTS — CITY LEVEL DISTRIBUTION
    # ---------------------------------------------------------
    st.markdown("### 🌍 Asset Distribution by City")

    if "city" in dfv.columns:
        fig_city = px.histogram(
            dfv, x="city", color="status",
            title="Asset Count per City by Status",
            barmode="group"
        )
        st.plotly_chart(fig_city, use_container_width=True)

    # ---------------------------------------------------------
    # ✅ VALUE INSIGHTS — Realizable Value Curve
    # ---------------------------------------------------------
    st.markdown("### 💰 Value Distribution — FMV vs Realizable Value")

    if "realizable_value" in dfv.columns:
        fig_val = go.Figure()
        fig_val.add_trace(go.Violin(y=dfv["fmv"], name="FMV", box_visible=True))
        fig_val.add_trace(go.Violin(y=dfv["realizable_value"], name="Realizable", box_visible=True))
        st.plotly_chart(fig_val, use_container_width=True)

    # ---------------------------------------------------------
    # ✅ FULL PORTFOLIO TABLE
    # ---------------------------------------------------------
    st.markdown("### 📂 Unified Portfolio (with status)")
    st.dataframe(dfv, use_container_width=True)


    # ---------------------------------------------------------
    # ✅ Approval distribution (robust to 0/1, strings, themes)
    # ---------------------------------------------------------
    st.markdown("### 📈 Approval Distribution")

    # 1) Normalize labels
    if "decision" not in df.columns:
        st.info("No 'decision' column found; skipping approval chart.")
    else:
        vals = df["decision"]

        def to_label(v):
            if isinstance(v, str):
                s = v.strip().lower()
                if s in ("approve", "approved", "yes", "y", "1", "true"):
                    return "approve"
                if s in ("reject", "rejected", "no", "n", "0", "false"):
                    return "reject"
                return s or "unknown"
            try:
                return "approve" if float(v) >= 1 else "reject"
            except Exception:
                return "unknown"

        df = df.copy()
        df["decision_label"] = vals.map(to_label).fillna("unknown")

        # 2) Safe color map (must be a LIST → map to dict)
        palette = px.colors.qualitative.Set2  # e.g., ['#66c2a5', '#fc8d62', ...]
        color_map = {
            "approve": palette[0] if len(palette) > 0 else "#22c55e",
            "reject":  palette[1] if len(palette) > 1 else "#ef4444",
            "unknown": palette[2] if len(palette) > 2 else "#94a3b8",
        }

        # 3) Fixed category order for readability
        categories = ["approve", "reject", "unknown"]

        fig = px.histogram(
            df,
            x="decision_label",
            color="decision_label",
            category_orders={"decision_label": categories},
            color_discrete_map=color_map,
            title="Approval vs Rejection",
        )
        fig.update_layout(
            legend_title_text="Decision",
            bargap=0.2,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color=("#e2e8f0" if st.session_state.get("theme", "dark") == "dark" else "#0f172a"),
        )
        st.plotly_chart(fig, use_container_width=True)


    # ---------------------------------------------------------
    # ✅ Department Handoff: Credit / Risk / Compliance / CS
    # ---------------------------------------------------------
    st.markdown("## 🏦 Department Handoff Packages")
    
    # ---------- helpers ----------
    def pick(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        """Return df with only columns that actually exist (no KeyError)."""
        keep = [c for c in cols if c in df.columns]
        return df[keep].copy()

    # ---------- ensure 'reason' exists ----------
    if "reason" not in df.columns:
        if "explanation" in df.columns:
            df["reason"] = df["explanation"].astype(str).str.slice(0, 200)
        elif {"pd", "dti", "ltv"}.issubset(df.columns) or "score" in df.columns:
            def infer_reason(row):
                try:
                    if float(row.get("pd", 0)) >= 0.15:
                        return "High probability of default"
                    if float(row.get("dti", 0)) >= 0.5:
                        return "High debt-to-income"
                    if float(row.get("ltv", 0)) >= 0.8:
                        return "High loan-to-value"
                    if float(row.get("score", 999)) < 600:
                        return "Low credit score"
                except Exception:
                    pass
                return "Policy/Other"
            df["reason"] = df.apply(infer_reason, axis=1)
        else:
            df["reason"] = ""

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    HANDOFF_DIR = Path("./credit_handoff")
    ZIP_DIR = HANDOFF_DIR / "zips"
    HANDOFF_DIR.mkdir(exist_ok=True)
    ZIP_DIR.mkdir(exist_ok=True)
    
    credit = pick(df, ["application_id","score","decision","reason","income","loan_amount"])
    risk = pick(df, ["application_id","score","pd","ltv","dti","decision"])
    compliance = pick(df, ["application_id","account_age","delinquencies","fraud_flag","decision"])
    customer = pick(df, ["application_id","score","decision","explanation","reason"])


    # credit = df[["application_id","score","decision","reason","income","loan_amount"]]
    # risk = df[["application_id","score","pd","ltv","dti","decision"]]
    # compliance = df[["application_id","account_age","delinquencies","fraud_flag","decision"]]
    # customer = df[["application_id","score","decision","explanation"]]

    paths = {
        "credit": HANDOFF_DIR / f"credit_{ts}.csv",
        "risk": HANDOFF_DIR / f"risk_{ts}.csv",
        "compliance": HANDOFF_DIR / f"compliance_{ts}.csv",
        "customer": HANDOFF_DIR / f"customer_service_{ts}.csv",
    }

    # Save all
    credit.to_csv(paths["credit"], index=False)
    risk.to_csv(paths["risk"], index=False)
    compliance.to_csv(paths["compliance"], index=False)
    customer.to_csv(paths["customer"], index=False)

    # ---------------------------------------------------------
    # ✅ ZIP bundle
    # ---------------------------------------------------------
    zip_path = ZIP_DIR / f"credit_handoff_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in paths.values():
            zf.write(p, arcname=os.path.basename(p))

    st.download_button(
        "⬇️ Download Full Handoff ZIP",
        data=open(zip_path, "rb").read(),
        file_name=os.path.basename(zip_path),
        mime="application/zip",
        use_container_width=True,
    )

    # # st.markdown("### 🧩 Department Package Map")
    # # st.json({k: list(df[list(credit.columns)].columns)})
    # st.markdown("### 🧩 Department Package Map")
    # st.json({
    #     "credit":   list(credit.columns),
    #     "risk":     list(risk.columns),
    #     "compliance": list(compliance.columns),
    #     "customer_service": list(customer.columns),
    # })

    # Optional: tell user if something was missing
    expected = {
        "credit": ["application_id","score","decision","reason","income","loan_amount"],
        "risk": ["application_id","score","pd","ltv","dti","decision"],
        "compliance": ["application_id","account_age","delinquencies","fraud_flag","decision"],
        "customer_service": ["application_id","score","decision","explanation","reason"],
    }
    missing_report = {
        pkg: [c for c in expected[pkg] if c not in cols]
        for pkg, cols in {
            "credit": credit.columns,
            "risk": risk.columns,
            "compliance": compliance.columns,
            "customer_service": customer.columns,
        }.items()
    }
    if any(missing_report.values()):
        st.info(f"Some expected columns were not present and were skipped: {missing_report}")


with tab_feedback:
    render_feedback_tab("💳 Credit Appraisal Agent")




# Legacy credit theme (kept for optional reuse)
LEGACY_CREDIT_THEME_SNIPPET = '''
def legacy_credit_theme(theme: str = "dark"):
    import streamlit as st

    st.markdown("""
    <style>
    /* ===============================================
       🌙 MACOS BLUE DARK THEME — GLOBAL BASE
    =============================================== */
    html, body, [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 20% 20%, #0b0f16, #060a12 85%) !important;
        color: #f8fafc !important;
        font-family: "Inter","SF Pro Display","Segoe UI",system-ui,sans-serif !important;
    }

    h1,h2,h3,h4,h5,h6 {
        color: #f8fafc !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    p, li, label, span, div {
        color: #e2e8f0 !important;
    }
    small, .stCaption { color: #94a3b8 !important; }

    a, a:link, a:visited { color: #339dff !important; }
    a:hover { color: #60a5fa !important; text-decoration: underline; }

    hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg,transparent,#007aff,transparent) !important;
    }

    /* ===============================================
       🧱 CONTAINERS & CARDS
    =============================================== */
    .stMarkdown, .stContainer, .stAlert, [class*="stCard"], [class*="block-container"] {
        background: #0f172a !important;
        border: 1px solid #1e3a8a !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
    }

    /* ===============================================
       🔘 BUTTONS — macOS BLUE
    =============================================== */
    button[kind="primary"], .stButton>button, .stDownloadButton>button, .stDownloadButton button {
        background: linear-gradient(180deg,#007aff,#005ecb) !important;
        color: #ffffff !important;
        border: 1px solid #0051b8 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 4px 10px rgba(0,122,255,0.35),
                    inset 0 -1px 0 rgba(255,255,255,0.2) !important;
        transition: all 0.25s ease-in-out !important;
    }
    button[kind="primary"]:hover, .stButton>button:hover, .stDownloadButton>button:hover {
        background: linear-gradient(180deg,#339dff,#006ae6) !important;
        box-shadow: 0 4px 14px rgba(0,122,255,0.45) !important;
        transform: translateY(-1px) !important;
    }
    button[kind="primary"]:active, .stButton>button:active, .stDownloadButton>button:active {
        background: linear-gradient(180deg,#004fc4,#0042a8) !important;
        box-shadow: inset 0 2px 6px rgba(0,122,255,0.3) !important;
        transform: translateY(0) !important;
    }
    .stButton button[disabled], .stDownloadButton button[disabled] {
        background: #1e293b !important;
        color: #64748b !important;
        border: 1px solid #334155 !important;
    }

    /* ===============================================
    🧠 INPUTS (Text, Select, Number) & FOCUS STATE
    =============================================== */
    .stTextInput>div>div>input,
    .stSelectbox>div>div>div,
    .stNumberInput input {
        background: #111827 !important;
        color: #f8fafc !important;
        border: 1px solid #1e3a8a !important;
        border-radius: 8px !important;
        padding: 6px 10px !important;
        transition: all 0.25s ease;
    }
    .stTextInput>div>div>input:focus,
    .stSelectbox>div>div>div:focus-within,
    .stNumberInput input:focus {
        outline: none !important;
        border-color: #007aff !important;
        box-shadow: 0 0 0 2px rgba(0,122,255,0.4) !important;
    }
    ::placeholder {
        color: #9ca3af !important;
        opacity: 1 !important;
    }
    /* ===============================================
   🎛 DROPDOWN MENUS
    =============================================== */
    [data-baseweb="popover"], [role="listbox"] {
        background: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid #1e3a8a !important;
        box-shadow: 0 4px 20px rgba(0,0,0,0.6) !important;
    }
    [data-baseweb="menu-item"] {
        background: #0f172a !important;
        color: #f8fafc !important;
    }
    [data-baseweb="menu-item"]:hover {
        background: #1e3a8a !important;
        color: #ffffff !important;
    }
    /* ===============================================
    🧭 SIDEBAR THEME
    =============================================== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg,#0d1320,#060a12) !important;
        border-right: 1px solid #1e3a8a !important;
        color: #f8fafc !important;
    }

    
    /* ===============================================
       ☑️ CHECKBOXES / RADIOS / SLIDERS
    =============================================== */
    input[type="checkbox"], input[type="radio"] {
        accent-color: #007aff !important;
    }
    .stSlider [role="slider"] {
        background-color: #007aff !important;
    }

    /* ===============================================
       🗂️ TABS
    =============================================== */
    .stTabs [data-baseweb="tab-list"] button {
        color: #e2e8f0 !important;
        background: #111827 !important;
        border: 1px solid #1e293b !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        margin-right: 4px !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background: #007aff !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(0,122,255,0.4) !important;
    }

    /* ===============================================
       🧭 EXPANDERS / ACCORDIONS
    =============================================== */
    .streamlit-expanderHeader {
        background: linear-gradient(90deg,#0d284d,#0a1f3a) !important;
        color: #dbeafe !important;
        border: 1px solid #1e3a5f !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    .streamlit-expanderContent {
        background: #0f172a !important;
        color: #e2e8f0 !important;
        border: 1px solid #1e3a5f !important;
        border-radius: 0 0 8px 8px !important;
    }

    /* ===============================================
       📊 METRIC CARDS (st.metric)
    =============================================== */
    [data-testid="stMetric"] {
        background: linear-gradient(180deg,#0b1220,#101a2c) !important;
        border: 1px solid #1e3a8a !important;
        border-radius: 10px !important;
        box-shadow: inset 0 0 10px rgba(255,255,255,0.03),
                    0 3px 10px rgba(0,0,0,0.6) !important;
        padding: 10px 14px !important;
        text-align: center !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.3rem !important;
        font-weight: 600 !important;
    }

    /* ===============================================
       📊 METRIC COMPARISON TABLE — FINAL
    =============================================== */
    [data-testid="stDataFrame"] {
        background: radial-gradient(circle at 50% 50%, #0b1220, #060a12 90%) !important;
        border: 1px solid #1e3a8a !important;
        border-radius: 12px !important;
        box-shadow:
            0 0 14px rgba(0,0,0,0.6) inset,
            0 4px 18px rgba(0,0,0,0.7),
            0 0 12px rgba(0,122,255,0.15) !important;
        margin-top: 12px !important;
        padding: 8px !important;
    }
    [data-testid="stDataFrame"] thead tr th {
        background: linear-gradient(90deg,#004fc4,#007aff) !important;
        color: #ffffff !important;
        border-bottom: 2px solid #007aff !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.02em !important;
        font-size: 0.92rem !important;
        padding: 10px 14px !important;
    }
    [data-testid="stDataFrame"] tbody tr {
        background-color: #0b1220 !important;
        color: #ffffff !important;
        transition: background 0.25s ease;
    }
    [data-testid="stDataFrame"] tbody tr:nth-child(even) {
        background-color: #101a2c !important;
    }
    [data-testid="stDataFrame"] tbody tr:hover {
        background-color: #112a52 !important;
        box-shadow: 0 0 8px rgba(0,122,255,0.25) inset !important;
    }
    [data-testid="stDataFrame"] tbody td {
        border-top: 1px solid #1e3a8a !important;
        color: #ffffff !important;
        padding: 9px 14px !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
    }
    [data-testid="stDataFrame"] tbody td:last-child {
        color: #60a5fa !important;
        font-weight: 500 !important;
    }

    /* ===============================================
       📁 FILE UPLOADER
    =============================================== */
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,0.03) !important;
        border: 1px dashed #1e3a8a !important;
        border-radius: 10px !important;
        color: #cbd5e1 !important;
        transition: all 0.25s ease;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #007aff !important;
        background: rgba(0,122,255,0.1) !important;
    }

    /* ===============================================
       ⚠️ ALERT BOXES
    =============================================== */
    [data-testid^="stAlert"] {
        border-radius: 10px !important;
        border: 1px solid #1e3a8a !important;
        color: #e2e8f0 !important;
        box-shadow: 0 3px 15px rgba(0,0,0,0.4) !important;
    }
    [data-testid="stAlertInfo"]    { background: linear-gradient(145deg,#0d1829,#10243d)!important; }
    [data-testid="stAlertSuccess"] { background: linear-gradient(145deg,#0f2414,#183820)!important; }
    [data-testid="stAlertError"]   { background: linear-gradient(145deg,#2b1617,#1a0c0d)!important; }
    [data-testid="stAlertWarning"] { background: linear-gradient(145deg,#2f2a10,#1c1a0a)!important; }

    </style>
    """, unsafe_allow_html=True)

'''

render_chat_assistant(
    page_id="credit_appraisal",
    context=_build_credit_chat_context(),
    faq_questions=CREDIT_FAQ,
)
