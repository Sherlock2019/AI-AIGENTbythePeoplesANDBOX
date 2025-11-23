#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏦 Asset Appraisal Agent — Full E2E Flow (Inputs → Anonymize → AI → Human Review → Training)
Author:  Nguyen Dzoan
Version: 2025-11-01

Includes:
- Stage 1: CSV + evidence (images/PDFs) + manual row; synthetic fallback + "why" table
- Stage 2: Explicit anonymization pipeline (RAW & ANON kept)
- Stage 3: AI appraisal with runtime flavor selector, agent discovery+probe, rule_reasons when backend omits
  + Production banner + asset-trained model selector + promote inside Stage 3
- Stage 4: Human Review with AI↔Human agreement gauge; export feedback CSV
- Stage 5: Training (upload feedback) → Train candidate → Promote to PRODUCTION
"""

import os
import io
import re
import json
import threading
import time
from datetime import datetime, timezone  # ✅ clean, safe, supports datetime.now()
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict

# ── Third-party
import requests
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
import csv
import zipfile  # ✅ ADD THIS

from services.ui.theme_manager import (
    apply_theme as apply_global_theme,
    get_palette,
    get_theme,
    render_theme_toggle,
)
from services.ui.components.operator_banner import render_operator_banner
from services.ui.components.feedback import render_feedback_tab
from services.ui.components.chat_assistant import render_chat_assistant
from services.common.model_registry import get_hf_models
from services.common.personas import get_persona_for_agent
from services.ui.utils.llm_selector import render_llm_selector







# ─────────────────────────────────────────────
# PAGE CONFIG + THEME
# ─────────────────────────────────────────────
import streamlit as st

st.set_page_config(page_title="Asset Appraisal Agent", layout="wide")
ss = st.session_state

st.markdown(
    """
    > **Unified Risk Checklist**  
    > ✅ Is the borrower real & safe? (handled by KYC/Fraud)  
    > ✅ Is the collateral worth enough? (this agent)  
    > ✅ Can they afford the loan? (Credit)  
    > ✅ Should the bank approve overall? (Unified agent)
    """
)

# ─────────────────────────────────────────────
# SESSION DEFAULTS (idempotent)
# ─────────────────────────────────────────────
def _init_defaults():
    ss.setdefault("asset_logged_in", True)
    ss.setdefault("asset_stage", "asset_flow")   # login → asset_flow
    ss.setdefault("asset_user", {"name": "Operator", "email": "operator@demo.local"})
    ss.setdefault("asset_pending_cases", 18)
    ss.setdefault("asset_flagged_cases", 3)
    ss.setdefault("asset_avg_time", "22 min")
    # Working tables/artifacts per our matrix (placeholders)
    ss.setdefault("asset_intake_df", None)
    ss.setdefault("asset_evidence_index", None)
    ss.setdefault("asset_anon_df", None)
    ss.setdefault("asset_features_df", None)
    ss.setdefault("asset_comps_used", None)
    ss.setdefault("asset_valued_df", None)
    ss.setdefault("asset_verified_df", None)
    ss.setdefault("asset_policy_df", None)
    ss.setdefault("asset_decision_df", None)
    ss.setdefault("asset_human_review_df", None)
    ss.setdefault("asset_feedback_csv", None)
    ss.setdefault("asset_trained_model_meta", None)
    ss.setdefault("asset_gpu_profile", None)  # will be set only in C.4
    ss.setdefault("asset_ai_performance", 0.88)
    os.makedirs("./.tmp_runs", exist_ok=True)

_init_defaults()
ASSET_PERSONA = get_persona_for_agent("asset_appraisal")


def _build_asset_chat_context() -> Dict[str, Any]:
    ss_local = st.session_state
    ctx = {
        "agent_type": "asset",
        "stage": ss_local.get("asset_stage"),
        "user": (ss_local.get("asset_user") or {}).get("name"),
        "pending_cases": ss_local.get("asset_pending_cases"),
        "flagged_cases": ss_local.get("asset_flagged_cases"),
        "avg_time": ss_local.get("asset_avg_time"),
        "ai_performance": ss_local.get("asset_ai_performance"),
        "last_run_id": ss_local.get("asset_last_run_id"),
        "last_runner": ss_local.get("asset_last_runner"),
        "last_error": ss_local.get("asset_last_error"),
        "next_step": ss_local.get("asset_next_step"),
    }
    return {k: v for k, v in ctx.items() if v not in (None, "", [])}


ASSET_FAQ = [
    "Explain ai_adjusted vs FMV.",
    "Show comps that drove the valuation.",
    "What encumbrances were detected?",
    "How do I rerun Stage C – Valuation?",
    "Show the last 10 assets approved with their FMV and AI-adjusted values.",
    "List the last 10 assets flagged or declined and why.",
    "What's the total asset value appraised this month?",
    "Which assets were marked suspect over the past 30 days?",
    "Where can I download the last 10 valuation_ai.csv artifacts?",
    "How many appraisal runs are currently stored in .tmp_runs?",
]

# Always bypass login step during operator demos
ss["asset_logged_in"] = True
if ss.get("asset_stage") == "login":
    ss["asset_stage"] = "asset_flow"


def _coerce_minutes(value, fallback: float = 0.0) -> float:
    """Convert values like '22 min' to floats for gauge percentages."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch == ".")
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            pass
    return float(fallback)


def _build_asset_chat_context() -> Dict[str, Any]:
    ss_local = st.session_state
    ctx = {
        "agent_type": "asset",
        "stage": ss_local.get("asset_stage"),
        "user": (ss_local.get("asset_user") or {}).get("name"),
        "pending_cases": ss_local.get("asset_pending_cases"),
        "flagged_cases": ss_local.get("asset_flagged_cases"),
        "avg_time": ss_local.get("asset_avg_time"),
        "ai_performance": ss_local.get("asset_ai_performance"),
        "last_run_id": ss_local.get("asset_last_run_id"),
        "last_runner": ss_local.get("asset_last_runner"),
        "last_error": ss_local.get("asset_last_error"),
        "next_step": ss_local.get("asset_next_step"),
    }
    return {k: v for k, v in ctx.items() if v not in (None, "", [])}


ASSET_FAQ = [
    "Explain ai_adjusted vs FMV.",
    "Show comps that drove the valuation.",
    "What encumbrances were detected?",
    "How do I rerun Stage C – Valuation?",
]

# Always bypass login step during operator demos
ss["asset_logged_in"] = True
if ss.get("asset_stage") == "login":
    ss["asset_stage"] = "asset_flow"

# ─────────────────────────────────────────────
# AUTO-LOAD DEMO DATA (if no results exist)
# ─────────────────────────────────────────────
if ss.get("asset_valued_df") is None and ss.get("asset_policy_df") is None:
    # Auto-generate demo data on first load
    rng = np.random.default_rng(42)
    demo_df = pd.DataFrame({
        "asset_id": [f"AST_{i:04d}" for i in range(1, 31)],
        "asset_type": rng.choice(["Residential", "Commercial", "Industrial", "Multifamily"], 30),
        "market_value": rng.integers(100000, 500000, 30),
        "condition_score": rng.uniform(0.6, 1.0, 30).round(3),
        "legal_penalty": rng.uniform(0.9, 1.0, 30).round(3),
        "age_years": rng.integers(0, 50, 30),
        "city": rng.choice(["San Jose", "Los Angeles", "Houston", "Chicago", "Miami"], 30),
        "loan_amount": rng.integers(50000, 400000, 30),
    })
    
    # Run asset appraisal agent on demo data
    try:
        from agents.asset_appraisal.runner import run as run_asset_appraisal
        form_fields = {}
        valued_df = run_asset_appraisal(demo_df, form_fields)
        ss["asset_valued_df"] = valued_df
        ss["asset_policy_df"] = valued_df.copy()
        ss["asset_demo_loaded"] = True
    except Exception as e:
        # If runner fails, at least store the input data
        ss["asset_demo_loaded"] = False
        import logging
        logging.warning(f"Could not auto-run asset appraisal: {e}")


def _coerce_minutes(value, fallback: float = 0.0) -> float:
    """Convert values like '22 min' to floats for gauge percentages."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch == ".")
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            pass
    return float(fallback)

def render_nav_bar_app():
    st.markdown(
        "<div style='display:flex;gap:12px;align-items:center'>"
        "<a href='?stage=agents' class='macbtn'>🤖 Agents</a>"
        "<span style='opacity:.6'>/</span>"
        "<span>🏛️ Asset Appraisal Agent</span>"
        "</div>",
        unsafe_allow_html=True,
    )


# ---- Global runs dir (used everywhere) ----
RUNS_DIR = os.path.abspath("./.tmp_runs")
os.makedirs(RUNS_DIR, exist_ok=True)






# ─────────────────────────────────────────────
# API CONFIG
# ─────────────────────────────────────────────

API_URL = os.getenv("API_URL", "http://localhost:8090")

_CHATBOT_REFRESH_STATE = {"last_ts": 0.0}

def _ping_chatbot_refresh(reason: str = "asset", *, min_interval: float = 300.0) -> None:
    now = time.time()
    if (now - _CHATBOT_REFRESH_STATE.get("last_ts", 0.0)) < min_interval:
        return
    _CHATBOT_REFRESH_STATE["last_ts"] = now

    def _fire():
        try:
            requests.post(f"{API_URL}/chatbot/refresh", json={"reason": reason}, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_fire, daemon=True).start()

# Default fallbacks (will be superseded by discovery)

ASSET_AGENT_IDS = [a.strip() for a in os.getenv("ASSET_AGENT_IDS", "asset_appraisal,asset").split(",") if a.strip()]

# ─────────────────────────────────────────────
# NAV (reliable jump to Home / Agents from a page)
# ─────────────────────────────────────────────
def _set_query_params_safe(**kwargs):
    # New API (Streamlit ≥1.40)
    try:
        for k, v in kwargs.items():
            st.query_params[k] = v
        return True
    except Exception:
        pass
    # Older versions
    try:
        st.experimental_set_query_params(**kwargs)
        return True
    except Exception:
        return False

def _go_stage(target_stage: str):
    # 1) let app.py’s router know what to show
    st.session_state["stage"] = target_stage

    # 2) preferred: jump to main app file
    try:
        # path is relative to the run root when you launch:
        #   streamlit run services/ui/app.py
        st.switch_page("app.py")
        return
    except Exception:
        pass

    # 3) fallback: set query param and rerun so app.py picks it up
    _set_query_params_safe(stage=target_stage)
    st.rerun()

# ─────────────────────────────────────────────
# UTILITIES — DataFrame selection helpers
# ─────────────────────────────────────────────
# ---- DataFrame selection helpers (avoid boolean ambiguity) ----
def first_nonempty_df(*candidates):
    """Return the first candidate that is a non-empty pandas DataFrame, else None."""
    for df in candidates:
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    return None

def is_nonempty_df(x) -> bool:
    return isinstance(x, pd.DataFrame) and not x.empty

def render_nav_bar_app():
    stage = st.session_state.get("stage", "landing")

    # three columns: home, agents, theme toggle
    c1, c2, c3 = st.columns([1, 1, 2.5])

    with c1:
        if st.button("🏠 Back to Home", key=f"btn_home_{stage}"):
            _go_stage("landing")
            st.stop()

    with c2:
        if st.button("🤖 Back to Agents", key=f"btn_agents_{stage}"):
            _go_stage("agents")
            st.stop()

    with c3:
        render_theme_toggle(
            label="🌗 Dark mode",
            key="asset_theme_toggle",
            help="Switch theme",
        )

    st.markdown("---")




# ─────────────────────────────────────────────
# GEO UTILITIES: EXIF GPS, Geocode, Geohash   ← PASTE START
# ─────────────────────────────────────────────
from typing import Optional, Tuple

def _exif_to_degrees(value):
    try:
        d = float(value[0][0]) / float(value[0][1])
        m = float(value[1][0]) / float(value[1][1])
        s = float(value[2][0]) / float(value[2][1])
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return None

def extract_gps_from_image(path: str) -> Optional[Tuple[float, float]]:
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        img = Image.open(path)
        exif = img._getexif() or {}
        tagged = {TAGS.get(k, k): v for k, v in exif.items()}
        gps_info = tagged.get("GPSInfo")
        if not gps_info:
            return None
        gps_data = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}
        lat = _exif_to_degrees(gps_data.get("GPSLatitude"))
        lon = _exif_to_degrees(gps_data.get("GPSLongitude"))
        if lat is None or lon is None:
            return None
        lat_ref = gps_data.get("GPSLatitudeRef", "N")
        lon_ref = gps_data.get("GPSLongitudeRef", "E")
        if lat_ref == "S": lat = -lat
        if lon_ref == "W": lon = -lon
        return (lat, lon)
    except Exception:
        return None

_GEOCODE_CACHE_PATH = "./.tmp_runs/geocode_cache.json"

def _load_geocode_cache():
    try:
        with open(_GEOCODE_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_geocode_cache(cache: dict):
    os.makedirs("./.tmp_runs", exist_ok=True)
    with open(_GEOCODE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def geocode_freeform(addr: str) -> Optional[Tuple[float, float]]:
    """Nominatim via geopy; cached locally. Returns None if offline."""
    try:
        cache = _load_geocode_cache()
        key = addr.strip().lower()
        if key in cache:
            v = cache[key]
            return (v["lat"], v["lon"])
        from geopy.geocoders import Nominatim
        geolocator = Nominatim(user_agent="asset-appraisal-agent")
        loc = geolocator.geocode(addr, timeout=10)
        if not loc:
            return None
        cache[key] = {"lat": float(loc.latitude), "lon": float(loc.longitude)}
        _save_geocode_cache(cache)
        return (float(loc.latitude), float(loc.longitude))
    except Exception:
        return None

def geohash_decode(s: str) -> Optional[Tuple[float, float]]:
    try:
        import geohash  # pip install python-geohash
        lat, lon = geohash.decode(s)
        return (float(lat), float(lon))
    except Exception:
        return None



# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────
ss = st.session_state
ss.setdefault("asset_stage", "login")
ss.setdefault("asset_logged_in", False)
ss.setdefault("asset_user", None)

# Stage caches
ss.setdefault("asset_raw_df", None)     # Stage 1 raw (after CSV/manual merge)
ss.setdefault("asset_evidence", [])     # evidence filenames (images/pdfs)
ss.setdefault("asset_anon_df", None)    # Stage 2 anonymized
ss.setdefault("asset_stage2_df", None)  # Stage 3 input (resolved source)
ss.setdefault("asset_ai_df", None)      # Stage 3 AI output
ss.setdefault("asset_selected_model", None)  # trained model path

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def anonymize_text_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = (
                out[col].astype(str)
                .apply(lambda x: re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "[EMAIL]", x))
            )
    return out

def quick_synth(rows: int = 150) -> pd.DataFrame:
    """Generate asset rows + finance metrics for demo/backup."""
    rng = np.random.default_rng(42)
    cities = [
        ("Hanoi", 21.0285, 105.8542),
        ("HCMC", 10.7769, 106.7009),
        ("Da Nang", 16.0544, 108.2022),
        ("Hue", 16.4637, 107.5909),
        ("Can Tho", 10.0452, 105.7469),
    ]
    df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, rows + 1)],
        "asset_id": [f"A{i:04d}" for i in range(1, rows + 1)],
        "asset_type": rng.choice(["House","Apartment","Car","Land","Factory"], rows),
        "age_years": rng.integers(1, 40, rows),
        "market_value": rng.integers(50_000, 2_000_000, rows),
        "condition_score": rng.uniform(0.6, 1.0, rows),
        "legal_penalty": rng.uniform(0.95, 1.0, rows),          # legal/title risk adj
        "employment_years": rng.integers(0, 30, rows),
        "credit_history_years": rng.integers(0, 25, rows),
        "delinquencies": rng.integers(0, 6, rows),
        "current_loans": rng.integers(0, 8, rows),
        "loan_amount": rng.integers(10_000, 200_000, rows),
        "customer_type": rng.choice(["bank","non-bank"], rows, p=[0.7,0.3]),
    })
    cdf = pd.DataFrame(cities, columns=["city","lat","lon"])
    df["city"] = rng.choice(cdf["city"], rows)
    df = df.merge(cdf, on="city", how="left")
    df["depreciation_rate"] = (1 - df["condition_score"]) * 100
    df["market_segment"] = np.where(df["market_value"] > 500_000, "High", "Mass")
    df["DTI"] = rng.uniform(0.05, 0.9, rows)
    df["LTV"] = np.clip(df["loan_amount"] / np.maximum(df["market_value"], 1), 0.05, 1.5)
    df["evidence_files"] = [[] for _ in range(rows)]
    return df

def synth_why_table() -> pd.DataFrame:
    return pd.DataFrame([
        {"Metric": "DTI", "Why": "Debt service relative to income — proxy for payability."},
        {"Metric": "LTV", "Why": "Loan vs asset value — proxy for collateral adequacy."},
        {"Metric": "condition_score", "Why": "Asset physical state impacts fair value/depreciation."},
        {"Metric": "legal_penalty", "Why": "Legal/title flags reduce realizable value."},
        {"Metric": "employment_years / credit_history_years", "Why": "Stability/track record."},
        {"Metric": "delinquencies / current_loans", "Why": "Current risk pressure."},
        {"Metric": "market_segment / city / lat,lon", "Why": "Market & location effects on pricing."},
    ])

# ─────────────────────────────────────────────
# DATAFRAME SELECTION (avoid boolean ambiguity)
# ─────────────────────────────────────────────
def first_nonempty_df(*candidates):
    """Return the first candidate that is a non-empty pandas DataFrame, else None."""
    for df in candidates:
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    return None



# ─────────────────────────────────────────────
# UNIVERSAL INGEST + NORMALIZATION HELPERS
# ─────────────────────────────────────────────
def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "dataset")).strip("_").lower()

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

def _read_any_table(uploaded_file) -> pd.DataFrame:
    """
    Robust reader for CSV/TSV/TXT/XLSX with encoding + delimiter fallback.
    Accepts Streamlit UploadedFile or a file-like object.
    """
    name = getattr(uploaded_file, "name", "").lower()

    # Excel first
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)

    # Text (CSV/TSV/TXT): try utf-8, then latin-1; sniff delimiter.
    raw = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    for enc in ("utf-8", "latin-1"):
        try:
            text = raw.decode(enc) if isinstance(raw, (bytes, bytearray)) else raw
            lines = text.splitlines()
            sample = "\n".join(lines[:5]) if lines else ""
            try:
                dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
                sep = getattr(dialect, "delimiter", ",")
            except Exception:
                sep = ","
            return pd.read_csv(io.StringIO(text), sep=sep)
        except Exception:
            continue
    # last resort
    return pd.read_csv(io.BytesIO(raw), engine="python")

def _normalize_for_agents(df: pd.DataFrame) -> pd.DataFrame:
    """
    Light normalization for credit/asset agents.
    Creates a consistent thin schema if columns exist; leaves extras intact.
    """
    out = df.copy()

    # alias map (extend freely)
    aliases = {
        "application_id": ["application_id", "app_id", "loan_id", "id", "request_id"],
        "asset_id":       ["asset_id", "property_id", "house_id", "assetid"],
        "asset_type":     ["asset_type", "type", "category"],
        "address":        ["address", "addr", "street", "location"],
        "city":           ["city", "town"],
        "state":          ["state", "province", "region"],
        "country":        ["country"],
        "price":          ["price", "value", "market_value", "listing_price", "sale_price"],
        "bedrooms":       ["bedrooms", "beds"],
        "bathrooms":      ["bathrooms", "baths"],
        "parking_space":  ["parking_space", "parking", "garage"],
        "title":          ["title", "name"],
    }

    # rename by first matching alias
    rename_map = {}
    cols = set(out.columns)
    for target, cands in aliases.items():
        for c in cands:
            if c in cols:
                rename_map[c] = target
                break
    out = out.rename(columns=rename_map)

    # ensure presence of common columns
    required = ["application_id", "asset_id", "asset_type", "address", "city", "state", "price"]
    for col in required:
        if col not in out.columns:
            out[col] = None

    # numeric coercions
    for col in ("price", "bedrooms", "bathrooms", "parking_space"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # provenance
    out["source_dataset"] = st.session_state.get("asset_intake_source_name", "uploaded")
    return out


# ─────────────────────────────────────────────
# THEME SYSTEM (Light/Dark CSS + map style)
# ─────────────────────────────────────────────
from textwrap import dedent

THEME_EXTRAS = {
    "light": {
        "success": "#16A34A",
        "warn": "#D97706",
        "danger": "#DC2626",
        "stripe": "#F1F5F9",
        "shadow": "0 6px 24px rgba(15,23,42,0.08)",
    },
    "dark": {
        "success": "#22C55E",
        "warn": "#FBBF24",
        "danger": "#F87171",
        "stripe": "#111827",
        "shadow": "0 8px 30px rgba(0,0,0,0.35)",
    },
}


def _theme_tokens(theme: str) -> dict[str, str]:
    pal = get_palette(theme)
    extra = THEME_EXTRAS.get(theme, THEME_EXTRAS["dark"])
    return {
        "bg": pal["bg"],
        "panel": pal["card"],
        "text": pal["text"],
        "muted": pal["subtext"],
        "primary": pal["accent"],
        "accent": pal["accent_alt"],
        "success": extra["success"],
        "warn": extra["warn"],
        "danger": extra["danger"],
        "stripe": extra["stripe"],
        "shadow": extra["shadow"],
    }


def _theme_css(theme: str) -> str:
    t = _theme_tokens(theme)
    return dedent(f"""
    <style>
      /* Fonts: Inter + JetBrains Mono */
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

      :root {{
        --bg: {t['bg']};
        --panel: {t['panel']};
        --text: {t['text']};
        --muted: {t['muted']};
        --primary: {t['primary']};
        --success: {t['success']};
        --warn: {t['warn']};
        --danger: {t['danger']};
        --accent: {t['accent']};
        --stripe: {t['stripe']};
        --shadow: {t['shadow']};
        --radius: 14px;
      }}

      html, body, .stApp {{
        background: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif !important;
      }}

      /* Panel-like boxes (use .left-box/.right-box or your custom containers) */
      .left-box, .right-box, .stExpander, .stTabs [data-baseweb="tab-highlight"] {{
        background: var(--panel) !important;
        border-radius: var(--radius);
        box-shadow: var(--shadow);
      }}

      /* Headings */
      h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
        color: var(--text) !important;
        font-weight: 700;
        letter-spacing: -0.01em;
      }}

      /* Buttons */
      .stButton>button, button[kind="primary"] {{
        background: var(--primary) !important;
        color: #fff !important;
        border-radius: 12px !important;
        border: none !important;
        box-shadow: 0 3px 12px rgba(37,99,235,0.35) !important;
      }}
      .stDownloadButton button {{
        background: var(--success) !important;
        color: #fff !important;
        border-radius: 12px !important;
        border: none !important;
        box-shadow: 0 3px 12px rgba(34,197,94,0.35) !important;
      }}

      /* Tables (dataframe) */
      .stDataFrame thead tr th {{
        background: var(--panel) !important;
        color: var(--muted) !important;
        font-weight: 600 !important;
      }}
      .stDataFrame tbody tr:nth-child(odd) {{
        background: var(--stripe) !important;
      }}

      /* Chips / small badges */
      .chip {{
        display:inline-block; padding:4px 10px; border-radius:999px;
        background: var(--panel); color: var(--muted); border:1px solid rgba(148,163,184,0.35);
      }}

      /* Code font */
      code, pre, .stCodeBlock, .st-emotion-cache-ffhzg2 {{
        font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
      }}
      
      /* NEW  Optional: hide sidebar without touching theme */
      [data-testid="stSidebar"], section[data-testid="stSidebar"], nav[data-testid="stSidebarNav"] {{
        display: none !important;
      }}
      [data-testid="stAppViewContainer"] {{
        margin-left: 0 !important;
        padding-left: 0 !important;
      }}
      
      
    </style>
    """)

def apply_theme(theme: str | None = None):
    """Inject shared Streamlit theme plus asset-specific tokens."""
    theme = theme or get_theme()
    apply_global_theme(theme)
    st.markdown(_theme_css(theme), unsafe_allow_html=True)


apply_theme()



# ─────────────────────────────────────────────
# MAP THEME HELPERS (Mapbox style + token + adapters)
# ─────────────────────────────────────────────
import os
import streamlit as st

def get_mapbox_token() -> str | None:
    """Find a Mapbox token from secrets or env. Return None if not set."""
    try:
        tok = st.secrets.get("MAPBOX_TOKEN")
    except Exception:
        tok = None
    if not tok:
        tok = os.environ.get("MAPBOX_TOKEN") or os.environ.get("MAPBOX_ACCESS_TOKEN")
    return tok or None


def plotly_map_style() -> str:
    """
    Return a Plotly-compatible map style.
    - Uses bright style in light mode even without a Mapbox token.
    - Falls back to CARTO 'positron' if Mapbox token not set.
    """
    theme = get_theme()
    token = get_mapbox_token()
    if token:
        return "light" if theme == "light" else "dark"
    else:
        # fallback to open CARTO tiles (bright)
        return "carto-positron" if theme == "light" else "carto-darkmatter"


def get_map_style() -> str:
    """
    Return a Mapbox style URL (for pydeck only).
    Light → bright, Dark → dark. Defaults to light for safety.
    """
    theme = get_theme()
    return "mapbox://styles/mapbox/light-v11" if theme == "light" else "mapbox://styles/mapbox/dark-v11"


def apply_plotly_mapbox_defaults():
    """Set Plotly's Mapbox token globally (if available)."""
    import plotly.express as px
    token = get_mapbox_token()
    if token:
        px.set_mapbox_access_token(token)
    else:
        st.info("ℹ️ Mapbox token not set — using free bright map style (carto-positron).")


def make_pydeck_view_state(lat=10.7769, lon=106.7009, zoom=10, pitch=0, bearing=0):
    import pydeck as pdk
    return pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom, pitch=pitch, bearing=bearing)


def pydeck_map_style() -> str:
    """pydeck uses the same Mapbox style URLs when a token is available."""
    return get_map_style()


# ============================================================================
# MAP GENERATION FUNCTIONS (from Real Estate Evaluator)
# ============================================================================

def _generate_ultra_3d_map(map_data, zone_data, assets_geojson, zones_geojson, theme="dark"):
    """Generate Ultra 3D map HTML with advanced features and theme support"""
    # Calculate center from data
    if map_data:
        avg_lat = sum(item["lat"] for item in map_data) / len(map_data)
        avg_lon = sum(item["lon"] for item in map_data) / len(map_data)
    else:
        avg_lat, avg_lon = 16.0, 107.5
    
    # Calculate stats
    total_properties = len(map_data)
    avg_market_price = sum(item.get("market_price", 0) for item in map_data) / total_properties if total_properties > 0 else 0
    zones_count = len(zone_data)
    
    # Theme colors - normalize theme to ensure it's "dark" or "light"
    theme_normalized = str(theme).lower() if theme else "dark"
    is_dark = theme_normalized == "dark"
    palette = get_palette(theme_normalized)
    
    # Theme-specific styling
    bg_gradient = "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)" if is_dark else "linear-gradient(135deg, #f5f7fa 0%, #e2e8f0 50%, #cbd5e1 100%)"
    panel_bg = "rgba(0,0,0,0.9)" if is_dark else "rgba(255,255,255,0.95)"
    text_color = "#ffffff" if is_dark else "#000000"
    map_style_url = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json" if is_dark else "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🏗️ Asset Appraisal Map</title>
        <script src='https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js'></script>
        <link href='https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css' rel='stylesheet' />
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
                background: {bg_gradient};
                min-height: 100vh;
                margin: 0;
                color: {text_color};
                overflow: hidden;
            }}
            #map-container {{
                position: relative;
                width: 100%;
                height: 800px;
                overflow: hidden;
            }}
            #map {{ width: 100%; height: 100%; }}
            #control-panel {{
                position: absolute;
                top: 20px;
                left: 20px;
                width: 280px;
                background: {panel_bg};
                backdrop-filter: blur(20px);
                border-radius: 20px;
                padding: 20px;
                z-index: 1000;
                box-shadow: 0 20px 50px rgba(0,0,0,0.6);
                max-height: calc(100% - 40px);
                overflow-y: auto;
                color: {text_color};
            }}
            #control-panel h1 {{
                font-size: 20px;
                margin-bottom: 10px;
                color: #00ff88;
                background: linear-gradient(90deg, #00ff88, #00d4ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .layer-controls {{
                background: {"rgba(255,255,255,0.05)" if is_dark else "rgba(0,0,0,0.05)"};
                border-radius: 15px;
                padding: 15px;
                margin: 15px 0;
            }}
            .layer-toggle {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 0;
                border-bottom: 1px solid {"rgba(255,255,255,0.1)" if is_dark else "rgba(0,0,0,0.1)"};
            }}
            .layer-toggle:last-child {{ border-bottom: none; }}
            .layer-toggle span {{
                color: {text_color};
            }}
            .toggle-switch {{
                width: 50px;
                height: 26px;
                background: {"#444" if is_dark else "#ccc"};
                border-radius: 13px;
                position: relative;
                cursor: pointer;
                transition: background 0.3s;
            }}
            .toggle-switch.active {{
                background: #00ff88;
            }}
            .toggle-switch::after {{
                content: '';
                position: absolute;
                top: 2px;
                left: 2px;
                width: 22px;
                height: 22px;
                background: white;
                border-radius: 50%;
                transition: transform 0.3s;
            }}
            .toggle-switch.active::after {{
                transform: translateX(24px);
            }}
            #stats-dashboard {{
                position: absolute;
                top: 20px;
                right: 20px;
                width: 280px;
                background: {panel_bg};
                border-radius: 20px;
                padding: 20px;
                backdrop-filter: blur(20px);
                z-index: 1000;
                color: {text_color};
            }}
            .stat-card {{
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 15px;
                margin: 10px 0;
                border-left: 4px solid #00ff88;
            }}
            .stat-value {{
                font-size: 24px;
                font-weight: bold;
                color: #00ff88;
            }}
            .stat-label {{
                font-size: 12px;
                opacity: 0.7;
                margin-top: 5px;
            }}
            #legend {{
                position: absolute;
                bottom: 20px;
                right: 20px;
                background: {panel_bg};
                border-radius: 20px;
                padding: 20px;
                backdrop-filter: blur(20px);
                z-index: 1000;
                color: {text_color};
            }}
            .legend-item {{
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 6px;
                font-size: 12px;
            }}
            .legend-color {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
            }}
            .popup-content {{
                font-family: inherit;
                min-width: 250px;
                color: #000;
            }}
            .popup-content h4 {{
                margin-bottom: 8px;
                color: #f5576c;
                font-size: 16px;
            }}
            .popup-content p {{
                margin: 4px 0;
                font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div id="map-container">
            <div id="map"></div>
            
            <!-- Control Panel -->
            <div id="control-panel">
                <h1>🏗️ Asset Appraisal Map</h1>
                <p style="font-size: 12px; opacity: 0.7;">Interactive 3D map with asset locations</p>
                
                <div class="layer-controls">
                    <h3 style="color: #00ff88; margin-bottom: 15px; font-size: 14px;">🎨 3D Layers</h3>
                    <div class="layer-toggle">
                        <span style="font-size: 12px;">3D District Zones</span>
                        <div class="toggle-switch active" id="toggle-zones"></div>
                    </div>
                    <div class="layer-toggle">
                        <span style="font-size: 12px;">Customer Assets</span>
                        <div class="toggle-switch active" id="toggle-assets"></div>
                    </div>
                    <div class="layer-toggle">
                        <span style="font-size: 12px;">Zone Labels</span>
                        <div class="toggle-switch active" id="toggle-labels"></div>
                    </div>
                </div>
            </div>
            
            <!-- Stats Dashboard -->
            <div id="stats-dashboard">
                <h3 style="color: #00ff88; margin-bottom: 15px; font-size: 16px;">📈 Asset Analytics</h3>
                <div class="stat-card">
                    <div class="stat-value" id="stat-total">{total_properties}</div>
                    <div class="stat-label">Total Assets</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-avg">${avg_market_price:,.0f}</div>
                    <div class="stat-label">Avg Value</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="stat-zones">{zones_count}</div>
                    <div class="stat-label">Price Zones</div>
                </div>
            </div>
            
            <!-- Price Legend -->
            <div id="legend">
                <h3 style="color: #00ff88; margin-bottom: 15px; font-size: 16px;">💰 Price Zones</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: #2d5016;"></div>
                    <span>$1,000 - $2,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #73b504;"></div>
                    <span>$2,000 - $3,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ffcc00;"></div>
                    <span>$3,000 - $4,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ff6600;"></div>
                    <span>$4,000 - $5,000</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ff0000;"></div>
                    <span>$5,000+</span>
                </div>
            </div>
        </div>
        
        <script>
            const assetsData = {json.dumps(assets_geojson)};
            const zonesData = {json.dumps(zones_geojson)};
            
            // Calculate bounding box from assets
            const calculateBounds = (features) => {{
                if (!features || features.length === 0) return null;
                let minLon = Infinity, maxLon = -Infinity;
                let minLat = Infinity, maxLat = -Infinity;
                features.forEach(f => {{
                    const [lon, lat] = f.geometry.coordinates;
                    minLon = Math.min(minLon, lon);
                    maxLon = Math.max(maxLon, lon);
                    minLat = Math.min(minLat, lat);
                    maxLat = Math.max(maxLat, lat);
                }});
                return [[minLon, minLat], [maxLon, maxLat]];
            }};
            
            // Map style based on theme
            const mapStyleUrl = {json.dumps(map_style_url)};
            const map = new maplibregl.Map({{
                container: 'map',
                style: mapStyleUrl,
                center: [{avg_lon}, {avg_lat}],
                zoom: 10,
                pitch: 60,
                bearing: -20,
                antialias: true
            }});
            
            map.addControl(new maplibregl.NavigationControl({{
                visualizePitch: true,
                showZoom: true,
                showCompass: true
            }}));
            
            map.on('load', () => {{
                // Add terrain
                map.addSource('terrain', {{
                    type: 'raster-dem',
                    url: 'https://demotiles.maplibre.org/terrain-tiles/tiles.json',
                    tileSize: 256
                }});
                
                map.addLayer({{
                    id: 'terrain-layer',
                    source: 'terrain',
                    type: 'hillshade',
                    paint: {{
                        'hillshade-shadow-color': '#000',
                        'hillshade-highlight-color': '#fff',
                        'hillshade-illumination-anchor': 'viewport'
                    }}
                }});
                
                // Add price zone polygons
                if (zonesData.features && zonesData.features.length > 0) {{
                    map.addSource('price-zones', {{
                        type: 'geojson',
                        data: zonesData
                    }});
                    
                    // 3D extruded zones
                    map.addLayer({{
                        id: 'district-zones',
                        source: 'price-zones',
                        type: 'fill-extrusion',
                        paint: {{
                            'fill-extrusion-color': ['get', 'color'],
                            'fill-extrusion-height': [
                                'interpolate',
                                ['linear'],
                                ['get', 'market_price'],
                                1000, 50,
                                2000, 100,
                                3000, 150,
                                4000, 200,
                                5000, 250
                            ],
                            'fill-extrusion-base': 0,
                            'fill-extrusion-opacity': 0.75,
                            'fill-extrusion-vertical-gradient': true
                        }}
                    }});
                    
                    map.addLayer({{
                        id: 'district-zone-outline',
                        source: 'price-zones',
                        type: 'line',
                        paint: {{
                            'line-color': '#ffffff',
                            'line-width': 1.5,
                            'line-opacity': 0.6
                        }}
                    }});
                    
                    // Zone labels
                    map.addLayer({{
                        id: 'zone-labels',
                        source: 'price-zones',
                        type: 'symbol',
                        layout: {{
                            'text-field': ['get', 'district'],
                            'text-font': ['Open Sans Bold'],
                            'text-size': 14,
                            'text-transform': 'uppercase',
                            'text-anchor': 'center',
                            'text-pitch-alignment': 'viewport'
                        }},
                        paint: {{
                            'text-color': '#ffffff',
                            'text-halo-color': '#00ff88',
                            'text-halo-width': 3,
                            'text-opacity': 0.9
                        }}
                    }});
                }}
                
                // Add customer assets
                map.addSource('customer-assets', {{
                    type: 'geojson',
                    data: assetsData
                }});
                
                // Load pin icon
                map.loadImage('https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png', (error, image) => {{
                    if (error) {{
                        // Fallback to circle if icon fails to load
                        map.addLayer({{
                            id: 'customer-pins',
                            type: 'circle',
                            source: 'customer-assets',
                            paint: {{
                                'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 8, 15, 15],
                                'circle-color': '#ff0000',
                                'circle-stroke-width': 3,
                                'circle-stroke-color': '#ffffff',
                                'circle-opacity': 0.9
                            }}
                        }});
                    }} else {{
                        map.addImage('red-pin', image);
                        map.addLayer({{
                            id: 'customer-pins',
                            type: 'symbol',
                            source: 'customer-assets',
                            layout: {{
                                'icon-image': 'red-pin',
                                'icon-size': 0.5,
                                'icon-anchor': 'bottom'
                            }}
                        }});
                    }}
                    
                    // Add price labels below pins
                    map.addLayer({{
                        id: 'customer-price-labels',
                        type: 'symbol',
                        source: 'customer-assets',
                        layout: {{
                            'text-field': ['concat', '$', ['to-string', ['round', ['get', 'value']]], ''],
                            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
                            'text-size': 11,
                            'text-offset': [0, 2.5],
                            'text-anchor': 'top'
                        }},
                        paint: {{
                            'text-color': '#ff0000',
                            'text-halo-color': '#ffffff',
                            'text-halo-width': 2
                        }}
                    }});
                    
                    // Auto-fit bounds to show all customer properties
                    const bounds = calculateBounds(assetsData.features);
                    if (bounds) {{
                        map.fitBounds(bounds, {{
                            padding: {{top: 50, bottom: 50, left: 50, right: 50}},
                            maxZoom: 12,
                            duration: 1500
                        }});
                    }}
                }});
                
                // Popups
                map.on('click', ['customer-pins', 'customer-price-labels'], (e) => {{
                    const props = e.features[0].properties;
                    new maplibregl.Popup()
                        .setLngLat([props.lon, props.lat])
                        .setHTML(`
                            <div class="popup-content">
                                <h4>${{props.name || props.asset_id || 'Asset'}}</h4>
                                <p style="color: #22c55e; font-weight: bold;">💰 Value: ${{props.value ? props.value.toLocaleString() : 'N/A'}}</p>
                                <p>📍 ${{props.city || 'Unknown'}} • ${{props.district || 'N/A'}}</p>
                                <p>🏘️ ${{props.asset_type || 'Unknown'}}</p>
                                <p>🏠 Area: ${{props.area_sqm || 'N/A'}} sqm</p>
                            </div>
                        `)
                        .addTo(map);
                }});
                
                map.on('mouseenter', ['customer-pins', 'customer-price-labels'], () => {{
                    map.getCanvas().style.cursor = 'pointer';
                }});
                
                map.on('mouseleave', ['customer-pins', 'customer-price-labels'], () => {{
                    map.getCanvas().style.cursor = '';
                }});
                
                if (zonesData.features && zonesData.features.length > 0) {{
                    map.on('click', 'district-zones', (e) => {{
                        const props = e.features[0].properties;
                        new maplibregl.Popup()
                            .setLngLat(e.lngLat)
                            .setHTML(`
                                <div class="popup-content">
                                    <h4>${{props.district}}</h4>
                                    <p style="color: #22c55e; font-weight: bold;">💰 Market: ${{props.market_price ? props.market_price.toLocaleString() : 'N/A'}}/sqm</p>
                                    <p>📍 ${{props.city}}</p>
                                    <p>📊 Range: ${{props.price_range ? props.price_range.replace('_', ' ').toUpperCase() : 'N/A'}}</p>
                                </div>
                            `)
                            .addTo(map);
                    }});
                }}
                
                // Toggle controls
                const toggleZones = document.getElementById('toggle-zones');
                if (toggleZones) {{
                    toggleZones.onclick = function() {{
                        const visibility = map.getLayoutProperty('district-zones', 'visibility');
                        map.setLayoutProperty('district-zones', 'visibility', visibility === 'none' ? 'visible' : 'none');
                        if (map.getLayer('district-zone-outline')) {{
                            map.setLayoutProperty('district-zone-outline', 'visibility', visibility === 'none' ? 'visible' : 'none');
                        }}
                        this.classList.toggle('active');
                    }};
                }}
                
                const toggleAssets = document.getElementById('toggle-assets');
                if (toggleAssets) {{
                    toggleAssets.onclick = function() {{
                        const visibility = map.getLayoutProperty('customer-pins', 'visibility');
                        map.setLayoutProperty('customer-pins', 'visibility', visibility === 'none' ? 'visible' : 'none');
                        map.setLayoutProperty('customer-price-labels', 'visibility', visibility === 'none' ? 'visible' : 'none');
                        this.classList.toggle('active');
                    }};
                }}
                
                const toggleLabels = document.getElementById('toggle-labels');
                if (toggleLabels) {{
                    toggleLabels.onclick = function() {{
                        if (map.getLayer('zone-labels')) {{
                            const visibility = map.getLayoutProperty('zone-labels', 'visibility');
                            map.setLayoutProperty('zone-labels', 'visibility', visibility === 'none' ? 'visible' : 'none');
                            this.classList.toggle('active');
                        }}
                    }};
                }}
            }});
        </script>
    </body>
    </html>
    """



# ─────────────────────────────────────────────
# AGENT DISCOVERY & PROBE
# ─────────────────────────────────────────────
def _safe_get_json(url: str, timeout: int = 8):
    try:
        r = requests.get(url, timeout=timeout)
        if r.ok:
            try:
                return True, r.json()
            except Exception as e:
                return False, f"parse error: {e}\nBody:\n{r.text[:2000]}"
        return False, f"{r.status_code} {r.reason}\nBody:\n{r.text[:2000]}"
    except Exception as e:
        return False, f"request error: {e}"

def discover_asset_agents() -> list[str]:
    """Try common discovery endpoints and extract agent ids. Cache in session."""
    cached = st.session_state.get("asset_agent_ids")
    if isinstance(cached, list) and cached:
        return cached

    candidates = []

    # 1) /v1/agents (prefer)
    ok, data = _safe_get_json(f"{API_URL}/v1/agents")
    if ok:
        try:
            if isinstance(data, dict) and "agents" in data:
                items = data["agents"]
                if isinstance(items, list):
                    for it in items:
                        if isinstance(it, str):
                            candidates.append(it)
                        elif isinstance(it, dict):
                            aid = it.get("id") or it.get("name") or it.get("agent") or it.get("slug")
                            if aid: candidates.append(aid)
            elif isinstance(data, list):
                for it in data:
                    if isinstance(it, str):
                        candidates.append(it)
                    elif isinstance(it, dict):
                        aid = it.get("id") or it.get("name")
                        if aid: candidates.append(aid)
        except Exception:
            pass

    # 2) /v1/agents/list (alt)
    if not candidates:
        ok2, data2 = _safe_get_json(f"{API_URL}/v1/agents/list")
        if ok2:
            try:
                if isinstance(data2, dict):
                    for k in ("agents", "data", "items"):
                        if k in data2 and isinstance(data2[k], list):
                            for it in data2[k]:
                                if isinstance(it, str):
                                    candidates.append(it)
                                elif isinstance(it, dict):
                                    aid = it.get("id") or it.get("name")
                                    if aid: candidates.append(aid)
                elif isinstance(data2, list):
                    for it in data2:
                        if isinstance(it, str):
                            candidates.append(it)
                        elif isinstance(it, dict):
                            aid = it.get("id") or it.get("name")
                            if aid: candidates.append(aid)
            except Exception:
                pass

    # 3) /v1/health (sometimes lists agents)
    if not candidates:
        ok3, data3 = _safe_get_json(f"{API_URL}/v1/health")
        if ok3 and isinstance(data3, dict):
            for k in ("agents", "services", "available_agents"):
                val = data3.get(k)
                if isinstance(val, list):
                    for it in val:
                        if isinstance(it, str):
                            candidates.append(it)
                        elif isinstance(it, dict):
                            aid = it.get("id") or it.get("name")
                            if aid: candidates.append(aid)

    discovered = [c for c in dict.fromkeys(candidates) if c]  # de-dupe
    if not discovered:
        discovered = ASSET_AGENT_IDS[:]  # fallback to env/defaults

    st.session_state["asset_agent_ids"] = discovered
    return discovered

def probe_api() -> dict:
    """Collect quick diagnostics for UI."""
    diag = {}
    for path in ("/v1/health", "/v1/agents", "/v1/agents/list"):
        ok, data = _safe_get_json(f"{API_URL}{path}")
        diag[path] = data if ok else {"error": data}
    diag["API_URL"] = API_URL
    diag["discovered_agents"] = discover_asset_agents()
    return diag

# NEW: run_id extractor for various API payload shapes
def _extract_run_id(obj) -> str | None:
    """Find a run_id in a nested dict/list API response."""
    if isinstance(obj, dict):
        rid = obj.get("run_id")
        if isinstance(rid, str) and rid:
            return rid
        for k in ("data", "meta", "result", "payload"):
            v = obj.get(k)
            if isinstance(v, dict):
                rid = v.get("run_id")
                if isinstance(rid, str) and rid:
                    return rid
    elif isinstance(obj, list):
        for it in obj:
            rid = _extract_run_id(it)
            if rid:
                return rid
    return None

def try_run_asset_agent(csv_bytes: bytes, form_fields: dict, timeout_sec: int = 180):
    """
    Discover agent ids, then try each. Rebuild multipart for each attempt.
    Preferred: use run_id to GET merged CSV and DataFrame it.
    Fallback: normalize 'result' only (not whole JSON).

    Returns (ok: bool, DataFrame | error_string)
    """
    agent_ids = discover_asset_agents()
    errors = []
    for agent_id in agent_ids:
        files = {"file": ("asset_verified.csv", io.BytesIO(csv_bytes), "text/csv")}
        url = f"{API_URL}/v1/agents/{agent_id}/run"
        try:
            resp = requests.post(url, files=files, data=form_fields, timeout=timeout_sec)
        except Exception as e:
            errors.append(f"[{agent_id}] request error: {e}")
            continue

        if resp.ok:
            body_text = resp.text[:4000]
            try:
                payload = resp.json()
            except Exception as e:
                errors.append(f"[{agent_id}] parse error: {e}\nBody:\n{body_text}")
                continue

            rid = _extract_run_id(payload)
            if rid:
                # Preferred: fetch merged CSV
                try:
                    r_csv = requests.get(f"{API_URL}/v1/runs/{rid}/report?format=csv", timeout=60)
                    if r_csv.ok:
                        df = pd.read_csv(io.BytesIO(r_csv.content))
                        st.session_state["asset_last_run_id"] = rid
                        st.session_state["asset_last_runner"] = ((payload.get("meta") or {}).get("runner_used"))
                        return True, df
                    else:
                        errors.append(
                            f"[{agent_id}] report GET {r_csv.status_code} {r_csv.reason} for run_id={rid}\n"
                            f"Body:\n{r_csv.text[:2000]}"
                        )
                except Exception as e:
                    errors.append(f"[{agent_id}] report GET error for run_id={rid}: {e}")

            # Fallback: try to render just 'result'
            result_part = payload.get("result")
            if isinstance(result_part, list):
                try:
                    df = pd.json_normalize(result_part)
                    return True, df
                except Exception as e:
                    errors.append(f"[{agent_id}] fallback normalize error: {e}\nBody:\n{body_text}")
            elif isinstance(result_part, dict):
                try:
                    df = pd.json_normalize(result_part)
                    return True, df
                except Exception as e:
                    errors.append(f"[{agent_id}] fallback normalize error: {e}\nBody:\n{body_text}")
            else:
                errors.append(f"[{agent_id}] no run_id and empty/unknown 'result'.\nBody:\n{body_text}")
        else:
            errors.append(f"[{agent_id}] {resp.status_code} {resp.reason}\nBody:\n{resp.text[:2000]}")

    combined = "All agent attempts failed (discovered=" + ", ".join(agent_ids) + "):\n" + "\n\n".join(errors)
    if errors and all(
        any(token in err.lower() for token in ("connection refused", "failed to establish", "errno 111"))
        for err in errors
    ):
        combined += (
            "\n\nHint: the backend API on port 8090 is not reachable. "
            "Start your agent server (uvicorn/fastapi) and rerun this stage."
        )
    return False, combined


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
if ss["asset_stage"] == "login" and not ss["asset_logged_in"]:
    render_nav_bar_app()
    st.title("🔐 Login to AI Asset Appraisal Platform")
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        user = st.text_input("Username", placeholder="e.g. dzoan")
    with c2:
        email = st.text_input("Email", placeholder="e.g. dzoan@demo.local")
    with c3:
        pwd = st.text_input("Password", type="password", placeholder="Enter any password")
    if st.button("Login", key="btn_asset_login", use_container_width=True):
        if (user or "").strip() and (email or "").strip():
            ss["asset_user"] = {
                "name": user.strip(),
                "email": email.strip(),
                "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ fixed
            }
            ss["asset_logged_in"] = True
            ss["asset_stage"] = "asset_flow"
            st.rerun()
        else:
            st.error("⚠️ Please fill all fields before continuing.")
    st.stop()


# ─────────────────────────────────────────────
# WORKFLOW (A→G)
# ─────────────────────────────────────────────
if ss.get("asset_logged_in") and ss.get("asset_stage") in ("asset_flow", "asset_agent"):
    render_nav_bar_app()
    st.title("🏛️ Asset Appraisal Agent")
    st.caption(
        "A→G pipeline — Intake → Privacy → Valuation → Policy → Human Review → Model Training → Reporting "
        f"| 👋 {ss['asset_user']['name']}"
    )

    asset_ai_minutes = _coerce_minutes(ss.get("asset_avg_time"), 22.0)

    render_operator_banner(
        operator_name=ss.get("asset_user", {}).get("name", "Operator"),
        title="Asset Appraisal Command",
        summary="Automate collateral intake, anonymization, valuation, and policy checks with AI copilots.",
        bullets=[
            "Unify intake sources (CSV, HF, Kaggle) and auto-enrich with geospatial context.",
            "Apply FMV modeling + haircut & LTV policy thresholds before human review.",
            "Capture reviewer feedback to retrain valuation models and improve reports.",
        ],
        metrics=[
            {
                "label": "Avg AI Turnaround",
                "value": ss.get("asset_avg_time") or f"{asset_ai_minutes:.0f} min",
                "delta": "-5 min vs last week",
                "delta_color": "#60a5fa",
                "color": "#60a5fa",
                "percent": min(1.0, asset_ai_minutes / 50.0),
                "context": "AI valuation cycle time",
            },
            {
                "label": "Assets Pending Valuation",
                "value": ss.get("asset_pending_cases"),
                "delta": "+4 vs prior cycle",
                "delta_color": "#34d399",
                "color": "#34d399",
                "percent": min(1.0, ss.get("asset_pending_cases", 0) / 40.0),
                "context": "Manual backlog avg: 35",
            },
            {
                "label": "Flagged Risk Cases",
                "value": ss.get("asset_flagged_cases"),
                "delta": "+1 escalation",
                "delta_color": "#f87171",
                "color": "#f87171",
                "percent": min(1.0, ss.get("asset_flagged_cases", 0) / 12.0),
                "context": "Human avg: 6 risk flags",
            },
        ],
        icon="🏛️",
    )
    # ─────────────────────────────────────────
    # TABS (How-To + A..H) — Live tabs
    # ─────────────────────────────────────────
    tabHow, tabA, tabB, tabC, tabD, tabE, tabF, tabG, tabH, tabFeedback = st.tabs([
        "📘 How-To",
        "🟦 A) Intake & Evidence",
        "🟩 B) Privacy & Features",
        "🟨 C) Valuation & Verification",
        "🟧 D) Policy & Decision",
        "🟪 E) Human Review & Feedback",
        "🟫 F) Model Training & Promotion",
        "🟫 G) Deployment & Export 🚀",     # ✅ corrected label (was double F)
        "⬜ H) Reporting & Handoff 🧾",
        "🗣️ Feedback"
    ])

    with tabHow:
        st.title("📘 How to Use This Agent")
        st.markdown("""
### What
An AI-powered agent that performs collateral and asset valuation automatically using market data, machine learning, and verification logic.

### Goal
To provide instant, data-driven, and consistent asset valuations for credit, insurance, or regulatory use.

### How
1. Import property or asset data from CSV, Kaggle, or Hugging Face sources.
2. The agent anonymizes and enriches data, extracts geospatial and condition features, and predicts fair market value (FMV).
3. Applies haircut and LTV policy thresholds to derive realizable value.
4. Verifies ownership, encumbrances, and generates professional reports.

### So What (Benefits)
- Cuts appraisal turnaround from days to minutes.
- Standardizes valuations across asset classes.
- Increases confidence with explainable AI valuations.
- Ensures data consistency and legal traceability.

### What Next
1. Run a test with your asset dataset or public examples.
2. Contact our team to customize valuation rules, haircut logic, and report templates.
3. Once validated, integrate the agent into your production credit or appraisal systems to automate end-to-end asset evaluation.
        """)


    # Runtime tip
    st.caption(
        "📘 Tip: Move sequentially from A→G or revisit individual stages. "
        "If a stage reports missing data, rerun the previous one or load demo data."
    )

    with tabFeedback:
        render_feedback_tab("🏦 Asset Appraisal Agent")

else:
    st.warning("Please log in first to access the Asset Appraisal workflow.")


# ─────────────────────────────────────────
# 🟦 STAGE A — INTAKE & EVIDENCE
# ─────────────────────────────────────────
with tabA:
    import io, os, json, hashlib, pandas as pd
    from datetime import datetime, timezone
    
    
    ss = st.session_state  # ✅ make 'ss' available in this scope
    st.subheader("A. Intake & Evidence")
    st.caption("Steps: (1) Upload / Import, (2) Normalize, (3) Generate unified intake CSV")

    # ─────────────────────────────────────────
    # 📘 Quick User Guide (updated)
    # ─────────────────────────────────────────
    with st.expander("📘 Quick User Guide", expanded=False):
        st.markdown("""
        **Goal:** Collect, normalize, and unify all asset-related data before appraisal.

        **1️⃣ Upload Your Data**
        - Upload **field agent reports**, **loan lists with collateral**, and **legal property documents**.
        - Supported: `.csv`, `.xlsx`, `.zip` (evidence images/docs).

        **2️⃣ Import Open Data**
        - Search **Kaggle** or **Hugging Face** for relevant valuation datasets.
        - You can mix public + internal uploads — AI will normalize columns.

        **3️⃣ Normalize**
        - After upload/import, click **"Normalize Data"** to merge and standardize features.
        - Output: `intake_table.csv` ready for Stage B (Anonymization).

        **4️⃣ Generate Synthetic Data**
        - If no input data is available, the AI can synthesize a demo dataset representing:
          `asset_id, asset_type, city, market_value, loan_amount, legal_source, condition_score`.

        **5️⃣ Output**
        - A unified CSV file is produced → download or proceed directly to **Stage B**.
        """)

    # ─────────────────────────────────────────
    # (A.1) UPLOAD ZONE — Human Inputs
    # ─────────────────────────────────────────
    st.markdown("### 📤 Upload Data Files (Field Agents / Loans / Legal Docs)")
    uploaded_files = st.file_uploader(
        "Upload multiple files",
        type=["csv", "xlsx", "zip"],
        accept_multiple_files=True,
        key="asset_upload_files"
    )

    uploaded_dfs = []
    if uploaded_files:
        for f in uploaded_files:
            try:
                if f.name.endswith(".csv"):
                    df = pd.read_csv(f)
                elif f.name.endswith(".xlsx"):
                    df = pd.read_excel(f)
                else:
                    st.info(f"📦 Skipping non-tabular file: {f.name}")
                    continue
                st.success(f"✅ Loaded `{f.name}` ({len(df)} rows, {len(df.columns)} cols)")
                uploaded_dfs.append(df)
            except Exception as e:
                st.error(f"❌ Failed to read {f.name}: {e}")


    # ──New  global runs dir (shared across stages) ─────────────────
    RUNS_DIR = os.path.abspath("./.tmp_runs")
    os.makedirs(RUNS_DIR, exist_ok=True)
    
   

    # ─────────────────────────────────────────
    # (A.2) PUBLIC DATASETS — Kaggle / HF / OpenML
    # ─────────────────────────────────────────
    st.markdown("### 🌍 Import Public Datasets (Kaggle / Hugging Face / OpenML / Portals)")

    # keep a place to persist search results across reruns
    ss.setdefault("kaggle_search_df", pd.DataFrame())

    src = st.selectbox(
        "Select source",
        ["Kaggle (API)", "Hugging Face", "OpenML", "Public Domain Portals"],
        key="asset_pubsrc"
    )
    query = st.text_input("Search keywords", "house prices real estate valuation", key="asset_pubquery")

    # helpers
    def _ts():
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    
    def _safe_read_csv(fp: str) -> pd.DataFrame:
        """
        Robust CSV reader:
        - Tries multiple encodings (utf-8, utf-8-sig, cp1252, latin-1)
        - Tries common separators
        - Skips bad rows rather than crashing
        """
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
        seps = [",", ";", "\t", "|"]

        last_err = None
        for enc in encodings:
            for sep in seps:
                try:
                    df_try = pd.read_csv(
                        fp,
                        encoding=enc,
                        sep=sep,
                        engine="python",
                        on_bad_lines="skip",   # pandas >=1.3
                    )
                    # Require at least 2 columns to consider it valid
                    if df_try.shape[1] >= 2:
                        return df_try
                except Exception as e:
                    last_err = e
                    continue

        # Final fallback: read bytes, decode with latin-1 replacement, then parse in-memory
        try:
            with open(fp, "rb") as f:
                raw = f.read()
            text = raw.decode("latin-1", errors="replace")
            for sep in seps:
                try:
                    return pd.read_csv(
                        io.StringIO(text),
                        sep=sep,
                        engine="python",
                        on_bad_lines="skip",
                    )
                except Exception:
                    pass
        except Exception as e:
            last_err = e

        raise RuntimeError(f"Could not parse CSV with common encodings/separators. Last error: {last_err}")

    


    # Kaggle search
    if st.button("🔎 Search dataset", key="btn_asset_pubsearch"):
        with st.spinner("Searching datasets..."):
            try:
                if src == "Kaggle (API)":
                    import subprocess, io
                    cmd = ["kaggle", "datasets", "list", "-s", query, "-v"]  # -v => CSV output
                    out = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if out.returncode != 0:
                        st.error(f"Kaggle CLI failed: {out.stderr.strip() or out.stdout.strip()}")
                        st.info("💡 Ensure ~/.kaggle/kaggle.json exists and has chmod 600.")
                        ss["kaggle_search_df"] = pd.DataFrame()
                    else:
                        df_pub = pd.read_csv(io.StringIO(out.stdout))
                        keep = [c for c in ["ref","title","size","lastUpdated","downloadCount","voteCount","usabilityRating"] if c in df_pub.columns]
                        ss["kaggle_search_df"] = df_pub[keep]
                        st.success("✅ Kaggle API results shown.")
                elif src == "Hugging Face":
                    from huggingface_hub import list_datasets
                    results = list_datasets(search=query)
                    df_pub = pd.DataFrame([{"Dataset": r.id, "Tags": ", ".join(r.tags)} for r in results[:50]])
                    st.dataframe(df_pub, use_container_width=True, hide_index=True)
                    st.success("✅ Hugging Face datasets retrieved.")
                elif src == "OpenML":
                    st.markdown(f"[📊 OpenML Search ↗️](https://www.openml.org/search?type=data&q={query})")
                elif src == "Public Domain Portals":
                    st.markdown("""
                    - [🌎 data.gov](https://www.data.gov/)
                    - [🇪🇺 data.europa.eu](https://data.europa.eu/)
                    - [🇸🇬 data.gov.sg](https://data.gov.sg/)
                    - [🇻🇳 data.gov.vn](https://data.gov.vn/)
                    """)
            except Exception as e:
                st.error(f"Search failed: {e}")

    # If we have Kaggle results, show table + import controls
    if src == "Kaggle (API)" and not ss["kaggle_search_df"].empty:
        st.dataframe(ss["kaggle_search_df"], use_container_width=True, hide_index=True)

        with st.expander("⬇️ Import Selected Kaggle Dataset", expanded=True):
            refs = ss["kaggle_search_df"]["ref"].astype(str).tolist()
            selected_ref = st.selectbox("Choose a dataset (ref)", refs, key="asset_kaggle_ref")

            kag_dir = os.path.join(RUNS_DIR, "kaggle")
            os.makedirs(kag_dir, exist_ok=True)
            safe_ref = re.sub(r"[^a-zA-Z0-9._/-]+", "_", selected_ref)
            safe_ref_for_file = safe_ref.replace("/", "__")
            dest = os.path.join(kag_dir, safe_ref_for_file)
            os.makedirs(dest, exist_ok=True)

            # Optional: let user set a server-side save folder (relative to project root)
            st.markdown("**Optional server-side save folder (relative to project root)**")
            default_svdir = os.path.join(RUNS_DIR, "kaggle_exports")
            svdir = st.text_input(
                "Save to folder (server-side)",
                value=default_svdir,
                key="asset_kaggle_svdir",
                help="This saves on the server/WSL side (not your desktop). Use Download button below for local Save As."
            )

            # Main import button
            if st.button("📥 Download & Import Selected", key="btn_asset_kaggle_dl", use_container_width=True):
                try:
                    import subprocess
                    cmd = ["kaggle", "datasets", "download", "-d", selected_ref, "-p", dest, "--unzip"]
                    r = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if r.returncode != 0:
                        raise RuntimeError(r.stderr.strip() or r.stdout.strip())

                    csvs = [f for f in os.listdir(dest) if f.lower().endswith(".csv")]
                    if not csvs:
                        raise FileNotFoundError("No CSV found in the downloaded archive.")
                    fp = os.path.join(dest, csvs[0])

                    # Load & stash for downstream stages + download button
                    df_imp = _safe_read_csv(fp)
                    ss["asset_intake_df"] = df_imp

                    # Save a unified copy with timestamp in RUNS_DIR
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                    uni_fp = os.path.join(RUNS_DIR, f"intake_table.{ts}.csv")
                    df_imp.to_csv(uni_fp, index=False)

                    st.success(f"✅ Imported {len(df_imp):,} rows from `{selected_ref}`")
                    st.caption(f"Saved unified intake copy: `{uni_fp}`")
                    st.dataframe(df_imp.head(100), use_container_width=True)

                    # ── NEW: Local Download (browser) with dataset-name.csv ──
                    st.markdown("#### 💾 Download")
                    default_fname = f"{safe_ref_for_file}.csv"
                    st.download_button(
                        label="⬇️ Download CSV",
                        file_name=default_fname,
                        data=df_imp.to_csv(index=False).encode("utf-8"),
                        mime="text/csv",
                        key="asset_kaggle_download"
                    )

                    # ── NEW: Optional server-side save with user folder ──
                    st.markdown("#### 🗂️ Save on Server (optional)")
                    # sanitize: keep within project root
                    project_root = os.path.abspath(os.path.join(RUNS_DIR, "..", ".."))
                    svdir_abs = os.path.abspath(svdir)
                    if not svdir_abs.startswith(project_root):
                        st.warning("⚠️ Path is outside project root; resetting to default exports folder.")
                        svdir_abs = os.path.abspath(default_svdir)

                    os.makedirs(svdir_abs, exist_ok=True)
                    save_name = f"{safe_ref_for_file}.csv"
                    server_save_path = os.path.join(svdir_abs, save_name)

                    if st.button("💽 Save CSV on Server", key="btn_asset_kaggle_save_server"):
                        try:
                            df_imp.to_csv(server_save_path, index=False)
                            rel_path = os.path.relpath(server_save_path, start=project_root)
                            st.success(f"✅ Saved on server: `{server_save_path}`")
                            st.caption(f"(Relative to project root: ./{rel_path})")
                        except Exception as e:
                            st.error(f"Server save failed: {e}")

                except Exception as e:
                    st.error(f"Import failed: {e}")
                    st.info("Tip: check Kaggle auth and try another dataset.")

    
   

    # Quick HF import (optional direct load)
    if src == "Hugging Face":
        st.markdown("#### Or load directly by repo id")
        hf_repo = st.text_input("🤗 Dataset repo (e.g. uciml/real-estate-valuation)", value="uciml/real-estate-valuation", key="asset_hf_repo")
        if st.button("📥 Load from HF", key="btn_asset_hf_load", use_container_width=True):
            try:
                from datasets import load_dataset
                ds = load_dataset(hf_repo)
                split = next(iter(ds.keys()))
                df_imp = ds[split].to_pandas()
                ss["asset_intake_df"] = df_imp
                uni_fp = os.path.join(RUNS_DIR, f"intake_table.{_ts()}.csv")
                df_imp.to_csv(uni_fp, index=False)
                st.success(f"✅ Loaded {len(df_imp):,} rows from {hf_repo} (split: {split})")
                st.caption(f"Saved unified intake copy: `{uni_fp}`")
                st.dataframe(df_imp.head(100), use_container_width=True)
            except Exception as e:
                st.error(f"HF load failed: {e}")

    st.divider()
    
    
    # ─────────────────────────────────────────
    # (A.3) NORMALIZE & GENERATE UNIFIED CSV
    # ─────────────────────────────────────────
    st.markdown("### 🧹 Normalize & Combine All Inputs")

    # ---------- helpers ----------
    import io, csv, re
    from pathlib import Path

    def _slug(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "dataset")).strip("_").lower()

    def _read_any_table(uploaded_file) -> pd.DataFrame:
        """Robust reader for CSV/TSV/TXT/XLSX with encoding + delimiter fallback."""
        name = uploaded_file.name.lower()

        # Excel
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(uploaded_file)

        # Text (CSV/TSV/TXT): try utf-8 then latin-1; sniff delimiter
        raw = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
        for enc in ("utf-8", "latin-1"):
            try:
                text = raw.decode(enc) if isinstance(raw, (bytes, bytearray)) else raw
                head = "\n".join(text.splitlines()[:10]) or text
                try:
                    dialect = csv.Sniffer().sniff(head)
                    sep = dialect.delimiter
                except Exception:
                    sep = ","
                return pd.read_csv(io.StringIO(text), sep=sep)
            except Exception:
                continue
        # last resort (python engine)
        return pd.read_csv(io.BytesIO(raw), engine="python")

    # ---------- optional upload right here ----------
    st.markdown("#### ⬆️ Optional: Upload a CSV/TSV/TXT/XLSX to normalize")
    uploaded = st.file_uploader(
        "Upload a dataset file (or skip if you already imported via Kaggle/HF).",
        type=["csv", "tsv", "txt", "xlsx"],
        key="norm_upload_once",
        accept_multiple_files=False
    )

    if uploaded is not None:
        try:
            df_up = _read_any_table(uploaded)
            ss["asset_intake_df"] = df_up
            ss["last_dataset_name"] = Path(uploaded.name).stem  # remember original name
            st.success(f"✅ Loaded {len(df_up):,} rows from **{uploaded.name}**")
            st.dataframe(df_up.head(100), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not read file: {e}")

    # ---------- normalization source ----------
    df_src = ss.get("asset_intake_df")
    # Best-effort name priority: last_dataset_name (Kaggle/HF/upload) → fallback
    base_name = _slug(ss.get("last_dataset_name") or ss.get("asset_intake_source_name") or "dataset")

    if df_src is None or len(df_src) == 0:
        st.info("Upload/import a dataset first (Kaggle/HF/Upload), then come back to normalize.")
    else:
        with st.expander("⚙️ Normalization options", expanded=False):
            drop_dupes = st.checkbox("Drop duplicate rows", value=True)
            trim_whitespace = st.checkbox("Trim whitespace in string columns", value=True)
            lower_columns = st.checkbox("Lowercase column names", value=True)

        def _normalize(df: pd.DataFrame) -> pd.DataFrame:
            out = df.copy()
            # 1) basic cleanup
            if lower_columns:
                out.columns = [c.strip().lower() for c in out.columns]
            if trim_whitespace:
                for c in out.select_dtypes(include=["object"]).columns:
                    out[c] = out[c].astype(str).str.strip()
            if drop_dupes:
                out = out.drop_duplicates().reset_index(drop=True)
            # (Optional) add any schema harmonization here later
            return out

        if st.button("🧪 Normalize & Generate Unified CSV", key="btn_normalize", use_container_width=True):
            norm_df = _normalize(df_src)

            # Ensure output dir
            norm_dir = os.path.join(RUNS_DIR, "normalized")
            os.makedirs(norm_dir, exist_ok=True)

            # Build file name: <original>-Normalized.csv   (slug-safe base_name)
            norm_name = f"{base_name}-Normalized.csv"
            norm_path = os.path.join(norm_dir, norm_name)

            # Save to disk with utf-8-sig (friendlier for Excel)
            norm_df.to_csv(norm_path, index=False, encoding="utf-8-sig")

            # Prepare one bytes blob for both download buttons
            _norm_bytes = norm_df.to_csv(index=False).encode("utf-8-sig")
            _rows, _cols = len(norm_df), len(norm_df.columns)
            _size_kb = max(1, int(len(_norm_bytes) / 1024))
            _norm_file_only = Path(norm_path).name

            # Sticky banner: filename • rows×cols • size
            st.markdown(
                f"""
                <div style="
                    position: sticky;
                    top: 64px;
                    z-index: 50;
                    background: rgba(16,185,129,0.10);
                    border: 1px solid #10b981;
                    padding: 12px 16px;
                    border-radius: 12px;
                    margin: 8px 0 14px 0;
                ">
                <b>✅ Normalized CSV:</b> <code>{_norm_file_only}</code>
                &nbsp;•&nbsp; {_rows:,} rows × {_cols} cols &nbsp;•&nbsp; {_size_kb} KB
                </div>
                """,
                unsafe_allow_html=True
            )

            # BIG centered primary download button (TOP)
            cL, cM, cR = st.columns([1, 2.5, 1])
            with cM:
                st.download_button(
                    "⬇️  Download Normalized CSV",
                    data=_norm_bytes,
                    file_name=_norm_file_only,
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                    key="dl_norm_top"
                )

            # Copyable saved path
            st.text_input("Saved to (server path)", norm_path, disabled=True, label_visibility="collapsed")

            # Preview table
            st.dataframe(norm_df.head(100), use_container_width=True, hide_index=True)

            # BIG centered primary download button (BOTTOM)
            cL2, cM2, cR2 = st.columns([1, 2.5, 1])
            with cM2:
                st.download_button(
                    "⬇️  Download Normalized CSV",
                    data=_norm_bytes,
                    file_name=_norm_file_only,
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                    key="dl_norm_bottom"
                )

    # # ─────────────────────────────────────────
    # # (A.1b) QUICK START — Generate Synthetic Data (always visible here)
    # # ─────────────────────────────────────────
    # st.markdown("### 🎲 Quick Start: Generate Synthetic Data")
    # c_syn1, c_syn2 = st.columns([2, 1])
    # with c_syn1:
    #     nrows = st.slider("Number of synthetic rows", 20, 1000, 150, step=10, key="slider_synth_rows_A_quick")
    # with c_syn2:
    #     if st.button("🚀 Generate Synthetic Dataset Now", key="btn_generate_synth_A_quick", use_container_width=True):
    #         try:
    #             df_synth = quick_synth(nrows)
    #             ss["asset_intake_df"] = df_synth
    #             os.makedirs("./.tmp_runs", exist_ok=True)
    #             synth_path = f"./.tmp_runs/intake_table_synth_{_ts()}.csv"
    #             df_synth.to_csv(synth_path, index=False, encoding="utf-8-sig")
    #             st.success(f"✅ Synthetic dataset created ({len(df_synth)} rows). Saved: `{synth_path}`")
    #             st.dataframe(df_synth.head(20), use_container_width=True, hide_index=True)
    #             st.download_button(
    #                 "⬇️ Download Synthetic CSV",
    #                 df_synth.to_csv(index=False).encode("utf-8-sig"),
    #                 file_name="synthetic_intake.csv",
    #                 mime="text/csv",
    #                 key="dl_synth_A_quick"
    #             )
    #         except Exception as e:
    #             st.error(f"Synthetic generation failed: {e}")

       
        
    # ─────────────────────────────────────────
    # (A.4) SYNTHETIC DATA GENERATION
    # ─────────────────────────────────────────
    st.markdown("### 🤖 Generate Synthetic Data (Fallback)")
    nrows = st.slider("Number of synthetic rows", 10, 500, 150, step=10, key="slider_synth_rows")
    if st.button("🎲 Generate Synthetic Dataset", key="btn_generate_synth"):
        try:
            df_synth = quick_synth(nrows)
            ss["asset_intake_df"] = df_synth
            os.makedirs("./.tmp_runs", exist_ok=True)
            synth_path = f"./.tmp_runs/intake_table_synth_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
            df_synth.to_csv(synth_path, index=False)
            st.success(f"✅ Synthetic dataset created ({len(df_synth)} rows).")
            st.dataframe(df_synth.head(20), use_container_width=True)
            st.download_button("💾 Download Synthetic CSV", df_synth.to_csv(index=False), "synthetic_intake.csv", "text/csv")
        except Exception as e:
            st.error(f"Synthetic generation failed: {e}")





# ─────────────────────────────────────────
# B — PRIVACY & FEATURES (2..3)
# ─────────────────────────────────────────
with tabB:
    st.subheader("B. Privacy & Features")
    st.caption("Steps: **2) Anonymize**, **3) Feature Engineering + Comps**")

    import re, math, json, os, time
    from datetime import datetime, timezone

    RUNS_DIR = "./.tmp_runs"
    os.makedirs(RUNS_DIR, exist_ok=True)

    def _ts():
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    
    # ----------------------------
    # B.2 — Anonymize / Sanitize PII
    # ----------------------------
    st.markdown("### **2) Anonymize / Sanitize PII**")

    import io, csv, re, os
    from pathlib import Path

    ss = st.session_state  # make sure this exists globally

    def _slug(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "dataset")).strip("_").lower()

    def _read_any_table(uploaded_file) -> pd.DataFrame:
        """Robust reader for CSV/TSV/TXT/XLSX with encoding + delimiter fallback."""
        name = uploaded_file.name.lower()
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(uploaded_file)

        raw = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
        for enc in ("utf-8", "latin-1"):
            try:
                text = raw.decode(enc) if isinstance(raw, (bytes, bytearray)) else raw
                head = "\n".join(text.splitlines()[:10]) or text
                try:
                    sep = csv.Sniffer().sniff(head).delimiter
                except Exception:
                    sep = ","
                return pd.read_csv(io.StringIO(text), sep=sep)
            except Exception:
                continue
        return pd.read_csv(io.BytesIO(raw), engine="python")

    def _anonymize(df: pd.DataFrame) -> pd.DataFrame:
        """Mask likely-PII text while preserving common join keys."""
        if df is None or df.empty:
            return df
        out = df.copy()
        join_keys = {"loan_id", "asset_id", "application_id"}
        pii_like = re.compile(r"(name|email|phone|addr|address|national|passport|id|nid)", re.I)

        for col in out.columns:
            if col in join_keys:
                continue
            if out[col].dtype == "object" and pii_like.search(col):
                s = out[col].astype(str)
                s = s.str.replace(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "[EMAIL]", regex=True)
                s = s.str.replace(r"\b(\+?\d{1,3}[-.\s]?)?\d{7,}\b", "[PHONE]", regex=True)
                s = s.str.replace(r"\b\d{9,16}\b", "[ID]", regex=True)
                out[col] = s
        return out.drop_duplicates().reset_index(drop=True)

    # ---------- Source picker (Stage A or Upload here) ----------
    st.markdown("#### 🔄 Choose data source")
    src_choice = st.radio(
        "Pick how you want to provide data:",
        ["Use data from Stage A", "Upload a new file here"],
        horizontal=True,
        key="b_src_choice"
    )

    df_src, base_name = None, "dataset"

    if src_choice == "Use data from Stage A":
        df_src = ss.get("asset_intake_df")
        if isinstance(df_src, pd.DataFrame) and not df_src.empty:
            base_name = _slug(ss.get("last_dataset_name") or "dataset")
            st.success(f"Using Stage-A dataset: **{base_name}** • {len(df_src):,} rows")
            st.dataframe(df_src.head(10), use_container_width=True, hide_index=True)
        else:
            st.warning("No data found from Stage A. Upload below instead.")
    else:
        st.markdown(
            """
            <div style="border:2px dashed #22c55e;padding:14px;border-radius:12px;
                        background:rgba(34,197,94,0.06);margin:6px 0 12px 0;">
            <b>⬆️ Upload CSV/TSV/TXT/XLSX for anonymization</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
        up = st.file_uploader(
            "Upload a dataset file",
            type=["csv","tsv","txt","xlsx"],
            key="b_upload",
            accept_multiple_files=False,
        )
        if up is not None:
            try:
                df_src = _read_any_table(up)
                base_name = _slug(Path(up.name).stem)
                ss["asset_intake_df"] = df_src
                ss["last_dataset_name"] = base_name
                st.success(f"✅ Loaded {len(df_src):,} rows from **{up.name}**")
                st.dataframe(df_src.head(20), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Could not read file: {e}")

    if not (isinstance(df_src, pd.DataFrame) and not df_src.empty):
        st.info("Provide data (via Stage A or upload here) to enable anonymization.")
    else:
        if st.button("🛡️ Run Anonymization & Export CSV", type="primary", use_container_width=True, key="btn_b_anon"):
            anon_df = _anonymize(df_src)
            out_dir = os.path.join(RUNS_DIR, "normalized")
            os.makedirs(out_dir, exist_ok=True)
            out_name = f"{base_name}-Anonymized.csv"
            out_path = os.path.join(out_dir, out_name)
            anon_df.to_csv(out_path, index=False, encoding="utf-8-sig")
            ss["asset_anon_df"] = anon_df

            _bytes = anon_df.to_csv(index=False).encode("utf-8-sig")

            st.markdown(
                f"""
                <div style="position:sticky;top:64px;z-index:50;background:rgba(59,130,246,0.10);
                            border:1px solid #3b82f6;padding:12px 16px;border-radius:12px;margin:8px 0 14px 0;">
                <b>✅ Anonymized CSV:</b> <code>{out_name}</code> • {len(anon_df):,} rows × {len(anon_df.columns)} cols
                </div>
                """,
                unsafe_allow_html=True,
            )

            cL, cM, cR = st.columns([1, 2.6, 1])
            with cM:
                st.download_button(
                    "⬇️  Download Anonymized CSV",
                    data=_bytes,
                    file_name=out_name,
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                    key="dl_b_anon_top",
                )

            st.text_input("Saved to (server path)", out_path, disabled=True, label_visibility="collapsed")
            st.dataframe(anon_df.head(100), use_container_width=True, hide_index=True)

            cL2, cM2, cR2 = st.columns([1, 2.6, 1])
            with cM2:
                st.download_button(
                    "⬇️  Download Anonymized CSV",
                    data=_bytes,
                    file_name=out_name,
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                    key="dl_b_anon_bottom",
                )

    st.markdown("---")

    
    

    
    # ----------------------------
    # B.3 — Feature Engineering & Comps
    # ----------------------------
    st.markdown("### **3) Feature Engineering & Comps**")

    def feature_engineer(df: pd.DataFrame, evidence_index=None) -> pd.DataFrame:
        """
        Light feature engineering (safe):
        - Ensure city/lat/lon/age_years/delinquencies/current_loans
        - Coerce lat/lon including "10,762" → 10.762
        - Create stable 'geohash' (lat,lon preferred; fallback short city hash)
        - Derive condition_score (0..1) heuristically if inputs exist
        - Ensure legal_penalty numeric
        - Keep join keys up front if present
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()

        out = df.copy()

        # Ensure expected columns exist
        for c in ("city", "lat", "lon", "age_years", "delinquencies", "current_loans"):
            if c not in out.columns:
                out[c] = pd.NA

        # Coerce lat/lon
        for c in ("lat", "lon"):
            if out[c].dtype == "object":
                out[c] = out[c].astype(str).str.replace(",", ".", regex=False)
            out[c] = pd.to_numeric(out[c], errors="coerce")

        # Row-wise geokey: prefer lat/lon else short md5(city)
        import hashlib
        def _row_geokey(row) -> str:
            lat = row.get("lat")
            lon = row.get("lon")
            if pd.notna(lat) and pd.notna(lon):
                return f"{float(lat):.3f},{float(lon):.3f}"
            city_val = row.get("city")
            city_txt = "" if pd.isna(city_val) else str(city_val)
            return hashlib.md5(city_txt.encode("utf-8")).hexdigest()[:7]

        out["geohash"] = out.apply(_row_geokey, axis=1).astype(str)

        # Heuristic condition_score (0..1)
        age = pd.to_numeric(out.get("age_years"), errors="coerce").fillna(0.0)
        delinq = pd.to_numeric(out.get("delinquencies"), errors="coerce").fillna(0.0)
        curr_loans = pd.to_numeric(out.get("current_loans"), errors="coerce").fillna(0.0)
        cond = 1.0 - (0.02 * age) - (0.05 * delinq) - (0.03 * curr_loans)
        out["condition_score"] = pd.Series(cond, index=out.index).clip(0.10, 0.98)

        # legal_penalty safe numeric
        if "legal_penalty" not in out.columns:
            out["legal_penalty"] = 0.0
        else:
            out["legal_penalty"] = pd.to_numeric(out["legal_penalty"], errors="coerce").fillna(0.0)

        # Keep join keys in front
        front_cols = [c for c in ["loan_id", "application_id", "asset_id"] if c in out.columns]
        other_cols = [c for c in out.columns if c not in front_cols]
        out = out[front_cols + other_cols]

        return out


    def _fmt_mean(df, col, fmt="{:.2f}"):
        if isinstance(df, pd.DataFrame) and col in df.columns:
            v = pd.to_numeric(df[col], errors="coerce").mean()
            if pd.notna(v):
                return fmt.format(v)
        return "—"


    def fetch_and_clean_comps(df_feats: pd.DataFrame) -> dict:
        """Deterministic stub; replace with real comps feed."""
        mv = pd.to_numeric(df_feats.get("market_value", pd.Series(dtype=float)), errors="coerce")
        base = float(mv.median()) if mv.notna().any() else 100000.0
        comps = [{"comp_id": f"C-{i+1:03d}", "price": round(base * (0.95 + 0.02 * i), 2)} for i in range(5)]
        return {"used": comps, "count": len(comps), "median_baseline": base}


    if not isinstance(ss.get("asset_anon_df"), pd.DataFrame) or ss["asset_anon_df"].empty:
        st.info("Run **Anonymization (B.2)** first to prepare inputs for features.")
    else:
        c3a, c3b = st.columns([1.2, 0.8])

        with c3a:
            if st.button("Build Features & Fetch Comps", key="btn_build_features", use_container_width=True):
                # Build features in this rerun and persist
                feats = feature_engineer(ss["asset_anon_df"], ss.get("asset_evidence_index"))
                ss["asset_features_df"] = feats

                # Metrics (from feats)
                m1, m2, m3 = st.columns(3)
                with m1:
                    st.metric("Avg condition_score", _fmt_mean(feats, "condition_score"))
                with m2:
                    st.metric("Avg market_value", _fmt_mean(feats, "market_value", "{:,.0f}"))
                with m3:
                    st.metric("Avg loan_amount", _fmt_mean(feats, "loan_amount", "{:,.0f}"))

                # Persist features.parquet (BytesIO for download)
                features_path = os.path.join(RUNS_DIR, f"features.{_ts()}.parquet")
                feats.to_parquet(features_path, index=False)
                st.success(f"Saved features → `{features_path}`")

                import io as _io
                _buf = _io.BytesIO()
                feats.to_parquet(_buf, index=False)
                st.download_button(
                    "⬇️ Download features.parquet",
                    data=_buf.getvalue(),
                    file_name="features.parquet",
                    mime="application/octet-stream",
                    key="dl_features_parquet",
                    use_container_width=True
                )

                # Comps (and persist)
                comps = fetch_and_clean_comps(feats)
                ss["asset_comps_used"] = comps
                comps_path = os.path.join(RUNS_DIR, f"comps_used.{_ts()}.json")
                with open(comps_path, "w", encoding="utf-8") as fp:
                    json.dump(comps, fp, ensure_ascii=False, indent=2)
                st.success(f"Saved comps → `{comps_path}`")

        with c3b:
            # Show last built features (if any) and offer a second download
            df_feats = ss.get("asset_features_df")
            if isinstance(df_feats, pd.DataFrame) and not df_feats.empty:
                import io as _io2
                _buf2 = _io2.BytesIO()
                df_feats.to_parquet(_buf2, index=False)
                st.download_button(
                    "⬇️ Download last features.parquet",
                    data=_buf2.getvalue(),
                    file_name="features.parquet",
                    mime="application/octet-stream",
                    key="dl_features_parquet_last",
                    use_container_width=True
                )

    # Outside the columns: show current features + comps if present
    df_feats = ss.get("asset_features_df")
    if isinstance(df_feats, pd.DataFrame) and not df_feats.empty:
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Rows (features)", f"{len(df_feats):,}")
        with k2:
            st.metric("Avg condition_score", _fmt_mean(df_feats, "condition_score"))
        with k3:
            # evidence_count column is optional; show 0 if absent
            ev = pd.to_numeric(df_feats.get("evidence_count", pd.Series([0]*len(df_feats))), errors="coerce").fillna(0)
            st.metric("Evidence count (stub)", int(ev.mean()))

        st.dataframe(df_feats.head(30), use_container_width=True)

    if ss.get("asset_comps_used") is not None:
        st.caption("Comps used (stub)")
        st.json(ss["asset_comps_used"])

    


# ========== 3) AI APPRAISAL & VALUATION ==========
with tabC:
    st.subheader("🤖 Stage 3 — AI Appraisal & Valuation")

    import os, json, numpy as np, requests, pandas as pd, plotly.express as px
    from datetime import datetime, timezone

    RUNS_DIR = "./.tmp_runs"
    os.makedirs(RUNS_DIR, exist_ok=True)

    def _ts():
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # ─────────────────────────────────────────────
    # 🧭 HOW TO USE THIS STAGE
    # ─────────────────────────────────────────────
    st.markdown("""
    ### 🧭 How to Use This Stage
    1. **Select a model** — choose between production, trained, or open-source (Hugging Face) models.  
    2. **Check hardware** — confirm your GPU/CPU profile supports the chosen model.  
    3. **Select dataset** — use Stage 2 outputs (Features / Anonymized) or fallback synthetic data.  
    4. **Run appraisal** — compute AI-based valuation (`fmv`, `ai_adjusted`, `confidence`, `why`).  
    5. **Review outputs** — compare customer vs AI results, run projections, dashboards, and reports.  
    6. **Verify ownership** — perform Legal / Encumbrance checks (C.5).  
    """)

    # ─────────────────────────────────────────────
    # 🧠 MODEL FAMILY TABLE
    # ─────────────────────────────────────────────
    st.markdown("### 🧠 Model Families & Recommended Use-Cases")

    model_ref = pd.DataFrame([
        {"Category": "Local / Trained", "Model": "LightGBM / XGBoost / CatBoost",
         "Use Case": "Numeric → FMV prediction", "GPU": "CPU OK",
         "Notes": "Fast, explainable baseline model"},
        {"Category": "Production (⭐)", "Model": "asset_lgbm-v1 / credit_lr",
         "Use Case": "Enterprise-grade deployed valuation", "GPU": "CPU OK",
         "Notes": "Stable, low-latency predictions"},
        {"Category": "LLM (HF)", "Model": "Mistral 7B / Gemma 2 9B",
         "Use Case": "Text reasoning + narratives", "GPU": "≥ 8 GB",
         "Notes": "Fast reasoning for appraisal explanations"},
        {"Category": "LLM (HF)", "Model": "LLaMA 3 8B / Qwen 2 7B",
         "Use Case": "Multilingual valuation reports", "GPU": "≥ 12 GB",
         "Notes": "Strong contextual generation"},
        {"Category": "LLM (HF)", "Model": "Mixtral 8×7B",
         "Use Case": "High-end MoE valuation", "GPU": "≥ 24 GB",
         "Notes": "Premium precision for portfolios"},
    ])
    st.dataframe(model_ref, use_container_width=True)
    st.markdown("---")

    # ─────────────────────────────────────────────
    # 🟢 PRODUCTION MODEL BANNER
    # ─────────────────────────────────────────────
    try:
        resp = requests.get(f"{API_URL}/v1/training/production_meta", timeout=5)
        if resp.status_code == 200:
            meta = resp.json()
            if meta.get("has_production"):
                ver = (meta.get("meta") or {}).get("version", "1.x")
                src = (meta.get("meta") or {}).get("source", "production")
                st.success(f"🟢 Production model active — version {ver} • source {src}")
            else:
                st.warning("⚠️ No production model promoted yet — using baseline.")
        else:
            st.info("ℹ️ Could not fetch production model meta.")
    except Exception:
        st.info("ℹ️ Production meta unavailable.")

    # ─────────────────────────────────────────────
    # 🧩 Model Selection (list all trained models) — HARD-CODED TEST
    # ─────────────────────────────────────────────
    from datetime import datetime
    import os, shutil, streamlit as st

    # Hardcoded absolute paths for your environment
    trained_dir = "/home/dzoan/AI-AIGENTbythePeoplesANDBOX/HUGKAG/agents/asset_appraisal/models/trained"
    production_dir = "/home/dzoan/AI-AIGENTbythePeoplesANDBOX/HUGKAG/agents/asset_appraisal/models/production"

    # Debug info
    st.caption(f"📂 Trained dir: `{trained_dir}`")
    st.caption(f"📦 Production dir: `{production_dir}`")

    # Refresh button — use unique key for asset
    if st.button("↻ Refresh models", key="asset_refresh_models"):
        st.session_state.pop("asset_selected_model", None)
        st.rerun()

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

    if models:
        # Sort by creation time (latest first)
        models.sort(key=lambda x: os.path.getctime(x[1]), reverse=True)
        display_names = [f"{m[0]} — {m[2]}" for m in models]

        selected_display = st.selectbox("📦 Select trained model to use", display_names, key="asset_model_select")
        selected_model = models[display_names.index(selected_display)][1]
        st.success(f"✅ Using model: {os.path.basename(selected_model)}")

        st.session_state["asset_selected_model"] = selected_model

        # Promote to production
        if st.button("🚀 Promote this model to Production", key="asset_promote_button"):
            try:
                os.makedirs(production_dir, exist_ok=True)
                prod_path = os.path.join(production_dir, "model.joblib")
                shutil.copy2(selected_model, prod_path)
                st.balloons()
                st.success(f"✅ Model promoted to production: {prod_path}")
            except Exception as e:
                st.error(f"❌ Promotion failed: {e}")
    else:
        st.warning("⚠️ No trained models found — train one in Stage F first.")


    

    
    # ─────────────────────────────────────────────
    # 🧠 LLM + HARDWARE PROFILE (LOCAL + HUGGING FACE)
    # ─────────────────────────────────────────────
    st.markdown("### 🧠 LLM & Hardware Profile (Local + Hugging Face Models)")

    HF_MODELS = [
        {"Model": "mistralai/Mistral-7B-Instruct-v0.3",
         "Type": "Reasoning / valuation narrative",
         "GPU": "≥ 8 GB", "Notes": "Fast multilingual contextual LLM"},
        {"Model": "google/gemma-2-9b-it",
         "Type": "Instruction-tuned financial reports",
         "GPU": "≥ 12 GB", "Notes": "Great for valuation explanations"},
        {"Model": "meta-llama/Meta-Llama-3-8B-Instruct",
         "Type": "Valuation summarization",
         "GPU": "≥ 12 GB", "Notes": "High accuracy + low hallucination"},
        {"Model": "Qwen/Qwen2-7B-Instruct",
         "Type": "Multilingual reasoning (VN + EN)",
         "GPU": "≥ 12 GB", "Notes": "Excellent for VN asset appraisal"},
        {"Model": "microsoft/Phi-3-mini-4k-instruct",
         "Type": "Compact instruction LLM",
         "GPU": "≤ 8 GB", "Notes": "Fast lightweight valuation logic"},
        {"Model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
         "Type": "MoE premium reasoning",
         "GPU": "≥ 24 GB", "Notes": "Top-tier valuation model"},
        {"Model": "LightAutoML/LightGBM",
         "Type": "Tabular regression baseline",
         "GPU": "CPU OK", "Notes": "Numeric FMV baseline"},
    ]
    st.dataframe(pd.DataFrame(HF_MODELS), use_container_width=True)

    LLM_MODELS = [
        {"label": "CPU Recommended — Phi-3 Mini (3.8B)", "value": "phi3:3.8b", "hint": "CPU 8 GB RAM (fast)", "tier": "cpu"},
        {"label": "CPU Recommended — Mistral 7B Instruct", "value": "mistral:7b-instruct", "hint": "GPU ≥ 8 GB (fast)", "tier": "balanced"},
        {"label": "GPU Recommended — Gemma-2 9B", "value": "gemma2:9b", "hint": "GPU ≥ 12 GB (high accuracy)", "tier": "gpu"},
        {"label": "GPU Recommended — LLaMA-3 8B", "value": "llama3:8b-instruct", "hint": "GPU ≥ 12 GB (context heavy)", "tier": "gpu"},
        {"label": "GPU Recommended — Qwen-2 7B", "value": "qwen2:7b-instruct", "hint": "GPU ≥ 12 GB (multilingual)", "tier": "gpu"},
        {"label": "GPU Heavy — Mixtral 8×7B", "value": "mixtral:8x7b-instruct", "hint": "GPU 24-48 GB (batch)", "tier": "gpu_large"},
    ]

    cpu_first = [m for m in LLM_MODELS if m["tier"] in {"cpu", "balanced"}]
    gpu_first = [m for m in LLM_MODELS if m["tier"] not in {"cpu", "balanced"}]
    ordered_models = cpu_first + gpu_first

    LLM_LABELS = [m["label"] for m in ordered_models]
    LLM_VALUE_BY_LABEL = {m["label"]: m["value"] for m in ordered_models}
    LLM_HINT_BY_LABEL  = {m["label"]: m["hint"] for m in ordered_models}
    st.dataframe(pd.DataFrame(get_hf_models()), use_container_width=True)

    OPENSTACK_FLAVORS = {
        "m4.medium": "4 vCPU / 8 GB RAM (CPU-only small)",
        "m8.large": "8 vCPU / 16 GB RAM (CPU-only medium)",
        "g1.a10.1": "8 vCPU / 32 GB RAM + 1×A10 24 GB",
        "g1.l40.1": "16 vCPU / 64 GB RAM + 1×L40 48 GB",
        "g2.a100.1": "24 vCPU / 128 GB RAM + 1×A100 80 GB",
    }

    with st.expander("🧠 Choose Model & Hardware Profile", expanded=True):
        st.info("CPU picks land first so you can generate valuation narratives without waiting on GPUs. Jump to the GPU section only if you need deeper reasoning or longer context windows.", icon="⚙️")
        selected_llm = render_llm_selector(context="asset_appraisal")
        st.session_state["asset_llm_label"] = selected_llm["model"]
        st.session_state["asset_llm_model"] = selected_llm["value"]
        llm_value = selected_llm["value"]
        use_llm = st.checkbox(
            "Use LLM narrative (explanations)",
            value=st.session_state.get("asset_use_llm", False),
            key="asset_use_llm",
        )
        flavor = st.selectbox(
            "OpenStack flavor / host profile",
            list(OPENSTACK_FLAVORS.keys()),
            index=0,
            key="asset_flavor",
        )
        st.caption(OPENSTACK_FLAVORS[flavor])
        st.caption("These parameters are passed to backend (Ollama / Flowise / RunAI).")

    # ─────────────────────────────────────────────
    # GPU PROFILE AND DATASET SOURCE (keep existing logic)
    # ─────────────────────────────────────────────
    st.markdown("### **C.4 — Valuation (AI)**")
    gpu_profile = st.selectbox(
        "GPU Profile (for valuation compute)",
        ["CPU (slow)", "GPU: 1×A100", "GPU: 1×H100", "GPU: 2×L40S"],
        index=1, key="asset_gpu_profile_c4")
    ss["asset_gpu_profile"] = gpu_profile

    # Gather candidates from prior stages (they may be None/empty)
    cand_features = ss.get("asset_features_df")
    cand_anon     = ss.get("asset_anon_df")
    cand_intake   = ss.get("asset_intake_df")

    src = st.selectbox(
        "Data source for AI run",
        [
            "Use FEATURES (Stage 2/3)",
            "Use ANON (Stage 2)",
            "Use RAW → auto-sanitize",
            "Use synthetic (fallback)",
        ],
        key="asset_c4_source"
    )

    # Decide df2 explicitly based on choice
    df2 = None
    if src == "Use FEATURES (Stage 2/3)":
        # First non-empty among features → anon → intake
        df2 = first_nonempty_df(cand_features, cand_anon, cand_intake)

    elif src == "Use ANON (Stage 2)":
        df2 = cand_anon

    elif src == "Use RAW → auto-sanitize":
        # If intake exists, sanitize; else leave None
        df2 = anonymize_text_cols(cand_intake) if isinstance(cand_intake, pd.DataFrame) and not cand_intake.empty else None

    else:  # "Use synthetic (fallback)"
        df2 = quick_synth(150)

    # Final safety check
    if not isinstance(df2, pd.DataFrame) or df2.empty:
        st.warning("No usable dataset found. Please complete Stage A (Intake) and Stage B (Privacy/Features), or choose the synthetic fallback.")
        st.stop()

    # Preview selected data
    st.dataframe(df2.head(10), use_container_width=True)



    # Probe API (health & agents)
    with st.expander("🔎 Probe API (health & agents)", expanded=False):
        if st.button("Run probe now", key="btn_probe_api"):
            diag = probe_api()
            st.json(diag)

    # Run model button (runtime flavor + gpu_profile included)
    if st.button("🚀 Run AI Appraisal now", key="btn_run_ai"):
        health_ok, health_payload = _safe_get_json(f"{API_URL}/v1/health")
        if not health_ok:
            st.error("Backend API is not reachable. Start your API server (port 8090) via newstart.sh and rerun.")
            st.caption("Details from /v1/health probe:")
            st.code(str(health_payload)[:2000])
            st.stop()

        csv_bytes = df2.to_csv(index=False).encode("utf-8")

        form_fields = {
            "use_llm": str(use_llm).lower(),
            "llm": llm_value,
            "flavor": flavor,
            "gpu_profile": gpu_profile,  # NEW: pass GPU profile to backend
            "selected_model": ss.get("asset_selected_model", ""),
            "agent_name": "asset_appraisal",
        }

        with st.spinner("Calling asset agent…"):
            ok, result = try_run_asset_agent(csv_bytes, form_fields=form_fields, timeout_sec=180)

        if not ok:
            st.error("❌ Model API error.")
            st.info("Tip: open '🔎 Probe API' above to see health and discovered agent ids.")
            st.code(str(result)[:8000])
            st.stop()

        df_app = result.copy()

        # Ensure core valuation columns per blueprint
        if "ai_adjusted" not in df_app.columns and "market_value" in df_app.columns:
            df_app["ai_adjusted"] = df_app["market_value"]
        if "fmv" not in df_app.columns:
            # heuristics: if model returns fmv, keep; else set fmv ~ ai_adjusted
            df_app["fmv"] = pd.to_numeric(df_app.get("ai_adjusted", np.nan), errors="coerce")
        if "confidence" not in df_app.columns:
            df_app["confidence"] = 80.0
        if "why" not in df_app.columns:
            df_app["why"] = ["Condition, comps, and features (placeholder)"] * len(df_app)

        # Persist valuation artifact
        val_path = os.path.join(RUNS_DIR, f"valuation_ai.{_ts()}.csv")
        df_app.to_csv(val_path, index=False)
        
        _ping_chatbot_refresh("asset_run")
        
        st.success(f"Saved valuation artifact → `{val_path}`")

        # # ✅ PATCH: Save Stage C valuation table for Stage H (use df_app, not ai_df)
        # try:
        #     st.session_state["asset_ai_df"] = df_app.copy()
        #     ss["asset_ai_df"] = df_app.copy()
        #     st.info("✅ Stage C valuation stored for Stage D / E / H.")
        # except Exception as e:
        #     st.warning(f"Could not store Stage C output: {e}")

        # st.success(f"Saved valuation artifact → `{val_path}`")
        # # ✅ PATCH: Save Stage C valuation table for Stage H
        # try:
        #     st.session_state["asset_ai_df"] = ai_df.copy()
        #     st.info("✅ Stage C results stored for Stage H portfolio view.")
        # except Exception as e:
        #     st.warning(f"Could not store Stage C output: {e}")


        # Keep table for downstream steps
        ss["asset_ai_df"] = df_app

        # ─────────────────────────────────────────
        # ✅ Real Estate Evaluator Map (displayed on top of results)
        # ─────────────────────────────────────────
        # Check if coordinates are available and trigger map evaluation
        has_coords = "lat" in df_app.columns and "lon" in df_app.columns
        if has_coords:
            eval_df = df_app.dropna(subset=["lat", "lon"]).copy()
            
            if not eval_df.empty:
                with st.spinner("🗺️ Generating Real Estate Evaluator map..."):
                    try:
                        API_URL = os.getenv("API_URL", "http://localhost:8090")
                        url = f"{API_URL}/v1/agents/real_estate_evaluator/run/json"
                        
                        # Prepare payload
                        payload_data = []
                        for idx, row in eval_df.iterrows():
                            asset_id = str(row.get("asset_id", "")) if pd.notna(row.get("asset_id")) else ""
                            address = asset_id if asset_id else str(row.get("city", "Unknown"))
                            
                            payload_data.append({
                                "address": address,
                                "asset_id": asset_id,
                                "city": str(row.get("city", "Unknown")),
                                "district": str(row.get("district", "")),
                                "property_type": str(row.get("asset_type", "Unknown")),
                                "customer_price": float(row.get("realizable_value", row.get("ai_adjusted", 0))) if pd.notna(row.get("realizable_value", row.get("ai_adjusted", 0))) else 0,
                                "area_sqm": float(row.get("area_sqm", 0)) if pd.notna(row.get("area_sqm")) else 0,
                                "lat": float(row["lat"]),
                                "lon": float(row["lon"])
                            })
                        
                        payload = {
                            "df": payload_data,
                            "params": {"use_scraper": True}
                        }
                        
                        # Run evaluation
                        resp = requests.post(url, json=payload, timeout=120)
                        
                        if resp.status_code == 200:
                            result = resp.json()
                            
                            # Store evaluated data
                            evaluated_df_data = result.get("evaluated_df", [])
                            if isinstance(evaluated_df_data, list):
                                ss["re_evaluated_df"] = pd.DataFrame(evaluated_df_data)
                            else:
                                ss["re_evaluated_df"] = pd.DataFrame([evaluated_df_data])
                            
                            ss["re_map_data"] = result.get("map_data", [])
                            ss["re_zone_data"] = result.get("zone_data", [])
                            ss["re_summary"] = result.get("summary", {})
                            ss["asset_re_eval_hash"] = hash(tuple(sorted(df_app.get("asset_id", []).astype(str))))
                            
                            # Display map immediately
                            if ss.get("re_map_data") and len(ss["re_map_data"]) > 0:
                                st.markdown("### 🗺️ Real Estate Evaluator Map - Market Price Zones")
                                
                                map_data = ss["re_map_data"]
                                zone_data = ss.get("re_zone_data", [])
                                
                                # Prepare GeoJSON for customer assets
                                asset_features = []
                                for item in map_data:
                                    asset_features.append({
                                        "type": "Feature",
                                        "geometry": {
                                            "type": "Point",
                                            "coordinates": [item["lon"], item["lat"]]
                                        },
                                        "properties": item
                                    })
                                
                                assets_geojson = {
                                    "type": "FeatureCollection",
                                    "features": asset_features
                                }
                                
                                # Prepare GeoJSON for price zones
                                zone_features = []
                                for zone in zone_data:
                                    zone_features.append({
                                        "type": "Feature",
                                        "geometry": {
                                            "type": "Polygon",
                                            "coordinates": [zone["polygon"]]
                                        },
                                        "properties": {
                                            "city": zone["city"],
                                            "district": zone["district"],
                                            "market_price": zone["market_price"],
                                            "color": zone["color"],
                                            "price_range": zone["price_range"]
                                        }
                                    })
                                
                                zones_geojson = {
                                    "type": "FeatureCollection",
                                    "features": zone_features
                                }
                                
                                # Get current theme
                                current_theme = get_theme()
                                
                                # Generate and render map
                                map_html = _generate_ultra_3d_map(map_data, zone_data, assets_geojson, zones_geojson, current_theme)
                                components.html(map_html, height=800)
                                
                                # Display summary with calculated values from actual asset data
                                summary = result.get("summary", {})
                                
                                # Calculate customer prices from df_app (the actual asset data from Stage C)
                                customer_prices = []
                                # Use df_app if available (from Stage C), otherwise try asset_ai_df
                                asset_df = None
                                if 'df_app' in locals() and df_app is not None:
                                    asset_df = df_app
                                elif "asset_ai_df" in ss and ss["asset_ai_df"] is not None:
                                    asset_df = ss["asset_ai_df"]
                                
                                if asset_df is not None:
                                    # Try to get customer price from various columns (prioritize customer-declared prices)
                                    for col in ["realizable_value", "customer_price", "market_value", "ai_adjusted", "fmv"]:
                                        if col in asset_df.columns:
                                            prices = pd.to_numeric(asset_df[col], errors="coerce").dropna()
                                            valid_prices = prices[prices > 0].tolist()
                                            if valid_prices:
                                                customer_prices.extend(valid_prices)
                                                break
                                
                                # Also try to get customer prices from map_data (which was sent to the evaluator)
                                if not customer_prices and map_data:
                                    for item in map_data:
                                        cust_price = item.get("customer_price", item.get("value", 0))
                                        if cust_price and cust_price > 0:
                                            customer_prices.append(cust_price)
                                
                                # Calculate market prices from map data (per sqm, need to convert to total if area available)
                                market_prices_per_sqm = []
                                market_prices_total = []
                                if map_data:
                                    for item in map_data:
                                        market_price_per_sqm = item.get("market_price", item.get("market_price_per_sqm", 0))
                                        if market_price_per_sqm and market_price_per_sqm > 0:
                                            market_prices_per_sqm.append(market_price_per_sqm)
                                            # Also calculate total if area is available
                                            area = item.get("area_sqm", 0)
                                            if area and area > 0:
                                                market_prices_total.append(market_price_per_sqm * area)
                                
                                # Calculate averages
                                total_assets = len(map_data) or summary.get("total_assets", 0)
                                avg_market_price = np.mean(market_prices_per_sqm) if market_prices_per_sqm else summary.get("avg_market_price", 0)
                                avg_customer_price = np.mean(customer_prices) if customer_prices else 0
                                
                                # If customer prices are total prices, compare with total market prices
                                if not market_prices_per_sqm and market_prices_total:
                                    avg_market_price = np.mean(market_prices_total)
                                
                                # Calculate price delta
                                if avg_market_price > 0 and avg_customer_price > 0:
                                    # If comparing total prices, use total; otherwise use per sqm
                                    if market_prices_total and len(market_prices_total) > 0:
                                        avg_price_delta = ((avg_customer_price - np.mean(market_prices_total)) / np.mean(market_prices_total)) * 100
                                    else:
                                        avg_price_delta = ((avg_customer_price - avg_market_price) / avg_market_price) * 100
                                elif avg_market_price > 0:
                                    avg_price_delta = -100.0  # Customer price is 0
                                else:
                                    avg_price_delta = 0.0
                                
                                st.markdown("#### 📊 Market Comparison Summary")
                                col_a, col_b, col_c, col_d = st.columns(4)
                                with col_a:
                                    st.metric("Total Assets", total_assets)
                                with col_b:
                                    st.metric("Avg Market Price", f"${avg_market_price:,.0f}/sqm" if avg_market_price > 0 else "N/A")
                                with col_c:
                                    st.metric("Avg Customer Price", f"${avg_customer_price:,.0f}" + ("/sqm" if market_prices_per_sqm else "") if avg_customer_price > 0 else "N/A")
                                with col_d:
                                    delta_color = "normal" if abs(avg_price_delta) < 10 else "inverse"
                                    st.metric("Avg Price Delta", f"{avg_price_delta:+.1f}%", delta=f"{abs(avg_price_delta):.1f}%", delta_color=delta_color)
                                
                                st.markdown("---")
                    except Exception as e:
                        # Silently fail - map will just not show if evaluation fails
                        st.warning(f"⚠️ Could not generate map: {str(e)[:200]}")

        # Display minimal KPIs
        k1, k2, k3 = st.columns(3)
        try:
            k1.metric("Avg FMV", f"{pd.to_numeric(df_app['fmv'], errors='coerce').mean():,.0f}")
        except Exception:
            k1.metric("Avg FMV", "—")
        try:
            k2.metric("Avg Confidence", f"{pd.to_numeric(df_app['confidence'], errors='coerce').mean():.2f}")
        except Exception:
            k2.metric("Avg Confidence", "—")
        k3.metric("Rows", len(df_app))

        st.markdown("### 🧾 Valuation Output (preview)")
        cols_first = [c for c in [
            "application_id","asset_id","asset_type","city",
            "fmv","ai_adjusted","confidence","why"
        ] if c in df_app.columns]
        st.dataframe(df_app[cols_first].head(50), use_container_width=True)

        # ─────────────────────────────────────────
        # Customer vs AI — Details & 5-Year Deltas
        # (Place this right after the valuation preview table)
        # ─────────────────────────────────────────
        st.markdown("### 📋 Customer & Loan Details (Declared) + AI Alignment")

        import numpy as np
        from datetime import datetime, timezone
        import os

        RUNS_DIR = "./.tmp_runs"
        os.makedirs(RUNS_DIR, exist_ok=True)
        _ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        
        # ✅ Save Stage C output for Stage H (single source of truth)
        st.session_state["asset_ai_df"] = df_app.copy()
        ss["asset_ai_df"] = df_app.copy()
        st.info("✅ Stage C valuation stored for Stage D / E / H.")

        # ✅ Use the saved valuation table
        ai_df = st.session_state["asset_ai_df"]

        # ✅ Merge intake (customer-declared) if available
        intake_df = ss.get("asset_intake_df")
        if intake_df is not None and not intake_df.empty:
            join_keys = [
                k for k in ["application_id", "asset_id"]
                if k in ai_df.columns and k in intake_df.columns
            ]
            if join_keys:
                merged = intake_df.merge(
                    ai_df, on=join_keys,
                    suffixes=("_cust", "_ai"),
                    how="left"
                )
            else:
                merged = ai_df.copy()
        else:
            merged = ai_df.copy()

        # Optional: show preview table
        st.markdown("### 🔍 Stage C Output Preview")
        st.dataframe(merged, use_container_width=True)

        
        # # ✅ Save Stage C output for Stage H (using df_app, not undefined ai_df)
        # st.session_state["asset_ai_df"] = df_app.copy()
        # #ai_df = df_app.copy()
        # ai_df = st.session_state["asset_ai_df"]
        

        

        # ✅ Merge intake (customer-declared) if available
        intake_df = ss.get("asset_intake_df")
        if intake_df is not None and not intake_df.empty:
            # Choose join keys available in both frames
            join_keys = [
                k for k in ["application_id", "asset_id"]
                if k in ai_df.columns and k in intake_df.columns
            ]
            if join_keys:
                merged = intake_df.merge(
                    ai_df, on=join_keys,
                    suffixes=("_cust", "_ai"),
                    how="left"
                )
            else:
                merged = ai_df.copy()
        else:
            merged = ai_df.copy()

        
        # # ✅ Save Stage C output for Stage H
        # #st.session_state["asset_ai_df"] = ai_df.copy()
        # ai_df = ss.get("asset_ai_df")
        # if ai_df is None or len(ai_df) == 0:
        #     st.info("Run the AI appraisal first to populate these tables.")
        # else:
        #     # Merge intake (customer-declared) if available
        #     intake_df = ss.get("asset_intake_df")
        #     if intake_df is not None and not intake_df.empty:
        #         # Choose join keys available in both frames
        #         join_keys = [k for k in ["application_id", "asset_id"] if k in ai_df.columns and k in intake_df.columns]
        #         if join_keys:
        #             merged = intake_df.merge(ai_df, on=join_keys, suffixes=("_cust", "_ai"), how="left")
        #         else:
        #             merged = ai_df.copy()
        #     else:
        #         merged = ai_df.copy()

            # Canonical column mapping
            # customer declared value (prefer *_cust if merge happened)
            customer_val_col = "market_value_cust" if "market_value_cust" in merged.columns else (
                "market_value" if "market_value" in merged.columns else None
            )
            # AI value (prefer fmv, fallback ai_adjusted)
            ai_val_col = "fmv" if "fmv" in merged.columns else (
                "ai_adjusted" if "ai_adjusted" in merged.columns else None
            )

            # Build Customer & Loan Details table
            details_cols = [c for c in [
                "application_id","asset_id","asset_type","city",
                customer_val_col,
                "loan_amount",
                ai_val_col, "confidence","why"
            ] if c and c in merged.columns]

            details_tbl = merged[details_cols].copy() if details_cols else merged.copy()

            # Rename for clarity in the UI
            rename_map = {}
            if customer_val_col:
                rename_map[customer_val_col] = "customer_declared_value"
            if ai_val_col:
                rename_map[ai_val_col] = "ai_estimate_value"
            details_tbl = details_tbl.rename(columns=rename_map)

            # Explanation / Source
            selected_model = os.path.basename(str(ss.get("asset_selected_model","") or ""))
            comps_count = int((ss.get("asset_comps_used") or {}).get("count", 0))
            details_tbl["explanation_source"] = details_tbl.apply(
                lambda r: f"Customer input CSV vs AI model {selected_model or 'production'} (comps={comps_count})",
                axis=1
            )

            st.dataframe(details_tbl.head(50), use_container_width=True)

            # Persist details table
            details_path = os.path.join(RUNS_DIR, f"customer_loan_details.{_ts}.csv")
            details_tbl.to_csv(details_path, index=False)
            st.download_button(
                "⬇️ Download Customer & Loan Details (CSV)",
                data=details_tbl.to_csv(index=False).encode("utf-8"),
                file_name="customer_loan_details.csv",
                mime="text/csv"
            )

            st.markdown("---")
            st.markdown("### 📈 5-Year Deltas: Customer vs AI (per-year Δ and %Δ)")

            # Controls for forward projections
            cgr_a, cgr_b = st.columns(2)
            with cgr_a:
                cust_cagr = st.slider("Customer Expected CAGR (%)", min_value=-20, max_value=40, value=5, step=1) / 100.0
            with cgr_b:
                ai_cagr = st.slider("AI Expected CAGR (%)", min_value=-20, max_value=40, value=4, step=1) / 100.0

            if not customer_val_col or not ai_val_col:
                st.warning("Missing base columns to compute deltas. Ensure both customer and AI values exist.")
            else:
                base_cust = merged[customer_val_col].astype(float)
                base_ai   = merged[ai_val_col].astype(float)

                # Build long-format 5-year projection table
                rows = []
                years = [1, 2, 3, 4, 5]
                for idx in range(len(merged)):
                    cust0 = base_cust.iloc[idx]
                    ai0   = base_ai.iloc[idx]
                    app_id = merged.iloc[idx].get("application_id", None)
                    asset_id = merged.iloc[idx].get("asset_id", None)
                    asset_type = merged.iloc[idx].get("asset_type", None)
                    city = merged.iloc[idx].get("city", None)

                    for y in years:
                        cust_y = cust0 * ((1.0 + cust_cagr) ** y) if np.isfinite(cust0) else np.nan
                        ai_y   = ai0   * ((1.0 + ai_cagr) ** y)   if np.isfinite(ai0)   else np.nan
                        delta  = ai_y - cust_y if (np.isfinite(ai_y) and np.isfinite(cust_y)) else np.nan
                        pct    = (delta / cust_y * 100.0) if (np.isfinite(delta) and cust_y not in [0, np.nan]) else np.nan

                        rows.append({
                            "application_id": app_id,
                            "asset_id": asset_id,
                            "asset_type": asset_type,
                            "city": city,
                            "year_ahead": y,
                            "customer_value": cust_y,
                            "ai_value": ai_y,
                            "delta": delta,
                            "delta_pct": pct,
                            "explanation_source": f"Customer CAGR={cust_cagr*100:.1f}% vs AI CAGR={ai_cagr*100:.1f}%; AI model {selected_model or 'production'} (comps={comps_count})"
                        })

                deltas_tbl = pd.DataFrame(rows)

            # Display & export
            # Round for readability
            for c in ["customer_value","ai_value","delta","delta_pct"]:
                if c in deltas_tbl.columns:
                    deltas_tbl[c] = pd.to_numeric(deltas_tbl[c], errors="coerce")

            st.dataframe(deltas_tbl.head(100), use_container_width=True)

            deltas_path = os.path.join(RUNS_DIR, f"valuation_deltas_5y.{_ts}.csv")
            deltas_tbl.to_csv(deltas_path, index=False)
            st.download_button(
                "⬇️ Download 5-Year Deltas (CSV)",
                data=deltas_tbl.to_csv(index=False).encode("utf-8"),
                file_name="valuation_deltas_5y.csv",
                mime="text/csv"
            )


        st.markdown("---")
        # 🔒 C.5 — Legal/Ownership Verification (encumbrances, liens, fraud)
        st.markdown("### **C.5 — Legal/Ownership Verification**")

        def _verify_stub(df_in: pd.DataFrame) -> pd.DataFrame:
            df = df_in.copy()
            if "verification_status" not in df.columns:
                df["verification_status"] = "verified"
            if "encumbrance_flag" not in df.columns:
                df["encumbrance_flag"] = False
            if "verified_owner" not in df.columns:
                df["verified_owner"] = np.where(df.get("asset_type","").astype(str).str.lower().str.contains("car"), "DMV Registry", "Land Registry")
            if "notes" not in df.columns:
                df["notes"] = "Registry check passed (stub)"
            return df

        if st.button("🔍 Run Legal/Ownership Checks", key="btn_run_verification"):
            base_df = ss.get("asset_ai_df")
            if base_df is None:
                st.warning("Run valuation first.")
            else:
                verified_df = _verify_stub(base_df)
                ss["asset_verified_df"] = verified_df
                ver_path = os.path.join(RUNS_DIR, f"verification_status.{_ts()}.csv")
                verified_df.to_csv(ver_path, index=False)
                st.success(f"Saved verification artifact → `{ver_path}`")

                v1, v2 = st.columns(2)
                with v1:
                    try:
                        pct = (verified_df["verification_status"] == "verified").mean()
                        st.metric("Verified %", f"{pct:.0%}")
                    except Exception:
                        st.metric("Verified %", "—")
                with v2:
                    try:
                        st.metric("Encumbrance Flags", int(pd.to_numeric(verified_df["encumbrance_flag"]).sum()))
                    except Exception:
                        st.metric("Encumbrance Flags", "—")

                cols_ver = [c for c in [
                    "application_id","asset_id","verified_owner","verification_status","encumbrance_flag","notes"
                ] if c in verified_df.columns]
                st.dataframe(verified_df[cols_ver].head(50), use_container_width=True)

        # ─────────────────────────────────────────
        # 📊 Executive Portfolio Dashboard (Spectacular)
        # ─────────────────────────────────────────
        st.divider()
        st.subheader("📊 Executive Portfolio Dashboard")

        df_src = ss.get("asset_ai_df")
        ft = ss.get("asset_first_table")  # loan-centric projection you already built
        if df_src is None or (hasattr(df_src, "empty") and df_src.empty):
            st.info("Run appraisal to populate the dashboard.")
        else:
            df = df_src.copy()

            # ---- Safe numerics
            def _num(series, default=None):
                s = pd.to_numeric(series, errors="coerce")
                if default is not None:
                    s = s.fillna(default)
                return s

            for c in ["ai_adjusted","realizable_value","loan_amount",
                    "valuation_gap_pct","ltv_ai","ltv_cap","confidence",
                    "condition_score","legal_penalty"]:
                if c in df.columns:
                    df[c] = _num(df[c])

            # ---- KPIs row
            k1, k2, k3, k4, k5 = st.columns(5)
            total_ai        = float(df.get("ai_adjusted", pd.Series(dtype=float)).sum()) if "ai_adjusted" in df.columns else 0.0
            total_realiz    = float(df.get("realizable_value", pd.Series(dtype=float)).sum()) if "realizable_value" in df.columns else 0.0
            avg_conf        = float(df.get("confidence", pd.Series(dtype=float)).mean()) if "confidence" in df.columns else 0.0
            ltv_breach_rate = 0.0
            if {"ltv_ai","ltv_cap"}.issubset(df.columns):
                ltv_breach_rate = float((df["ltv_ai"] > df["ltv_cap"]).mean() * 100)
            approved_cnt = int(df.get("decision","").astype(str).str.lower().eq("approved").sum()) if "decision" in df.columns else 0

            k1.metric("AI Gross Value",       f"${total_ai:,.0f}")
            k2.metric("Realizable Value",     f"${total_realiz:,.0f}")
            k3.metric("Avg Confidence",       f"{avg_conf:.1f}%")
            k4.metric("LTV Breach Rate",      f"{ltv_breach_rate:.1f}%")
            k5.metric("Approved Count",       f"{approved_cnt:,}")

            # ---- Row 1: Top-10 Assets & Decision Mix
            r1c1, r1c2 = st.columns([1.2, 1])
            with r1c1:
                value_col = "realizable_value" if "realizable_value" in df.columns else ("ai_adjusted" if "ai_adjusted" in df.columns else None)
                if value_col:
                    df_top = (df.assign(_val=df[value_col])
                                .sort_values("_val", ascending=False)
                                .head(10))
                    fig_top = px.bar(
                        df_top,
                        x="_val", y=df_top.get("asset_id", df_top.index).astype(str),
                        color="asset_type" if "asset_type" in df_top.columns else None,
                        orientation="h",
                        title=f"Top 10 Assets by {value_col.replace('_',' ').title()}",
                        hover_data=[c for c in ["application_id","asset_id","asset_type","city","_val"] if c in df_top.columns]
                    )
                    fig_top.update_layout(template="plotly_dark", height=380, yaxis_title=None, xaxis_title=value_col)
                    st.plotly_chart(fig_top, use_container_width=True)
            with r1c2:
                names_series = (df["decision"].astype(str).str.title()
                                if "decision" in df.columns
                                else np.where(df.get("policy_breaches","").astype(str).str.len().gt(0),
                                            "Has Breach","No Breach"))
                fig_mix = px.pie(df, names=names_series, title="Decision / Breach Mix")
                fig_mix.update_layout(template="plotly_dark", height=380)
                st.plotly_chart(fig_mix, use_container_width=True)

            # ---- Row 2: By Asset Type & City Concentration
            r2c1, r2c2 = st.columns(2)
            with r2c1:
                if "asset_type" in df.columns:
                    df_type = (df
                            .assign(value=df[value_col] if value_col else 0)
                            .groupby("asset_type", dropna=False)["value"]
                            .sum().sort_values(ascending=False).reset_index())
                    fig_type = px.bar(df_type, x="asset_type", y="value",
                                    title="Value by Asset Type",
                                    text_auto=True)
                    fig_type.update_layout(template="plotly_dark", height=360, xaxis_title=None, yaxis_title="Value")
                    st.plotly_chart(fig_type, use_container_width=True)
            with r2c2:
                if "city" in df.columns and value_col:
                    df_city = (df.groupby("city", dropna=False)[value_col]
                                .sum().sort_values(ascending=False)
                                .head(10).reset_index())
                    fig_city = px.pie(df_city, values=value_col, names="city",
                                    title="Top-10 City Concentration")
                    fig_city.update_layout(template="plotly_dark", height=360)
                    st.plotly_chart(fig_city, use_container_width=True)

            # ---- Row 3: LTV vs Cap & Condition×Legal Heat
            r3c1, r3c2 = st.columns(2)
            with r3c1:
                if {"ltv_ai","ltv_cap"}.issubset(df.columns):
                    fig_sc = px.scatter(
                        df, x="ltv_cap", y="ltv_ai",
                        color="asset_type" if "asset_type" in df.columns else None,
                        hover_data=[c for c in ["application_id","asset_id","asset_type","city","loan_amount"] if c in df.columns],
                        title="LTV (AI) vs LTV Cap"
                    )
                    try:
                        max_cap = float((df["ltv_cap"].max() or 1.2))
                        fig_sc.add_shape(type="line", x0=0, y0=0, x1=max_cap, y1=max_cap, line=dict(dash="dash"))
                    except Exception:
                        pass
                    fig_sc.update_layout(template="plotly_dark", height=360,
                                        xaxis_title="LTV Cap", yaxis_title="LTV (AI)")
                    st.plotly_chart(fig_sc, use_container_width=True)
            with r3c2:
                if {"condition_score","legal_penalty"}.issubset(df.columns):
                    try:
                        cond_bins  = pd.cut(df["condition_score"], bins=[0,0.70,0.85,1.00], labels=["<0.70","0.70–0.85",">0.85"])
                        legal_bins = pd.cut(df["legal_penalty"],  bins=[0,0.97,0.99,1.00], labels=["<0.97","0.97–0.99",">=0.99"])
                        heat = (df.assign(cond=cond_bins, legal=legal_bins)
                                .groupby(["cond","legal"]).size().reset_index(name="count"))
                        fig_hm = px.density_heatmap(heat, x="legal", y="cond", z="count",
                                                    title="Condition vs Legal — Density")
                        fig_hm.update_layout(template="plotly_dark", height=360)
                        st.plotly_chart(fig_hm, use_container_width=True)
                    except Exception:
                        pass

            # ---- Row 4: City Leaderboard + Per-City Asset List
            st.markdown("### 🏙️ City Leaderboard & Assets")
            if "city" in df.columns:
                value_col = value_col or "ai_adjusted"
                city_sum = (df.groupby("city", dropna=False)[value_col]
                            .sum().sort_values(ascending=False).reset_index()
                            .rename(columns={value_col: "total_value"}))
                left, right = st.columns([1, 2])
                with left:
                    st.dataframe(city_sum, use_container_width=True)
                with right:
                    # show top assets per top city
                    top_cities = city_sum["city"].astype(str).head(5).tolist()
                    for city in top_cities:
                        with st.expander(f"📍 {city} — top assets", expanded=False):
                            sub = (df[df["city"].astype(str)==city]
                                .assign(value=df[value_col])
                                .sort_values("value", ascending=False)
                                [[c for c in ["application_id","asset_id","asset_type","value","loan_amount","confidence"] if c in df.columns]]
                                .head(15))
                            st.dataframe(sub, use_container_width=True)


            # ---- Exports of aggregates
            st.markdown("#### 📤 Export dashboard aggregates")
            exports = {}
            if "asset_type" in df.columns:
                exports["by_asset_type.csv"] = df_type.to_csv(index=False) if 'df_type' in locals() else ""
            if "city" in df.columns and value_col:
                exports["by_city_top10.csv"] = df_city.to_csv(index=False) if 'df_city' in locals() else ""
            if 'df_top' in locals():
                exports["top_assets.csv"] = df_top.drop(columns=["_val"], errors="ignore").to_csv(index=False)

            ex1, ex2, ex3 = st.columns(3)
            for i, (fname, data) in enumerate(exports.items()):
                if not data:
                    continue
                col = [ex1, ex2, ex3][i % 3]
                with col:
                    st.download_button(f"⬇️ {fname}", data=data.encode("utf-8"), file_name=fname, mime="text/csv")
                    
            
            # ✅ NEW: Export full AI decision file for Stage E (Human Review)
            st.markdown("### 🧾 Export AI Decision for Human Review (Stage E)")

            if 'ai_df' in locals() and isinstance(ai_df, pd.DataFrame) and not ai_df.empty:
                ai_export_name = f"ai_decision_stageC_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
                ai_csv_data = ai_df.to_csv(index=False, encoding="utf-8-sig")

                st.download_button(
                    "⬇️ Export AI Decisions (send to Stage E)",
                    data=ai_csv_data,
                    file_name=ai_export_name,
                    mime="text/csv",
                    key="dl_ai_stagec_export"
                )
            else:
                st.info("AI table (ai_df) not available — run valuation first.")

            # ========================
            # Stage C — AI Appraisal & Valuation
            # ========================
            # Now send AI results to Stage E for review
            if st.button("💬 Review in Stage E"):
                # Store AI appraisal results in session_state for Stage E
                st.session_state["ai_review_df"] = ai_df  # ai_df should be the AI results dataframe from the current stage
                st.session_state["current_stage"] = "human_review"
                st.success("AI results sent to Stage E for human review!")
                st.rerun()

            
            # # ========================
            # # Stage C — AI Appraisal & Valuation
            # # ========================
            # # Now send AI results to Stage E for review
            # if st.button("💬 Review in Stage E"):
            #     # Store AI appraisal results in session_state for Stage E
            #     st.session_state["ai_review_df"] = ai_df  # ai_df should be the AI results dataframe from the current stage
            #     st.session_state["current_stage"] = "human_review"
            #     st.success("AI results sent to Stage E for human review!")
            #     st.rerun()  # Trigger a page refresh to go to the next stage




# ========== 4) POLICY & DECISION (Stage D: steps 6–7) ==========
with tabD:
    st.subheader("🧮 Stage 4 — Policy & Decision (D.6 / D.7)")

    import os, json
    import numpy as np
    from datetime import datetime, timezone

    RUNS_DIR = "./.tmp_runs"
    os.makedirs(RUNS_DIR, exist_ok=True)
    def _ts(): return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # ---- Input table: prefer verified → else AI valuation (safe selector) ----
    base_df = first_nonempty_df(ss.get("asset_verified_df"), ss.get("asset_ai_df"))
    if not is_nonempty_df(base_df):
        st.warning("Run Stage C first (valuation, and optionally verification).")
        st.stop()

    st.caption("Input: valuation + (optional) verification outputs.")

    # ── D.6 and D.7 continue here (your existing haircuts / caps / breaches / decision code) ──

    # -------- D.6 — Policy & Haircuts → realizable_value --------
    st.markdown("### **D.6 — Policy & Haircuts**")
    p1, p2, p3 = st.columns(3)
    with p1:
        base_haircut_pct = st.slider("Base haircut (%)", 0, 60, 10, 1, key="policy_base_haircut")
    with p2:
        condition_weight = st.slider("Condition multiplier min", 0.50, 1.00, 0.80, 0.01, key="policy_cond_min")
    with p3:
        legal_weight = st.slider("Legal multiplier min", 0.50, 1.00, 0.95, 0.01, key="policy_legal_min")

    if st.button("Apply Haircuts", key="btn_apply_haircuts"):
        df = base_df.copy()

        # Ensure necessary inputs exist
        for col, default in [("ai_adjusted", np.nan), ("condition_score", 0.9), ("legal_penalty", 1.0)]:
            if col not in df.columns:
                df[col] = default

        ai_adj = pd.to_numeric(df["ai_adjusted"], errors="coerce")
        cond   = pd.to_numeric(df["condition_score"], errors="coerce").clip(condition_weight, 1.0)
        legal  = pd.to_numeric(df["legal_penalty"],  errors="coerce").clip(legal_weight, 1.0)
        base_cut = (1.0 - float(base_haircut_pct) / 100.0)

        df["realizable_value"] = ai_adj * cond * legal * base_cut

        # Persist artifact
        policy_path = os.path.join(RUNS_DIR, f"policy_haircuts.{_ts()}.csv")
        df.to_csv(policy_path, index=False)

        # ✅ Save Stage D policy results for Stage H
        try:
            # Save into BOTH namespaces safely
            st.session_state["asset_policy_df"] = df.copy()
            ss["asset_policy_df"] = df.copy()

            st.info("✅ Stage D policy results stored for Stage H.")
        except Exception as e:
            st.warning(f"Could not store Stage D output: {e}")

        st.success(f"Saved: `{policy_path}`")

        # KPIs
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric(
                "Avg Realizable Value",
                f"{pd.to_numeric(df['realizable_value'], errors='coerce').mean():,.0f}"
            )
        with k2:
            st.metric("Rows", len(df))
        with k3:
            st.metric("Base Haircut", f"{base_haircut_pct}%")

        st.dataframe(df.head(30), use_container_width=True)

        
        # # ✅ Save Stage D policy results for Stage H
        # try:
        #     st.session_state["asset_policy_df"] = df.copy()
        #     ss["asset_policy_df"] = df.copy()
        #     st.info("✅ Stage D policy results stored for Stage H.")
        # except Exception as e:
        #     st.warning(f"Could not store Stage D output: {e}")

        # st.success(f"Saved: `{policy_path}`")

        # # KPIs
        # k1, k2, k3 = st.columns(3)
        # with k1:
        #     st.metric("Avg Realizable Value", f"{pd.to_numeric(df['realizable_value'], errors='coerce').mean():,.0f}")
        # with k2:
        #     st.metric("Rows", len(df))
        # with k3:
        #     st.metric("Base Haircut", f"{base_haircut_pct}%")

        # st.dataframe(df.head(30), use_container_width=True)

    # # -------- D.6 — Policy & Haircuts → realizable_value --------
    # st.markdown("### **D.6 — Policy & Haircuts**")
    # p1, p2, p3 = st.columns(3)
    # with p1:
    #     base_haircut_pct = st.slider("Base haircut (%)", 0, 60, 10, 1, key="policy_base_haircut")
    # with p2:
    #     condition_weight = st.slider("Condition multiplier min", 0.50, 1.00, 0.80, 0.01, key="policy_cond_min")
    # with p3:
    #     legal_weight = st.slider("Legal multiplier min", 0.50, 1.00, 0.95, 0.01, key="policy_legal_min")

    # if st.button("Apply Haircuts", key="btn_apply_haircuts"):
    #     df = base_df.copy()

    #     # Ensure necessary inputs exist
    #     for col, default in [("ai_adjusted", np.nan), ("condition_score", 0.9), ("legal_penalty", 1.0)]:
    #         if col not in df.columns:
    #             df[col] = default

    #     ai_adj = pd.to_numeric(df["ai_adjusted"], errors="coerce")
    #     cond   = pd.to_numeric(df["condition_score"], errors="coerce").clip(condition_weight, 1.0)
    #     legal  = pd.to_numeric(df["legal_penalty"],  errors="coerce").clip(legal_weight, 1.0)
    #     base_cut = (1.0 - float(base_haircut_pct) / 100.0)

    #     df["realizable_value"] = ai_adj * cond * legal * base_cut

    #     # Persist policy_haircuts artifact
    #     policy_path = os.path.join(RUNS_DIR, f"policy_haircuts.{_ts()}.csv")
    #     df.to_csv(policy_path, index=False)
        
    #     # ✅ Save Stage D policy for Stage H
    #     st.session_state["asset_policy_df"] = policy_df.copy()

    #     ss["asset_policy_df"] = df
    #     st.success(f"Saved: `{policy_path}`")

    #     # KPIs
    #     k1, k2, k3 = st.columns(3)
    #     with k1:
    #         st.metric("Avg Realizable Value", f"{pd.to_numeric(df['realizable_value'], errors='coerce').mean():,.0f}")
    #     with k2:
    #         st.metric("Rows", len(df))
    #     with k3:
    #         st.metric("Base Haircut", f"{base_haircut_pct}%")

    #     st.dataframe(df.head(30), use_container_width=True)

    # st.markdown("---")

    # -------- D.7 — Risk / Decision --------
    st.markdown("### **D.7 — Risk / Decision**")

    if ss.get("asset_policy_df") is None:
        st.info("Run D.6 first to compute `realizable_value`.")
    else:
        df = ss["asset_policy_df"].copy()

        # Inputs
        r1, r2, r3 = st.columns(3)
        with r1:
            loan_amount_default = float(pd.to_numeric(df.get("loan_amount", pd.Series([60000])).median()))
            loan_amount = st.number_input("Loan amount (default=median)", value=loan_amount_default, min_value=0.0, step=1000.0, key="risk_loan_amt")
        with r2:
            ltv_mode = st.selectbox("LTV cap mode", ["Fixed cap", "Per asset_type"], index=0, key="risk_ltv_mode")
        with r3:
            fixed_ltv_cap = st.slider("Fixed LTV cap (×)", 0.10, 2.00, 0.80, 0.05, key="risk_ltv_cap_fixed")

        # Per-type caps if requested
        type_caps = {}
        if ltv_mode == "Per asset_type":
            types = sorted(list(map(str, (df.get("asset_type") or pd.Series(["Asset"])).dropna().unique())))[0:10]
            st.caption("Tune LTV caps per asset_type")
            grid = st.columns(4 if len(types) > 3 else max(1, len(types)))
            for i, t in enumerate(types):
                with grid[i % len(grid)]:
                    type_caps[t] = st.number_input(f"{t} cap ×", 0.10, 2.00, 0.80, 0.05, key=f"cap_{t}")

        # Thresholds for decisioning
        t1, t2, t3 = st.columns(3)
        with t1:
            min_conf = st.slider("Min confidence (%)", 0, 100, 70, 1, key="risk_min_conf")
        with t2:
            min_cond = st.slider("Min condition_score", 0.60, 1.00, 0.75, 0.01, key="risk_min_cond")
        with t3:
            min_legal = st.slider("Min legal_penalty", 0.80, 1.00, 0.97, 0.01, key="risk_min_legal")

        if st.button("Compute Decision", key="btn_compute_decision"):
            # Compute ltv_ai
            df["ltv_ai"] = pd.to_numeric(loan_amount, errors="coerce") / pd.to_numeric(df.get("ai_adjusted", np.nan), errors="coerce")

            # ltv_cap
            if ltv_mode == "Fixed cap":
                df["ltv_cap"] = float(fixed_ltv_cap)
            else:
                atypes = df.get("asset_type").astype(str) if "asset_type" in df.columns else pd.Series(["Asset"] * len(df))
                df["ltv_cap"] = atypes.map(lambda t: float(type_caps.get(t, fixed_ltv_cap)))

            # Breaches
            conf = pd.to_numeric(df.get("confidence", 100.0), errors="coerce")
            cond = pd.to_numeric(df.get("condition_score", 1.0), errors="coerce")
            legal= pd.to_numeric(df.get("legal_penalty", 1.0),  errors="coerce")
            ltv  = pd.to_numeric(df["ltv_ai"], errors="coerce")
            lcap = pd.to_numeric(df["ltv_cap"], errors="coerce")

            breaches = []
            for i in range(len(df)):
                b = []
                if pd.notna(conf.iat[i]) and conf.iat[i] < min_conf:
                    b.append(f"confidence<{min_conf}%")
                if pd.notna(cond.iat[i]) and cond.iat[i] < min_cond:
                    b.append(f"condition<{min_cond:.2f}")
                if pd.notna(legal.iat[i]) and legal.iat[i] < min_legal:
                    b.append(f"legal<{min_legal:.2f}")
                if pd.notna(ltv.iat[i]) and pd.notna(lcap.iat[i]) and ltv.iat[i] > lcap.iat[i]:
                    b.append("ltv>cap")
                breaches.append(", ".join(b))
            df["policy_breaches"] = breaches

            # Decision rule
            # - reject if LTV>cap OR confidence << min_conf (<= min_conf-10)
            # - review if any breach but not hard reject
            # - approve otherwise
            hard_reject = (
                (ltv > lcap) |
                (pd.to_numeric(conf, errors="coerce") <= (min_conf - 10))
            )
            any_breach = df["policy_breaches"].str.len().gt(0)

            df["decision"] = np.select(
                [
                    hard_reject,
                    any_breach
                ],
                ["reject", "review"],
                default="approve"
            )

            # Persist risk_decision artifact
            risk_path = os.path.join(RUNS_DIR, f"risk_decision.{_ts()}.csv")
            df.to_csv(risk_path, index=False)
            ss["asset_decision_df"] = df
            st.success(f"Saved: `{risk_path}`")

            # KPIs + Table
            k1, k2, k3 = st.columns(3)
            with k1:
                st.metric("Avg LTV (AI)", f"{pd.to_numeric(df['ltv_ai'], errors='coerce').mean():.2f}")
            with k2:
                try:
                    st.metric("Breach Rate", f"{(df['policy_breaches'].str.len().gt(0)).mean():.0%}")
                except Exception:
                    st.metric("Breach Rate", "—")
            with k3:
                mix = df["decision"].value_counts(dropna=False)
                st.metric("Approve/Review/Reject", f"{int(mix.get('approve',0))}/{int(mix.get('review',0))}/{int(mix.get('reject',0))}")

            cols_view = [c for c in [
                "application_id","asset_id","asset_type","city",
                "ai_adjusted","realizable_value",
                "loan_amount","ltv_ai","ltv_cap",
                "confidence","condition_score","legal_penalty",
                "policy_breaches","decision"
            ] if c in df.columns]
            st.dataframe(df[cols_view].head(50), use_container_width=True)

            st.download_button(
                "⬇️ Download Policy+Decision (CSV)",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="risk_decision.csv",
                mime="text/csv"
            )



# ─────────────────────────────────────────
# E — HUMAN REVIEW & FEEDBACK DASHBOARD
# ─────────────────────────────────────────
from datetime import datetime, timezone  # ensure available inside this block
import os, glob, json
import numpy as np
import pandas as pd
import plotly.graph_objects as go

with tabE:
    st.subheader("🧑‍⚖️ Stage E — Human Review & Feedback")
    st.caption("Compare AI-estimated collateral values against business metrics, adjust valuations, and record justification for retraining.")

    
    # Workspace
    RUNS_DIR = "./.tmp_runs"
    os.makedirs(RUNS_DIR, exist_ok=True)

    # ─────────────────────────────────────────
    # Stage C loader controls (Auto-load + picker)
    # ─────────────────────────────────────────
    def _find_stage_c_candidates():
        pats = ["valuation_ai*.csv", "valuation_ai*.parquet"]
        files = []
        for pat in pats:
            files.extend(glob.glob(os.path.join(RUNS_DIR, pat)))
        return sorted(files, key=os.path.getmtime, reverse=True)

    if "stage_c_selected_path" not in st.session_state:
        st.session_state["stage_c_selected_path"] = None

    ctrl1, ctrl2, ctrl3 = st.columns([1.2, 1, 2.8])
    with ctrl1:
        btn_autoload = st.button("🔄 Auto-load latest Stage C", use_container_width=True)
    with ctrl2:
        btn_refresh = st.button("🔁 Refresh list", use_container_width=True)
    with ctrl3:
        st.caption("Looks for `valuation_ai*.csv|.parquet` under `./.tmp_runs`")

    if btn_refresh:
        pass  # triggers rerun → list will refresh

    candidates = _find_stage_c_candidates()
    if not candidates:
        st.warning("⚠️ No AI appraisal results found. Please complete Stage C first.")
        st.stop()

    # Pick newest on first load or when autoload pressed
    if btn_autoload:
        st.session_state["stage_c_selected_path"] = candidates[0]
    elif not st.session_state["stage_c_selected_path"]:
        st.session_state["stage_c_selected_path"] = candidates[0]
    # Ensure the selected one still exists
    if st.session_state["stage_c_selected_path"] not in candidates:
        st.session_state["stage_c_selected_path"] = candidates[0]

    # Human-friendly label
    def _fmt(p):
        ts = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")
        return f"{os.path.basename(p)}  •  {ts}"

    current_idx = candidates.index(st.session_state["stage_c_selected_path"])
    picked = st.selectbox(
        "Stage C output to review",
        options=candidates,
        index=current_idx,
        format_func=_fmt,
    )
    st.session_state["stage_c_selected_path"] = picked

    # ─────────────────────────────────────────
    # ✅ NEW: Direct Upload of Stage C Export (CSV)
    # ─────────────────────────────────────────
    st.markdown("### 📤 Or Upload Stage C Export")
    uploaded_c = st.file_uploader(
        "Upload a Stage C file (valuation_ai*.csv)",
        type=["csv"],
        key="stage_c_upload"
    )

    if uploaded_c is not None:
        try:
            df_ai = pd.read_csv(uploaded_c)
            #st.success(f"✅ Imported uploaded file ({len[df_ai)} rows).")
            st.success(f"✅ Imported uploaded file ({len(df_ai)} rows).")


            temp_path = os.path.join(RUNS_DIR, f"uploaded_stage_c_{datetime.now().timestamp()}.csv")
            df_ai.to_csv(temp_path, index=False, encoding="utf-8-sig")

            st.session_state["stage_c_selected_path"] = temp_path
            st.session_state["df_ai_current"] = df_ai.copy()

            st.rerun()

        except Exception as e:
            st.error(f"Upload failed: {e}")
    

    # Load the selected Stage C table → df_ai
    ai_path = st.session_state["stage_c_selected_path"]
    try:
        if ai_path.lower().endswith(".parquet"):
            df_ai = pd.read_parquet(ai_path)
        else:
            df_ai = pd.read_csv(ai_path)
        st.success(f"✅ Loaded Stage C: {os.path.basename(ai_path)}  ({len(df_ai)} rows × {df_ai.shape[1]} cols)")
    except Exception as e:
        st.error(f"Failed to read `{ai_path}`: {e}")
        st.stop()

    # Ensure join keys exist to avoid editor KeyErrors later
    for col in ["application_id", "asset_id", "asset_type", "city"]:
        if col not in df_ai.columns:
            df_ai[col] = None

    # Ensure human_value / justification columns for adjustments
    if "human_value" not in df_ai.columns:
        df_ai["human_value"] = pd.to_numeric(df_ai["fmv"], errors="coerce") if "fmv" in df_ai.columns else np.nan
    if "justification" not in df_ai.columns:
        df_ai["justification"] = ""

    # ─────────────────────────────────────────
    # ✅ Auto-run Real Estate Evaluator (if coordinates available)
    # ─────────────────────────────────────────
    # Check if we need to evaluate assets (if not already evaluated or if data changed)
    has_coords = "lat" in df_ai.columns and "lon" in df_ai.columns
    needs_evaluation = has_coords and (
        ss.get("re_evaluated_df") is None or 
        len(ss.get("re_evaluated_df", pd.DataFrame())) != len(df_ai) or
        ss.get("asset_re_eval_hash") != hash(tuple(sorted(df_ai.get("asset_id", []).astype(str))))
    )
    
    if needs_evaluation and has_coords:
        eval_df = df_ai.dropna(subset=["lat", "lon"]).copy()
        
        if not eval_df.empty:
            # Auto-evaluate in background (non-blocking)
            try:
                API_URL = os.getenv("API_URL", "http://localhost:8090")
                url = f"{API_URL}/v1/agents/real_estate_evaluator/run/json"
                
                # Prepare payload
                payload_data = []
                for idx, row in eval_df.iterrows():
                    asset_id = str(row.get("asset_id", "")) if pd.notna(row.get("asset_id")) else ""
                    address = asset_id if asset_id else str(row.get("city", "Unknown"))
                    
                    payload_data.append({
                        "address": address,
                        "asset_id": asset_id,
                        "city": str(row.get("city", "Unknown")),
                        "district": str(row.get("district", "")),
                        "property_type": str(row.get("asset_type", "Unknown")),
                        "customer_price": float(row.get("realizable_value", row.get("ai_adjusted", 0))) if pd.notna(row.get("realizable_value", row.get("ai_adjusted", 0))) else 0,
                        "area_sqm": float(row.get("area_sqm", 0)) if pd.notna(row.get("area_sqm")) else 0,
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"])
                    })
                
                payload = {
                    "df": payload_data,
                    "params": {"use_scraper": True}
                }
                
                # Run evaluation
                resp = requests.post(url, json=payload, timeout=120)
                
                if resp.status_code == 200:
                    result = resp.json()
                    
                    # Store evaluated data
                    evaluated_df_data = result.get("evaluated_df", [])
                    if isinstance(evaluated_df_data, list):
                        ss["re_evaluated_df"] = pd.DataFrame(evaluated_df_data)
                    else:
                        ss["re_evaluated_df"] = pd.DataFrame([evaluated_df_data])
                    
                    ss["re_map_data"] = result.get("map_data", [])
                    ss["re_zone_data"] = result.get("zone_data", [])
                    ss["re_summary"] = result.get("summary", {})
                    ss["asset_re_eval_hash"] = hash(tuple(sorted(df_ai.get("asset_id", []).astype(str))))
            except Exception as e:
                # Silently fail - map will just not show if evaluation fails
                pass

    # ── Market Projections (safe)
    st.markdown("### 📈 Market Projections")
    horizon = st.select_slider("Projection Horizon (years)", options=[3, 5, 10], value=5)
    growth = st.slider("Expected Market Growth (%)", -10, 25, 4) / 100

    df_proj = df_ai.copy()
    if "fmv" in df_proj.columns:
        fmv_num = pd.to_numeric(df_proj["fmv"], errors="coerce")
        df_proj[f"fmv_proj_{horizon}y"] = (fmv_num * ((1 + growth) ** horizon)).round(0)
        st.line_chart(df_proj[["fmv", f"fmv_proj_{horizon}y"]])
    else:
        st.info("FMV column not found; projection chart will appear after you run Stage C.")

    # ✅ Helper: return the first column present in dataframe
    def _first_present(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None


    # ─────────────────────────────────────────
    # ✅ Real Estate Evaluator Map (INTEGRATED DIRECTLY)
    # ─────────────────────────────────────────
    st.markdown("### 🏠 Real Estate Evaluator - Market Price Map")
    
    # Display Real Estate Evaluator map if available
    if ss.get("re_map_data") and len(ss["re_map_data"]) > 0:
        map_data = ss["re_map_data"]
        zone_data = ss.get("re_zone_data", [])
        
        # Prepare GeoJSON for customer assets
        asset_features = []
        for item in map_data:
            asset_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [item["lon"], item["lat"]]
                },
                "properties": item
            })
        
        assets_geojson = {
            "type": "FeatureCollection",
            "features": asset_features
        }
        
        # Prepare GeoJSON for price zones
        zone_features = []
        for zone in zone_data:
            zone_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [zone["polygon"]]
                },
                "properties": {
                    "city": zone["city"],
                    "district": zone["district"],
                    "market_price": zone["market_price"],
                    "color": zone["color"],
                    "price_range": zone["price_range"]
                }
            })
        
        zones_geojson = {
            "type": "FeatureCollection",
            "features": zone_features
        }
        
        # Get current theme
        current_theme = get_theme()
        
        # Generate and render map directly (no button needed)
        map_html = _generate_ultra_3d_map(map_data, zone_data, assets_geojson, zones_geojson, current_theme)
        components.html(map_html, height=800)
        
        # Display summary with calculated values from actual asset data
        if ss.get("re_summary") or ss.get("re_map_data"):
            summary = ss.get("re_summary", {})
            
            # Get customer prices from map_data (most reliable source - contains original customer_price)
            # Also try asset_df as fallback
            asset_df = None
            if "asset_ai_df" in ss and ss["asset_ai_df"] is not None:
                asset_df = ss["asset_ai_df"]
            elif "last_merged_df" in ss and ss["last_merged_df"] is not None:
                asset_df = ss["last_merged_df"]
            customer_prices_per_sqm = []
            customer_prices_total = []
            if ss.get("re_map_data"):
                for item in ss["re_map_data"]:
                    # Customer price from map_data (this is what was sent to evaluator)
                    cust_price = item.get("customer_price") or item.get("value") or item.get("price")
                    if cust_price and cust_price > 0:
                        cust_price_val = float(cust_price)
                        # Check if it's per sqm or total by comparing with area
                        area = item.get("area_sqm", 0)
                        if area and area > 0:
                            # If customer_price is much larger than area, it's likely total price
                            if cust_price_val > area * 1000:  # Likely total price
                                customer_prices_total.append(cust_price_val)
                                # Convert to per sqm for comparison
                                customer_prices_per_sqm.append(cust_price_val / area)
                            else:
                                # Likely per sqm already
                                customer_prices_per_sqm.append(cust_price_val)
                        else:
                            # No area info, assume it's total price
                            customer_prices_total.append(cust_price_val)
            
            # If we don't have customer prices from map_data, use asset_df
            if not customer_prices_per_sqm and not customer_prices_total and asset_df is not None:
                for col in ["realizable_value", "customer_price", "market_value", "ai_adjusted", "fmv", "human_value"]:
                    if col in asset_df.columns:
                        prices = pd.to_numeric(asset_df[col], errors="coerce").dropna()
                        valid_prices = prices[prices > 0].tolist()
                        if valid_prices:
                            customer_prices_total.extend(valid_prices)
                            break
            
            # Calculate market prices from map data (per sqm)
            market_prices_per_sqm = []
            if ss.get("re_map_data"):
                for item in ss["re_map_data"]:
                    # Market price per sqm from evaluator response
                    market_price_per_sqm = item.get("market_price_per_sqm") or item.get("market_price", 0)
                    if market_price_per_sqm and market_price_per_sqm > 0:
                        market_prices_per_sqm.append(float(market_price_per_sqm))
            
            # Calculate averages
            total_assets = len(ss.get("re_map_data", [])) or summary.get("total_assets", 0)
            avg_market_price = np.mean(market_prices_per_sqm) if market_prices_per_sqm else summary.get("avg_market_price", 0)
            
            # Use per sqm customer prices if available, otherwise convert total to per sqm
            if customer_prices_per_sqm:
                avg_customer_price = np.mean(customer_prices_per_sqm)
            elif customer_prices_total and market_prices_per_sqm:
                # Convert total customer prices to per sqm using average area
                if ss.get("re_map_data"):
                    areas = [item.get("area_sqm", 0) for item in ss["re_map_data"] if item.get("area_sqm", 0) > 0]
                    avg_area = np.mean(areas) if areas else 100  # Default 100 sqm
                    avg_customer_price = np.mean(customer_prices_total) / avg_area if avg_area > 0 else 0
                else:
                    avg_customer_price = 0
            else:
                avg_customer_price = 0
            
            # Calculate price delta (both should be per sqm now)
            if avg_market_price > 0 and avg_customer_price > 0:
                avg_price_delta = ((avg_customer_price - avg_market_price) / avg_market_price) * 100
            elif avg_market_price > 0:
                avg_price_delta = -100.0  # Customer price is 0
            else:
                avg_price_delta = 0.0
            
            st.markdown("#### 📊 Market Comparison Summary")
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("Total Assets", total_assets)
            with col_b:
                st.metric("Avg Market Price", f"${avg_market_price:,.0f}/sqm" if avg_market_price > 0 else "N/A")
            with col_c:
                st.metric("Avg Customer Price", f"${avg_customer_price:,.0f}/sqm" if avg_customer_price > 0 else "N/A")
            with col_d:
                delta_color = "normal" if abs(avg_price_delta) < 10 else "inverse"
                st.metric("Avg Price Delta", f"{avg_price_delta:+.1f}%", delta=f"{abs(avg_price_delta):.1f}%", delta_color=delta_color)
        
        # ─────────────────────────────────────────
        # ✅ Big Update Button (under the map)
        # ─────────────────────────────────────────
        st.markdown("---")
        st.markdown("")
        
        # Create a large button using custom CSS for bigger size
        st.markdown("""
        <style>
        /* Target the specific button by key */
        div[data-testid="stButton"]:has(button[kind="primary"][data-baseweb="button"]) {
            width: 100% !important;
        }
        button[kind="primary"][data-baseweb="button"] {
            height: 90px !important;
            font-size: 28px !important;
            font-weight: 700 !important;
            padding: 25px 50px !important;
            width: 100% !important;
            border-radius: 10px !important;
            transition: all 0.3s ease !important;
        }
        button[kind="primary"][data-baseweb="button"]:hover {
            transform: scale(1.02) !important;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3) !important;
        }
        /* Fallback selectors */
        div[data-testid="stButton"] > button[kind="primary"] {
            height: 90px !important;
            font-size: 28px !important;
            font-weight: 700 !important;
            padding: 25px 50px !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        button_col1, button_col2, button_col3 = st.columns([0.5, 4, 0.5])
        with button_col2:
            # Create the button
            button_clicked = st.button(
                "🔄 UPDATE REVIEW TABLE WITH MARKET PRICES",
                use_container_width=True,
                type="primary",
                key="btn_update_review_table_map"
            )
        
        # Handle button click
        if button_clicked:
            # Get the current dataframe
            df_ai_with_market = df_ai.copy()
            
            # Merge market prices if available
            if ss.get("re_evaluated_df") is not None:
                re_eval_df = ss["re_evaluated_df"]
                
                # Create a mapping from asset identifiers to market prices
                market_price_map = {}
                market_price_per_sqm_map = {}
                
                for _, re_row in re_eval_df.iterrows():
                    market_price_per_sqm = float(re_row.get("market_price_per_sqm", 0))
                    area_sqm = float(re_row.get("area_sqm", 0))
                    market_price_total = market_price_per_sqm * area_sqm if area_sqm > 0 else 0
                    
                    asset_id = str(re_row.get("asset_id", "")).lower() if pd.notna(re_row.get("asset_id")) else ""
                    address = str(re_row.get("address", "")).lower()
                    city = str(re_row.get("city", "")).lower()
                    district = str(re_row.get("district", "")).lower()
                    
                    keys = []
                    if asset_id:
                        keys.append(asset_id)
                    if address:
                        keys.append(address)
                    if city and district:
                        keys.append(f"{city}_{district}")
                    if city:
                        keys.append(city)
                    
                    for key in keys:
                        if key:
                            market_price_map[key] = market_price_total
                            market_price_per_sqm_map[key] = market_price_per_sqm
                
                # Ensure columns exist
                if "human_value" not in df_ai_with_market.columns:
                    df_ai_with_market["human_value"] = pd.to_numeric(df_ai_with_market.get("fmv", np.nan), errors="coerce")
                if "justification" not in df_ai_with_market.columns:
                    df_ai_with_market["justification"] = ""
                
                # Update human_value with market prices where available
                updated_count = 0
                for idx, row in df_ai_with_market.iterrows():
                    asset_id = str(row.get("asset_id", "")).lower() if pd.notna(row.get("asset_id")) else ""
                    city_val = str(row.get("city", "")).lower() if pd.notna(row.get("city")) else ""
                    district_val = str(row.get("district", "")).lower() if pd.notna(row.get("district")) else ""
                    
                    matched_price = None
                    if asset_id and asset_id in market_price_map:
                        matched_price = market_price_map[asset_id]
                    elif city_val and district_val:
                        city_district_key = f"{city_val}_{district_val}"
                        if city_district_key in market_price_map:
                            matched_price = market_price_map[city_district_key]
                    elif city_val and city_val in market_price_map:
                        matched_price = market_price_map[city_val]
                    
                    if matched_price:
                        df_ai_with_market.at[idx, "human_value"] = matched_price
                        existing_just = str(df_ai_with_market.at[idx, "justification"]) if pd.notna(df_ai_with_market.at[idx, "justification"]) else ""
                        df_ai_with_market.at[idx, "justification"] = existing_just + " | Updated with market price from Real Estate Evaluator map"
                        updated_count += 1
                
                # Save back to file to persist changes
                ai_path = st.session_state.get("stage_c_selected_path")
                if ai_path:
                    try:
                        df_ai_with_market.to_csv(ai_path, index=False, encoding="utf-8-sig")
                    except Exception:
                        pass
                
                # Update session state
                ss["asset_ai_df"] = df_ai_with_market.copy()
                ss["last_merged_df"] = df_ai_with_market.copy()
                
                st.success(f"✅ Review table updated! Applied market prices to {updated_count} assets.")
                st.rerun()
            else:
                st.warning("⚠️ No market price data available. Please ensure the map has been generated.")
        
        st.markdown("")
        st.markdown("---")
        
        # ─────────────────────────────────────────
        # ✅ Car Price Depreciation Chart (Japanese Models)
        # ─────────────────────────────────────────
        st.markdown("### 🚗 Japanese Car Models - Market Price & Depreciation Analysis")
        st.caption("Price depreciation trends for major Japanese car models over time")
        
        # Generate mockup data for major Japanese car models
        japanese_cars = [
            "Toyota Camry", "Toyota Corolla", "Toyota Prius", "Toyota RAV4", "Toyota Highlander",
            "Honda Accord", "Honda Civic", "Honda CR-V", "Honda Pilot", "Honda Odyssey",
            "Nissan Altima", "Nissan Sentra", "Nissan Rogue", "Nissan Pathfinder", "Nissan Maxima",
            "Mazda CX-5", "Mazda CX-9", "Mazda3", "Mazda6", "Mazda MX-5",
            "Subaru Outback", "Subaru Forester", "Subaru Impreza", "Subaru Legacy", "Subaru Ascent",
            "Lexus RX", "Lexus ES", "Lexus NX", "Lexus GX", "Lexus LS",
            "Acura MDX", "Acura RDX", "Acura TLX", "Acura ILX", "Acura NSX",
            "Infiniti Q50", "Infiniti QX60", "Infiniti QX80", "Infiniti QX50", "Infiniti Q70"
        ]
        
        # Create depreciation data (years 0-10, with realistic depreciation curves)
        years = list(range(11))  # 0 to 10 years
        car_data = []
        
        for car in japanese_cars[:15]:  # Show top 15 models
            # Base price varies by car model (luxury vs economy)
            if "Lexus" in car or "Acura" in car or "Infiniti" in car:
                base_price = np.random.uniform(35000, 55000)
            elif "Toyota" in car or "Honda" in car:
                base_price = np.random.uniform(25000, 35000)
            else:
                base_price = np.random.uniform(20000, 30000)
            
            for year in years:
                # Realistic depreciation: ~20% first year, ~15% second year, then ~10% annually
                if year == 0:
                    depreciation = 0
                elif year == 1:
                    depreciation = 0.20  # 20% first year
                elif year == 2:
                    depreciation = 0.32  # cumulative: 20% + 15% of remaining
                else:
                    # After year 2: ~10% annually of remaining value
                    remaining_value = 0.68  # After 2 years
                    annual_depreciation = 0.10
                    for y in range(3, year + 1):
                        remaining_value *= (1 - annual_depreciation)
                    depreciation = 1 - remaining_value
                
                # Add some randomness per model
                model_factor = hash(car) % 100 / 1000  # Consistent per model
                depreciation += np.random.uniform(-0.01, 0.01) + model_factor
                depreciation = max(0, min(0.90, depreciation))  # Cap at 90% depreciation
                
                current_price = base_price * (1 - depreciation)
                car_data.append({
                    "Model": car,
                    "Year": year,
                    "Market Price": current_price,
                    "Depreciation %": depreciation * 100,
                    "Base Price": base_price
                })
        
        car_df = pd.DataFrame(car_data)
        
        # Create interactive chart
        fig_cars = px.line(
            car_df,
            x="Year",
            y="Market Price",
            color="Model",
            title="Japanese Car Models - Market Price Depreciation Over Time",
            labels={"Market Price": "Market Price ($)", "Year": "Years Since Purchase"},
            hover_data=["Depreciation %", "Base Price"]
        )
        fig_cars.update_layout(
            height=600,
            xaxis_title="Years Since Purchase",
            yaxis_title="Market Price ($)",
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
            hovermode='closest'
        )
        st.plotly_chart(fig_cars, use_container_width=True)
        
        # Summary statistics
        st.markdown("#### 📊 Depreciation Summary by Model")
        summary_stats = car_df.groupby("Model").agg({
            "Market Price": ["min", "max", "mean"],
            "Depreciation %": "max"
        }).round(2)
        summary_stats.columns = ["Min Price ($)", "Max Price ($)", "Avg Price ($)", "Max Depreciation (%)"]
        st.dataframe(summary_stats, use_container_width=True)
        
        st.markdown("---")
    else:
        st.info("📍 Map will appear here once asset coordinates are available and evaluation is complete.")

    # ─────────────────────────────────────────
    # ✅ Human Review Table (LIVE + REFRESH SAFE)
    # ─────────────────────────────────────────
    st.markdown("### ✏️ Human review and justification table")
    
    # Merge Real Estate Evaluator market prices into the editable dataframe
    df_ai_with_market = df_ai.copy()
    
    if ss.get("re_evaluated_df") is not None:
        re_eval_df = ss["re_evaluated_df"]
        
        # Create a mapping from asset identifiers to market prices
        market_price_map = {}
        market_price_per_sqm_map = {}
        price_delta_map = {}
        evaluation_status_map = {}
        
        for _, re_row in re_eval_df.iterrows():
            # Calculate total market price
            market_price_per_sqm = float(re_row.get("market_price_per_sqm", 0))
            area_sqm = float(re_row.get("area_sqm", 0))
            market_price_total = market_price_per_sqm * area_sqm if area_sqm > 0 else 0
            
            # Use asset_id if available (for direct matching), otherwise use address
            asset_id = str(re_row.get("asset_id", "")).lower() if pd.notna(re_row.get("asset_id")) else ""
            address = str(re_row.get("address", "")).lower()
            city = str(re_row.get("city", "")).lower()
            district = str(re_row.get("district", "")).lower()
            
            # Create multiple keys for flexible matching
            keys = []
            if asset_id:
                keys.append(asset_id)
            if address:
                keys.append(address)
            if city and district:
                keys.append(f"{city}_{district}")
            if city:
                keys.append(city)
            
            # Store market data with all keys
            for key in keys:
                if key:
                    market_price_map[key] = market_price_total
                    market_price_per_sqm_map[key] = market_price_per_sqm
                    price_delta_map[key] = float(re_row.get("price_delta", 0))
                    evaluation_status_map[key] = str(re_row.get("evaluation_status", ""))
        
        # Add market price columns to df_ai
        df_ai_with_market["market_price"] = np.nan
        df_ai_with_market["market_price_per_sqm"] = np.nan
        df_ai_with_market["current_price_estimate"] = np.nan  # For cars and other non-real estate assets
        df_ai_with_market["price_delta_pct"] = np.nan
        df_ai_with_market["market_evaluation_status"] = ""
        df_ai_with_market["human_vs_market_pct"] = np.nan
        df_ai_with_market["ai_vs_market_pct"] = np.nan
        
        # Add customer_estimate_price column (from realizable_value, customer_price, or fmv)
        if "customer_estimate_price" not in df_ai_with_market.columns:
            df_ai_with_market["customer_estimate_price"] = np.nan
        
        # Add new columns: date of purchase, warranty status, price depreciation, years of usage
        if "date_of_purchase" not in df_ai_with_market.columns:
            df_ai_with_market["date_of_purchase"] = pd.NaT
        if "warranty_status" not in df_ai_with_market.columns:
            df_ai_with_market["warranty_status"] = ""
        if "price_depreciation" not in df_ai_with_market.columns:
            df_ai_with_market["price_depreciation"] = np.nan
        if "nb_years_usage" not in df_ai_with_market.columns:
            df_ai_with_market["nb_years_usage"] = np.nan
        
        # Match assets to market prices and calculate asset-specific fields
        for idx, row in df_ai_with_market.iterrows():
            asset_id = str(row.get("asset_id", "")).lower() if pd.notna(row.get("asset_id")) else ""
            city_val = str(row.get("city", "")).lower() if pd.notna(row.get("city")) else ""
            district_val = str(row.get("district", "")).lower() if pd.notna(row.get("district")) else ""
            asset_type = str(row.get("asset_type", "")).lower() if pd.notna(row.get("asset_type")) else ""
            
            matched_price = None
            matched_price_per_sqm = None
            matched_delta = None
            matched_status = None
            
            # Try matching by asset_id, then city+district, then city only
            if asset_id and asset_id in market_price_map:
                matched_price = market_price_map[asset_id]
                matched_price_per_sqm = market_price_per_sqm_map[asset_id]
                matched_delta = price_delta_map[asset_id]
                matched_status = evaluation_status_map[asset_id]
            elif city_val and district_val:
                city_district_key = f"{city_val}_{district_val}"
                if city_district_key in market_price_map:
                    matched_price = market_price_map[city_district_key]
                    matched_price_per_sqm = market_price_per_sqm_map[city_district_key]
                    matched_delta = price_delta_map[city_district_key]
                    matched_status = evaluation_status_map[city_district_key]
            elif city_val and city_val in market_price_map:
                matched_price = market_price_map[city_val]
                matched_price_per_sqm = market_price_per_sqm_map[city_val]
                matched_delta = price_delta_map[city_val]
                matched_status = evaluation_status_map[city_val]
            
            # Asset-type-specific price handling
            is_real_estate = any(term in asset_type for term in ["house", "apartment", "land", "property", "residential", "commercial", "industrial", "multifamily", "factory"])
            is_car = any(term in asset_type for term in ["car", "vehicle", "automobile", "truck", "suv"])
            
            if is_real_estate:
                # Real estate: use market_price_per_sqm and calculate total from area
                if pd.isna(matched_price) and matched_price_per_sqm and pd.notna(row.get("area_sqm")):
                    area = float(row.get("area_sqm", 0))
                    if area > 0:
                        matched_price = matched_price_per_sqm * area
                # Don't set current_price_estimate for real estate
                df_ai_with_market.at[idx, "current_price_estimate"] = np.nan
            elif is_car or not is_real_estate:
                # Cars and other assets: use current_price_estimate, not sqm price
                if matched_price:
                    df_ai_with_market.at[idx, "current_price_estimate"] = matched_price
                # Don't set market_price_per_sqm for cars
                df_ai_with_market.at[idx, "market_price_per_sqm"] = np.nan
            
            # Assign matched values
            if matched_price:
                if is_real_estate:
                    df_ai_with_market.at[idx, "market_price"] = matched_price
                else:
                    df_ai_with_market.at[idx, "current_price_estimate"] = matched_price
            if matched_price_per_sqm and is_real_estate:
                df_ai_with_market.at[idx, "market_price_per_sqm"] = matched_price_per_sqm
            if matched_delta is not None:
                df_ai_with_market.at[idx, "price_delta_pct"] = matched_delta
            if matched_status:
                df_ai_with_market.at[idx, "market_evaluation_status"] = matched_status
            
            # Calculate date of purchase and years of usage
            date_of_purchase = row.get("date_of_purchase")
            if pd.isna(date_of_purchase) or date_of_purchase is None or date_of_purchase == "":
                # Generate a random purchase date if not provided (between 0-15 years ago)
                years_ago = np.random.uniform(0, 15)
                date_of_purchase = datetime.now() - pd.Timedelta(days=years_ago * 365)
                df_ai_with_market.at[idx, "date_of_purchase"] = date_of_purchase
            
            # Calculate years of usage
            date_val = df_ai_with_market.at[idx, "date_of_purchase"]
            if pd.notna(date_val) and date_val != "":
                try:
                    if isinstance(date_val, str):
                        date_val = pd.to_datetime(date_val)
                    elif not isinstance(date_val, (datetime, pd.Timestamp)):
                        date_val = pd.to_datetime(date_val)
                    years_usage = (datetime.now() - date_val.to_pydatetime()).days / 365.25
                    df_ai_with_market.at[idx, "nb_years_usage"] = round(years_usage, 1)
                except Exception as e:
                    df_ai_with_market.at[idx, "nb_years_usage"] = np.nan
            
            # Set warranty status based on asset type and age
            warranty_status = row.get("warranty_status", "")
            if not warranty_status or warranty_status == "":
                years_usage = df_ai_with_market.at[idx, "nb_years_usage"]
                if pd.notna(years_usage):
                    if is_car:
                        # Cars: typically 3-5 year warranty
                        warranty_status = "Active" if years_usage < 3 else ("Expiring Soon" if years_usage < 5 else "Expired")
                    elif is_real_estate:
                        # Real estate: structural warranty typically 10 years
                        warranty_status = "Active" if years_usage < 10 else "Expired"
                    else:
                        # Other assets: default 2 year warranty
                        warranty_status = "Active" if years_usage < 2 else "Expired"
                else:
                    warranty_status = "Unknown"
                df_ai_with_market.at[idx, "warranty_status"] = warranty_status
            
            # Calculate price depreciation based on asset type and years of usage
            years_usage = df_ai_with_market.at[idx, "nb_years_usage"]
            if pd.notna(years_usage) and years_usage > 0:
                if is_car:
                    # Cars: ~20% first year, ~15% second year, then ~10% annually
                    if years_usage <= 1:
                        depreciation_pct = 20
                    elif years_usage <= 2:
                        depreciation_pct = 32
                    else:
                        remaining_value = 0.68
                        for y in range(3, int(years_usage) + 1):
                            remaining_value *= 0.90
                        depreciation_pct = (1 - remaining_value) * 100
                elif is_real_estate:
                    # Real estate: much slower depreciation, ~2-3% annually
                    depreciation_pct = min(years_usage * 2.5, 30)  # Cap at 30%
                else:
                    # Other assets: ~10% annually
                    depreciation_pct = min(years_usage * 10, 80)  # Cap at 80%
                
                df_ai_with_market.at[idx, "price_depreciation"] = round(depreciation_pct, 1)
            
            # Set customer_estimate_price (from realizable_value, customer_price, or fmv)
            customer_est_price = None
            if "realizable_value" in df_ai_with_market.columns:
                customer_est_price = pd.to_numeric(df_ai_with_market.at[idx, "realizable_value"], errors="coerce")
            if (pd.isna(customer_est_price) or customer_est_price == 0) and "customer_price" in df_ai_with_market.columns:
                customer_est_price = pd.to_numeric(df_ai_with_market.at[idx, "customer_price"], errors="coerce")
            if (pd.isna(customer_est_price) or customer_est_price == 0) and "fmv" in df_ai_with_market.columns:
                customer_est_price = pd.to_numeric(df_ai_with_market.at[idx, "fmv"], errors="coerce")
            if pd.notna(customer_est_price) and customer_est_price > 0:
                df_ai_with_market.at[idx, "customer_estimate_price"] = customer_est_price
            
            # Calculate AI recommended price = market_price - 10% (or current_price_estimate - 10% for non-real estate)
            market_price_for_ai = matched_price if is_real_estate else df_ai_with_market.at[idx, "current_price_estimate"]
            if pd.notna(market_price_for_ai) and market_price_for_ai > 0:
                ai_recommended_price = market_price_for_ai * 0.9  # Market price - 10%
                df_ai_with_market.at[idx, "ai_adjusted"] = ai_recommended_price
                # Pre-populate human_value with AI recommended price if not already set
                if "human_value" not in df_ai_with_market.columns or pd.isna(df_ai_with_market.at[idx, "human_value"]) or df_ai_with_market.at[idx, "human_value"] == 0:
                    df_ai_with_market.at[idx, "human_value"] = ai_recommended_price
            
            # Calculate percentage above/below market for human_value and ai_adjusted
            price_for_comparison = matched_price if is_real_estate else df_ai_with_market.at[idx, "current_price_estimate"]
            if price_for_comparison and price_for_comparison > 0:
                # Calculate for human_value if available
                human_val = pd.to_numeric(df_ai_with_market.at[idx, "human_value"], errors="coerce")
                if pd.notna(human_val) and human_val > 0:
                    human_vs_market_pct = ((human_val - price_for_comparison) / price_for_comparison) * 100
                    df_ai_with_market.at[idx, "human_vs_market_pct"] = human_vs_market_pct
                else:
                    df_ai_with_market.at[idx, "human_vs_market_pct"] = np.nan
                
                # Calculate for ai_adjusted if available
                ai_adj = pd.to_numeric(df_ai_with_market.at[idx, "ai_adjusted"], errors="coerce")
                if pd.notna(ai_adj) and ai_adj > 0:
                    ai_vs_market_pct = ((ai_adj - price_for_comparison) / price_for_comparison) * 100
                    df_ai_with_market.at[idx, "ai_vs_market_pct"] = ai_vs_market_pct
                else:
                    df_ai_with_market.at[idx, "ai_vs_market_pct"] = np.nan
            else:
                df_ai_with_market.at[idx, "human_vs_market_pct"] = np.nan
                df_ai_with_market.at[idx, "ai_vs_market_pct"] = np.nan
        
        # Show market price comparison metrics
        if "market_price" in df_ai_with_market.columns and df_ai_with_market["market_price"].notna().any():
            st.markdown("#### 💰 Market Price Comparison")
            
            market_cols = st.columns(4)
            with market_cols[0]:
                avg_market = df_ai_with_market["market_price"].mean()
                st.metric("Avg Market Price", f"${avg_market:,.0f}" if pd.notna(avg_market) else "N/A")
            with market_cols[1]:
                avg_ai = df_ai_with_market["ai_adjusted"].mean() if "ai_adjusted" in df_ai_with_market.columns else 0
                st.metric("Avg AI Adjusted", f"${avg_ai:,.0f}" if pd.notna(avg_ai) else "N/A")
            with market_cols[2]:
                if pd.notna(avg_market) and pd.notna(avg_ai) and avg_market > 0:
                    market_vs_ai_delta = ((avg_ai - avg_market) / avg_market * 100)
                    delta_color = "normal" if abs(market_vs_ai_delta) < 10 else "inverse"
                    st.metric("Market vs AI Delta", f"{market_vs_ai_delta:+.1f}%", delta=f"{abs(market_vs_ai_delta):.1f}% difference", delta_color=delta_color)
            with market_cols[3]:
                above_market_count = (df_ai_with_market["market_evaluation_status"] == "above_market").sum()
                below_market_count = (df_ai_with_market["market_evaluation_status"] == "below_market").sum()
                st.metric("Above/Below Market", f"{above_market_count} / {below_market_count}")
            
            # Single button to update review table with market prices
            st.markdown("---")
            update_col1, update_col2, update_col3 = st.columns([1, 2, 1])
            with update_col2:
                if st.button("🔄 Update Review Table with Market Prices", use_container_width=True, type="primary", key="btn_update_review_table"):
                    # Update human_value with market prices where available
                    market_price_mask = df_ai_with_market["market_price"].notna()
                    df_ai_with_market.loc[market_price_mask, "human_value"] = df_ai_with_market.loc[market_price_mask, "market_price"]
                    
                    # Update justification
                    existing_just = df_ai_with_market.loc[market_price_mask, "justification"].fillna("")
                    df_ai_with_market.loc[market_price_mask, "justification"] = existing_just + " | Updated with market price from Real Estate Evaluator map"
                    
                    # Save back to file to persist changes
                    ai_path = st.session_state.get("stage_c_selected_path")
                    if ai_path:
                        try:
                            df_ai_with_market.to_csv(ai_path, index=False, encoding="utf-8-sig")
                        except Exception:
                            pass
                    
                    # Update session state
                    ss["asset_ai_df"] = df_ai_with_market.copy()
                    
                    updated_count = market_price_mask.sum()
                    st.success(f"✅ Review table updated! Applied market prices to {updated_count} assets.")
                    st.rerun()
    
    # Use the enhanced dataframe
    df_ai = df_ai_with_market
    
    # Clear persisted edited dataframe if the underlying data has changed significantly
    # (e.g., new data loaded, market prices updated)
    # We'll detect this by checking if the number of rows or key columns changed
    if "human_review_edited_df" in ss and ss["human_review_edited_df"] is not None:
        persisted_df = ss["human_review_edited_df"]
        # If row count changed significantly or if this is a fresh load, reset persisted edits
        if len(persisted_df) != len(df_ai) or "application_id" not in persisted_df.columns:
            # Clear persisted edits to start fresh
            if "human_review_edited_df" in ss:
                del ss["human_review_edited_df"]
            if "human_review_original_ai_values" in ss:
                del ss["human_review_original_ai_values"]

    # ─────────────────────────────────────────
    # ✅ Ensure ALL columns are filled with default values
    # ─────────────────────────────────────────
    
    # Core identification columns
    for col in ["application_id", "asset_id", "asset_type", "city", "district"]:
        if col not in df_ai.columns:
            df_ai[col] = ""
        else:
            df_ai[col] = df_ai[col].fillna("")
    
    # Date and usage columns
    if "date_of_purchase" not in df_ai.columns:
        df_ai["date_of_purchase"] = pd.NaT
    else:
        # Fill missing dates with random dates (0-15 years ago)
        missing_dates = df_ai["date_of_purchase"].isna()
        if missing_dates.any():
            for idx in df_ai[missing_dates].index:
                years_ago = np.random.uniform(0, 15)
                df_ai.at[idx, "date_of_purchase"] = datetime.now() - pd.Timedelta(days=years_ago * 365)
    
    # Calculate years of usage if missing
    if "nb_years_usage" not in df_ai.columns:
        df_ai["nb_years_usage"] = np.nan
    
    missing_usage = df_ai["nb_years_usage"].isna()
    if missing_usage.any():
        for idx in df_ai[missing_usage].index:
            date_val = df_ai.at[idx, "date_of_purchase"]
            if pd.notna(date_val) and date_val != "":
                try:
                    if isinstance(date_val, str):
                        date_val = pd.to_datetime(date_val)
                    years_usage = (datetime.now() - date_val.to_pydatetime()).days / 365.25
                    df_ai.at[idx, "nb_years_usage"] = round(years_usage, 1)
                except Exception:
                    df_ai.at[idx, "nb_years_usage"] = np.random.uniform(0, 15)
            else:
                df_ai.at[idx, "nb_years_usage"] = np.random.uniform(0, 15)
    
    # Warranty status
    if "warranty_status" not in df_ai.columns:
        df_ai["warranty_status"] = ""
    
    missing_warranty = df_ai["warranty_status"].isna() | (df_ai["warranty_status"] == "")
    if missing_warranty.any():
        for idx in df_ai[missing_warranty].index:
            asset_type = str(df_ai.at[idx, "asset_type"]).lower() if pd.notna(df_ai.at[idx, "asset_type"]) else ""
            years_usage = df_ai.at[idx, "nb_years_usage"]
            
            is_car = any(term in asset_type for term in ["car", "vehicle", "automobile", "truck", "suv"])
            is_real_estate = any(term in asset_type for term in ["house", "apartment", "land", "property", "residential", "commercial", "industrial", "multifamily", "factory"])
            
            if pd.notna(years_usage):
                if is_car:
                    warranty_status = "Active" if years_usage < 3 else ("Expiring Soon" if years_usage < 5 else "Expired")
                elif is_real_estate:
                    warranty_status = "Active" if years_usage < 10 else "Expired"
                else:
                    warranty_status = "Active" if years_usage < 2 else "Expired"
            else:
                warranty_status = "Unknown"
            df_ai.at[idx, "warranty_status"] = warranty_status
    
    # Price depreciation
    if "price_depreciation" not in df_ai.columns:
        df_ai["price_depreciation"] = np.nan
    
    missing_depreciation = df_ai["price_depreciation"].isna()
    if missing_depreciation.any():
        for idx in df_ai[missing_depreciation].index:
            asset_type = str(df_ai.at[idx, "asset_type"]).lower() if pd.notna(df_ai.at[idx, "asset_type"]) else ""
            years_usage = df_ai.at[idx, "nb_years_usage"]
            
            is_car = any(term in asset_type for term in ["car", "vehicle", "automobile", "truck", "suv"])
            is_real_estate = any(term in asset_type for term in ["house", "apartment", "land", "property", "residential", "commercial", "industrial", "multifamily", "factory"])
            
            if pd.notna(years_usage) and years_usage > 0:
                if is_car:
                    if years_usage <= 1:
                        depreciation_pct = 20
                    elif years_usage <= 2:
                        depreciation_pct = 32
                    else:
                        remaining_value = 0.68
                        for y in range(3, int(years_usage) + 1):
                            remaining_value *= 0.90
                        depreciation_pct = (1 - remaining_value) * 100
                elif is_real_estate:
                    depreciation_pct = min(years_usage * 2.5, 30)
                else:
                    depreciation_pct = min(years_usage * 10, 80)
                df_ai.at[idx, "price_depreciation"] = round(depreciation_pct, 1)
            else:
                df_ai.at[idx, "price_depreciation"] = 0.0
    
    # Price columns
    if "fmv" not in df_ai.columns:
        df_ai["fmv"] = np.nan
    else:
        df_ai["fmv"] = pd.to_numeric(df_ai["fmv"], errors="coerce")
    
    if "ai_adjusted" not in df_ai.columns:
        df_ai["ai_adjusted"] = df_ai["fmv"].copy() if "fmv" in df_ai.columns else np.nan
    else:
        df_ai["ai_adjusted"] = pd.to_numeric(df_ai["ai_adjusted"], errors="coerce")
    
    if "market_price" not in df_ai.columns:
        df_ai["market_price"] = np.nan
    else:
        df_ai["market_price"] = pd.to_numeric(df_ai["market_price"], errors="coerce")
    
    if "market_price_per_sqm" not in df_ai.columns:
        df_ai["market_price_per_sqm"] = np.nan
    else:
        df_ai["market_price_per_sqm"] = pd.to_numeric(df_ai["market_price_per_sqm"], errors="coerce")
    
    if "current_price_estimate" not in df_ai.columns:
        df_ai["current_price_estimate"] = np.nan
    else:
        df_ai["current_price_estimate"] = pd.to_numeric(df_ai["current_price_estimate"], errors="coerce")
    
    # Percentage columns
    if "human_vs_market_pct" not in df_ai.columns:
        df_ai["human_vs_market_pct"] = np.nan
    if "ai_vs_market_pct" not in df_ai.columns:
        df_ai["ai_vs_market_pct"] = np.nan
    if "price_delta_pct" not in df_ai.columns:
        df_ai["price_delta_pct"] = np.nan
    
    # Status columns
    if "market_evaluation_status" not in df_ai.columns:
        df_ai["market_evaluation_status"] = ""
    else:
        df_ai["market_evaluation_status"] = df_ai["market_evaluation_status"].fillna("")
    
    if "confidence" not in df_ai.columns:
        df_ai["confidence"] = 80.0
    else:
        df_ai["confidence"] = pd.to_numeric(df_ai["confidence"], errors="coerce").fillna(80.0)
    
    if "loan_amount" not in df_ai.columns:
        df_ai["loan_amount"] = np.nan
    else:
        df_ai["loan_amount"] = pd.to_numeric(df_ai["loan_amount"], errors="coerce")
    
    # Ensure customer_estimate_price column exists
    if "customer_estimate_price" not in df_ai.columns:
        df_ai["customer_estimate_price"] = np.nan
    
    # Populate customer_estimate_price from realizable_value, customer_price, or fmv
    for idx in df_ai.index:
        customer_est_price = None
        if "realizable_value" in df_ai.columns:
            customer_est_price = pd.to_numeric(df_ai.at[idx, "realizable_value"], errors="coerce")
        if (pd.isna(customer_est_price) or customer_est_price == 0) and "customer_price" in df_ai.columns:
            customer_est_price = pd.to_numeric(df_ai.at[idx, "customer_price"], errors="coerce")
        if (pd.isna(customer_est_price) or customer_est_price == 0) and "fmv" in df_ai.columns:
            customer_est_price = pd.to_numeric(df_ai.at[idx, "fmv"], errors="coerce")
        if pd.notna(customer_est_price) and customer_est_price > 0:
            df_ai.at[idx, "customer_estimate_price"] = customer_est_price
    
    # Ensure market_price column exists (use market_price for real estate, current_price_estimate for others)
    if "market_price" not in df_ai.columns:
        df_ai["market_price"] = np.nan
    if "current_price_estimate" not in df_ai.columns:
        df_ai["current_price_estimate"] = np.nan
    if "market_price_per_sqm" not in df_ai.columns:
        df_ai["market_price_per_sqm"] = np.nan
    if "area_sqm" not in df_ai.columns:
        df_ai["area_sqm"] = np.nan
    else:
        df_ai["area_sqm"] = pd.to_numeric(df_ai["area_sqm"], errors="coerce")
    
    # Determine market price for each asset (real estate uses market_price, others use current_price_estimate)
    for idx in df_ai.index:
        asset_type = str(df_ai.at[idx, "asset_type"]).lower() if "asset_type" in df_ai.columns and pd.notna(df_ai.at[idx, "asset_type"]) else ""
        is_real_estate = any(term in asset_type for term in ["house", "apartment", "land", "property", "residential", "commercial", "industrial", "multifamily", "factory"])
        
        if is_real_estate:
            # For real estate, use market_price
            if "market_price" in df_ai.columns:
                market_price_val = df_ai.at[idx, "market_price"] if pd.notna(df_ai.at[idx, "market_price"]) else 0
            else:
                market_price_val = 0
            
            if pd.isna(market_price_val) or market_price_val == 0:
                # Try to calculate from market_price_per_sqm if available
                if "market_price_per_sqm" in df_ai.columns and "area_sqm" in df_ai.columns:
                    market_price_per_sqm_val = df_ai.at[idx, "market_price_per_sqm"]
                    area_sqm_val = df_ai.at[idx, "area_sqm"]
                    if pd.notna(market_price_per_sqm_val) and pd.notna(area_sqm_val) and area_sqm_val > 0:
                        df_ai.at[idx, "market_price"] = market_price_per_sqm_val * area_sqm_val
        else:
            # For non-real estate, use current_price_estimate as market price
            if "current_price_estimate" in df_ai.columns:
                current_price_val = df_ai.at[idx, "current_price_estimate"]
                if pd.notna(current_price_val) and current_price_val > 0:
                    df_ai.at[idx, "market_price"] = current_price_val
    
    # Ensure AI recommended price (ai_adjusted) exists
    if "ai_adjusted" not in df_ai.columns:
        df_ai["ai_adjusted"] = df_ai["fmv"].copy() if "fmv" in df_ai.columns else np.nan
    else:
        df_ai["ai_adjusted"] = pd.to_numeric(df_ai["ai_adjusted"], errors="coerce")
    
    # Calculate AI recommended price if not set (market_price - 10%)
    for idx in df_ai.index:
        if pd.isna(df_ai.at[idx, "ai_adjusted"]) or df_ai.at[idx, "ai_adjusted"] == 0:
            market_price_val = df_ai.at[idx, "market_price"]
            if pd.notna(market_price_val) and market_price_val > 0:
                df_ai.at[idx, "ai_adjusted"] = market_price_val * 0.9  # Market price - 10%
            elif pd.notna(df_ai.at[idx, "fmv"]) and df_ai.at[idx, "fmv"] > 0:
                df_ai.at[idx, "ai_adjusted"] = df_ai.at[idx, "fmv"]
    
    # Human review columns - prepopulate human_value with AI recommended price
    if "human_value" not in df_ai.columns:
        df_ai["human_value"] = df_ai["ai_adjusted"].copy()
    else:
        df_ai["human_value"] = pd.to_numeric(df_ai["human_value"], errors="coerce")
        # Fill missing human_value with ai_adjusted
        missing_human = df_ai["human_value"].isna() | (df_ai["human_value"] == 0)
        if missing_human.any():
            df_ai.loc[missing_human, "human_value"] = df_ai.loc[missing_human, "ai_adjusted"]
    
    if "justification" not in df_ai.columns:
        df_ai["justification"] = ""
    else:
        df_ai["justification"] = df_ai["justification"].fillna("")
    
    # Area columns (for real estate)
    if "area_sqm" not in df_ai.columns:
        df_ai["area_sqm"] = np.nan
    else:
        df_ai["area_sqm"] = pd.to_numeric(df_ai["area_sqm"], errors="coerce")
    
    # ─────────────────────────────────────────
    # ✅ RECREATE HUMAN REVIEW TABLE WITH GROUPED PRICE COLUMNS
    # ─────────────────────────────────────────
    
    # Calculate percentage comparisons before displaying
    for idx in df_ai.index:
        # Recalculate years of usage from date_of_purchase
        date_val = df_ai.at[idx, "date_of_purchase"]
        if pd.notna(date_val) and date_val != "":
            try:
                if isinstance(date_val, str):
                    date_val = pd.to_datetime(date_val)
                years_usage = (datetime.now() - date_val.to_pydatetime()).days / 365.25
                df_ai.at[idx, "nb_years_usage"] = round(years_usage, 1)
            except Exception:
                pass
        
        # Recalculate warranty status
        asset_type = str(df_ai.at[idx, "asset_type"]).lower() if pd.notna(df_ai.at[idx, "asset_type"]) else ""
        years_usage = df_ai.at[idx, "nb_years_usage"]
        is_car = any(term in asset_type for term in ["car", "vehicle", "automobile", "truck", "suv"])
        is_real_estate = any(term in asset_type for term in ["house", "apartment", "land", "property", "residential", "commercial", "industrial", "multifamily", "factory"])
        
        if pd.notna(years_usage):
            if is_car:
                warranty_status = "Active" if years_usage < 3 else ("Expiring Soon" if years_usage < 5 else "Expired")
            elif is_real_estate:
                warranty_status = "Active" if years_usage < 10 else "Expired"
            else:
                warranty_status = "Active" if years_usage < 2 else "Expired"
            df_ai.at[idx, "warranty_status"] = warranty_status
        
        # Recalculate price depreciation
        if pd.notna(years_usage) and years_usage > 0:
            if is_car:
                if years_usage <= 1:
                    depreciation_pct = 20
                elif years_usage <= 2:
                    depreciation_pct = 32
                else:
                    remaining_value = 0.68
                    for y in range(3, int(years_usage) + 1):
                        remaining_value *= 0.90
                    depreciation_pct = (1 - remaining_value) * 100
            elif is_real_estate:
                depreciation_pct = min(years_usage * 2.5, 30)
            else:
                depreciation_pct = min(years_usage * 10, 80)
            df_ai.at[idx, "price_depreciation"] = round(depreciation_pct, 1)
        
        # Recalculate percentage comparisons
        asset_type_val = str(df_ai.at[idx, "asset_type"]).lower() if pd.notna(df_ai.at[idx, "asset_type"]) else ""
        is_real_estate_val = any(term in asset_type_val for term in ["house", "apartment", "land", "property", "residential", "commercial", "industrial", "multifamily", "factory"])
        
        price_for_comparison = None
        if is_real_estate_val and pd.notna(df_ai.at[idx, "market_price"]):
            price_for_comparison = df_ai.at[idx, "market_price"]
        elif pd.notna(df_ai.at[idx, "current_price_estimate"]):
            price_for_comparison = df_ai.at[idx, "current_price_estimate"]
        elif pd.notna(df_ai.at[idx, "market_price"]):
            price_for_comparison = df_ai.at[idx, "market_price"]
        
        if price_for_comparison and price_for_comparison > 0:
            human_val = pd.to_numeric(df_ai.at[idx, "human_value"], errors="coerce")
            if pd.notna(human_val) and human_val > 0:
                df_ai.at[idx, "human_vs_market_pct"] = ((human_val - price_for_comparison) / price_for_comparison) * 100
            
            ai_adj = pd.to_numeric(df_ai.at[idx, "ai_adjusted"], errors="coerce")
            if pd.notna(ai_adj) and ai_adj > 0:
                df_ai.at[idx, "ai_vs_market_pct"] = ((ai_adj - price_for_comparison) / price_for_comparison) * 100
    
    # Calculate human_vs_market_pct and ai_vs_market_pct
    for idx in df_ai.index:
        market_price_val = df_ai.at[idx, "market_price"]
        if pd.notna(market_price_val) and market_price_val > 0:
            human_val = pd.to_numeric(df_ai.at[idx, "human_value"], errors="coerce")
            if pd.notna(human_val) and human_val > 0:
                df_ai.at[idx, "human_vs_market_pct"] = ((human_val - market_price_val) / market_price_val) * 100
            
            ai_val = pd.to_numeric(df_ai.at[idx, "ai_adjusted"], errors="coerce")
            if pd.notna(ai_val) and ai_val > 0:
                df_ai.at[idx, "ai_vs_market_pct"] = ((ai_val - market_price_val) / market_price_val) * 100
    
    # Use persisted edited dataframe from session state if available, otherwise use df_ai
    if "human_review_edited_df" in ss and ss["human_review_edited_df"] is not None:
        persisted_edited = ss["human_review_edited_df"].copy()
        # Ensure all columns exist
        for col in df_ai.columns:
            if col not in persisted_edited.columns:
                if len(persisted_edited) == len(df_ai):
                    persisted_edited[col] = df_ai[col].values
                else:
                    persisted_edited[col] = np.nan
        # Update non-editable columns while preserving human edits
        if len(persisted_edited) == len(df_ai):
            for col in df_ai.columns:
                if col not in ["human_value", "justification"]:
                    persisted_edited[col] = df_ai[col].values
        df_ai_for_editing = persisted_edited.copy()
    else:
        df_ai_for_editing = df_ai.copy()
    
    # Store original AI values for comparison
    if "human_review_original_ai_values" not in ss:
        if "ai_adjusted" in df_ai.columns:
            ss["human_review_original_ai_values"] = df_ai["ai_adjusted"].copy()
        else:
            ss["human_review_original_ai_values"] = df_ai["fmv"].copy() if "fmv" in df_ai.columns else pd.Series(index=df_ai.index)
    
    original_ai_values = ss["human_review_original_ai_values"]
    
    # ─────────────────────────────────────────
    # CREATE TABLE WITH GROUPED PRICE COLUMNS
    # ─────────────────────────────────────────
    
    # Prepare display dataframe with grouped price columns
    display_df = df_ai_for_editing.copy()
    
    # Ensure all required price columns exist
    required_price_cols = ["customer_estimate_price", "market_price", "ai_adjusted", "human_value"]
    for col in required_price_cols:
        if col not in display_df.columns:
            display_df[col] = np.nan
    
    # Create grouped column order: ID columns, then grouped price columns, then other columns
    id_cols = []
    for col in ["application_id", "asset_id", "asset_type", "city"]:
        if col in display_df.columns:
            id_cols.append(col)
    
    # Grouped price columns (in order: customer estimate, market price, AI recommend, human decision)
    price_cols = ["customer_estimate_price", "market_price", "ai_adjusted", "human_value"]
    price_cols = [col for col in price_cols if col in display_df.columns]
    
    # Other columns
    other_cols = []
    for col in ["justification", "human_vs_market_pct", "ai_vs_market_pct", "confidence", "loan_amount"]:
        if col in display_df.columns:
            other_cols.append(col)
    
    # Combine columns in order
    display_cols = id_cols + price_cols + other_cols
    
    # Rename columns for better display
    display_df_renamed = display_df[display_cols].copy()
    column_rename_map = {
        "customer_estimate_price": "💰 Customer Estimate Price",
        "market_price": "📊 Market Price",
        "ai_adjusted": "🤖 AI Recommend Price",
        "human_value": "✏️ Human Decision (Editable)"
    }
    display_df_renamed = display_df_renamed.rename(columns=column_rename_map)
    
    # Display caption
    st.caption("💡 **Review Guide:** Edit the '✏️ Human Decision (Editable)' column to set your final price. Changes will automatically update the gauge and changed rows table below.")
    
    # Display editable table with grouped price columns
    edited_renamed = st.data_editor(
        display_df_renamed,
        num_rows="dynamic",
        use_container_width=True,
        key="human_review_data_editor"
    )
    
    # Map back to original column names
    reverse_rename_map = {v: k for k, v in column_rename_map.items()}
    edited = edited_renamed.copy()
    edited = edited.rename(columns=reverse_rename_map)
    
    # Ensure all original columns are present in edited dataframe
    for col in df_ai_for_editing.columns:
        if col not in edited.columns:
            if col in display_cols:
                # Column was in display, add it back
                edited[col] = display_df[col].values if len(display_df) == len(edited) else np.nan
            else:
                # Column was not displayed, add from original
                edited[col] = df_ai_for_editing[col].values if len(df_ai_for_editing) == len(edited) else np.nan
    
    # Detect if changes were made by comparing with stored dataframe
    has_changes = False
    if "human_review_edited_df" in ss and ss["human_review_edited_df"] is not None:
        stored_df = ss["human_review_edited_df"]
        # Check if human_value column changed
        if "human_value" in edited.columns and "human_value" in stored_df.columns:
            # Align indices for comparison
            stored_aligned = stored_df["human_value"].reindex(edited.index)
            edited_vals = pd.to_numeric(edited["human_value"], errors="coerce")
            stored_vals = pd.to_numeric(stored_aligned, errors="coerce")
            # Check for any differences (more than rounding error)
            if not edited_vals.equals(stored_vals):
                has_changes = True
        else:
            has_changes = True  # Column structure changed
    else:
        has_changes = True  # First time editing
    
    # Store edited dataframe in session state to persist changes (always update to latest)
    ss["human_review_edited_df"] = edited.copy()
    
    # Store original human values before recalculation for change tracking
    original_human_values = edited["human_value"].copy() if "human_value" in edited.columns else pd.Series(index=edited.index)
    
    # After editing, recalculate all fields (years of usage, warranty, depreciation, percentages)
    # This ensures that when human_value is edited, all dependent fields (including human_vs_market_pct)
    # are updated, which will then be reflected in the gauge and changed rows table below
    for idx in edited.index:
        # Recalculate years of usage from date_of_purchase if changed
        date_val = edited.at[idx, "date_of_purchase"] if "date_of_purchase" in edited.columns else None
        if pd.notna(date_val) and date_val != "":
            try:
                if isinstance(date_val, str):
                    date_val = pd.to_datetime(date_val)
                years_usage = (datetime.now() - date_val.to_pydatetime()).days / 365.25
                edited.at[idx, "nb_years_usage"] = round(years_usage, 1)
            except Exception:
                pass
        
        # Recalculate warranty status
        asset_type = str(edited.at[idx, "asset_type"]).lower() if "asset_type" in edited.columns and pd.notna(edited.at[idx, "asset_type"]) else ""
        years_usage = edited.at[idx, "nb_years_usage"] if "nb_years_usage" in edited.columns else np.nan
        is_car = any(term in asset_type for term in ["car", "vehicle", "automobile", "truck", "suv"])
        is_real_estate = any(term in asset_type for term in ["house", "apartment", "land", "property", "residential", "commercial", "industrial", "multifamily", "factory"])
        
        if pd.notna(years_usage):
            if is_car:
                warranty_status = "Active" if years_usage < 3 else ("Expiring Soon" if years_usage < 5 else "Expired")
            elif is_real_estate:
                warranty_status = "Active" if years_usage < 10 else "Expired"
            else:
                warranty_status = "Active" if years_usage < 2 else "Expired"
            if "warranty_status" in edited.columns:
                edited.at[idx, "warranty_status"] = warranty_status
        
        # Recalculate price depreciation
        if pd.notna(years_usage) and years_usage > 0:
            if is_car:
                if years_usage <= 1:
                    depreciation_pct = 20
                elif years_usage <= 2:
                    depreciation_pct = 32
                else:
                    remaining_value = 0.68
                    for y in range(3, int(years_usage) + 1):
                        remaining_value *= 0.90
                    depreciation_pct = (1 - remaining_value) * 100
            elif is_real_estate:
                depreciation_pct = min(years_usage * 2.5, 30)
            else:
                depreciation_pct = min(years_usage * 10, 80)
            if "price_depreciation" in edited.columns:
                edited.at[idx, "price_depreciation"] = round(depreciation_pct, 1)
        
        # Recalculate percentage comparisons using market_price
        if "market_price" in edited.columns:
            market_price_val = pd.to_numeric(edited.at[idx, "market_price"], errors="coerce")
            
            # Recalculate human_vs_market_pct (using CURRENT edited human_value)
            if "human_value" in edited.columns:
                human_val = pd.to_numeric(edited.at[idx, "human_value"], errors="coerce")
                if pd.notna(human_val) and pd.notna(market_price_val) and market_price_val > 0:
                    if "human_vs_market_pct" in edited.columns:
                        edited.at[idx, "human_vs_market_pct"] = ((human_val - market_price_val) / market_price_val) * 100
            
            # Recalculate ai_vs_market_pct
            if "ai_adjusted" in edited.columns:
                ai_val = pd.to_numeric(edited.at[idx, "ai_adjusted"], errors="coerce")
                if pd.notna(ai_val) and pd.notna(market_price_val) and market_price_val > 0:
                    if "ai_vs_market_pct" in edited.columns:
                        edited.at[idx, "ai_vs_market_pct"] = ((ai_val - market_price_val) / market_price_val) * 100
    
    # Update persisted edited dataframe with recalculated values (always use latest edited)
    ss["human_review_edited_df"] = edited.copy()
    

    # ── Agreement / Deviation Gauge + Changed Rows List
    st.markdown("### 🎯 Human vs AI Agreement / Deviation")
    
    # Use the CURRENT edited dataframe directly for calculations
    # The 'edited' dataframe from st.data_editor contains the most recent user edits
    # This ensures the gauge and changed rows list update immediately when values change
    
    # Calculate agreement based on human_value vs ai_adjusted from review table (using CURRENT edited values)
    if "human_value" in edited.columns and "ai_adjusted" in edited.columns:
        human_vals = pd.to_numeric(edited["human_value"], errors="coerce")
        ai_vals = pd.to_numeric(edited["ai_adjusted"], errors="coerce")
        
        # Calculate agreement: consider values "agreeing" if within 5% of each other
        valid_mask = (human_vals.notna()) & (ai_vals.notna()) & (ai_vals != 0)
        
        if valid_mask.any():
            # Calculate percentage difference for all valid rows (using CURRENT edited values)
            pct_diff_series = pd.Series(index=edited.index, dtype=float)
            pct_diff_series[valid_mask] = ((human_vals[valid_mask] - ai_vals[valid_mask]).abs() / ai_vals[valid_mask].abs() * 100).values
            
            # Consider agreement if within 5% difference
            agreements = (pct_diff_series[valid_mask] <= 5.0)
            agree_pct = float(agreements.mean() * 100.0) if len(agreements) > 0 else 0.0
            
            # Count changed rows (compare CURRENT edited human_value with original AI values)
            changed_count = 0
            if len(original_ai_values) > 0:
                original_ai_aligned = original_ai_values.reindex(edited.index)
                changes_mask = (human_vals.notna()) & (original_ai_aligned.notna()) & (original_ai_aligned != 0)
                if changes_mask.any():
                    change_pct = ((human_vals[changes_mask] - original_ai_aligned[changes_mask]).abs() / original_ai_aligned[changes_mask].abs() * 100)
                    has_changes = (change_pct > 0.01)  # More than 0.01% change
                    changed_count = has_changes.sum()
            
            # Create agreement gauge (updates dynamically based on CURRENT edited values)
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=round(agree_pct, 2),
                number={'suffix': '%'},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'thickness': 0.35},
                    'steps': [
                        {'range': [0, 50], 'color': '#fee2e2'},
                        {'range': [50, 80], 'color': '#fef9c3'},
                        {'range': [80, 100], 'color': '#dcfce7'},
                    ],
                    'threshold': {'line': {'color': '#2563eb', 'width': 4}, 'thickness': 0.9, 'value': round(agree_pct, 2)}
                },
                title={'text': f"Human ↔ AI Agreement (within 5%) | {changed_count} rows changed"}
            ))
            st.plotly_chart(fig, use_container_width=True)
            
            # Find ALL changed rows (where CURRENT human_value differs from original AI by any amount)
            changed_rows_indices = []
            if len(original_ai_values) > 0:
                original_ai_aligned = original_ai_values.reindex(edited.index)
                for idx in edited.index:
                    human_val = pd.to_numeric(edited.at[idx, "human_value"], errors="coerce") if "human_value" in edited.columns else np.nan
                    original_ai_val = pd.to_numeric(original_ai_aligned.at[idx], errors="coerce") if idx in original_ai_aligned.index else np.nan
                    
                    if pd.notna(human_val) and pd.notna(original_ai_val) and original_ai_val != 0:
                        change_pct = abs((human_val - original_ai_val) / original_ai_val * 100)
                        if change_pct > 0.01:  # Any change more than 0.01%
                            changed_rows_indices.append(idx)
            
            # Combine with rows that differ from current AI by more than 5%
            changed_mask = valid_mask & (pct_diff_series > 5.0)
            all_changed_indices = list(set(changed_rows_indices + edited.loc[changed_mask].index.tolist()))
            changed_df = edited.loc[all_changed_indices].copy() if all_changed_indices else pd.DataFrame()
            
            if not changed_df.empty:
                st.markdown("#### 📝 Changed Rows — Human Adjustments from AI Recommendations")
                st.caption(f"Showing {len(changed_df)} rows where human decision differs from AI recommendations (updated from adjustment table)")
                
                # Prepare display columns
                display_cols = []
                key_cols = ["application_id", "asset_id", "asset_type", "city"]
                display_cols.extend([c for c in key_cols if c in changed_df.columns])
                
                # Add original AI value column
                if len(original_ai_values) > 0:
                    original_ai_aligned = original_ai_values.reindex(changed_df.index)
                    changed_df = changed_df.copy()
                    changed_df["original_ai_value"] = original_ai_aligned
                    display_cols.append("original_ai_value")
                
                # Add price comparison columns
                if "ai_adjusted" in changed_df.columns:
                    display_cols.append("ai_adjusted")
                if "human_value" in changed_df.columns:
                    display_cols.append("human_value")
                if "market_price" in changed_df.columns:
                    display_cols.append("market_price")
                if "current_price_estimate" in changed_df.columns:
                    display_cols.append("current_price_estimate")
                if "human_vs_market_pct" in changed_df.columns:
                    display_cols.append("human_vs_market_pct")
                if "ai_vs_market_pct" in changed_df.columns:
                    display_cols.append("ai_vs_market_pct")
                if "justification" in changed_df.columns:
                    display_cols.append("justification")
                
                # Calculate differences for display
                changed_display = changed_df[display_cols].copy()
                
                if "ai_adjusted" in changed_display.columns and "human_value" in changed_display.columns:
                    ai_adj_vals = pd.to_numeric(changed_display["ai_adjusted"], errors="coerce")
                    human_vals_display = pd.to_numeric(changed_display["human_value"], errors="coerce")
                    
                    # Difference from current AI
                    diff_vals = human_vals_display - ai_adj_vals
                    diff_pct = ((diff_vals / ai_adj_vals) * 100).round(1)
                    changed_display["difference"] = diff_vals.round(2)
                    changed_display["difference_pct"] = diff_pct
                    
                    # Change from original AI
                    if "original_ai_value" in changed_display.columns:
                        orig_ai_vals = pd.to_numeric(changed_display["original_ai_value"], errors="coerce")
                        change_from_orig = human_vals_display - orig_ai_vals
                        change_from_orig_pct = ((change_from_orig / orig_ai_vals) * 100).round(1)
                        changed_display["change_from_ai"] = change_from_orig.round(2)
                        changed_display["change_from_ai_pct"] = change_from_orig_pct
                    
                    # Reorder columns: key cols, original_ai_value, ai_adjusted, human_value, change_from_ai, change_from_ai_pct, difference, difference_pct, ...
                    new_cols = []
                    for col in ["application_id", "asset_id", "asset_type", "city"]:
                        if col in display_cols:
                            new_cols.append(col)
                    if "original_ai_value" in changed_display.columns:
                        new_cols.append("original_ai_value")
                    if "ai_adjusted" in changed_display.columns:
                        new_cols.append("ai_adjusted")
                    if "human_value" in changed_display.columns:
                        new_cols.append("human_value")
                    if "change_from_ai" in changed_display.columns:
                        new_cols.extend(["change_from_ai", "change_from_ai_pct"])
                    if "difference" in changed_display.columns:
                        new_cols.extend(["difference", "difference_pct"])
                    # Add remaining columns
                    for col in display_cols:
                        if col not in new_cols:
                            new_cols.append(col)
                    display_cols = [c for c in new_cols if c in changed_display.columns]
                
                # Rename human_value for display
                if "human_value" in changed_display.columns:
                    changed_display = changed_display.rename(columns={"human_value": "Human decision with market price base line"})
                    # Update display_cols list
                    display_cols = ["Human decision with market price base line" if c == "human_value" else c for c in display_cols]
                
                st.dataframe(changed_display[display_cols], use_container_width=True, hide_index=True)
            else:
                st.success("🎉 Perfect agreement — no rows changed (all within 5% of AI recommendations).")
        else:
            st.info("⚠️ No valid data for comparison. Ensure both 'human_value' and 'ai_adjusted' columns have numeric values.")
    else:
        st.info("⚠️ Missing required columns. The agreement gauge requires both 'human_value' and 'ai_adjusted' columns from the review table.")

    
        # ── Human Changes Only (colored)
        st.markdown("### 🖍️ Human Changes Only (colored)")

        # Reuse helper and edited df from above
        value_ai = _first_present(edited, ["ai_adjusted", "fmv", "predicted_value"])
        value_hu = _first_present(edited, ["human_value", "reviewed_value", "final_value"])
        ai_dec_col = _first_present(edited, ["ai_decision", "ai_label", "ai_outcome", "decision_ai"])
        human_dec_col = _first_present(edited, ["human_decision", "human_label", "final_decision", "decision_human"])

        if value_ai and value_hu:
            ai_vals = pd.to_numeric(edited[value_ai], errors="coerce")
            hu_vals = pd.to_numeric(edited[value_hu], errors="coerce")

            # decisions -> Series aligned to edited.index
            if ai_dec_col and human_dec_col:
                a = edited[ai_dec_col].astype(str).str.strip().str.lower()
                h = edited[human_dec_col].astype(str).str.strip().str.lower()
                dec_changed = (a != h)  # Series
            else:
                dec_changed = pd.Series(False, index=edited.index)

            # justification -> Series aligned
            just_present = edited.get("justification", pd.Series("", index=edited.index)) \
                                .astype(str).str.strip().ne("")

            # treat tiny diffs as equal
            rel_tol = 1e-9
            val_changed = (ai_vals.fillna(np.nan) - hu_vals.fillna(np.nan)).abs() > (
                (ai_vals.abs() + hu_vals.abs()).fillna(0) * rel_tol
            )

            changed_mask = val_changed | dec_changed | just_present
            diff_df = edited.loc[changed_mask].copy()

            if diff_df.empty:
                st.success("🎉 No human changes detected.")
            else:
                # compute deltas on the FILTERED subset ONLY
                ai_sub = ai_vals.reindex(diff_df.index)
                hu_sub = hu_vals.reindex(diff_df.index)

                diff_df["Δ_value"] = (hu_sub - ai_sub)
                base = ai_sub.replace(0, np.nan)
                diff_df["Δ_%"] = ((diff_df["Δ_value"] / base) * 100.0).round(2)

                key_cols = [c for c in ["application_id", "asset_id", "asset_type", "city"] if c in diff_df.columns]
                show_cols = key_cols + [c for c in [value_ai, value_hu, "Δ_value", "Δ_%", ai_dec_col, human_dec_col, "justification"] if c in diff_df.columns]
                show_df = diff_df[show_cols].copy()

                def _color_row(row):
                    styles = [""] * len(row.index)

                    def _idx(colname):
                        try:
                            return show_df.columns.get_loc(colname)
                        except Exception:
                            return None

                    idx_ai = _idx(value_ai)
                    idx_hu = _idx(value_hu)
                    idx_dv = _idx("Δ_value")
                    idx_dp = _idx("Δ_%")

                    # Value changes
                    try:
                        ai_v = float(row.get(value_ai, np.nan))
                        hu_v = float(row.get(value_hu, np.nan))
                    except Exception:
                        ai_v, hu_v = np.nan, np.nan

                    if pd.notna(ai_v) and pd.notna(hu_v):
                        if hu_v > ai_v:  # green for up
                            for i in [idx_hu, idx_dv, idx_dp]:
                                if i is not None:
                                    styles[i] = "background-color:#dcfce7; color:#065f46; font-weight:600;"
                            if idx_ai is not None:
                                styles[idx_ai] = "background-color:#ecfdf5; color:#064e3b;"
                        elif hu_v < ai_v:  # red for down
                            for i in [idx_hu, idx_dv, idx_dp]:
                                if i is not None:
                                    styles[i] = "background-color:#fee2e2; color:#7f1d1d; font-weight:600;"
                            if idx_ai is not None:
                                styles[idx_ai] = "background-color:#fef2f2; color:#7f1d1d;"

                    # Decision changes → amber
                    if ai_dec_col in show_df.columns and human_dec_col in show_df.columns:
                        ai_d = str(row.get(ai_dec_col, "")).strip().lower()
                        hu_d = str(row.get(human_dec_col, "")).strip().lower()
                        if ai_d != "" and hu_d != "" and ai_d != hu_d:
                            for colname in [ai_dec_col, human_dec_col]:
                                j = _idx(colname)
                                if j is not None:
                                    styles[j] = "background-color:#fef9c3; color:#7c2d12; font-weight:600;"

                    # Justification present → blue
                    if "justification" in show_df.columns:
                        just = str(row.get("justification", "")).strip()
                        if just:
                            j = _idx("justification")
                            if j is not None:
                                styles[j] = "background-color:#e0f2fe; color:#0c4a6e;"

                    return styles

                styled = show_df.style.apply(_color_row, axis=1) \
                                    .format({value_ai: "{:,.0f}", value_hu: "{:,.0f}", "Δ_value": "{:,.0f}", "Δ_%": "{:.2f}%"})
                st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.info("To show the colorful Human-Changes table, ensure value columns exist (e.g., ai_adjusted/fmv and human_value).")

        

    
    # ── Export for Retraining
    st.markdown("### 💾 Save & Export for Training")
    # Lightweight export view for training: keep keys + AI/Human value/decisions if present
    train_cols_base = ["application_id", "asset_id", "asset_type", "city"]
    ai_val_col = _first_present(edited, ["ai_adjusted", "fmv", "predicted_value"])
    hu_val_col = _first_present(edited, ["human_value", "reviewed_value", "final_value"])
    ai_dec_col = _first_present(edited, ["ai_decision", "ai_label", "ai_outcome", "decision_ai"])
    human_dec_col = _first_present(edited, ["human_decision", "human_label", "final_decision", "decision_human"])
    keep_cols = [c for c in train_cols_base if c in edited.columns] + \
                [c for c in [ai_dec_col, human_dec_col, ai_val_col, hu_val_col, "confidence", "loan_amount", "justification"] if c and c in edited.columns]
    export_df = edited[keep_cols].copy() if keep_cols else edited.copy()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(RUNS_DIR, f"reviewed_appraisal.{ts}.csv")

    cE1, cE2 = st.columns([1.2, 1])
    with cE1:
        st.text_input("Will save to (server path)", out_path, label_visibility="collapsed")
    with cE2:
        st.download_button(
            "⬇️ Download Human vs AI CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=os.path.basename(out_path),
            mime="text/csv",
            key="dl_reviewed_appraisal_stageE"
        )

    if st.button("💾 Save Human Feedback (server)", key="btn_save_feedback"):
        try:
            export_df.to_csv(out_path, index=False, encoding="utf-8-sig")
            st.success(f"✅ Saved human-reviewed data → `{out_path}`")
        except Exception as e:
            st.error(f"Save failed: {e}")


# # ============================================================
# # ✅ STAGE F FOOTER FUNCTION — must be defined BEFORE Stage F
# # ============================================================

def render_stage_f_footer(
    new_m, prod_m, RUNS_DIR, model_path, report,
    df_train=None, yte=None, y_pred_new=None
):
    import streamlit as st
    import pandas as pd
    import numpy as np
    import os, json, glob, shutil, zipfile
    from datetime import datetime, timezone
    import plotly.express as px

    st.markdown("## 🧭 Executive Model Evaluation Dashboard (Stage F)")

    # -----------------------------------------
    # ✅ Compute deltas
    # -----------------------------------------
    if prod_m:
        delta_mae = (prod_m["MAE"] - new_m["MAE"]) / prod_m["MAE"] * 100
        delta_rmse = (prod_m["RMSE"] - new_m["RMSE"]) / prod_m["RMSE"] * 100
        delta_mape = (prod_m["MAPE%"] - new_m["MAPE%"]) / prod_m["MAPE%"] * 100
        delta_r2  = (new_m["R2"] - prod_m["R2"]) * 100

        improved = {
            "MAE": delta_mae > 0,
            "RMSE": delta_rmse > 0,
            "MAPE%": delta_mape > 0,
            "R2": delta_r2 > 0
        }

        # Main headline message
        headline = f"✅ The new model outperforms the production model by **{delta_mae:+.1f}% MAE** and **{delta_r2:+.2f} R² points**."
        headline_color = "#D1FAE5"  # greenish
        reward_phrase = "✔ This is a strong improvement and beneficial for production use."
    else:
        headline = "🟢 First model trained — this will become the initial production baseline."
        headline_color = "#DBEAFE"  # blueish
        reward_phrase = "✔ You can safely promote this model."

    # -----------------------------------------
    # ✅ WHAT — Big one-sentence discovery
    # -----------------------------------------
    st.markdown(
        f"""
        <div style="
            padding: 18px;
            border-radius: 12px;
            background-color: {headline_color};
            font-size: 1.3rem;
            font-weight: 600;
        ">
        {headline}
        </div>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------------------
    # ✅ SO WHAT — Why does this matter?
    # -----------------------------------------
    st.markdown("### 🧐 SO WHAT — Why does this matter?")
    if prod_m:
        st.write(
            f"""
            The new model shows measurable improvements across key financial and ML metrics:

            - **MAE** (Average absolute error) improved by **{delta_mae:+.1f}%**  
            - **RMSE** (Hard penalties on large mismatches) improved by **{delta_rmse:+.1f}%**  
            - **MAPE** (Percentage error relative to asset value) improved by **{delta_mape:+.1f}%**  
            - **R²** (How well the model explains variance) improved by **{delta_r2:+.2f} points**  

            These metrics together mean:
            - ✅ More accurate valuation predictions  
            - ✅ Smaller high-error outliers  
            - ✅ Better stability with fewer “shocks”  
            - ✅ Higher confidence for underwriting, credit, and collateral decisions  
            """
        )
    else:
        st.info(
            """
            Since there is **no existing production model**, this trained model becomes 
            the best available baseline for your valuation pipeline.
            """
        )

    # -----------------------------------------
    # ✅ KEY COMPARISON TABLE
    # -----------------------------------------
    st.markdown("### 📊 Metric Comparison (New vs Production)")

    if prod_m:
        df_cmp = pd.DataFrame([
            ["MAE",   f"{new_m['MAE']:,.0f}",   f"{prod_m['MAE']:,.0f}",   f"{delta_mae:+.1f}%",  "Lower is better"],
            ["RMSE",  f"{new_m['RMSE']:,.0f}",  f"{prod_m['RMSE']:,.0f}",  f"{delta_rmse:+.1f}%", "Penalizes large errors"],
            ["MAPE%", f"{new_m['MAPE%']:.2f}%", f"{prod_m['MAPE%']:.2f}%", f"{delta_mape:+.1f}%", "Percent accuracy"],
            ["R²",    f"{new_m['R2']:.3f}",     f"{prod_m['R2']:.3f}",     f"{delta_r2:+.2f}",    "Explained variance"],
        ], columns=["Metric", "New Model", "Production", "Δ (Change)", "Meaning"])
    else:
        df_cmp = pd.DataFrame([
            ["MAE",   f"{new_m['MAE']:,.0f}",   "—",  "—", "Lower is better"],
            ["RMSE",  f"{new_m['RMSE']:,.0f}",  "—",  "—", "Penalizes large errors"],
            ["MAPE%", f"{new_m['MAPE%']:.2f}%", "—",  "—", "Percent accuracy"],
            ["R²",    f"{new_m['R2']:.3f}",     "—",  "—", "Explained variance"],
        ], columns=["Metric", "New Model", "Production", "Δ (Change)", "Meaning"])

    st.table(df_cmp)

    # -----------------------------------------
    # ✅ NOW WHAT — Recommended Action
    # -----------------------------------------
    st.markdown("### 🚀 NOW WHAT — Recommended Next Action")

    if not prod_m or (delta_mae > 0 and delta_r2 > 0):
        st.success(
            f"""
            ### ✅ Recommendation: **Promote the new model to production.**

            {reward_phrase}

            #### Why?
            - It reduces valuation errors.
            - It improves consistency and confidence scores.
            - It captures market variance better (higher R²).
            - It reduces underwriting risk.
            - It generates more stable predictions for credit, risk & collateral workflows.
            """
        )
        promote_ready = True
    else:
        st.warning(
            f"""
            ### ⚠️ Recommendation: **Do NOT promote yet.**

            Some metrics degrade when compared to production.

            #### Before promoting:
            - Tune hyperparameters  
            - Add more diverse training samples  
            - Validate anomalies / outliers  
            - Re-check human_value labels from Stage E  
            """
        )
        promote_ready = False

    # -----------------------------------------
    # ✅ Next Steps Checklist
    # -----------------------------------------
    st.markdown("### ✅ Next Steps Checklist")

    if promote_ready:
        st.markdown(
            """
            ✅ Promote to production  
            ✅ Export ZIP bundle  
            ✅ Notify Credit / Risk agents  
            ✅ Schedule monitoring in Stage I  
            ✅ Optional: widen training dataset  
            """
        )
    else:
        st.markdown(
            """
            🔄 Retrain with more data  
            🧹 Clean labeling inconsistencies  
            🔍 Inspect outliers via residual plots  
            🔧 Try Gradient Boosting or Random Forest  
            """
        )

    # -----------------------------------------
    # ✅ Show Drift Trend (mini chart)
    # -----------------------------------------
    st.markdown("### 📈 Performance Trend (MAE & R² over time)")
    reports = sorted(glob.glob(os.path.join(RUNS_DIR, "training_report_*.json")), reverse=True)[:10]
    trend = []
    for f in reports:
        try:
            with open(f) as jf:
                rep = json.load(jf)
            trend.append({
                "timestamp": rep["timestamp"],
                "MAE": rep["metrics_new"]["MAE"],
                "R2": rep["metrics_new"]["R2"],
            })
        except:
            pass

    if trend:
        df_tr = pd.DataFrame(trend).sort_values("timestamp")
        st.line_chart(df_tr.set_index("timestamp")[["MAE", "R2"]])

    # -----------------------------------------
    # ✅ Promotion Button
    # -----------------------------------------
    st.markdown("### 📤 Promote to Production")

    if st.button("✅ Promote This Model Now"):
        try:
            #prod_dir = "./agents/asset_appraisal/models/production"
            prod_dir = "/home/dzoan/AI-AIGENTbythePeoplesANDBOX/HUGKAG/agents/asset_appraisal/models/production"

            
            os.makedirs(prod_dir, exist_ok=True)

            shutil.copy(model_path, os.path.join(prod_dir, "model.joblib"))
            json.dump(
                {"model_path": model_path, "promoted_at": datetime.now(timezone.utc).isoformat(), "report": report},
                open(os.path.join(prod_dir, "production_meta.json"), "w"),
                indent=2
            )
            st.balloons()
            st.success("✅ Model promoted successfully!")
        except Exception as e:
            st.error(f"❌ Promotion failed: {e}")
    



# ─────────────────────────────────────────
# F — MODEL TRAINING & PROMOTION (A/B with Prod)
# ─────────────────────────────────────────
with tabF:
    import os, json, glob
    from datetime import datetime, timezone
    import numpy as np
    import pandas as pd
    import plotly.graph_objects as go
    import plotly.express as px
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    import joblib
    import shutil
    from pathlib import Path


    st.subheader("🧪 Stage F — Model Training & Promotion")
    st.caption("Train or retrain with human feedback, compare against production (A/B), and promote if better.")
    
    
    # -----------------------------------------
    # ✅ HOW TO USE THIS TRAINING STAGE (Dark / Collapsible)
    # -----------------------------------------
    with st.expander("🧭 How this stage works", expanded=False):
        st.markdown("""
        <div style="
            padding:18px;
            border-radius:12px;
            background:linear-gradient(145deg,#0d1829,#10243d);
            border:1px solid #1e3a5f;
            color:#e2e8f0;
            font-size:1.05rem;
            line-height:1.55;
        ">
        <b>📘 How this stage works:</b><br><br>
        You are now in <b>Stage F</b>, where your appraisal model is trained, compared, and prepared for production.
        <br>This stage takes the <b>human-reviewed values</b> produced in Stage E and builds a model that predicts
        future valuations with better accuracy.
        <br><br><b>✅ Follow these steps:</b><br>
        <b>1️⃣ Load Training Data</b><br>• Auto-detect latest <code>reviewed_appraisal*.csv</code> from Stage E.<br>
        • Or upload CSV with <code>human_value</code> labels.
        <br><br><b>2️⃣ Select Features</b><br>• Numeric columns auto-selected; leakage columns excluded.
        <br><br><b>3️⃣ Choose a Model</b><br>Select GradientBoosting, RandomForest, or LinearRegression (fast cycle).
        <br><br><b>4️⃣ Train & Compare</b><br>• Train on data → evaluate holdout → A/B compare if baseline exists.
        <br><br><b>5️⃣ Review Metrics & Insights</b><br>• Actual vs predicted charts, residuals, importance, summary.
        <br><br><b>6️⃣ Save / Promote / Export</b><br>• Promote best model → Stage G ZIP bundle.
        <br><br><b>🎯 Goal:</b> Produce a model that’s <b>more accurate, more stable, and more explainable</b>.
        </div>
        """, unsafe_allow_html=True)

    # # -----------------------------------------
    # # ✅ HOW TO USE THIS TRAINING STAGE
    # # -----------------------------------------
    # st.markdown("""
    # <div style="
    #     padding: 18px;
    #     border-radius: 12px;
    #     background-color: #EFF6FF;
    #     border-left: 6px solid #2563EB;
    #     font-size: 1.05rem;
    # ">
    # <b>📘 How this stage works:</b><br><br>

    # You are now in <b>Stage F</b>, where your appraisal model is trained, compared, and prepared for production.

    # This stage takes the <b>human-reviewed values</b> produced in Stage E and builds a model that predicts future valuations with better accuracy.

    # <br><br>

    # <b>✅ Follow these steps:</b><br>

    # <b>1️⃣ Load Training Data</b><br>
    # • The system auto-detects your latest <code>reviewed_appraisal*.csv</code> from Stage E.  
    # • If you prefer, upload a new CSV containing <code>human_value</code> labels.  

    # <br>

    # <b>2️⃣ Select Features</b><br>
    # • Numeric and relevant features are automatically selected.  
    # • ID columns and leakage columns (asset_id, ai_adjusted, etc.) are excluded.

    # <br>

    # <b>3️⃣ Choose a Model</b><br>
    # Select an algorithm (GradientBoosting, RandomForest, LinearRegression).  
    # The system will auto-tune nothing—this is a fast-iteration training cycle.

    # <br>

    # <b>4️⃣ Train & Compare</b><br>
    # • The model trains on your data.  
    # • A holdout test set evaluates performance.  
    # • If a production model exists, an A/B comparison is displayed.  

    # <br>

    # <b>5️⃣ Review Metrics & Insights</b><br>
    # • Actual vs predicted charts  
    # • Residual distributions  
    # • Feature importance analysis  
    # • Executive summary (WHAT → SO WHAT → NOW WHAT)  
    # • AI recommendation (promote / retrain)

    # <br>

    # <b>6️⃣ Save, Promote or Export</b><br>
    # • Save trained models  
    # • Promote to production (Stage G uses it for ZIP packaging)  
    # • Export full ZIP bundles for deployment (AWS S3, Swift, GitHub)

    # <br><br>

    # <b>🎯 Goal of Stage F:</b><br>
    # Produce a model that is <b>more accurate, more stable, and more explainable</b> than your current production baseline — and ready for deployment in Stage G.
    # </div>
    # """, unsafe_allow_html=True)

    

    # ---------- helpers ----------
    def _ts():
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def _rmse(y_true, y_pred):
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))

    def _mape(y_true, y_pred):
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        mask = (y_true != 0) & np.isfinite(y_true) & np.isfinite(y_pred)
        if not mask.any():
            return float("nan")
        return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)

    def _safe_len_df(x):
        return (0 if not isinstance(x, pd.DataFrame) else len(x))

    # ---------- diagnostics (always visible) ----------
    st.markdown("#### 🔎 Data availability (snapshots)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("decision_df",  _safe_len_df(ss.get("asset_decision_df")))
    c2.metric("policy_df",    _safe_len_df(ss.get("asset_policy_df")))
    c3.metric("verified_df",  _safe_len_df(ss.get("asset_verified_df")))
    c4.metric("ai_df",        _safe_len_df(ss.get("asset_ai_df")))

    with st.expander("Load demo portfolio (if earlier stages not run)"):
        if st.button("Load demo portfolio (10 rows)", key="btn_demo_portfolio"):
            rng = np.random.default_rng(42)
            demo = pd.DataFrame({
                "application_id": [f"APP_{i:04d}" for i in range(10)],
                "asset_id":      [f"A{i:04d}" for i in range(10)],
                "asset_type":    rng.choice(["House","Apartment","Car","Land"], 10),
                "city":          rng.choice(["HCMC","Hanoi","Da Nang","Hue"], 10),
                "market_value":  rng.integers(80_000, 800_000, 10),
                "ai_adjusted":   rng.integers(75_000, 820_000, 10),
                "loan_amount":   rng.integers(30_000, 500_000, 10),
                "confidence":    rng.integers(60, 98, 10),
                "condition_score": rng.uniform(0.6, 1.0, 10).round(3),
                "legal_penalty":   rng.uniform(0.95, 1.0, 10).round(3),
                "human_value":   rng.integers(75_000, 820_000, 10),
            })
            ss["asset_decision_df"] = demo
            st.success("Demo portfolio loaded into ss['asset_decision_df'].")

    st.divider()

    # ---------- training data source ----------
    RUNS_DIR = "./.tmp_runs"
    os.makedirs(RUNS_DIR, exist_ok=True)

    # Auto-pick latest reviewed CSV from Stage E
    reviewed = sorted([f for f in os.listdir(RUNS_DIR)
                       if f.startswith("reviewed_appraisal") and f.endswith(".csv")], reverse=True)
    df_train = None
    auto_path = None
    if reviewed:
        auto_path = os.path.join(RUNS_DIR, reviewed[0])
        try:
            df_train = pd.read_csv(auto_path)
        except Exception as e:
            st.warning(f"Could not read `{auto_path}`: {e}")

    st.markdown("#### 📥 Training dataset")
    colU1, colU2 = st.columns([1.4, 1])
    with colU1:
        st.text_input("Auto-detected Stage E file", value=(auto_path or "—"), disabled=True)
    with colU2:
        up = st.file_uploader("Or upload CSV with human_value", type=["csv"], key="train_csv_upload")

    if up is not None:
        try:
            df_train = pd.read_csv(up)
            st.success(f"Loaded uploaded CSV ({len(df_train)} rows).")
        except Exception as e:
            st.error(f"Upload read failed: {e}")

    if df_train is None or df_train.empty:
        st.warning("⚠️ No training data available. Use Stage E to export `reviewed_appraisal*.csv` or upload a CSV above.")
        st.stop()

    st.markdown(f"**Using training rows:** {len(df_train):,}")
    st.dataframe(df_train.head(20), use_container_width=True)

    # ---------- feature building ----------
    st.markdown("#### 🧱 Feature selection")
    target_col = "human_value"
    if target_col not in df_train.columns:
        st.error("CSV must include a 'human_value' column (target).")
        st.stop()

    # Exclude obvious leak/IDs/targets from X
    drop_cols = {
        target_col, "fmv", "ai_adjusted",  # avoid leakage; AI numbers used only for comparison
        "ai_decision", "human_decision", "decision", "final_decision",
        "justification", "reviewed_value", "final_value",
        "application_id", "asset_id", "asset_type", "city"
    }
    num_cols = [c for c in df_train.columns
                if c not in drop_cols and pd.api.types.is_numeric_dtype(df_train[c])]

    if not num_cols:
        st.error("No numeric features left after filtering. Please include numeric columns for training.")
        st.stop()

    dataset_rows = len(df_train)
    numeric_feature_count = len(num_cols)

    X = df_train[num_cols].copy()
    y = pd.to_numeric(df_train[target_col], errors="coerce")

    # Drop rows with missing target
    mask = pd.notna(y)
    X, y = X.loc[mask], y.loc[mask]

    st.markdown("#### ⭐ Recommended models (EQACh signal)")
    st.caption(f"{dataset_rows:,} labeled assets · {numeric_feature_count} numeric features")

    def score_asset_model(name: str) -> tuple[int, str]:
        """Coarse scoring so operators see why a regressor fits their data."""
        reason = ""
        score = 0

        if name == "GradientBoostingRegressor":
            score = 5 if dataset_rows > 5_000 else 3
            reason = "Captures nonlinear patterns and handles wide appraisal signals."
        elif name == "RandomForestRegressor":
            score = 4 if 1_000 < dataset_rows <= 10_000 else 2
            reason = "Stable when you have mixed-quality human feedback and want robustness."
        elif name == "LinearRegression":
            score = 3 if dataset_rows <= 2_000 else 1
            reason = "Fast, fully explainable baseline for regulators or smoke tests."

        if numeric_feature_count >= 8 and name != "LinearRegression":
            score += 1
            reason += " Extra numeric features boost tree ensembles."

        return score, reason

    model_profiles = []
    for candidate in ["GradientBoostingRegressor", "RandomForestRegressor", "LinearRegression"]:
        score, reason = score_asset_model(candidate)
        model_profiles.append(
            {
                "name": candidate,
                "score": score,
                "tagline": {
                    "GradientBoostingRegressor": "Enterprise-ready EQACh default",
                    "RandomForestRegressor": "Resilient midsize option",
                    "LinearRegression": "Audit-friendly baseline",
                }[candidate],
                "reason": reason,
            }
        )

    model_profiles.sort(key=lambda x: x["score"], reverse=True)
    rec_cols = st.columns(len(model_profiles))
    for col, profile in zip(rec_cols, model_profiles):
        with col:
            st.markdown(f"**{profile['name']}**")
            st.caption(profile["tagline"])
            st.write(profile["reason"])
            if st.button(f"Use {profile['name']}", key=f"use_asset_{profile['name']}"):
                ss["asset_model_choice"] = profile["name"]

    # Train/Test split
    test_size = st.slider("Holdout size", 10, 40, 20, step=5) / 100.0
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=test_size, random_state=42)

    # ---------- model choice ----------
    st.markdown("#### 🤖 Choose model")
    model_options = ["GradientBoostingRegressor", "RandomForestRegressor", "LinearRegression"]
    
    # Get recommended model from presets (map preset names to sklearn names)
    def _get_recommended_asset_model() -> str | None:
        """Get recommended tabular model for asset appraisal."""
        try:
            import yaml
            from pathlib import Path
            config_path = Path(__file__).resolve().parents[3] / "config" / "agent_model_presets.yaml"
            if config_path.exists():
                with open(config_path, "r") as f:
                    presets = yaml.safe_load(f)
                    if presets and "tabular_models" in presets:
                        agent_config = presets["tabular_models"].get("asset_appraisal")
                        if agent_config:
                            # Map preset names to sklearn model names
                            preset_to_sklearn = {
                                "LightGBM": "GradientBoostingRegressor",  # Closest equivalent
                                "RandomForest": "RandomForestRegressor",
                                "XGBoost": "GradientBoostingRegressor",  # Closest equivalent
                                "LogisticRegression": "LinearRegression",  # Closest equivalent
                            }
                            primary = agent_config.get("primary")
                            if primary:
                                mapped = preset_to_sklearn.get(primary)
                                if mapped and mapped in model_options:
                                    return mapped
                            fallback = agent_config.get("fallback")
                            if fallback:
                                mapped = preset_to_sklearn.get(fallback)
                                if mapped and mapped in model_options:
                                    return mapped
        except Exception:
            pass
        return None
    
    recommended_model = _get_recommended_asset_model()
    default_choice = ss.get("asset_model_choice")
    if not default_choice or default_choice not in model_options:
        # Priority: recommended > first available
        if recommended_model and recommended_model in model_options:
            default_choice = recommended_model
            ss["asset_model_choice"] = recommended_model
            st.info(f"✅ **Recommended for asset appraisal**: {recommended_model} (auto-selected)", icon="⭐")
        else:
            default_choice = model_profiles[0]["name"] if model_profiles else model_options[0]

    model_choice = st.selectbox(
        "Select model algorithm",
        model_options,
        index=model_options.index(default_choice)
    )
    ss["asset_model_choice"] = model_choice
    ModelCls = {
        "GradientBoostingRegressor": GradientBoostingRegressor,
        "RandomForestRegressor": RandomForestRegressor,
        "LinearRegression": LinearRegression,
    }[model_choice]

    # ---------- train & compare ----------
    if st.button("🚀 Train & Compare (A/B vs Production)", key="btn_train_model"):
        # Train new
        new_model = ModelCls().fit(Xtr, ytr)
        y_pred_new = new_model.predict(Xte)

        # Load production baseline if exists
        prod_model_path = "./agents/asset_appraisal/models/production/model.joblib"
        prod_exists = os.path.exists(prod_model_path)
        y_pred_prod = None
        if prod_exists:
            try:
                prod_model = joblib.load(prod_model_path)
                # guard: try only if shapes align
                y_pred_prod = prod_model.predict(Xte)
            except Exception as e:
                st.warning(f"Production model failed to score holdout: {e}")

        # Metrics
        def _metrics(y_true, y_pred):
            return {
                "MAE": float(mean_absolute_error(y_true, y_pred)),
                "RMSE": _rmse(y_true, y_pred),
                "MAPE%": _mape(y_true, y_pred),
                "R2": float(r2_score(y_true, y_pred)),
            }

        new_m = _metrics(yte, y_pred_new)
        prod_m = _metrics(yte, y_pred_prod) if y_pred_prod is not None else None

        # ===== Dashboard: KPIs & deltas =====
        st.markdown("### 📊 A/B Metrics (Holdout)")
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric("New MAE", f"{new_m['MAE']:,.0f}",
                      delta=(f"{(new_m['MAE'] - prod_m['MAE']):+.0f}" if prod_m else None))
        with k2:
            st.metric("New RMSE", f"{new_m['RMSE']:,.0f}",
                      delta=(f"{(new_m['RMSE'] - prod_m['RMSE']):+.0f}" if prod_m else None))
        with k3:
            st.metric("New MAPE", f"{new_m['MAPE%']:.2f}%",
                      delta=(f"{(new_m['MAPE%'] - prod_m['MAPE%']):+.2f}%" if prod_m else None))
        with k4:
            st.metric("New R²", f"{new_m['R2']:.3f}",
                      delta=(f"{(new_m['R2'] - prod_m['R2']):+.3f}" if prod_m else None))
        with k5:
            st.metric("Test rows", f"{len(yte):,}")

        # ===== Plots: Actual vs Pred, Residuals =====
        plot_df = pd.DataFrame({
            "y_true": yte.values,
            "y_pred_new": y_pred_new,
            "y_pred_prod": (y_pred_prod if y_pred_prod is not None else np.full_like(y_pred_new, np.nan))
        })

        # Actual vs Pred overlay
        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=plot_df["y_true"], y=plot_df["y_pred_new"],
            mode="markers", name="New", opacity=0.7
        ))
        if y_pred_prod is not None:
            fig_scatter.add_trace(go.Scatter(
                x=plot_df["y_true"], y=plot_df["y_pred_prod"],
                mode="markers", name="Production", opacity=0.6
            ))
        # diagonal reference
        minv, maxv = np.nanmin(plot_df[["y_true","y_pred_new","y_pred_prod"]].values), np.nanmax(plot_df[["y_true","y_pred_new","y_pred_prod"]].values)
        fig_scatter.add_trace(go.Scatter(x=[minv, maxv], y=[minv, maxv], mode="lines", name="Ideal", line=dict(dash="dash")))
        fig_scatter.update_layout(title="Actual vs Predicted (Holdout)", xaxis_title="Actual", yaxis_title="Predicted")
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Residuals hist
        plot_df["res_new"]  = plot_df["y_true"] - plot_df["y_pred_new"]
        if y_pred_prod is not None:
            plot_df["res_prod"] = plot_df["y_true"] - plot_df["y_pred_prod"]

        fig_res = go.Figure()
        fig_res.add_trace(go.Histogram(x=plot_df["res_new"], name="New", opacity=0.7))
        if y_pred_prod is not None:
            fig_res.add_trace(go.Histogram(x=plot_df["res_prod"], name="Production", opacity=0.6))
        fig_res.update_layout(barmode="overlay", title="Residuals Distribution (Actual - Predicted)")
        fig_res.update_traces(nbinsx=40)
        st.plotly_chart(fig_res, use_container_width=True)

        # ===== Feature importance / coefficients =====
        st.markdown("### 🧠 Feature Importance / Coefficients")
        if hasattr(new_model, "feature_importances_"):
            imp = pd.DataFrame({
                "feature": num_cols,
                "importance": new_model.feature_importances_
            }).sort_values("importance", ascending=False)
            st.bar_chart(imp.set_index("feature"))
        elif hasattr(new_model, "coef_"):
            coef = pd.DataFrame({
                "feature": num_cols,
                "coef": np.ravel(new_model.coef_)
            }).sort_values("coef", key=np.abs, ascending=False)
            st.bar_chart(coef.set_index("feature"))
        else:
            st.info("This model does not expose importances/coefficients.")

        # ===== Persist artifacts =====
        #trained_dir = "./agents/asset_appraisal/models/trained"
        trained_dir = "/home/dzoan/AI-AIGENTbythePeoplesANDBOX/HUGKAG/agents/asset_appraisal/models/trained"
        
        os.makedirs(trained_dir, exist_ok=True)
        ts = _ts()
        model_path = os.path.join(trained_dir, f"{model_choice}_asset_{ts}.joblib")
        joblib.dump(new_model, model_path)

        preds_csv = os.path.join(RUNS_DIR, f"training_preds_{ts}.csv")
        plot_df.to_csv(preds_csv, index=False)

        report = {
            "timestamp": ts,
            "model_choice": model_choice,
            "trained_model_path": model_path,
            "features": num_cols,
            "metrics_new": new_m,
            "metrics_prod": prod_m,
            "holdout_rows": int(len(yte)),
            "source_file": (auto_path or "uploaded"),
            "preds_csv": preds_csv,
        }
        report_path = os.path.join(RUNS_DIR, f"training_report_{ts}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        st.success(f"✅ Trained model saved → `{model_path}`")
        st.caption(f"Report → `{report_path}` | Predictions → `{preds_csv}`")

        # Download helpers
        cdl1, cdl2 = st.columns(2)
        with cdl1:
            st.download_button("⬇️ Download training report (JSON)",
                               data=json.dumps(report, indent=2).encode("utf-8"),
                               file_name=os.path.basename(report_path),
                               mime="application/json")
        with cdl2:
            st.download_button("⬇️ Download holdout predictions (CSV)",
                               data=plot_df.to_csv(index=False).encode("utf-8-sig"),
                               file_name=os.path.basename(preds_csv),
                               mime="text/csv")
        # ✅ ✅ ✅ CALL DASHBOARD — FIX FOR YOUR ISSUE
        render_stage_f_footer(
            new_m=new_m,
            prod_m=prod_m,
            RUNS_DIR=RUNS_DIR,
            model_path=model_path,
            report=report,
            df_train=df_train,
            yte=yte,
            y_pred_new=y_pred_new
        )
        
# ───────────────────────────────────────────────
# ✅ Helper functions required by Stage G
# ───────────────────────────────────────────────
def is_nonempty_df(x):
    import pandas as pd
    return isinstance(x, pd.DataFrame) and not x.empty

def first_nonempty_df(*candidates):
    for c in candidates:
        if is_nonempty_df(c):
            return c
    return None


# ───────────────────────────────────────────────
# G — DEPLOYMENT & DISTRIBUTION STAGE
# ───────────────────────────────────────────────
with tabG:
    import os, json, hashlib, zipfile, requests
    from datetime import datetime, timezone
    from pathlib import Path
    import streamlit as st

    st.title("🚀 Stage G — Deployment & Distribution")
    st.caption("Package → Verify → Upload → Release → Distribute to Credit / Legal / Risk units.")
    EXPORT_DIR = Path("./exports")
    EXPORT_DIR.mkdir(exist_ok=True)

    st.markdown("## 📦 Build Project Bundle (Model + Reports + Artifacts)")
    build_zip_name = f"asset_project_bundle_{_ts()}.zip"
    build_zip_path = EXPORT_DIR / build_zip_name

    if st.button("⬇️ Build & Download Project ZIP", key="btn_build_stage_g_zip"):
        try:
            with zipfile.ZipFile(build_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(RUNS_DIR):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, RUNS_DIR)
                        zf.write(full, f"runs/{arc}")

                if os.path.exists("./agents/asset_appraisal/models/production"):
                    for root, dirs, files in os.walk("./agents/asset_appraisal/models/production"):
                        for f in files:
                            full = os.path.join(root, f)
                            zf.write(full, f"production_models/{f}")

                if os.path.exists("./agents/asset_appraisal/models/trained"):
                    for root, dirs, files in os.walk("./agents/asset_appraisal/models/trained"):
                        for f in files:
                            full = os.path.join(root, f)
                            zf.write(full, f"trained_models/{f}")

                latest_report = sorted(Path(RUNS_DIR).glob("training_report_*.json"), reverse=True)
                if latest_report:
                    zf.write(latest_report[0], "training_report.json")

            st.success(f"✅ Exported: {build_zip_name}")
            with open(build_zip_path, "rb") as fp:
                st.download_button(
                    "⬇️ Download ZIP Now",
                    data=fp,
                    file_name=build_zip_name,
                    mime="application/zip",
                    use_container_width=True,
                    key="btn_download_stage_g_zip",
                )
        except Exception as e:
            st.error(f"❌ ZIP creation failed: {e}")

    # ---------------------------------------------
    # 1) Load the latest ZIP bundle created in Stage F
    # ---------------------------------------------
    st.markdown("## 📦 1) Project Package (Generated in Stage F)")

    # Find ZIP files
    zip_files = sorted(EXPORT_DIR.glob("asset_project_bundle_*.zip"), reverse=True)
    
    if not zip_files:
        st.warning("⚠️ No project ZIP found. Run Stage F and export a bundle first.")
        st.stop()

    latest_zip = zip_files[0]

    st.success(f"✅ Latest bundle detected: `{latest_zip.name}`")
    st.caption(f"Size: **{latest_zip.stat().st_size/1e6:.2f} MB**")
    
    # # Show preview
    # with zipfile.ZipFile(latest_zip, "r") as z:
    #     preview = z.namelist()[:20]
    #     st.code("\n".join(preview), language="text")
    

    # ---------------------------------------------
    # 2) Integrity Check (SHA256)
    # ---------------------------------------------
    st.markdown("## ✅ 2) File Integrity Check (SHA256)")

    sha256 = hashlib.sha256(latest_zip.read_bytes()).hexdigest()
    st.code(sha256)

    checksum_path = latest_zip.with_suffix(".sha256")
    checksum_path.write_text(sha256)
    st.caption(f"Checksum written → `{checksum_path.name}`")

    # Simple signature
    sig_path = latest_zip.with_suffix(".sig")
    sig_path.write_text(f"AI-Agent-Hub signed @ {datetime.now(timezone.utc).isoformat()}")
    st.caption(f"Signature stub → `{sig_path.name}`")


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
    # 4) Deployment Audit Log
    # ---------------------------------------------
    st.markdown("## 🧾 4) Deployment Audit Log")

    audit = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "export_file": latest_zip.name,
        "checksum": sha256,
        "target": dest,
    }

    audit_path = EXPORT_DIR / "deployment_audit.jsonl"
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit) + "\n")

    st.success(f"Audit record added → `{audit_path.name}`")


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


# ─────────────────────────────────────────
# ✅ STAGE H — Executive Dashboard + Handoff Export
# ─────────────────────────────────────────

with tabH:
    import os, json, zipfile
    from pathlib import Path
    from datetime import datetime, timezone
    import pandas as pd
    import numpy as np
    import streamlit as st
    import plotly.express as px
    import plotly.graph_objects as go

    st.markdown("## 🧭 Stage H — Unified Portfolio, Insights & Handoff Export")
    st.caption("Executive summary • Asset insights • Fraud/risk signals • Department deliverables")


    
    # ---------------------------------------------------------
    # ✅ Required outputs from earlier stages — MUST COME FIRST
    # ---------------------------------------------------------
    ai_df        = st.session_state.get("asset_ai_df")
    policy_df    = st.session_state.get("asset_policy_df")
    decision_df  = st.session_state.get("asset_decision_df")

    missing = []

    if ai_df is None or ai_df.empty:
        missing.append("Stage C (valuation)")
    if decision_df is None or decision_df.empty:
        missing.append("Stage D (risk & decision)")

    if missing:
        st.error("⚠️ Missing required data: " + ", ".join(missing))
        st.info("Please run the missing stages before returning to Stage H.")
        st.stop()

    # ✅ Only now is dfv allowed to be created
    dfv = decision_df.copy()


    # ---------------------------------------------------------
    # ✅ STATUS LABEL (Validated / Risky / Fraud)
    # ---------------------------------------------------------
    def label_row(r):
        if r.get("fraud_flag") in [True, "True", 1]:
            return "FRAUD"
        if r.get("encumbrance_flag") in [True, "True", 1]:
            return "ENCUMBERED"
        if str(r.get("decision", "")).lower() == "reject":
            return "RISKY"
        if str(r.get("policy_breaches", "")).strip():
            return "RISKY"
        return "VALIDATED"

    dfv["status"] = dfv.apply(label_row, axis=1)

    # ---------------------------------------------------------
    # ✅ EXECUTIVE SUMMARY METRICS
    # ---------------------------------------------------------
    st.markdown("### 📊 Executive Summary")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Assets", len(dfv))
    with col2:
        st.metric("Validated", (dfv["status"] == "VALIDATED").sum())
    with col3:
        st.metric("Risky", (dfv["status"] == "RISKY").sum())
    with col4:
        st.metric("Fraud / Encumbered", (dfv["status"].isin(["FRAUD","ENCUMBERED"])).sum())

    # ---------------------------------------------------------
    # ✅ HEATMAP — Asset Risk & Fraud Signals
    # ---------------------------------------------------------
    st.markdown("### 🔥 Fraud / Risk Heatmap")
    
    try:
        hm = dfv[["confidence", "ltv_ai"]].copy()
        hm = hm.dropna()

        fig_hm = px.density_heatmap(
            hm, x="confidence", y="ltv_ai",
            nbinsx=30, nbinsy=30,
            color_continuous_scale="YlOrRd",
            title="Fraud/Anomaly Density — (Low confidence + High LTV = Hot Zones)"
        )
        st.plotly_chart(fig_hm, use_container_width=True)
    except Exception:
        st.info("Heatmap unavailable until confidence / LTV data is complete.")

    # ---------------------------------------------------------
    # ✅ MARKET INSIGHTS — CITY LEVEL DISTRIBUTION
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
    # ✅ DEPARTMENT HANDOFF EXPORTS (bulletproof)
    # ---------------------------------------------------------
    st.markdown("## 🏦 Department Handoff Packages")
    st.caption("Each team receives only what they need. Clear, simple, compliant.")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    HANDOFF_DIR = Path("./handoff")
    ZIP_DIR      = HANDOFF_DIR / "zips"
    HANDOFF_DIR.mkdir(exist_ok=True)
    ZIP_DIR.mkdir(exist_ok=True)

    # ---------------------------
    # ✅ CREDIT APPRAISAL EXPORT
    # ---------------------------
    credit_cols = [ 
        "application_id","asset_id","asset_type","city",
        "ai_adjusted","fmv","realizable_value",
        "loan_amount","ltv_ai","ltv_cap",
        "decision","policy_breaches"
    ]
    credit = dfv[[c for c in credit_cols if c in dfv.columns]].copy()
    credit_path = HANDOFF_DIR / f"credit_appraisal_{ts}.csv"
    credit.to_csv(credit_path, index=False)

    # Download button
    with open(credit_path, "rb") as f:
        st.download_button("⬇️ Credit Appraisal CSV", f, file_name=credit_path.name, mime="text/csv")

    # ---------------------------
    # ✅ LEGAL / TITLE EXPORT
    # ---------------------------
    legal_cols = [
        "application_id","asset_id","verified_owner",
        "encumbrance_flag","legal_penalty","condition_score","notes"
    ]
    legal = dfv[[c for c in legal_cols if c in dfv.columns]].copy()
    legal_path = HANDOFF_DIR / f"legal_pack_{ts}.csv"
    legal.to_csv(legal_path, index=False)

    with open(legal_path, "rb") as f:
        st.download_button("⬇️ Legal & Title CSV", f, file_name=legal_path.name, mime="text/csv")

    # ---------------------------
    # ✅ RISK MANAGEMENT EXPORT
    # ---------------------------
    risk_cols = [
        "application_id","asset_id","confidence",
        "ltv_ai","ltv_cap","policy_breaches","decision","status"
    ]
    risk = dfv[[c for c in risk_cols if c in dfv.columns]].copy()
    risk_path = HANDOFF_DIR / f"risk_management_{ts}.csv"
    risk.to_csv(risk_path, index=False)

    with open(risk_path, "rb") as f:
        st.download_button("⬇️ Risk Management CSV", f, file_name=risk_path.name, mime="text/csv")

    # ---------------------------
    # ✅ CUSTOMER SERVICE EXPORT
    # ---------------------------
    cust_cols = [
        "application_id","asset_id","asset_type","city",
        "fmv","ai_adjusted","decision","status","why"
    ]
    cust = dfv[[c for c in cust_cols if c in dfv.columns]].copy()
    cust_path = HANDOFF_DIR / f"customer_service_{ts}.csv"
    cust.to_csv(cust_path, index=False)

    with open(cust_path, "rb") as f:
        st.download_button("⬇️ Customer Service CSV", f, file_name=cust_path.name, mime="text/csv")

    # ---------------------------
    # ✅ PORTFOLIO SUMMARY
    # ---------------------------
    portfolio_path = HANDOFF_DIR / f"portfolio_{ts}.csv"
    dfv.to_csv(portfolio_path, index=False)

    with open(portfolio_path, "rb") as f:
        st.download_button("⬇️ Portfolio Summary CSV", f, file_name=portfolio_path.name, mime="text/csv")

    # ---------------------------
    # ✅ AUDIT RECORD
    # ---------------------------
    audit = {
        "timestamp": ts,
        "rows": len(dfv),
        "status": dfv["status"].value_counts().to_dict(),
        "avg_confidence": float(dfv["confidence"].mean() if "confidence" in dfv else 0.0),
    }
    audit_path = HANDOFF_DIR / f"audit_{ts}.json"
    with open(audit_path, "w") as f:
        json.dump(audit, f, indent=2)

    with open(audit_path, "rb") as f:
        st.download_button("⬇️ Audit Record (JSON)", f, file_name=audit_path.name, mime="application/json")

    # # ---------------------------
    # # ✅ FULL ZIP BUNDLE
    # # ---------------------------
    # zip_path = ZIP_DIR / f"handoff_bundle_{ts}.zip"
    # with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    #     for fp in [credit_path, legal_path, risk_path, cust_path, portfolio_path, audit_path]:
    #         zf.write(fp, arcname=os.path.basename(fp))

    # with open(zip_path, "rb") as f:
    #     st.download_button("⬇️ Download FULL Handoff ZIP", f,
    #                     file_name=zip_path.name, mime="application/zip",
    #                     use_container_width=True)

    
    
   
    # ---------------------------------------------------------
    # ✅ ZIP bundle
    # ---------------------------------------------------------
    zip_path = ZIP_DIR / f"handoff_bundle_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in [credit_path, legal_path, risk_path, cust_path, portfolio_path, audit_path]:
            zf.write(fp, arcname=os.path.basename(fp))

    st.markdown("### 📦 Download Unified Handoff Bundle")
    with open(zip_path, "rb") as f:
        st.download_button(
            "⬇️ Download Full Handoff ZIP",
            data=f,
            file_name=os.path.basename(zip_path),
            mime="application/zip",
            use_container_width=True
        )


# Legacy macOS blue theme (kept for optional reuse)
LEGACY_ASSET_THEME_SNIPPET = '''
def legacy_asset_theme(theme: str = "dark"):
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
    page_id="asset_appraisal",
    context=_build_asset_chat_context(),
    faq_questions=ASSET_FAQ,
    persona=ASSET_PERSONA,
)
