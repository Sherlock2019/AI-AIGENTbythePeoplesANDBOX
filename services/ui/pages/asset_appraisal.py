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
import os, io, re, json
import datetime as dt  # ← single, unambiguous datetime import
from typing import Any, Dict

# ── Third-party
import requests
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
import os, io, re, json, datetime, requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone


# ─────────────────────────────────────────────
# PAGE CONFIG — must be the first Streamlit call
# ─────────────────────────────────────────────

st.set_page_config(page_title="Asset Appraisal Agent", layout="wide")
ss = st.session_state

# ─────────────────────────────────────────────
# SESSION DEFAULTS (idempotent)
# ─────────────────────────────────────────────
def _init_defaults():
    ss.setdefault("asset_logged_in", False)
    ss.setdefault("asset_stage", "login")   # login → asset_flow
    ss.setdefault("asset_user", {"name": "Guest", "email": None})
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
    os.makedirs("./.tmp_runs", exist_ok=True)

_init_defaults()

def render_nav_bar_app():
    st.markdown(
        "<div style='display:flex;gap:12px;align-items:center'>"
        "<a href='?stage=agents' class='macbtn'>🤖 Agents</a>"
        "<span style='opacity:.6'>/</span>"
        "<span>🏛️ Asset Appraisal Agent</span>"
        "</div>",
        unsafe_allow_html=True,
    )




# ─────────────────────────────────────────────
# THEME INJECTION (Dark + Sidebar hide, with MutationObserver)
# Run immediately on every script execution to avoid flicker on rerun
# ─────────────────────────────────────────────
import streamlit.components.v1 as components # <--- IMPORT IS HERE
# 1) CSS (global, persistent)
# Note: Removed the inject_dark_theme_once() function and session state check
st.markdown("""
    <style>
      :root { color-scheme: dark; } /* Hint built-ins */
      html, body, .stApp {
        background-color:#0f172a !important;
        color:#e5e7eb !important;
        font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      }
      /* Sidebar off + container padding */
      [data-testid="stSidebar"], section[data-testid="stSidebar"], nav[data-testid="stSidebarNav"] { display:none !important; }
      [data-testid="stAppViewContainer"] { margin-left:0 !important; padding-left:0 !important; }
      /* Headings */
      h1, h2, h3, h4, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color:#e5e7eb !important; }
      /* Tabs */
      .stTabs [data-baseweb="tab-list"] { gap:6px; border-bottom:1px solid #1f2937; }
      .stTabs [data-baseweb="tab"] {
        background:#0b1222; border:1px solid #1f2937; border-bottom:none;
        padding:10px 14px; border-top-left-radius:10px; border-top-right-radius:10px; color:#cbd5e1;
      }
      .stTabs [aria-selected="true"] { background:#111827 !important; color:#e5e7eb !important; }
      /* Inputs */
      .stTextInput input, .stNumberInput input, .stSelectbox [data-baseweb="select"] > div {
        background:#0b1222 !important; color:#e5e7eb !important; border:1px solid #1f2937 !important;
      }
      /* Buttons */
      .stButton button {
        background:linear-gradient(180deg,#1f3b57 0%,#0e1f33 100%) !important;
        color:#e6f3ff !important; border:1px solid #1d2b3a !important; border-radius:10px !important;
        box-shadow:0 0 10px rgba(56,189,248,.15);
      }
      .stButton button:hover { filter:brightness(1.05); box-shadow:0 0 16px rgba(56,189,248,.25); }
      /* Metrics */
      div[data-testid="stMetric"] { background:#0b1222; border:1px solid #1f2937; border-radius:12px; padding:10px 12px; }
      div[data-testid="stMetricValue"] { color:#38bdf8 !important; }
      /* Tables */
      .stDataFrame, .stTable { background:#0b1222 !important; border:1px solid #1f2937 !important; border-radius:10px !important; }
      /* Expanders */
      details { background:#0b1222 !important; border:1px solid #1f2937 !important; border-radius:10px !important; padding:6px 10px !important; }
      /* Plotly */
      .js-plotly-plot .plotly .main-svg { background-color:transparent !important; }
    </style>
    """, unsafe_allow_html=True)

# 2) JS observer to re-assert dark after Streamlit mutates
components.html("""
    <script>
      (function() {
        const apply = () => {
          try {
            const root = parent.document.documentElement;
            const app = parent.document.querySelector('.stApp');
            if (root) root.style.setProperty('color-scheme','dark');
            if (app) app.classList.add('dark-hold');
          } catch(e) {}
        };
        apply();
        const mo = new MutationObserver(apply);
        mo.observe(parent.document.documentElement, {childList:true, subtree:true});
      })();
    </script>
    """, height=0)

# ─────────────────────────────────────────────
# API CONFIG
# ─────────────────────────────────────────────

API_URL = os.getenv("API_URL", "http://localhost:8090")

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
    # read the global stage (default to ‘landing’)
    stage = st.session_state.get("stage", "landing")

    # show both buttons on this page
    c1, c2, _ = st.columns([1, 1, 6])
    with c1:
        if st.button("🏠 Back to Home", key=f"btn_home_{stage}"):
            _go_stage("landing")
            st.stop()
    with c2:
        if st.button("🤖 Back to Agents", key=f"btn_agents_{stage}"):
            _go_stage("agents")
            st.stop()
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
# ─────────────────────────────────────────────  ← PASTE END


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

    return False, "All agent attempts failed (discovered=" + ", ".join(agent_ids) + "):\n" + "\n\n".join(errors)



# # ─────────────────────────────────────────────
# # LOGIN
# # ─────────────────────────────────────────────
# if ss["asset_stage"] == "login" and not ss["asset_logged_in"]:
#     render_nav_bar_app()
#     st.title("🔐 Login to AI Asset Appraisal Platform")
#     c1, c2, c3 = st.columns([1,1,1])
#     with c1: user = st.text_input("Username", placeholder="e.g. dzoan")
#     with c2: email = st.text_input("Email", placeholder="e.g. dzoan@demo.local")
#     with c3: pwd = st.text_input("Password", type="password", placeholder="Enter any password")
#     if st.button("Login", key="btn_asset_login", use_container_width=True):
#         if user.strip() and email.strip():
#             ss["asset_user"] = {"name": user.strip(), "email": email.strip(), "timestamp": datetime.datetime.utcnow().isoformat()}
#             ss["asset_logged_in"] = True
#             ss["asset_stage"] = "asset_flow"
#             st.rerun()
#         else:
#             st.error("⚠️ Please fill all fields before continuing.")
#     st.stop()

# ─────────────────────────────────────────────
# WORKFLOW
# # ─────────────────────────────────────────────
# if ss["asset_logged_in"]:
#     render_nav_bar_app()
#     st.title("🏛️ Asset Appraisal Agent")
#     st.caption(f"E2E flow — Inputs → Anonymize → AI → Human Review → Training | 👋 {ss['asset_user']['name']}")

    
    
    # # ─────────────────────────────────────────
    # # TABS (1..5)
    # # ─────────────────────────────────────────
    # tab1, tab2, tab3, tab4, tab5 = st.tabs([
    #     "📥 1) Data Input",
    #     "🧹 2) Anonymize",
    #     "🤖 3) AI Appraisal & Valuation",
    #     "🧑‍⚖️ 4) Human Review",
    #     "🧪 5) Training (Feedback → Retrain)"
    # ])
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

    # ─────────────────────────────────────────
    # TABS (A..G) — Commented blueprint (keep this above live tabs)
    # ─────────────────────────────────────────
    # tabA, tabB, tabC, tabD, tabE, tabF, tabG = st.tabs([
    #     "🟦 A) Intake & Evidence",
    #     "🟩 B) Privacy & Features",
    #     "🟨 C) Valuation & Verification",
    #     "🟧 D) Policy & Decision",
    #     "🟪 E) Human Review & Feedback",
    #     "🟫 F) Model Training & Promotion",
    #     "⬜ G) Reporting & Handoff"
    # ])

    # ─────────────────────────────────────────
    # TABS (A..G) — Live tabs
    # ─────────────────────────────────────────
    tabA, tabB, tabC, tabD, tabE, tabF, tabG = st.tabs([
        "🟦 A) Intake & Evidence",
        "🟩 B) Privacy & Features",
        "🟨 C) Valuation & Verification",
        "🟧 D) Policy & Decision",
        "🟪 E) Human Review & Feedback",
        "🟫 F) Model Training & Promotion",
        "⬜ G) Reporting & Handoff"
    ])

    # Runtime tip
    st.caption(
        "📘 Tip: Move sequentially from A→G or revisit individual stages. "
        "If a stage reports missing data, rerun the previous one or load demo data."
    )

else:
    st.warning("Please log in first to access the Asset Appraisal workflow.")



# # ─────────────────────────────────────────────
# # WORKFLOW (A→F)
# # ─────────────────────────────────────────────
# if ss["asset_logged_in"] and ss["asset_stage"] in ("asset_flow", "asset_agent"):
#     render_nav_bar_app()
#     st.title("🏛️ Asset Appraisal Agent")
#     st.caption(
#         "A→F pipeline — Intake→Privacy→Valuation→Policy→Review→Reporting "
#         f"| 👋 {ss['asset_user']['name']}"
#     )

#     # # ─────────────────────────────────────────
#     # # TABS (A..F) — Commented blueprint (keep this above live tabs)
#     # # ─────────────────────────────────────────
#     # tabA, tabB, tabC, tabD, tabE, tabF = st.tabs([
#     #     "🟦 A) Intake & Evidence",
#     #     "🟩 B) Privacy & Features",
#     #     "🟨 C) Valuation & Verification",
#     #     "🟧 D) Policy & Decision",
#     #     "🟪 E) Human Review & Training",
#     #     "⬜ F) Reporting & Handoff"
#     # ])

#     # ─────────────────────────────────────────
#     # TABS (A..F) — Live tabs
#     # ─────────────────────────────────────────
#     tabA, tabB, tabC, tabD, tabE, tabF = st.tabs([
#         "🟦 A) Intake & Evidence",
#         "🟩 B) Privacy & Features",
#         "🟨 C) Valuation & Verification",
#         "🟧 D) Policy & Decision",
#         "🟪 E) Human Review & Training",
#         "⬜ F) Reporting & Handoff"
#     ])



# ─────────────────────────────────────────
# 🟦 STAGE A — INTAKE & EVIDENCE
# ─────────────────────────────────────────
with tabA:
    import io, os, json, hashlib, pandas as pd
    from datetime import datetime, timezone

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

    # ─────────────────────────────────────────
    # (A.2) PUBLIC DATASETS — Kaggle / HF / OpenML
    # ─────────────────────────────────────────
    st.markdown("### 🌍 Import Public Datasets (Kaggle / Hugging Face / OpenML / Portals)")
    src = st.selectbox(
        "Select source",
        ["Kaggle (API)", "Kaggle (Web)", "Hugging Face", "OpenML", "Public Domain Portals"],
        key="asset_pubsrc"
    )
    query = st.text_input("Search keywords", "house prices Vietnam real estate valuation", key="asset_pubquery")

    if st.button("🔎 Search dataset", key="btn_asset_pubsearch"):
        with st.spinner("Searching datasets..."):
            try:
                if src == "Kaggle (API)":
                    import subprocess
                    cmd = ["kaggle", "datasets", "list", "-s", query, "-v"]
                    try:
                        out = subprocess.check_output(cmd, text=True)
                        rows = out.strip().splitlines()
                        if len(rows) > 1:
                            header = [h.strip() for h in rows[0].split(",")]
                            df_pub = pd.DataFrame([r.split(",") for r in rows[1:]], columns=header)
                            st.dataframe(df_pub.head(25))
                            st.success("✅ Kaggle API results shown.")
                        else:
                            st.warning("No results found.")
                    except Exception as e:
                        st.error(f"Kaggle CLI failed: {e}")
                        st.info("💡 Install Kaggle CLI & configure ~/.kaggle/kaggle.json.")

                elif src == "Kaggle (Web)":
                    st.markdown(f"[🌐 Open Kaggle ↗️](https://www.kaggle.com/datasets?search={query})")

                elif src == "Hugging Face":
                    from huggingface_hub import list_datasets
                    results = list_datasets(search=query)
                    df_pub = pd.DataFrame([{"Dataset": r.id, "Tags": ", ".join(r.tags)} for r in results[:25]])
                    st.dataframe(df_pub)
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

    st.divider()

    # ─────────────────────────────────────────
    # (A.3) NORMALIZATION — Merge + Generate CSV
    # ─────────────────────────────────────────
    st.markdown("### 🧮 Normalize & Combine All Inputs")
    st.caption("Merge data from uploaded, imported, or synthetic sources into a unified format.")

    def normalize_dataframes(dfs):
        """Unify schemas and ensure consistent column names."""
        import numpy as np
        if not dfs:
            st.warning("No data to normalize.")
            return pd.DataFrame()
        merged = pd.concat(dfs, ignore_index=True)
        merged.columns = [c.strip().lower().replace(" ", "_") for c in merged.columns]
        required_cols = ["asset_id", "asset_type", "market_value", "loan_amount", "city"]
        for col in required_cols:
            if col not in merged.columns:
                merged[col] = np.nan
        merged = merged[required_cols]
        merged.drop_duplicates(inplace=True)
        merged["normalized_at"] = datetime.now(timezone.utc).isoformat()
        return merged

    if st.button("⚙️ Normalize & Generate Unified CSV", key="btn_normalize_data"):
        try:
            all_dfs = uploaded_dfs.copy()
            if not all_dfs:
                st.info("No uploads found — using synthetic fallback.")
                all_dfs.append(quick_synth(100))
            df_norm = normalize_dataframes(all_dfs)
            ss["asset_intake_df"] = df_norm
            os.makedirs("./.tmp_runs", exist_ok=True)
            out_path = f"./.tmp_runs/intake_table_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
            df_norm.to_csv(out_path, index=False)
            st.success(f"✅ Unified dataset generated with {len(df_norm)} rows.")
            st.dataframe(df_norm.head(20), use_container_width=True)
            st.download_button("💾 Download CSV", df_norm.to_csv(index=False), "intake_table.csv", "text/csv")
        except Exception as e:
            st.error(f"Normalization failed: {e}")

    st.divider()

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



# # ─────────────────────────────────────────
# # A — INTAKE & EVIDENCE (0..1)
# # ─────────────────────────────────────────
# with tabA:
#     import hashlib, io, json, os
#     from datetime import datetime, timezone

#     st.subheader("A. Intake & Evidence")
#     st.caption("Steps: **0) Intake & Identity**, **1) Evidence Extraction (OCR/EXIF/GPS)**")

#     # ---------- Local helpers ----------
#     def sha1_of_filelike(fobj) -> str:
#         """Compute SHA1 hash from file-like object without exhausting stream."""
#         pos = fobj.tell() if hasattr(fobj, "tell") else None
#         fobj.seek(0)
#         h = hashlib.sha1()
#         for chunk in iter(lambda: fobj.read(8192), b""):
#             if isinstance(chunk, str):
#                 chunk = chunk.encode("utf-8")
#             h.update(chunk)
#         if pos is not None:
#             fobj.seek(pos)
#         return h.hexdigest()

#     def extract_fake_exif_gps() -> dict:
#         return {
#             "gps": {"lat": 10.7758, "lon": 106.7009},
#             "ts": datetime.now(timezone.utc).isoformat()
#         }
#     def quick_synth(n: int = 150) -> pd.DataFrame:
#         """Generate synthetic intake dataset for demonstration/testing."""
#         import random
#         import numpy as np
#         from datetime import datetime, timedelta, timezone

#         t = datetime.now(timezone.utc)
#         asset_types = ["House", "Apartment", "Car", "Land", "Factory"]
#         cities = ["HCMC", "Hanoi", "Da Nang", "Can Tho", "Hai Phong"]
#         regions = {
#             "HCMC": "South",
#             "Hanoi": "North",
#             "Da Nang": "Central",
#             "Can Tho": "Mekong",
#             "Hai Phong": "North"
#         }

#         rows = []
#         for i in range(n):
#             city = cities[i % len(cities)]
#             region = regions[city]
#             base_value = 120_000 + (i % 17) * 3_500
#             noise = random.uniform(-0.1, 0.1) * base_value

#             # Derived + synthetic realism
#             market_value = base_value + noise
#             age_years = random.randint(0, 40)
#             condition_score = round(max(0.5, 1.0 - (age_years / 100.0) + random.uniform(-0.1, 0.1)), 2)
#             loan_amount = round(market_value * random.uniform(0.4, 0.8))
#             employment_years = random.randint(1, 30)
#             credit_history_years = random.randint(1, 25)
#             delinquencies = random.randint(0, 3)
#             current_loans = random.randint(0, 5)
#             registry_source = random.choice(["gov_registry", "private_registry", "unknown"])
#             evidence_count = random.randint(1, 5)
#             valuation_date = (t - timedelta(days=random.randint(0, 720))).strftime("%Y-%m-%d")

#             rows.append({
#                 "application_id": f"APP_{t.strftime('%H%M%S')}_{i:04d}",
#                 "asset_id": f"A{t.strftime('%M%S')}{i:04d}",
#                 "asset_type": random.choice(asset_types),
#                 "market_value": round(market_value, 2),
#                 "loan_amount": round(loan_amount, 2),
#                 "age_years": age_years,
#                 "condition_score": condition_score,
#                 "employment_years": employment_years,
#                 "credit_history_years": credit_history_years,
#                 "delinquencies": delinquencies,
#                 "current_loans": current_loans,
#                 "city": city,
#                 "region": region,
#                 "registry_source": registry_source,
#                 "evidence_count": evidence_count,
#                 "valuation_date": valuation_date,
#             })

#         df = pd.DataFrame(rows)
#         df["ltv_ratio"] = (df["loan_amount"] / df["market_value"]).round(2)
#         df["legal_penalty_flag"] = np.where(df["registry_source"] == "unknown", 1, 0)
#         return df


#     # def quick_synth(n: int = 150) -> pd.DataFrame:
#     #     t = datetime.now(timezone.utc)
#     #     rows = [{
#     #         "application_id": f"APP_{t.strftime('%H%M%S')}_{i:04d}",
#     #         "asset_id": f"A{t.strftime('%M%S')}{i:04d}",
#     #         "asset_type": ["House","Apartment","Car","Land","Factory"][i % 5],
#     #         "market_value": 120000 + (i % 17) * 3500,
#     #         "age_years": (i % 35),
#     #         "loan_amount": 80000 + (i % 23) * 2500,
#     #         "employment_years": (i % 25),
#     #         "credit_history_years": (i % 20),
#     #         "delinquencies": (i % 3),
#     #         "current_loans": (i % 5),
#     #         "city": ["HCMC","Hanoi","Da Nang","Can Tho","Hai Phong"][i % 5],
#     #     } for i in range(n)]
#     #     return pd.DataFrame(rows)

#     # def synth_why_table() -> pd.DataFrame:
#     #     return pd.DataFrame([
#     #         {"Metric": "PII present", "Why it matters": "Must be masked before feature engineering (privacy-by-design)."},
#     #         {"Metric": "Evidence linked (%)", "Why it matters": "Traceability between assets and documents/photos."},
#     #         {"Metric": "Rows (intake)", "Why it matters": "Sanity-check volume before downstream costs."},
#     #     ])

#     # ---------- A.0 — Intake & Identity ----------
#     st.markdown("### **0) Intake & Identity**")

#     # 📘 Quick user guide
#     with st.expander("📘 Quick User Guide", expanded=False):
#         st.markdown("""
#         **Goal:** Collect, normalize, and validate all asset data before appraisal.

#         **1️⃣ Upload Your Data**
#         - CSV from field agents, real-estate papers, or loan portfolios.
#         - Include key columns: `asset_id`, `asset_type`, `market_value`, `loan_amount`, `city`.

#         **2️⃣ Manual Add**
#         - Use to simulate new asset entries for quick testing.

#         **3️⃣ Attach Evidence**
#         - Add photos or documents (JPG/PDF). GPS/EXIF auto-parsed.

#         **4️⃣ Public Datasets**
#         - Search Kaggle / Hugging Face / Open ML for open valuation benchmarks.
#         """)

#     # ─────────────────────────────────────────
#     # 🔍 Search & Import Public Datasets
#     # ─────────────────────────────────────────
#     st.markdown("### 🔍 Search Public Datasets (Kaggle / Hugging Face / OpenML / Public Portals)")
#     st.caption("Search, preview, or import datasets from open sources — useful for model benchmarking or demo generation.")

#     src = st.selectbox(
#         "Select source",
#         ["Kaggle (API)", "Kaggle (Web)", "Hugging Face", "OpenML", "Public Domain Portals"],
#         key="asset_pubsrc"
#     )
#     query = st.text_input(
#         "Search keywords",
#         placeholder="e.g. house prices Vietnam, real estate valuation",
#         key="asset_pubquery"
#     )

#     if st.button("🔎 Search dataset", key="btn_asset_pubsearch"):
#         with st.spinner("Searching public datasets…"):
#             try:
#                 # Kaggle API mode
#                 if src == "Kaggle (API)":
#                     import subprocess, pandas as pd
#                     cmd = ["kaggle", "datasets", "list", "-s", query, "-v"]
#                     try:
#                         output = subprocess.check_output(cmd, text=True)
#                         lines = output.strip().splitlines()
#                         if len(lines) > 1:
#                             header = [h.strip() for h in lines[0].split(",")]
#                             data = [l.split(",") for l in lines[1:]]
#                             df_pub = pd.DataFrame(data, columns=header)
#                             st.dataframe(df_pub.head(25), use_container_width=True)
#                             st.success("✅ Kaggle API search complete. Use CLI or download link to import.")
#                         else:
#                             st.warning("No datasets found for your query.")
#                     except Exception as e:
#                         st.error(f"Kaggle API search failed: {e}")
#                         st.info("💡 Tip: Ensure your Kaggle API key (~/.kaggle/kaggle.json) is configured.")

#                 # Kaggle Web mode (no API needed)
#                 elif src == "Kaggle (Web)":
#                     st.markdown(
#                         f"[🌐 Open Kaggle Search ↗️](https://www.kaggle.com/datasets?search={query})"
#                     )

#                 # Hugging Face datasets
#                 elif src == "Hugging Face":
#                     from huggingface_hub import list_datasets
#                     results = list_datasets(search=query)
#                     df_pub = pd.DataFrame(
#                         [{"Dataset": r.id, "Tags": ", ".join(r.tags)} for r in results[:25]]
#                     )
#                     st.dataframe(df_pub, use_container_width=True)
#                     st.success("✅ Hugging Face datasets retrieved successfully.")

#                 # OpenML
#                 elif src == "OpenML":
#                     st.markdown(
#                         f"[📊 Open OpenML Search ↗️](https://www.openml.org/search?type=data&q={query})"
#                     )

#                 # Public domain portals
#                 elif src == "Public Domain Portals":
#                     st.markdown("""
#                     **Global Open Data Portals**
#                     - [🌎 data.gov (US)](https://www.data.gov/)
#                     - [🇪🇺 data.europa.eu (EU)](https://data.europa.eu/)
#                     - [🇸🇬 data.gov.sg (Singapore)](https://data.gov.sg/)
#                     - [🇻🇳 data.gov.vn (Vietnam)](https://data.gov.vn/)
#                     """)
#             except Exception as e:
#                 st.error(f"❌ Search failed: {e}")

#     # Optional layout continuation
#     left, right = st.columns([1.4, 1])

    
    
#     # # 🔍 Search Public Datasets
#     # st.markdown("#### 🔍 Search Public Datasets (Kaggle / Hugging Face / Open ML)")
#     # src = st.selectbox("Source", ["Kaggle", "Hugging Face Datasets", "Open ML"], key="asset_pubsrc")
#     # query = st.text_input("Search keywords", placeholder="e.g. house prices Vietnam, real estate valuation", key="asset_pubquery")

#     # if st.button("Search dataset", key="btn_asset_pubsearch"):
#     #     with st.spinner("Searching public datasets…"):
#     #         try:
#     #             if src == "Hugging Face Datasets":
#     #                 from huggingface_hub import list_datasets
#     #                 results = list_datasets(search=query)
#     #                 df_pub = pd.DataFrame([{"Name": r.id, "Tags": ", ".join(r.tags)} for r in results[:25]])
#     #                 st.dataframe(df_pub)
#     #             elif src == "Kaggle":
#     #                 st.info("Use `kaggle datasets list -s <keywords>` in terminal to explore.")
#     #             else:
#     #                 st.info(f"Open ML search → https://www.openml.org/search?type=data&q={query}")
#     #         except Exception as e:
#     #             st.error(f"Search failed: {e}")

#     # left, right = st.columns([1.4, 1])
    


#     # ---------- A.1 — Evidence Extraction ----------
#     st.markdown("### **1) Evidence Extraction (OCR/EXIF/GPS)**")
#     evid = st.file_uploader("Attach evidence (images or PDFs, optional)",
#                             type=["png", "jpg", "jpeg", "pdf"],
#                             accept_multiple_files=True,
#                             key="asset_evidence_files")

#     cA1_1, cA1_2 = st.columns(2)
#     with cA1_1:
#         if st.button("Extract & Index Evidence", key="btn_extract_evidence"):
#             idx_items = []
#             for i, f in enumerate(evid or []):
#                 try:
#                     bio = io.BytesIO(f.read())
#                     file_hash = sha1_of_filelike(bio)
#                     bio.seek(0)
#                     ext = (f.name or "").split(".")[-1].lower()
#                     doc_type = "image" if ext in ("png","jpg","jpeg") else "pdf"
#                     exif = extract_fake_exif_gps()
#                     idx_items.append({
#                         "evidence_id": f"EV-{i+1:04d}",
#                         "file_name": f.name,
#                         "doc_type": doc_type,
#                         "sha1": file_hash,
#                         "exif": exif,
#                     })
#                 except Exception as e:
#                     st.error(f"Error processing {f.name}: {e}")

#             evidence_index = {
#                 "generated_at": datetime.now(timezone.utc).isoformat(),
#                 "count": len(idx_items),
#                 "items": idx_items,
#             }
#             ss["asset_evidence_index"] = evidence_index

#             ev_path = os.path.join("./.tmp_runs", f"evidence_index.{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json")
#             with open(ev_path, "w", encoding="utf-8") as fp:
#                 json.dump(evidence_index, fp, ensure_ascii=False, indent=2)
#             st.success(f"Saved: `{ev_path}`  •  Items: {len(idx_items)}")
#             st.json(evidence_index)

#     with cA1_2:
#         if ss.get("asset_intake_df") is not None and ss.get("asset_evidence_index") is not None:
#             linked_pct = 1.0 if len(ss["asset_evidence_index"]["items"]) >= 1 else 0.0
#             st.metric("Evidence Linked (≥1)", f"{linked_pct:.0%}")
#         elif ss.get("asset_intake_df") is not None:
#             st.info("Upload evidence and click **Extract & Index Evidence**.")
#         else:
#             st.warning("Build the intake table first (A.0).")


        
#     # ─────────────────────────────────────────
#     # 📊 Synthetic Data Generation
#     # ─────────────────────────────────────────
#     st.markdown("### 📊 Generate Synthetic Data")
#     st.caption("Quickly create a sample intake dataset for testing or demos.")

#     num_rows = st.slider("Number of synthetic rows", min_value=10, max_value=500, value=150, step=10)
#     if st.button("⚙️ Generate Synthetic Intake Dataset", key="btn_generate_synth"):
#         try:
#             df_synth = quick_synth(num_rows)
#             ss["asset_intake_df"] = df_synth
#             st.success(f"✅ Generated synthetic dataset with {len(df_synth)} rows.")
#             st.dataframe(df_synth.head(20), use_container_width=True)
#             # Optional: auto-save artifact
#             out_path = f"./.tmp_runs/intake_table_synth_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
#             os.makedirs("./.tmp_runs", exist_ok=True)
#             df_synth.to_csv(out_path, index=False)
#             st.info(f"Saved to: `{out_path}`")
#         except Exception as e:
#             st.error(f"Synthetic data generation failed: {e}")


#         # ---------- Intake block ----------
#         with left:
#             up_csv = st.file_uploader("Upload Asset CSV", type=["csv"], key="asset_csv")
#             with st.expander("➕ Add manual asset row", expanded=False):
#                 m1, m2 = st.columns(2)
#                 asset_type = m1.selectbox("Asset Type", ["House","Apartment","Car","Land","Factory"])
#                 market_value = m2.number_input("Market Value ($)", 0, 10_000_000, 250_000, step=1_000)
#                 age_years = m1.number_input("Age (years)", 0, 100, 10)
#                 loan_amount = m2.number_input("Requested Loan ($)", 0, 10_000_000, 120_000, step=1_000)
#                 employment_years = m1.number_input("Employment Years", 0, 60, 5)
#                 credit_hist_years = m2.number_input("Credit History (years)", 0, 50, 6)
#                 delinq = m1.number_input("Delinquencies", 0, 50, 1)
#                 curr_loans = m2.number_input("Current Loans", 0, 50, 2)
#                 city = m1.text_input("City", "HCMC")
#                 add_row = st.button("Add manual asset row", key="btn_add_manual_row")

#             if st.button("Build Intake Table (fallback to synthetic if empty)", key="btn_build_intake"):
#                 rows = []
#                 # CSV
#                 if up_csv is not None:
#                     try:
#                         rows.append(pd.read_csv(up_csv))
#                     except Exception as e:
#                         st.error(f"CSV parse error: {e}")
#                 # Manual row
#                 if add_row:
#                     rows.append(pd.DataFrame([{
#                         "application_id": f"APP_{datetime.now(timezone.utc).strftime('%H%M%S')}",
#                         "asset_id": f"A{datetime.now(timezone.utc).strftime('%M%S')}",
#                         "asset_type": asset_type, "market_value": market_value, "age_years": age_years,
#                         "loan_amount": loan_amount, "employment_years": employment_years,
#                         "credit_history_years": credit_hist_years, "delinquencies": delinq,
#                         "current_loans": curr_loans, "city": city
#                     }]))
#                 # Synthetic fallback
#                 df = pd.concat(rows, ignore_index=True) if rows else quick_synth(150)
#                 if not rows:
#                     st.info("No inputs provided — generated synthetic intake dataset.")

#                 ss["asset_intake_df"] = df
#                 os.makedirs("./.tmp_runs", exist_ok=True)
#                 intake_path = os.path.join("./.tmp_runs", f"intake_table.{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv")
#                 df.to_csv(intake_path, index=False)
#                 st.success(f"Saved: `{intake_path}`  •  Rows: {len(df)}")
#                 st.dataframe(df.head(15), use_container_width=True)

#         with right:
#             st.markdown("#### Generated Metrics — What & Why")
#             st.dataframe(synth_why_table(), use_container_width=True)

#         st.markdown("---")

# # ─────────────────────────────────────────
# # A — INTAKE & EVIDENCE (0..1)
# # ─────────────────────────────────────────
# with tabA:
#     st.subheader("A. Intake & Evidence")
#     st.caption("Steps: **0) Intake & Identity**, **1) Evidence Extraction (OCR/EXIF/GPS)**")

#     # Local helpers (light stubs; replace with real OCR/EXIF later)
#     import hashlib, io
#     from datetime import datetime, timezone

#     def sha1_of_filelike(fobj) -> str:
#         pos = fobj.tell() if hasattr(fobj, "tell") else None
#         fobj.seek(0)
#         h = hashlib.sha1()
#         while True:
#             chunk = fobj.read(8192)
#             if not chunk:
#                 break
#             if isinstance(chunk, str):
#                 chunk = chunk.encode("utf-8")
#             h.update(chunk)
#         if pos is not None:
#             fobj.seek(pos)
#         return h.hexdigest()

#     def extract_fake_exif_gps() -> dict:
#         # Placeholder until your real EXIF/GPS pipeline is wired
#         return {"gps": {"lat": 10.7758, "lon": 106.7009}, "ts": datetime.now(timezone.utc).isoformat()}

#     def quick_synth(n: int = 150) -> pd.DataFrame:
#         t = datetime.now(timezone.utc)
#         rows = []
#         for i in range(n):
#             rows.append({
#                 "application_id": f"APP_{t.strftime('%H%M%S')}_{i:04d}",
#                 "asset_id": f"A{t.strftime('%M%S')}{i:04d}",
#                 "asset_type": ["House","Apartment","Car","Land","Factory"][i % 5],
#                 "market_value": 120000 + (i % 17) * 3500,
#                 "age_years": (i % 35),
#                 "loan_amount": 80000 + (i % 23) * 2500,
#                 "employment_years": (i % 25),
#                 "credit_history_years": (i % 20),
#                 "delinquencies": (i % 3),
#                 "current_loans": (i % 5),
#                 "city": ["HCMC","Hanoi","Da Nang","Can Tho","Hai Phong"][i % 5],
#             })
#         return pd.DataFrame(rows)

#     def synth_why_table() -> pd.DataFrame:
#         return pd.DataFrame([
#             {"Metric": "PII present", "Why it matters": "Must be masked before feature engineering (privacy-by-design)."},
#             {"Metric": "Evidence linked (%)", "Why it matters": "Traceability between assets and documents/photos."},
#             {"Metric": "Rows (intake)", "Why it matters": "Sanity-check volume before downstream costs."},
#         ])

#     # A.0 — Intake & Identity
#     st.markdown("### **0) Intake & Identity**")
#     left, right = st.columns([1.4, 1])

#     with left:
#         up_csv = st.file_uploader("Upload Asset CSV", type=["csv"], key="asset_csv")
#         with st.expander("➕ Add manual asset row", expanded=False):
#             m1, m2 = st.columns(2)
#             asset_type = m1.selectbox("Asset Type", ["House","Apartment","Car","Land","Factory"])
#             market_value = m2.number_input("Market Value ($)", 0, 10_000_000, 250_000, step=1_000)
#             age_years = m1.number_input("Age (years)", 0, 100, 10)
#             loan_amount = m2.number_input("Requested Loan ($)", 0, 10_000_000, 120_000, step=1_000)
#             employment_years = m1.number_input("Employment Years", 0, 60, 5)
#             credit_hist_years = m2.number_input("Credit History (years)", 0, 50, 6)
#             delinq = m1.number_input("Delinquencies", 0, 50, 1)
#             curr_loans = m2.number_input("Current Loans", 0, 50, 2)
#             city = m1.text_input("City (optional)", "HCMC")
#             add_row = st.button("Add manual asset row", key="btn_add_manual_row")

#         if st.button("Build Intake Table (fallback to synthetic if empty)", key="btn_build_intake"):
#             rows = []

#             # CSV path
#             if up_csv is not None:
#                 try:
#                     rows.append(pd.read_csv(up_csv))
#                 except Exception as e:
#                     st.error(f"CSV parse error: {e}")

#             # Manual row path
#             if add_row:
#                 rows.append(pd.DataFrame([{
#                     "application_id": f"APP_{datetime.now(timezone.utc).strftime('%H%M%S')}",
#                     "asset_id": f"A{datetime.now(timezone.utc).strftime('%M%S')}",
#                     "asset_type": asset_type, "market_value": market_value, "age_years": age_years,
#                     "loan_amount": loan_amount, "employment_years": employment_years,
#                     "credit_history_years": credit_hist_years, "delinquencies": delinq,
#                     "current_loans": curr_loans, "city": city
#                 }]))

#             # Synthetic fallback
#             if len(rows) == 0:
#                 df = quick_synth(150)
#                 st.info("No inputs provided — generated a synthetic intake dataset.")
#             else:
#                 df = pd.concat(rows, ignore_index=True)

#             ss["asset_intake_df"] = df
#             # Persist exact artifact: intake_table.csv
#             os.makedirs("./.tmp_runs", exist_ok=True)
#             intake_path = os.path.join("./.tmp_runs", f"intake_table.{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv")
#             ss["asset_intake_df"].to_csv(intake_path, index=False)
#             st.success(f"Saved: `{intake_path}`  •  Rows: {len(df)}")
#             st.dataframe(df.head(15), use_container_width=True)

#     with right:
#         st.markdown("#### Generated Metrics — What & Why")
#         st.dataframe(synth_why_table(), use_container_width=True)

#     st.markdown("---")

#     # A.1 — Evidence Extraction (OCR/EXIF/GPS, doc type detect, hash & index)
#     st.markdown("### **1) Evidence Extraction (OCR/EXIF/GPS)**")
#     evid = st.file_uploader(
#         "Attach evidence (images or PDFs, optional)",
#         type=["png", "jpg", "jpeg", "pdf"],
#         accept_multiple_files=True,
#         key="asset_evidence_files"
#     )

#     cA1_1, cA1_2 = st.columns([1, 1])
#     with cA1_1:
#         if st.button("Extract & Index Evidence", key="btn_extract_evidence"):
#             idx_items = []
#             for i, f in enumerate(evid or []):
#                 # Read into BytesIO for hashing (Streamlit gives UploadedFile)
#                 bio = io.BytesIO(f.read())
#                 file_hash = sha1_of_filelike(bio)
#                 # Reset for any downstream use
#                 bio.seek(0)

#                 # Naive doc-type guess by extension
#                 ext = (getattr(f, "name", "") or "").split(".")[-1].lower()
#                 doc_type = "image" if ext in ("png", "jpg", "jpeg") else "pdf"

#                 # Fake EXIF/GPS until wired
#                 exif = extract_fake_exif_gps()

#                 idx_items.append({
#                     "evidence_id": f"EV-{i+1:04d}",
#                     "file_name": getattr(f, "name", f"file-{i+1}"),
#                     "doc_type": doc_type,
#                     "sha1": file_hash,
#                     "exif": exif,
#                 })

#             evidence_index = {
#                 "generated_at": datetime.now(timezone.utc).isoformat(),
#                 "count": len(idx_items),
#                 "items": idx_items,
#             }
#             ss["asset_evidence_index"] = evidence_index

#             # Persist exact artifact: evidence_index.json
#             ev_path = os.path.join("./.tmp_runs", f"evidence_index.{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json")
#             with open(ev_path, "w", encoding="utf-8") as fp:
#                 json.dump(evidence_index, fp, ensure_ascii=False, indent=2)

#             st.success(f"Saved: `{ev_path}`  •  Items: {len(idx_items)}")
#             st.json(evidence_index)

#     with cA1_2:
#         if ss.get("asset_intake_df") is not None and ss.get("asset_evidence_index") is not None:
#             # Optional quick linkage KPI (count only)
#             linked_pct = 1.0 if len(ss["asset_evidence_index"]["items"]) >= 1 else 0.0
#             st.metric("Evidence Linked (≥1)", f"{linked_pct:.0%}")
#         elif ss.get("asset_intake_df") is not None:
#             st.info("Load evidence and click **Extract & Index Evidence** to compute linkage.")
#         else:
#             st.info("Build the intake table first (A.0).")


#     # ========== 1) DATA INPUT ==========
#     with tab1:
#         st.subheader("📥 Stage 1 — Provide Asset Data (CSV, evidence files, or manual)")
#         left, right = st.columns([1.4, 1])

#         with left:
#             up_csv = st.file_uploader("Upload Asset CSV", type=["csv"], key="asset_csv")
#             evid = st.file_uploader("Attach evidence (images or PDFs, optional)", type=["png","jpg","jpeg","pdf"],
#                                     accept_multiple_files=True, key="asset_evidence")
#             with st.expander("➕ Add manual asset row", expanded=False):
#                 m1, m2 = st.columns(2)
#                 asset_type = m1.selectbox("Asset Type", ["House","Apartment","Car","Land","Factory"])
#                 market_value = m2.number_input("Market Value ($)", 0, 10_000_000, 250_000, step=1_000)
#                 age_years = m1.number_input("Age (years)", 0, 100, 10)
#                 loan_amount = m2.number_input("Requested Loan ($)", 0, 10_000_000, 120_000, step=1_000)
#                 employment_years = m1.number_input("Employment Years", 0, 60, 5)
#                 credit_hist_years = m2.number_input("Credit History (years)", 0, 50, 6)
#                 delinq = m1.number_input("Delinquencies", 0, 50, 1)
#                 curr_loans = m2.number_input("Current Loans", 0, 50, 2)
#                 city = m1.text_input("City (optional)", "HCMC")
#                 add_row = st.button("Add manual asset row", key="btn_add_manual_row")

#             if st.button("Build Stage 1 dataset (or fallback to synthetic if empty)", key="btn_build_stage1"):
#                 rows = []
#                 if up_csv is not None:
#                     try:
#                         rows.append(pd.read_csv(up_csv))
#                     except Exception as e:
#                         st.error(f"CSV parse error: {e}")

#                 if evid:
#                     ss["asset_evidence"] = [f.name for f in evid]

#                 if add_row:
#                     rows.append(pd.DataFrame([{
#                         "application_id": f"APP_{datetime.datetime.utcnow().strftime('%H%M%S')}",
#                         "asset_id": f"A{datetime.datetime.utcnow().strftime('%M%S')}",
#                         "asset_type": asset_type, "market_value": market_value, "age_years": age_years,
#                         "loan_amount": loan_amount, "employment_years": employment_years,
#                         "credit_history_years": credit_hist_years, "delinquencies": delinq,
#                         "current_loans": curr_loans, "city": city
#                     }]))

#                 if len(rows) == 0:
#                     df = quick_synth(150)
#                     st.info("No inputs provided — generated synthetic dataset.")
#                     st.dataframe(synth_why_table(), use_container_width=True)
#                 else:
#                     df = pd.concat(rows, ignore_index=True)

#                 if "evidence_files" not in df.columns:
#                     df["evidence_files"] = [ss.get("asset_evidence", []) for _ in range(len(df))]

#                 ss["asset_raw_df"] = df
#                 st.success(f"Stage 1 dataset ready. Rows: {len(df)}")
#                 st.dataframe(df.head(15), use_container_width=True)

#         with right:
#             st.markdown("#### Generated Metrics — What & Why")
#             st.dataframe(synth_why_table(), use_container_width=True)

#     # ========== 2) ANONYMIZE ==========
#     with tab2:
#         st.subheader("🧹 Stage 2 — Anonymize / Sanitize PII")
#         if ss["asset_raw_df"] is None:
#             st.warning("Build Stage 1 dataset first (tab 1).")
#         else:
#             if st.button("Run anonymization now", key="btn_run_anon"):
#                 ss["asset_anon_df"] = anonymize_text_cols(ss["asset_raw_df"])
#                 st.success("Anonymization complete. Saved ANON dataset.")
#             if ss["asset_anon_df"] is not None:
#                 st.dataframe(ss["asset_anon_df"].head(15), use_container_width=True)
#                 st.download_button("⬇️ Download anonymized CSV",
#                                    data=ss["asset_anon_df"].to_csv(index=False).encode("utf-8"),
#                                    file_name="asset_anonymized.csv", mime="text/csv")

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

    def anonymize_text_cols(df: pd.DataFrame) -> pd.DataFrame:
        """Mask likely-PII columns (name/email/phone/id/address) while preserving join keys."""
        if df is None or df.empty:
            return df
        out = df.copy()
        join_keys = {"loan_id", "asset_id", "application_id"}
        pii_like = re.compile(r"(name|email|phone|addr|national|id|passport)", re.I)
        for col in out.columns:
            if col in join_keys:
                continue
            if out[col].dtype == "object" and pii_like.search(col):
                # Replace alphanumerics with 'x', keep separators
                out[col] = out[col].astype(str).str.replace(r"[A-Za-z0-9]", "x", regex=True)
        return out

    if ss.get("asset_intake_df") is None:
        st.warning("Load Intake (A.0) first.")
    else:
        c2a, c2b = st.columns([1, 1])
        with c2a:
            if st.button("Run anonymization now", key="btn_run_anon"):
                anon_df = anonymize_text_cols(ss["asset_intake_df"])
                ss["asset_anon_df"] = anon_df
                anon_path = os.path.join(RUNS_DIR, f"asset_anonymized.{_ts()}.csv")
                anon_df.to_csv(anon_path, index=False)
                st.success(f"Anonymization complete. Saved: `{anon_path}`")
        with c2b:
            if ss.get("asset_anon_df") is not None:
                st.download_button(
                    "⬇️ Download asset_anonymized.csv",
                    data=ss["asset_anon_df"].to_csv(index=False).encode("utf-8"),
                    file_name="asset_anonymized.csv",
                    mime="text/csv",
                )

        if ss.get("asset_anon_df") is not None:
            st.dataframe(ss["asset_anon_df"].head(20), use_container_width=True)

    st.markdown("---")

    # ----------------------------
    # B.3 — Feature Engineering & Comps
    # ----------------------------
    st.markdown("### **3) Feature Engineering & Comps**")

    def _geohash_stub(city: str | None) -> str:
        # Minimal placeholder; swap in real geohash later
        if not city: return "w21z9"
        city_l = str(city).strip().lower()
        return {
            "hcmc": "w21z9", "ho chi minh": "w21z9", "ho-chi-minh": "w21z9",
            "hanoi": "w27z0", "ha noi": "w27z0",
            "da nang": "w23ye", "danang": "w23ye",
            "can tho": "w21ng", "hai phong": "w2cg1",
        }.get(city_l, "w21z9")

    def feature_engineer(df: pd.DataFrame, evidence_index: dict | None) -> pd.DataFrame:
        out = df.copy()

        # Evidence linkage KPI (count per asset)
        if evidence_index and "items" in evidence_index:
            # We don't have per-asset mapping yet; expose total count as a feature stub
            out["evidence_count"] = len(evidence_index["items"])
        else:
            out["evidence_count"] = 0

        # Keep age_years if present; otherwise default
        if "age_years" not in out.columns:
            out["age_years"] = 8.0

        # size_log if 'size' present
        if "size" in out.columns:
            out["size_log"] = out["size"].apply(lambda x: math.log1p(x) if pd.notnull(x) else 0.0)
        else:
            out["size_log"] = 0.0

        # condition_score heuristic from delinquency/age/current_loans (0..1)
        delinq = out["delinquencies"] if "delinquencies" in out.columns else 0
        curr_loans = out["current_loans"] if "current_loans" in out.columns else 0
        age = out["age_years"]
        out["condition_score"] = 1.0 - (0.02*age) - (0.05*delinq) - (0.03*curr_loans)
        out["condition_score"] = out["condition_score"].clip(0.1, 0.98)

        # legal_penalty placeholder (real value will come from C.5 verification later)
        out["legal_penalty"] = 0.0

        # geohash from 'city'
        out["geohash"] = out.get("city", "").apply(_geohash_stub)

        # Keep join keys at front if present
        front_cols = [c for c in ["loan_id","application_id","asset_id"] if c in out.columns]
        other_cols = [c for c in out.columns if c not in front_cols]
        out = out[front_cols + other_cols]
        return out

    def fetch_and_clean_comps(df_feats: pd.DataFrame) -> dict:
        """Simple, deterministic comps list stub; replace with real feed."""
        comps = []
        base = float(df_feats.get("market_value", pd.Series([100000])).median())
        for i in range(5):
            comps.append({"comp_id": f"C-{i+1:03d}", "price": round(base * (0.95 + 0.02*i), 2)})
        return {"used": comps, "count": len(comps), "median_baseline": base}

    if ss.get("asset_anon_df") is None:
        st.info("Run Anonymization (B.2) first.")
    else:
        c3a, c3b = st.columns([1.2, 0.8])
        with c3a:
            if st.button("Build Features & Fetch Comps", key="btn_build_features"):
                feats = feature_engineer(ss["asset_anon_df"], ss.get("asset_evidence_index"))
                ss["asset_features_df"] = feats

                # Persist features.parquet
                features_path = os.path.join(RUNS_DIR, f"features.{_ts()}.parquet")
                feats.to_parquet(features_path, index=False)
                st.success(f"Saved features → `{features_path}`")

                comps = fetch_and_clean_comps(feats)
                ss["asset_comps_used"] = comps

                # Persist comps_used.json
                comps_path = os.path.join(RUNS_DIR, f"comps_used.{_ts()}.json")
                with open(comps_path, "w", encoding="utf-8") as fp:
                    json.dump(comps, fp, ensure_ascii=False, indent=2)
                st.success(f"Saved comps → `{comps_path}`")

        with c3b:
            if ss.get("asset_features_df") is not None:
                st.download_button(
                    "⬇️ Download features.parquet",
                    data=ss["asset_features_df"].to_parquet(index=False),
                    file_name="features.parquet",
                    mime="application/octet-stream",
                )

        if ss.get("asset_features_df") is not None:
            k1, k2, k3 = st.columns(3)
            with k1:
                st.metric("Rows (features)", len(ss["asset_features_df"]))
            with k2:
                st.metric("Avg condition_score", f"{ss['asset_features_df']['condition_score'].mean():.2f}")
            with k3:
                st.metric("Evidence count (stub)", int(ss["asset_features_df"].get("evidence_count", 0).mean() if "evidence_count" in ss["asset_features_df"].columns else 0))
            st.dataframe(ss["asset_features_df"].head(30), use_container_width=True)

        if ss.get("asset_comps_used") is not None:
            st.caption("Comps used (stub)")
            st.json(ss["asset_comps_used"])


    # # ========== 3) AI APPRAISAL & VALUATION ==========
    # with tab3:
    #     st.subheader("🤖 Stage 3 — AI Appraisal & Valuation")

    #     # Production model banner (asset agent)
    #     try:
    #         resp = requests.get(f"{API_URL}/v1/training/production_meta", timeout=5)
    #         if resp.status_code == 200:
    #             meta = resp.json()
    #             if meta.get("has_production"):
    #                 ver = (meta.get("meta") or {}).get("version", "1.x")
    #                 src = (meta.get("meta") or {}).get("source", "production")
    #                 st.success(f"🟢 Production model active — version: {ver} • source: {src}")
    #             else:
    #                 st.warning("⚠️ No production model promoted yet — using baseline.")
    #         else:
    #             st.info("ℹ️ Could not fetch production model meta.")
    #     except Exception:
    #         st.info("ℹ️ Production meta unavailable.")

        
        
    #     # ─────────────────────────────────────────────
    #     # 🧩 Model Selection (asset trained + production) — dual dir, dedupe, refresh
    #     # ─────────────────────────────────────────────
    #     from time import time as _now

    #     trained_dirs = [
    #         os.path.expanduser("~/credit-appraisal-agent-poc/agents/asset_appraisal/models/trained"),            # canonical
    #         os.path.expanduser("~/credit-appraisal-agent-poc/services/agents/asset_appraisal/models/trained"),   # legacy
    #     ]
    #     production_default_fp = os.path.expanduser(
    #         "~/credit-appraisal-agent-poc/agents/asset_appraisal/models/production/model.joblib"
    #     )

    #     # Try to fetch production meta (compatible with your training router)
    #     production_fp = None
    #     try:
    #         r = requests.get(
    #             f"{API_URL}/v1/training/production_meta",
    #             params={"agent_id": "asset_appraisal"},
    #             timeout=5
    #         )
    #         if r.ok:
    #             j = r.json() or {}
    #             if j.get("has_production"):
    #                 meta = j.get("meta") or {}
    #                 production_fp = (meta.get("model_path") or meta.get("promoted_to") or production_default_fp)
    #     except Exception:
    #         production_fp = None
    #     if not production_fp:
    #         production_fp = production_default_fp

    #     # Manual refresh (cache-bust the selectbox key)
    #     c_ref, _ = st.columns([1, 6])
    #     with c_ref:
    #         if st.button("↻ Refresh models", key="asset_models_refresh"):
    #             st.session_state.pop("asset_model_select", None)
    #             st.session_state["_asset_models_bump"] = _now()
    #             st.rerun()

    #     # Build list (label, path, ctime, created_str, is_production)
    #     models = []

    #     # 1) Production entry
    #     if os.path.exists(production_fp):
    #         try:
    #             p_ctime = os.path.getctime(production_fp)
    #             p_created = datetime.datetime.fromtimestamp(p_ctime).strftime("%b %d, %Y %H:%M")
    #         except Exception:
    #             p_ctime, p_created = 0.0, "production"
    #         models.append(("⭐ Production", production_fp, p_ctime, p_created, True))

    #     # 2) Trained entries from both dirs
    #     raw = []
    #     for d in trained_dirs:
    #         if os.path.isdir(d):
    #             for f in os.listdir(d):
    #                 if f.endswith(".joblib"):
    #                     fpath = os.path.join(d, f)
    #                     try:
    #                         ctime = os.path.getctime(fpath)
    #                         created = datetime.datetime.fromtimestamp(ctime).strftime("%b %d, %Y %H:%M")
    #                     except Exception:
    #                         ctime, created = 0.0, ""
    #                     raw.append((f, fpath, ctime, created, False))

    #     # 3) De-dupe by filename (keep newest) and skip if identical to production
    #     newest_by_name = {}
    #     for name, path, ctime, created, is_prod in raw:
    #         # skip literal same file as production
    #         try:
    #             if os.path.exists(production_fp) and os.path.samefile(path, production_fp):
    #                 continue
    #         except Exception:
    #             pass
    #         if (name not in newest_by_name) or (ctime > newest_by_name[name][2]):
    #             newest_by_name[name] = (name, path, ctime, created, is_prod)

    #     models.extend(newest_by_name.values())

    #     # Sort: production first, then newest trained
    #     models = sorted(models, key=lambda x: (0 if x[4] else 1, -x[2]))

    #     if models:
    #         display_names = [
    #             f"{label} — {created}" if created else f"{label}"
    #             for (label, _, _, created, _) in models
    #         ]

    #         # keep previous selection if possible
    #         default_idx = 0
    #         prev_selected = st.session_state.get("asset_selected_model")
    #         if prev_selected:
    #             for i, (_, path, _, _, _) in enumerate(models):
    #                 if path == prev_selected:
    #                     default_idx = i
    #                     break

    #         select_key = f"asset_model_select::{st.session_state.get('_asset_models_bump','')}"
    #         selected_display = st.selectbox(
    #             "📦 Select trained model to use",
    #             display_names,
    #             index=default_idx,
    #             key=select_key
    #         )
    #         sel_idx = display_names.index(selected_display)
    #         selected_model = models[sel_idx][1]
    #         is_prod = models[sel_idx][4]

    #         st.session_state["asset_selected_model"] = selected_model

    #         if is_prod:
    #             st.success(f"🟢 Using PRODUCTION model: {os.path.basename(selected_model)}")
    #         else:
    #             st.success(f"✅ Using model: {os.path.basename(selected_model)}")

    #         # Promote only when a non-production model is selected
    #         if (not is_prod) and st.button("🚀 Promote this model to PRODUCTION", key="asset_promote_model"):
    #             try:
    #                 # Backend promotes newest trained; if you prefer exact file, copy locally instead.
    #                 r = requests.post(f"{API_URL}/v1/agents/asset_appraisal/training/promote_last", timeout=60)
    #                 if r.ok:
    #                     st.success("✅ Model promoted to PRODUCTION.")
    #                     # cache-bust & refresh so ⭐ Production appears immediately
    #                     st.session_state["_asset_models_bump"] = _now()
    #                     st.rerun()
    #                 else:
    #                     try:
    #                         st.error(f"❌ Promotion failed: {r.status_code} {r.reason}")
    #                         st.code(r.json())
    #                     except Exception:
    #                         st.code(r.text[:2000])
    #             except Exception as e:
    #                 st.error(f"❌ Promotion error: {e}")
    #     else:
    #         st.warning("⚠️ No trained models found — train one in Step 5 first.")


    #     # 🧠 Local LLM & Hardware Profile (runtime hints)
    #     LLM_MODELS = [
    #         ("Phi-3 Mini (3.8B) — CPU OK", "phi3:3.8b", "CPU 8GB RAM (fast)"),
    #         ("Mistral 7B Instruct — CPU slow / GPU OK", "mistral:7b-instruct", "CPU 16GB (slow) or GPU ≥8GB"),
    #         ("Gemma-2 7B — CPU slow / GPU OK", "gemma2:7b", "CPU 16GB (slow) or GPU ≥8GB"),
    #         ("LLaMA-3 8B — GPU recommended", "llama3:8b-instruct", "GPU ≥12GB (CPU very slow)"),
    #         ("Qwen2 7B — GPU recommended", "qwen2:7b-instruct", "GPU ≥12GB (CPU very slow)"),
    #         ("Mixtral 8x7B — GPU only (big)", "mixtral:8x7b-instruct", "GPU 24–48GB"),
    #     ]
    #     LLM_LABELS = [l for (l, _, _) in LLM_MODELS]
    #     LLM_VALUE_BY_LABEL = {l: v for (l, v, _) in LLM_MODELS}
    #     LLM_HINT_BY_LABEL  = {l: h for (l, _, h) in LLM_MODELS}

    #     OPENSTACK_FLAVORS = {
    #         "m4.medium":  "4 vCPU / 8 GB RAM — CPU-only small",
    #         "m8.large":   "8 vCPU / 16 GB RAM — CPU-only medium",
    #         "g1.a10.1":   "8 vCPU / 32 GB RAM + 1×A10 24GB",
    #         "g1.l40.1":   "16 vCPU / 64 GB RAM + 1×L40 48GB",
    #         "g2.a100.1":  "24 vCPU / 128 GB RAM + 1×A100 80GB",
    #     }

    #     with st.expander("🧠 Local LLM & Hardware Profile", expanded=True):
    #         c1, c2 = st.columns([1.2, 1])
    #         with c1:
    #             model_label = st.selectbox("Local LLM (used for narratives/explanations)", LLM_LABELS, index=1, key="asset_llm_label")
    #             llm_value = LLM_VALUE_BY_LABEL[model_label]
    #             use_llm = st.checkbox("Use LLM narrative (include explanations)", value=False, key="asset_use_llm")
    #             st.caption(f"Hint: {LLM_HINT_BY_LABEL[model_label]}")
    #         with c2:
    #             flavor = st.selectbox("OpenStack flavor / host profile", list(OPENSTACK_FLAVORS.keys()), index=0, key="asset_flavor")
    #             st.caption(OPENSTACK_FLAVORS[flavor])
    #         st.caption("These are passed to the API as hints; your API can choose Ollama/Flowise backends accordingly.")

    #     # Choose data source for run
    #     src = st.selectbox("Data source for AI run", [
    #         "Use ANON (from Stage 2)",
    #         "Use RAW → auto-sanitize",
    #         "Use synthetic (fallback)",
    #     ])

    #     if src == "Use ANON (from Stage 2)":
    #         df2 = ss.get("asset_anon_df")
    #     elif src == "Use RAW → auto-sanitize":
    #         df2 = anonymize_text_cols(ss.get("asset_raw_df")) if ss.get("asset_raw_df") is not None else None
    #     else:
    #         df2 = quick_synth(150)

    #     if df2 is None:
    #         st.warning("No dataset available. Build Stage 1 & run anonymization first.")
    #         st.stop()

    #     st.dataframe(df2.head(10), use_container_width=True)

    #     # 🔧 Policy & Haircut Controls (asset-centric)
    #     st.markdown("### ⚙️ Policy & Haircut Controls")
    #     p1, p2, p3 = st.columns([1, 1, 1])

    #     with p1:
    #         min_confidence = st.slider("Min confidence to auto-approve (%)", 0, 100, 70, 1)
    #         base_haircut   = st.slider("Base haircut (all assets, %)", 0, 50, 5, 1)
    #     with p2:
    #         legal_floor    = st.slider("Legal quality floor (min legal_penalty)", 0.90, 1.00, 0.97, 0.01)
    #         condition_floor= st.slider("Condition floor (min condition_score)", 0.60, 1.00, 0.75, 0.01)
    #     with p3:
    #         ltv_cap_mode   = st.selectbox("LTV cap mode", ["Fixed cap", "Per asset_type"], index=0)
    #         fixed_ltv_cap  = st.slider("Fixed LTV cap (×)", 0.10, 2.00, 0.80, 0.05)

    #     # Per-type caps if requested
    #     type_caps = {}
    #     if ltv_cap_mode == "Per asset_type":
    #         types = sorted(list(map(str, (df2.get("asset_type") or pd.Series(["Asset"])).dropna().unique())))[0:8]
    #         st.caption("Tune LTV caps per asset_type")
    #         grid_cols = st.columns(4 if len(types) > 3 else max(1, len(types)))
    #         for idx, t in enumerate(types):
    #             with grid_cols[idx % len(grid_cols)]:
    #                 type_caps[t] = st.number_input(f"{t} LTV cap ×", 0.10, 2.00, 0.80, 0.05, key=f"cap_{t}")

    #     # Probe API (health & agents)
    #     with st.expander("🔎 Probe API (health & agents)", expanded=False):
    #         if st.button("Run probe now", key="btn_probe_api"):
    #             diag = probe_api()
    #             st.json(diag)

    #     # Run model button (runtime flavor included)
    #     if st.button("🚀 Run AI Appraisal now", key="btn_run_ai"):
    #         csv_bytes = df2.to_csv(index=False).encode("utf-8")

    #         form_fields = {
    #             "use_llm": str(use_llm).lower(),
    #             "llm": llm_value,
    #             "flavor": flavor,
    #             "selected_model": ss.get("asset_selected_model", ""),
    #             "agent_name": "asset_appraisal",
    #             # Policy hints (backend may ignore; UI still enforces locally)
    #             "min_confidence": str(min_confidence),
    #             "legal_floor": str(legal_floor),
    #             "condition_floor": str(condition_floor),
    #             "ltv_cap_mode": ltv_cap_mode,
    #             "fixed_ltv_cap": str(fixed_ltv_cap),
    #             "type_caps": json.dumps(type_caps),
    #             "base_haircut": str(base_haircut),
    #         }

    #         with st.spinner("Calling asset agent…"):
    #             ok, result = try_run_asset_agent(csv_bytes, form_fields=form_fields, timeout_sec=180)

    #         if not ok:
    #             st.error("❌ Model API error.")
    #             st.info("Tip: open '🔎 Probe API' above to see health and discovered agent ids.")
    #             st.code(str(result)[:8000])
    #             st.stop()

    #         df_app = result.copy()

    #         # Ensure core columns
    #         if "ai_adjusted" not in df_app.columns and "market_value" in df_app.columns:
    #             df_app["ai_adjusted"] = df_app["market_value"]
    #         if "confidence" not in df_app.columns:
    #             df_app["confidence"] = 80.0
    #         if "legal_penalty" not in df_app.columns:
    #             df_app["legal_penalty"] = 1.0
    #         if "condition_score" not in df_app.columns:
    #             df_app["condition_score"] = 0.9
    #         if "loan_amount" not in df_app.columns:
    #             df_app["loan_amount"] = 0.0

    #         # Compute realizable value after haircuts
    #         df_app["realizable_value"] = (
    #             pd.to_numeric(df_app["ai_adjusted"], errors="coerce") *
    #             pd.to_numeric(df_app["legal_penalty"], errors="coerce") *
    #             pd.to_numeric(df_app["condition_score"], errors="coerce") *
    #             (1.0 - float(base_haircut) / 100.0)
    #         )

    #         # LTV (AI) and valuation gap %
    #         mv = pd.to_numeric(df_app.get("market_value", np.nan), errors="coerce")
    #         ai = pd.to_numeric(df_app.get("ai_adjusted", np.nan), errors="coerce")
    #         la = pd.to_numeric(df_app.get("loan_amount", np.nan), errors="coerce")

    #         df_app["valuation_gap_pct"] = (ai - mv) / mv.replace(0, np.nan) * 100.0
    #         df_app["ltv_ai"] = la / ai.replace(0, np.nan)

    #         # Determine LTV caps row-by-row
    #         if ltv_cap_mode == "Fixed cap":
    #             df_app["ltv_cap"] = float(fixed_ltv_cap)
    #         else:
    #             atypes = df_app.get("asset_type").astype(str) if "asset_type" in df_app.columns else pd.Series(["Asset"] * len(df_app))
    #             df_app["ltv_cap"] = atypes.map(lambda t: float(type_caps.get(t, fixed_ltv_cap)))

    #         # Policy breaches & decision
    #         breaches = []
    #         conf = pd.to_numeric(df_app["confidence"], errors="coerce")
    #         legal = pd.to_numeric(df_app["legal_penalty"], errors="coerce")
    #         cond  = pd.to_numeric(df_app["condition_score"], errors="coerce")
    #         ltv   = pd.to_numeric(df_app["ltv_ai"], errors="coerce")
    #         lcap  = pd.to_numeric(df_app["ltv_cap"], errors="coerce")

    #         for i in range(len(df_app)):
    #             b = []
    #             if pd.notna(conf.iat[i]) and conf.iat[i] < min_confidence:
    #                 b.append(f"confidence<{min_confidence}%")
    #             if pd.notna(legal.iat[i]) and legal.iat[i] < legal_floor:
    #                 b.append(f"legal<{legal_floor:.2f}")
    #             if pd.notna(cond.iat[i]) and cond.iat[i] < condition_floor:
    #                 b.append(f"condition<{condition_floor:.2f}")
    #             if pd.notna(ltv.iat[i]) and pd.notna(lcap.iat[i]) and ltv.iat[i] > lcap.iat[i]:
    #                 b.append("ltv>cap")
    #             breaches.append(", ".join(b))

    #         df_app["policy_breaches"] = breaches
    #         df_app["decision"] = np.where(df_app["policy_breaches"].str.len().gt(0), "review", "approved")

    #         # First Table (loan-centric validation)
    #         cols_first = [c for c in [
    #             "application_id","asset_id","asset_type","city",
    #             "market_value","ai_adjusted","realizable_value",
    #             "loan_amount","ltv_ai","ltv_cap",
    #             "confidence","legal_penalty","condition_score",
    #             "valuation_gap_pct","policy_breaches","decision"
    #         ] if c in df_app.columns]
    #         first_table = df_app[cols_first].copy()

    #         ss["asset_ai_df"] = df_app
    #         ss["asset_first_table"] = first_table

    #         st.success("✅ AI appraisal completed.")
    #         st.markdown("### 🧾 Loan & Asset Validation — First Table")
    #         st.dataframe(first_table, use_container_width=True)
    #         st.download_button(
    #             "⬇️ Export First Table (CSV)",
    #             data=first_table.to_csv(index=False).encode("utf-8"),
    #             file_name="asset_appraisal_first_table.csv",
    #             mime="text/csv"
    #         )


    #     # 📊 Portfolio Insights Dashboard
    #     st.divider()
    #     st.subheader("📊 Portfolio Insights Dashboard")

    #     ft = ss.get("asset_first_table")
    #     if ft is None or (hasattr(ft, "empty") and ft.empty):
    #         st.info("Run appraisal to populate the dashboard.")
    #     else:
    #         # Safe numerics & copy
    #         ft = ft.copy()
    #         def _num(s): return pd.to_numeric(s, errors="coerce")
    #         for c in ["ai_adjusted","realizable_value","loan_amount",
    #                   "valuation_gap_pct","ltv_ai","ltv_cap","confidence"]:
    #             if c in ft.columns:
    #                 ft[c] = _num(ft[c])

    #         # KPI strip
    #         k1, k2, k3, k4 = st.columns(4)
    #         if {"ltv_ai","ltv_cap"}.issubset(ft.columns):
    #             breach = (ft["ltv_ai"] > ft["ltv_cap"])
    #             breach_rate = float(breach.mean() * 100)
    #         else:
    #             breach_rate = 0.0
    #         total_ai        = float(_num(ft.get("ai_adjusted", pd.Series(dtype=float))).sum())
    #         total_realiz    = float(_num(ft.get("realizable_value", pd.Series(dtype=float))).sum())
    #         avg_gap         = float(_num(ft.get("valuation_gap_pct", pd.Series(dtype=float))).mean())
    #         avg_conf        = float(_num(ft.get("confidence", pd.Series(dtype=float))).mean())
    #         k1.metric("Breach Rate (LTV>cap)", f"{breach_rate:.1f}%")
    #         k2.metric("AI Gross Value",       f"${total_ai:,.0f}")
    #         k3.metric("Realizable Value",     f"${total_realiz:,.0f}")
    #         k4.metric("Avg Valuation Gap",    f"{avg_gap:+.2f}%")

    #         # Row 1: Decision mix & Gap histogram
    #         r1c1, r1c2 = st.columns(2)
    #         with r1c1:
    #             try:
    #                 names_series = (ft["decision"].astype(str).str.title()
    #                                 if "decision" in ft.columns
    #                                 else np.where(ft.get("policy_breaches","").astype(str).str.len().gt(0),
    #                                               "Has Breach","No Breach"))
    #                 fig_mix = px.pie(ft, names=names_series, title="Decision / Breach Mix")
    #                 fig_mix.update_layout(template="plotly_dark", height=320)
    #                 st.plotly_chart(fig_mix, use_container_width=True)
    #             except Exception:
    #                 pass
    #         with r1c2:
    #             if "valuation_gap_pct" in ft.columns:
    #                 try:
    #                     fig_gap = px.histogram(ft, x="valuation_gap_pct", nbins=40, title="Valuation Gap % Distribution")
    #                     fig_gap.update_layout(template="plotly_dark", height=320)
    #                     st.plotly_chart(fig_gap, use_container_width=True)
    #                 except Exception:
    #                     pass

    #         # Row 2: LTV vs Cap & City concentration
    #         r2c1, r2c2 = st.columns(2)
    #         with r2c1:
    #             if {"ltv_ai","ltv_cap"}.issubset(ft.columns):
    #                 try:
    #                     fig_sc = px.scatter(
    #                         ft, x="ltv_cap", y="ltv_ai",
    #                         hover_data=[c for c in ["application_id","asset_id","asset_type","city"] if c in ft.columns],
    #                         title="LTV (AI) vs LTV Cap"
    #                     )
    #                     max_cap = float((ft["ltv_cap"].max() or 1.2))
    #                     fig_sc.add_shape(type="line", x0=0, y0=0, x1=max_cap, y1=max_cap, line=dict(dash="dash"))
    #                     fig_sc.update_layout(template="plotly_dark", height=360,
    #                                          xaxis_title="LTV Cap", yaxis_title="LTV (AI)")
    #                     st.plotly_chart(fig_sc, use_container_width=True)
    #                 except Exception:
    #                     pass
    #         with r2c2:
    #             value_col = "realizable_value" if "realizable_value" in ft.columns else ("ai_adjusted" if "ai_adjusted" in ft.columns else None)
    #             if value_col and "city" in ft.columns:
    #                 try:
    #                     top_geo = (ft.groupby("city")[value_col].sum()
    #                                .sort_values(ascending=False).head(5).reset_index())
    #                     fig_geo = px.pie(top_geo, values=value_col, names="city", title="Top-5 City Concentration")
    #                     fig_geo.update_layout(template="plotly_dark", height=360)
    #                     st.plotly_chart(fig_geo, use_container_width=True)
    #                 except Exception:
    #                     pass

    #         # Row 3: Condition × Legal heatmap
    #         if {"condition_score","legal_penalty"}.issubset(ft.columns):
    #             try:
    #                 cond_bins  = pd.cut(ft["condition_score"], bins=[0,0.70,0.85,1.00], labels=["<0.70","0.70–0.85",">0.85"])
    #                 legal_bins = pd.cut(ft["legal_penalty"],  bins=[0,0.97,0.99,1.00], labels=["<0.97","0.97–0.99",">=0.99"])
    #                 heat = (ft.assign(cond=cond_bins, legal=legal_bins)
    #                         .groupby(["cond","legal"]).size().reset_index(name="count"))
    #                 fig_hm = px.density_heatmap(heat, x="legal", y="cond", z="count", title="Condition vs Legal — Density")
    #                 fig_hm.update_layout(template="plotly_dark", height=360)
    #                 st.plotly_chart(fig_hm, use_container_width=True)
    #             except Exception:
    #                 pass


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
    # 📦 MODEL SELECTION (Trained + Production)
    # ─────────────────────────────────────────────
    from time import time as _now

    trained_dirs = [
        os.path.expanduser("~/credit-appraisal-agent-poc/agents/asset_appraisal/models/trained"),
        os.path.expanduser("~/credit-appraisal-agent-poc/services/agents/asset_appraisal/models/trained"),
    ]
    production_default_fp = os.path.expanduser(
        "~/credit-appraisal-agent-poc/agents/asset_appraisal/models/production/model.joblib"
    )

    production_fp = None
    try:
        r = requests.get(f"{API_URL}/v1/training/production_meta",
                         params={"agent_id": "asset_appraisal"}, timeout=5)
        if r.ok:
            j = r.json() or {}
            if j.get("has_production"):
                meta = j.get("meta") or {}
                production_fp = meta.get("model_path") or meta.get("promoted_to") or production_default_fp
    except Exception:
        production_fp = None
    if not production_fp:
        production_fp = production_default_fp

    c_ref, _ = st.columns([1, 6])
    with c_ref:
        if st.button("↻ Refresh models", key="asset_models_refresh"):
            st.session_state.pop("asset_model_select", None)
            st.session_state["_asset_models_bump"] = _now()
            st.rerun()

    models = []
    if os.path.exists(production_fp):
        try:
            p_ctime = os.path.getctime(production_fp)
            p_created = datetime.fromtimestamp(p_ctime).strftime("%b %d, %Y %H:%M")
        except Exception:
            p_ctime, p_created = 0.0, "production"
        models.append(("⭐ Production", production_fp, p_ctime, p_created, True))

    raw = []
    for d in trained_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".joblib"):
                    fpath = os.path.join(d, f)
                    try:
                        ctime = os.path.getctime(fpath)
                        created = datetime.fromtimestamp(ctime).strftime("%b %d, %Y %H:%M")
                    except Exception:
                        ctime, created = 0.0, ""
                    raw.append((f, fpath, ctime, created, False))

    newest_by_name = {}
    for name, path, ctime, created, is_prod in raw:
        try:
            if os.path.exists(production_fp) and os.path.samefile(path, production_fp):
                continue
        except Exception:
            pass
        if (name not in newest_by_name) or (ctime > newest_by_name[name][2]):
            newest_by_name[name] = (name, path, ctime, created, is_prod)
    models.extend(newest_by_name.values())
    models = sorted(models, key=lambda x: (0 if x[4] else 1, -x[2]))

    if models:
        display_names = [f"{label} — {created}" if created else label for (label, _, _, created, _) in models]
        default_idx = 0
        prev_selected = st.session_state.get("asset_selected_model")
        if prev_selected:
            for i, (_, path, _, _, _) in enumerate(models):
                if path == prev_selected: default_idx = i; break
        select_key = f"asset_model_select::{st.session_state.get('_asset_models_bump','')}"
        selected_display = st.selectbox("📦 Select trained model", display_names,
                                        index=default_idx, key=select_key)
        sel_idx = display_names.index(selected_display)
        selected_model = models[sel_idx][1]
        is_prod = models[sel_idx][4]
        st.session_state["asset_selected_model"] = selected_model

        st.success(f"{'🟢' if is_prod else '✅'} Using model: {os.path.basename(selected_model)}")
        if (not is_prod) and st.button("🚀 Promote to PRODUCTION", key="asset_promote_model"):
            try:
                r = requests.post(f"{API_URL}/v1/agents/asset_appraisal/training/promote_last", timeout=60)
                if r.ok:
                    st.success("✅ Model promoted to PRODUCTION.")
                    st.session_state["_asset_models_bump"] = _now(); st.rerun()
                else:
                    st.error(f"❌ Promotion failed: {r.status_code} {r.reason}")
                    st.code(r.text[:1500])
            except Exception as e:
                st.error(f"❌ Promotion error: {e}")
    else:
        st.warning("⚠️ No trained models found — train one in Stage 5.")

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
        ("Phi-3 Mini (3.8B)", "phi3:3.8b", "CPU 8 GB RAM (fast)"),
        ("Mistral 7B Instruct", "mistral:7b-instruct", "GPU ≥ 8 GB (fast)"),
        ("Gemma-2 9B", "gemma2:9b", "GPU ≥ 12 GB (high accuracy)"),
        ("LLaMA-3 8B", "llama3:8b-instruct", "GPU ≥ 12 GB (context heavy)"),
        ("Qwen-2 7B", "qwen2:7b-instruct", "GPU ≥ 12 GB (multilingual)"),
        ("Mixtral 8×7B", "mixtral:8x7b-instruct", "GPU 24-48 GB (batch)"),
    ]
    LLM_LABELS = [l for (l, _, _) in LLM_MODELS]
    LLM_VALUE_BY_LABEL = {l: v for (l, v, _) in LLM_MODELS}
    LLM_HINT_BY_LABEL  = {l: h for (l, _, h) in LLM_MODELS}

    OPENSTACK_FLAVORS = {
        "m4.medium": "4 vCPU / 8 GB RAM (CPU-only small)",
        "m8.large": "8 vCPU / 16 GB RAM (CPU-only medium)",
        "g1.a10.1": "8 vCPU / 32 GB RAM + 1×A10 24 GB",
        "g1.l40.1": "16 vCPU / 64 GB RAM + 1×L40 48 GB",
        "g2.a100.1": "24 vCPU / 128 GB RAM + 1×A100 80 GB",
    }

    with st.expander("🧠 Choose Model & Hardware Profile", expanded=True):
        c1, c2 = st.columns([1.2, 1])
        with c1:
            model_label = st.selectbox(
                "Select Local or HF LLM (for narratives / explanations)",
                LLM_LABELS, index=1, key="asset_llm_label")
            llm_value = LLM_VALUE_BY_LABEL[model_label]
            use_llm = st.checkbox("Use LLM narrative (explanations)",
                                  value=False, key="asset_use_llm")
            st.caption(f"Hint: {LLM_HINT_BY_LABEL[model_label]}")
        with c2:
            flavor = st.selectbox("OpenStack flavor / host profile",
                                  list(OPENSTACK_FLAVORS.keys()), index=0,
                                  key="asset_flavor")
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

    src = st.selectbox("Data source for AI run", [
        "Use FEATURES (Stage 2/3)",
        "Use ANON (Stage 2)",
        "Use RAW → auto-sanitize",
        "Use synthetic (fallback)",
    ])
    if src == "Use FEATURES (Stage 2/3)":
        df2 = ss.get("asset_features_df") or ss.get("asset_anon_df")
    elif src == "Use ANON (Stage 2)":
        df2 = ss.get("asset_anon_df")
    elif src == "Use RAW → auto-sanitize":
        df2 = anonymize_text_cols(ss.get("asset_intake_df")) if ss.get("asset_intake_df") is not None else None
    else:
        df2 = quick_synth(150)
    if df2 is None:
        st.warning("No dataset available — build Stage B first."); st.stop()
    st.dataframe(df2.head(10), use_container_width=True)

    # ─────────────────────────────────────────────
    # APPRAISAL LOGIC + DASHBOARD + VERIFICATION
    # ─────────────────────────────────────────────
    # ⬇ keep your existing “Run AI Appraisal now” button,
    # delta analysis, verification checks, and executive dashboard
    # from your previous version — they plug in after this section.


# # ========== 3) AI APPRAISAL & VALUATION ==========
# with tabC:
#     st.subheader("🤖 Stage 3 — AI Appraisal & Valuation")

#     import os, json, numpy as np
#     from datetime import datetime, timezone

#     RUNS_DIR = "./.tmp_runs"
#     os.makedirs(RUNS_DIR, exist_ok=True)

#     def _ts():
#         return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

#     # Production model banner (asset agent)
#     try:
#         resp = requests.get(f"{API_URL}/v1/training/production_meta", timeout=5)
#         if resp.status_code == 200:
#             meta = resp.json()
#             if meta.get("has_production"):
#                 ver = (meta.get("meta") or {}).get("version", "1.x")
#                 src = (meta.get("meta") or {}).get("source", "production")
#                 st.success(f"🟢 Production model active — version: {ver} • source: {src}")
#             else:
#                 st.warning("⚠️ No production model promoted yet — using baseline.")
#         else:
#             st.info("ℹ️ Could not fetch production model meta.")
#     except Exception:
#         st.info("ℹ️ Production meta unavailable.")

#     # ─────────────────────────────────────────────
#     # 🧩 Model Selection (asset trained + production) — dual dir, dedupe, refresh
#     # (KEPT AS-IS per your instruction)
#     # ─────────────────────────────────────────────
#     from time import time as _now

#     trained_dirs = [
#         os.path.expanduser("~/credit-appraisal-agent-poc/agents/asset_appraisal/models/trained"),            # canonical
#         os.path.expanduser("~/credit-appraisal-agent-poc/services/agents/asset_appraisal/models/trained"),   # legacy
#     ]
#     production_default_fp = os.path.expanduser(
#         "~/credit-appraisal-agent-poc/agents/asset_appraisal/models/production/model.joblib"
#     )

#     # Try to fetch production meta (compatible with your training router)
#     production_fp = None
#     try:
#         r = requests.get(
#             f"{API_URL}/v1/training/production_meta",
#             params={"agent_id": "asset_appraisal"},
#             timeout=5
#         )
#         if r.ok:
#             j = r.json() or {}
#             if j.get("has_production"):
#                 meta = j.get("meta") or {}
#                 production_fp = (meta.get("model_path") or meta.get("promoted_to") or production_default_fp)
#     except Exception:
#         production_fp = None
#     if not production_fp:
#         production_fp = production_default_fp

#     # Manual refresh (cache-bust the selectbox key)
#     c_ref, _ = st.columns([1, 6])
#     with c_ref:
#         if st.button("↻ Refresh models", key="asset_models_refresh"):
#             st.session_state.pop("asset_model_select", None)
#             st.session_state["_asset_models_bump"] = _now()
#             st.rerun()

#     # Build list (label, path, ctime, created_str, is_production)
#     models = []

#     # 1) Production entry
#     if os.path.exists(production_fp):
#         try:
#             p_ctime = os.path.getctime(production_fp)
#             p_created = datetime.fromtimestamp(p_ctime).strftime("%b %d, %Y %H:%M")
#         except Exception:
#             p_ctime, p_created = 0.0, "production"
#         models.append(("⭐ Production", production_fp, p_ctime, p_created, True))

#     # 2) Trained entries from both dirs
#     raw = []
#     for d in trained_dirs:
#         if os.path.isdir(d):
#             for f in os.listdir(d):
#                 if f.endswith(".joblib"):
#                     fpath = os.path.join(d, f)
#                     try:
#                         ctime = os.path.getctime(fpath)
#                         created = datetime.fromtimestamp(ctime).strftime("%b %d, %Y %H:%M")
#                     except Exception:
#                         ctime, created = 0.0, ""
#                     raw.append((f, fpath, ctime, created, False))

#     # 3) De-dupe by filename (keep newest) and skip if identical to production
#     newest_by_name = {}
#     for name, path, ctime, created, is_prod in raw:
#         try:
#             if os.path.exists(production_fp) and os.path.samefile(path, production_fp):
#                 continue
#         except Exception:
#             pass
#         if (name not in newest_by_name) or (ctime > newest_by_name[name][2]):
#             newest_by_name[name] = (name, path, ctime, created, is_prod)

#     models.extend(newest_by_name.values())

#     # Sort: production first, then newest trained
#     models = sorted(models, key=lambda x: (0 if x[4] else 1, -x[2]))

#     if models:
#         display_names = [
#             f"{label} — {created}" if created else f"{label}"
#             for (label, _, _, created, _) in models
#         ]

#         # keep previous selection if possible
#         default_idx = 0
#         prev_selected = st.session_state.get("asset_selected_model")
#         if prev_selected:
#             for i, (_, path, _, _, _) in enumerate(models):
#                 if path == prev_selected:
#                     default_idx = i
#                     break

#         select_key = f"asset_model_select::{st.session_state.get('_asset_models_bump','')}"
#         selected_display = st.selectbox(
#             "📦 Select trained model to use",
#             display_names,
#             index=default_idx,
#             key=select_key
#         )
#         sel_idx = display_names.index(selected_display)
#         selected_model = models[sel_idx][1]
#         is_prod = models[sel_idx][4]

#         st.session_state["asset_selected_model"] = selected_model

#         if is_prod:
#             st.success(f"🟢 Using PRODUCTION model: {os.path.basename(selected_model)}")
#         else:
#             st.success(f"✅ Using model: {os.path.basename(selected_model)}")

#         # Promote only when a non-production model is selected
#         if (not is_prod) and st.button("🚀 Promote this model to PRODUCTION", key="asset_promote_model"):
#             try:
#                 r = requests.post(f"{API_URL}/v1/agents/asset_appraisal/training/promote_last", timeout=60)
#                 if r.ok:
#                     st.success("✅ Model promoted to PRODUCTION.")
#                     st.session_state["_asset_models_bump"] = _now()
#                     st.rerun()
#                 else:
#                     try:
#                         st.error(f"❌ Promotion failed: {r.status_code} {r.reason}")
#                         st.code(r.json())
#                     except Exception:
#                         st.code(r.text[:2000])
#             except Exception as e:
#                 st.error(f"❌ Promotion error: {e}")
#     else:
#         st.warning("⚠️ No trained models found — train one in Step 5 first.")

#     # 🧠 Local LLM & Hardware Profile (runtime hints) — kept
#     LLM_MODELS = [
#         ("Phi-3 Mini (3.8B) — CPU OK", "phi3:3.8b", "CPU 8GB RAM (fast)"),
#         ("Mistral 7B Instruct — CPU slow / GPU OK", "mistral:7b-instruct", "CPU 16GB (slow) or GPU ≥8GB"),
#         ("Gemma-2 7B — CPU slow / GPU OK", "gemma2:7b", "CPU 16GB (slow) or GPU ≥8GB"),
#         ("LLaMA-3 8B — GPU recommended", "llama3:8b-instruct", "GPU ≥12GB (CPU very slow)"),
#         ("Qwen2 7B — GPU recommended", "qwen2:7b-instruct", "GPU ≥12GB (CPU very slow)"),
#         ("Mixtral 8x7B — GPU only (big)", "mixtral:8x7b-instruct", "GPU 24–48GB"),
#     ]
#     LLM_LABELS = [l for (l, _, _) in LLM_MODELS]
#     LLM_VALUE_BY_LABEL = {l: v for (l, v, _) in LLM_MODELS}
#     LLM_HINT_BY_LABEL  = {l: h for (l, _, h) in LLM_MODELS}

#     OPENSTACK_FLAVORS = {
#         "m4.medium":  "4 vCPU / 8 GB RAM — CPU-only small",
#         "m8.large":   "8 vCPU / 16 GB RAM — CPU-only medium",
#         "g1.a10.1":   "8 vCPU / 32 GB RAM + 1×A10 24GB",
#         "g1.l40.1":   "16 vCPU / 64 GB RAM + 1×L40 48GB",
#         "g2.a100.1":  "24 vCPU / 128 GB RAM + 1×A100 80GB",
#     }

#     with st.expander("🧠 Local LLM & Hardware Profile", expanded=True):
#         c1, c2 = st.columns([1.2, 1])
#         with c1:
#             model_label = st.selectbox("Local LLM (used for narratives/explanations)", LLM_LABELS, index=1, key="asset_llm_label")
#             llm_value = LLM_VALUE_BY_LABEL[model_label]
#             use_llm = st.checkbox("Use LLM narrative (include explanations)", value=False, key="asset_use_llm")
#             st.caption(f"Hint: {LLM_HINT_BY_LABEL[model_label]}")
#         with c2:
#             flavor = st.selectbox("OpenStack flavor / host profile", list(OPENSTACK_FLAVORS.keys()), index=0, key="asset_flavor")
#             st.caption(OPENSTACK_FLAVORS[flavor])
#         st.caption("These are passed to the API as hints; your API can choose Ollama/Flowise backends accordingly.")

#     # 🚀 C.4 GPU profile (C.4 ONLY, per blueprint)
#     st.markdown("### **C.4 — Valuation (AI)**")
#     gpu_profile = st.selectbox(
#         "GPU Profile (for valuation compute)",
#         ["CPU (slow)", "GPU: 1x A100", "GPU: 1x H100", "GPU: 2x L40S"],
#         index=1,
#         key="asset_gpu_profile_c4"
#     )
#     ss["asset_gpu_profile"] = gpu_profile  # store per the template rule

#     # Preferred data source: FEATURES (Stage B). Fallbacks preserved.
#     src = st.selectbox("Data source for AI run", [
#         "Use FEATURES (from Stage 2/3)",
#         "Use ANON (from Stage 2)",
#         "Use RAW → auto-sanitize",
#         "Use synthetic (fallback)",
#     ])

#     if src == "Use FEATURES (from Stage 2/3)":
#         df2 = ss.get("asset_features_df")
#         if df2 is None and ss.get("asset_anon_df") is not None:
#             # fallback to anon if features missing
#             df2 = ss.get("asset_anon_df")
#     elif src == "Use ANON (from Stage 2)":
#         df2 = ss.get("asset_anon_df")
#     elif src == "Use RAW → auto-sanitize":
#         df2 = anonymize_text_cols(ss.get("asset_intake_df")) if ss.get("asset_intake_df") is not None else None
#     else:
#         df2 = quick_synth(150)

#     if df2 is None:
#         st.warning("No dataset available. Build Stage B first.")
#         st.stop()

#     st.dataframe(df2.head(10), use_container_width=True)

    # Probe API (health & agents)
    with st.expander("🔎 Probe API (health & agents)", expanded=False):
        if st.button("Run probe now", key="btn_probe_api"):
            diag = probe_api()
            st.json(diag)

    # Run model button (runtime flavor + gpu_profile included)
    if st.button("🚀 Run AI Appraisal now", key="btn_run_ai"):
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
        st.success(f"Saved valuation artifact → `{val_path}`")

        # Keep table for downstream steps
        ss["asset_ai_df"] = df_app

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

        ai_df = ss.get("asset_ai_df")
        if ai_df is None or len(ai_df) == 0:
            st.info("Run the AI appraisal first to populate these tables.")
        else:
            # Merge intake (customer-declared) if available
            intake_df = ss.get("asset_intake_df")
            if intake_df is not None and not intake_df.empty:
                # Choose join keys available in both frames
                join_keys = [k for k in ["application_id", "asset_id"] if k in ai_df.columns and k in intake_df.columns]
                if join_keys:
                    merged = intake_df.merge(ai_df, on=join_keys, suffixes=("_cust", "_ai"), how="left")
                else:
                    merged = ai_df.copy()
            else:
                merged = ai_df.copy()

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

            # ---- Optional Map (if lat/lon present)
            st.markdown("### 🗺️ Map (optional)")
            map_cols = [("lat","lon"), ("latitude","longitude"), ("gps_lat","gps_lon")]
            have_map = False
            for la, lo in map_cols:
                if la in df.columns and lo in df.columns:
                    have_map = True
                    map_df = df[[la, lo] + [c for c in ["asset_id","asset_type","city","ai_adjusted","realizable_value","confidence"] if c in df.columns]].copy()
                    map_df = map_df.rename(columns={la: "lat", lo: "lon"})
                    try:
                        import pydeck as pdk
                        layer = pdk.Layer(
                            "ScatterplotLayer",
                            data=map_df.dropna(subset=["lat","lon"]),
                            get_position="[lon, lat]",
                            get_radius=80,
                            pickable=True,
                        )
                        view_state = pdk.ViewState(latitude=float(map_df["lat"].mean()), longitude=float(map_df["lon"].mean()), zoom=8)
                        st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text":"{asset_id} · {asset_type}\n{city}\nAI: {ai_adjusted}\nRealiz: {realizable_value}\nConf: {confidence}"}))
                    except Exception:
                        st.map(map_df.rename(columns={"lat":"latitude","lon":"longitude"}), use_container_width=True)
                    break
            if not have_map:
                st.caption("No lat/lon columns found (lat/lon or latitude/longitude or gps_lat/gps_lon). Map hidden.")

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

    # # ========== 4) HUMAN REVIEW ==========
    # with tab4:
    #     st.subheader("🧑‍⚖️ Stage 4 — Human Review & Agreement Score")
    #     src_choice = st.radio("Use AI output from Stage 3, or import a CSV:", ["Use Stage 3 output","Import CSV"])
    #     df_rev = None
    #     if src_choice == "Use Stage 3 output":
    #         df_rev = ss.get("asset_ai_df")
    #         if df_rev is None:
    #             st.warning("No Stage 3 output found. Run appraisal first or import a CSV.")
    #     else:
    #         up_rev = st.file_uploader("Upload AI decisions CSV", type=["csv"], key="rev_csv")
    #         if up_rev is not None:
    #             df_rev = pd.read_csv(up_rev)

    #     if df_rev is not None:
    #         if "human_decision" not in df_rev.columns:
    #             df_rev["human_decision"] = df_rev.get("decision", "approved")
    #         if "human_reason" not in df_rev.columns:
    #             df_rev["human_reason"] = ""

    #         st.markdown("**1) Select rows to review and correct**")
    #         edited = st.data_editor(df_rev, use_container_width=True, key="human_editor")

    #         st.markdown("**2) Compute agreement score**")
    #         if st.button("Compute agreement score", key="btn_agree_score"):
    #             ai_col = "decision" if "decision" in edited.columns else "rule_decision"
    #             ai_vals = edited[ai_col].astype(str).str.lower()
    #             human_vals = edited["human_decision"].astype(str).str.lower()
    #             agree = (ai_vals == human_vals)
    #             agree_pct = float(agree.mean() * 100)
    #             gauge = go.Figure(go.Indicator(
    #                 mode="gauge+number", value=agree_pct,
    #                 title={'text': "AI ↔ Human Agreement"},
    #                 gauge={'axis': {'range': [0, 100]}, 'bar': {'color': '#22d3ee'},
    #                        'steps': [{'range': [0, 70], 'color': '#1e293b'},
    #                                  {'range': [70, 90], 'color': '#0ea5e9'},
    #                                  {'range': [90, 100], 'color': '#22d3ee'}]}
    #             ))
    #             gauge.update_layout(template="plotly_dark", height=260)
    #             st.plotly_chart(gauge, use_container_width=True)

    #             dis = edited.loc[~agree, [c for c in edited.columns if c in ["application_id","asset_id","decision","human_decision","ai_reasons","rule_reasons","human_reason"]]]
    #             st.markdown(f"❌ **{len(dis)}** rows disagreed out of **{len(edited)}**  ({(1-agree.mean())*100:.1f}% disagreement rate)")
    #             st.dataframe(dis, use_container_width=True)

    #             fname = f"assetappraisal.{ss['asset_user']['name']}.production.{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
    #             st.download_button("⬇️ Export review CSV (for Training tab)",
    #                                data=edited.to_csv(index=False).encode("utf-8"),
    #                                file_name=fname, mime="text/csv")

    #             ss["asset_human_feedback_df"] = edited

    # ========== 4) POLICY & DECISION (Stage D: steps 6–7) ==========
# with tabD:
#     st.subheader("🧮 Stage 4 — Policy & Decision (D.6 / D.7)")

#     import os, json
#     import numpy as np
#     from datetime import datetime, timezone

#     RUNS_DIR = "./.tmp_runs"
#     os.makedirs(RUNS_DIR, exist_ok=True)
#     def _ts(): return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

#     # Source data: prefer verified → else AI valuation
#     base_df = ss.get("asset_verified_df") or ss.get("asset_ai_df")
#     if base_df is None or len(base_df) == 0:
#         st.warning("Run Stage C first (valuation, and optionally verification).")
#         st.stop()

#     st.caption("Input: valuation + (optional) verification outputs.")





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

        # Persist policy_haircuts artifact
        policy_path = os.path.join(RUNS_DIR, f"policy_haircuts.{_ts()}.csv")
        df.to_csv(policy_path, index=False)
        ss["asset_policy_df"] = df
        st.success(f"Saved: `{policy_path}`")

        # KPIs
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Avg Realizable Value", f"{pd.to_numeric(df['realizable_value'], errors='coerce').mean():,.0f}")
        with k2:
            st.metric("Rows", len(df))
        with k3:
            st.metric("Base Haircut", f"{base_haircut_pct}%")

        st.dataframe(df.head(30), use_container_width=True)

    st.markdown("---")

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
with tabE:
    st.subheader("🧑‍⚖️ Stage E — Human Review & Feedback")
    st.caption("Compare AI-estimated collateral values against business metrics, adjust valuations, and record justification for retraining.")

    RUNS_DIR = "./.tmp_runs"
    os.makedirs(RUNS_DIR, exist_ok=True)

    ai_files = sorted([f for f in os.listdir(RUNS_DIR) if f.startswith("valuation_ai")], reverse=True)
    if not ai_files:
        st.warning("⚠️ No AI appraisal results found. Please complete Stage C first.")
        st.stop()

    ai_path = os.path.join(RUNS_DIR, ai_files[0])
    df_ai = pd.read_csv(ai_path)

    # ── KPI Overview
    st.markdown("### 📊 Business Metrics Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Average FMV", f"${df_ai['fmv'].mean():,.0f}")
    c2.metric("Average Confidence", f"{df_ai['confidence'].mean():.1f}%")
    c3.metric("Average LTV", f"{(df_ai['loan_amount']/df_ai['fmv']).mean():.2f}")
    c4.metric("Assets", len(df_ai))

    # ── Market Projections
    st.markdown("### 📈 Market Projections")
    horizon = st.select_slider("Projection Horizon (years)", [3, 5, 10], value=5)
    growth = st.slider("Expected Market Growth (%)", -10, 25, 4) / 100
    df_ai[f"fmv_proj_{horizon}y"] = (df_ai["fmv"] * ((1 + growth) ** horizon)).round(0)
    st.line_chart(df_ai[["fmv", f"fmv_proj_{horizon}y"]])

    # ── Human Adjustment Table
    st.markdown("### ✏️ Human Adjustments & Justification")
    if "human_value" not in df_ai.columns:
        df_ai["human_value"] = df_ai["fmv"]
    if "justification" not in df_ai.columns:
        df_ai["justification"] = ""

    editable_cols = ["application_id", "asset_id", "asset_type", "city", "fmv", "ai_adjusted", "confidence", "human_value", "justification"]
    edited = st.data_editor(df_ai[editable_cols], num_rows="dynamic", use_container_width=True)

    # ── Deviation Gauge
    import numpy as np
    deviation = abs((edited["human_value"] - edited["fmv"]) / edited["fmv"])
    score = max(0, 100 - (deviation.mean() * 200))
    st.markdown("### 🎯 Human vs AI Deviation")
    st.metric("Alignment Score", f"{score:.1f} / 100")

    # ── Export for Retraining
    if st.button("💾 Save Human Feedback", key="btn_save_feedback"):
        out = os.path.join(RUNS_DIR, f"reviewed_appraisal.{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv")
        edited.to_csv(out, index=False)
        st.success(f"✅ Saved human-reviewed data → `{out}`")

# ─────────────────────────────────────────
# F — MODEL TRAINING & PROMOTION
# ─────────────────────────────────────────
with tabF:
    st.subheader("🧪 Stage F — Model Training & Promotion")
    st.caption("Train or retrain models using human feedback, then promote them to production for Stage C evaluation.")
    
    
    # ─────────────────────────────────────────
    # Stage F header diagnostics (always visible)
    # ─────────────────────────────────────────
    st.markdown("#### 🔎 Data availability")

    def _len_df(x):
        return (0 if not isinstance(x, pd.DataFrame) else len(x))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("decision_df",  _len_df(ss.get("asset_decision_df")))
    c2.metric("policy_df",    _len_df(ss.get("asset_policy_df")))
    c3.metric("verified_df",  _len_df(ss.get("asset_verified_df")))
    c4.metric("ai_df",        _len_df(ss.get("asset_ai_df")))

    with st.expander("Show sample (if no data yet)"):
        st.caption("If you haven't run earlier stages, load a small demo so this page is not empty.")
        if st.button("Load demo portfolio (10 rows)", key="btn_demo_portfolio"):
            try:
                # Prefer your real synthesizer if present
                if "quick_synth" in globals():
                    demo = quick_synth(10)
                else:
                    # Minimal fallback demo
                    import numpy as np, pandas as pd, random
                    demo = pd.DataFrame({
                        "application_id": [f"APP_{i:04d}" for i in range(10)],
                        "asset_id":      [f"A{i:04d}" for i in range(10)],
                        "asset_type":    np.random.choice(["House","Apartment","Car","Land"], size=10),
                        "city":          np.random.choice(["HCMC","Hanoi","Da Nang","Hue"], size=10),
                        "market_value":  np.random.randint(80_000, 800_000, size=10),
                        "ai_adjusted":   np.random.randint(75_000, 820_000, size=10),
                        "loan_amount":   np.random.randint(30_000, 500_000, size=10),
                        "confidence":    np.random.randint(60, 98, size=10),
                        "condition_score": np.random.uniform(0.6, 1.0, size=10).round(3),
                        "legal_penalty":   np.random.uniform(0.95, 1.0, size=10).round(3),
                    })
                    demo["realizable_value"] = (demo["ai_adjusted"] * demo["condition_score"] * demo["legal_penalty"]).round(2)
                    demo["ltv_ai"] = (demo["loan_amount"] / demo["ai_adjusted"]).round(3)
                    demo["ltv_cap"] = 0.8
                    demo["policy_breaches"] = ""
                    demo["decision"] = np.where(demo["ltv_ai"] > demo["ltv_cap"], "review", "approved")
                ss["asset_decision_df"] = demo
                st.success("Demo portfolio loaded into ss['asset_decision_df']. Scroll down.")
            except Exception as e:
                st.error(f"Demo load failed: {e}")

    st.divider()



    reviewed = sorted([f for f in os.listdir("./.tmp_runs") if f.startswith("reviewed_appraisal")], reverse=True)
    if not reviewed:
        st.warning("⚠️ No reviewed feedback CSV found. Complete Stage E first.")
        st.stop()

    csv_path = os.path.join("./.tmp_runs", reviewed[0])
    df = pd.read_csv(csv_path)
    st.markdown(f"**Loaded:** `{csv_path}` ({len(df)} rows)")
    st.dataframe(df.head(20), use_container_width=True)

    model_choice = st.selectbox("Select model algorithm", ["GradientBoostingRegressor", "RandomForestRegressor", "LinearRegression"])
    if st.button("🚀 Train Model", key="btn_train_model"):
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score, mean_absolute_error
        from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
        from sklearn.linear_model import LinearRegression
        import joblib, json, shutil

        y = df["human_value"]
        X = df.select_dtypes("number").drop(columns=["human_value", "fmv", "ai_adjusted"], errors="ignore")

        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
        ModelCls = {"GradientBoostingRegressor": GradientBoostingRegressor,
                    "RandomForestRegressor": RandomForestRegressor,
                    "LinearRegression": LinearRegression}[model_choice]
        model = ModelCls().fit(Xtr, ytr)

        y_pred = model.predict(Xte)
        metrics = {"r2": r2_score(yte, y_pred), "mae": mean_absolute_error(yte, y_pred)}

        train_dir = "./agents/asset_appraisal/models/trained"
        os.makedirs(train_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        model_path = os.path.join(train_dir, f"{model_choice}_asset_{ts}.joblib")
        joblib.dump(model, model_path)
        st.success(f"✅ Model trained and saved → `{model_path}`")
        st.json(metrics)

        if st.button("📤 Promote to Production", key="btn_promote_prod"):
            prod_dir = "./agents/asset_appraisal/models/production"
            os.makedirs(prod_dir, exist_ok=True)
            shutil.copy(model_path, os.path.join(prod_dir, "model.joblib"))
            meta = {"model_path": model_path, "metrics": metrics, "promoted_at": datetime.now(timezone.utc).isoformat()}
            with open(os.path.join(prod_dir, "production_meta.json"), "w") as f:
                json.dump(meta, f, indent=2)
            st.success("🟢 Model promoted to production. Stage C will now use this model.")



# # ========== 5) HUMAN REVIEW & TRAINING (Stage E: steps 8–9) ==========
# with tabE:
#     st.subheader("🧑‍⚖️ Stage 5 — Human Review & Training (E.8 / E.9)")

#     import os, io, json
#     import numpy as np
#     from datetime import datetime, timezone

#     RUNS_DIR = "./.tmp_runs"
#     os.makedirs(RUNS_DIR, exist_ok=True)
#     def _ts(): return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

#     # -------- E.8 — Human Review --------

#     st.markdown("### **E.8 — Human Review**")
#     src_choice = st.radio(
#         "Use Policy+Decision table from Stage 4, or import your own CSV:",
#         ["Use Stage 4 output", "Import CSV"], horizontal=True, key="hr_src_choice"
#     )

#     rev_df = None
#     if src_choice == "Use Stage 4 output":
#         rev_df = ss.get("asset_decision_df")
#         if rev_df is None:
#             st.warning("No Stage 4 output found. Run Policy & Decision (D.6/D.7) first, or import a CSV.")
#     else:
#         up_rev = st.file_uploader("Upload reviewed_appraisal CSV", type=["csv"], key="hr_up_rev")
#         if up_rev is not None:
#             try:
#                 rev_df = pd.read_csv(up_rev)
#             except Exception as e:
#                 st.error(f"CSV parse error: {e}")

#     if rev_df is not None and len(rev_df) > 0:
#         df_display = rev_df.copy()

#         # Ensure human columns for editing
#         if "human_decision" not in df_display.columns:
#             df_display["human_decision"] = df_display.get("decision", "approve")
#         if "human_reason" not in df_display.columns:
#             df_display["human_reason"] = ""

#         # Compact view with common columns first
#         lead_cols = [c for c in [
#             "application_id","asset_id","asset_type","city",
#             "ai_adjusted","realizable_value",
#             "loan_amount","ltv_ai","ltv_cap",
#             "confidence","condition_score","legal_penalty",
#             "policy_breaches","decision","human_decision","human_reason"
#         ] if c in df_display.columns]
#         tail_cols = [c for c in df_display.columns if c not in lead_cols]
#         df_display = df_display[lead_cols + tail_cols]

#         st.caption("Edit decisions/reasons below, then export as feedback for training.")
#         edited = st.data_editor(
#             df_display, use_container_width=True, key="hr_editor", num_rows="dynamic"
#         )

#         c_e81, c_e82, c_e83 = st.columns(3)
#         with c_e81:
#             if st.button("💾 Export reviewed_appraisal.csv", key="btn_export_review"):
#                 reviewed_path = os.path.join(RUNS_DIR, f"reviewed_appraisal.{_ts()}.csv")
#                 edited.to_csv(reviewed_path, index=False)
#                 ss["asset_human_review_df"] = edited
#                 ss["asset_feedback_csv"] = reviewed_path
#                 st.success(f"Saved: `{reviewed_path}`")
#                 st.download_button(
#                     "⬇️ Download reviewed_appraisal.csv",
#                     data=edited.to_csv(index=False).encode("utf-8"),
#                     file_name="reviewed_appraisal.csv",
#                     mime="text/csv"
#                 )

#         with c_e82:
#             if st.button("📏 Compute Agreement Score", key="btn_agree_score"):
#                 ai_col = "decision" if "decision" in edited.columns else None
#                 if not ai_col:
#                     st.warning("No AI decision column found to compare against.")
#                 else:
#                     ai_vals = edited[ai_col].astype(str).str.lower()
#                     human_vals = edited["human_decision"].astype(str).str.lower()
#                     agree = (ai_vals == human_vals)
#                     agree_pct = float(agree.mean() * 100.0)
#                     st.metric("AI ↔ Human Agreement", f"{agree_pct:.2f}%")
#                     # Save lightweight summary for E.9
#                     ss["asset_agreement_score"] = agree_pct
#                     # Show disagreements
#                     dis = edited.loc[~agree, [c for c in edited.columns
#                                               if c in ["application_id","asset_id",ai_col,"human_decision","policy_breaches","human_reason"]]]
#                     if len(dis):
#                         st.markdown(f"❌ **{len(dis)}** rows disagreed out of **{len(edited)}**")
#                         st.dataframe(dis, use_container_width=True)

#         with c_e83:
#             st.caption("Tip: Export reviewed CSV before training.")

#     else:
#         st.info("Awaiting input for review (Stage 4 table or an imported CSV).")

#     st.markdown("---")

#     # -------- E.9 — Feedback → Train --------
#     st.markdown("### **E.9 — Feedback → Train**")

#     fb_path = ss.get("asset_feedback_csv")
#     if not fb_path or not os.path.exists(fb_path):
#         st.info("Export a reviewed_appraisal CSV in E.8 to enable training.")
#     else:
#         st.write(f"Using feedback file: `{os.path.basename(fb_path)}`")

#         c_t1, c_t2, c_t3 = st.columns([1,1,1])
#         with c_t1:
#             train_timeout = st.number_input("Train timeout (sec)", min_value=30, value=180, step=10, key="train_timeout")
#         with c_t2:
#             eval_metric = st.selectbox("Eval metric", ["agreement_score", "RMSE", "MAE"], index=0, key="train_metric")
#         with c_t3:
#             promote_after = st.checkbox("Promote to PRODUCTION after training", value=False, key="train_promote")

#         # Backend-aware training (preferred), with a local fallback
#         if st.button("🧠 Train Candidate Model", key="btn_train_candidate"):
#             model_path = None
#             meta = {}
#             try:
#                 # Try backend training endpoint if present
#                 with open(fb_path, "rb") as fobj:
#                     files = {"feedback_csv": (os.path.basename(fb_path), fobj, "text/csv")}
#                     data = {"agent_id": "asset_appraisal", "metric": eval_metric}
#                     r = requests.post(f"{API_URL}/v1/agents/asset_appraisal/training/train_from_feedback",
#                                       files=files, data=data, timeout=int(train_timeout))
#                 if r.ok:
#                     j = r.json() or {}
#                     model_path = j.get("model_path")
#                     meta = j.get("meta", {})
#                 else:
#                     # Fall back to local stub artifact
#                     raise RuntimeError(f"Backend returned {r.status_code}: {r.text[:200]}")
#             except Exception as e:
#                 # Local stub: create a timestamped model file and meta
#                 model_path = os.path.join(RUNS_DIR, f"model-{_ts()}.joblib")
#                 # create a tiny placeholder so the path exists
#                 with open(model_path, "wb") as fp:
#                     fp.write(b"")  # placeholder joblib
#                 meta = {
#                     "trained_on": os.path.basename(fb_path),
#                     "metric": eval_metric,
#                     "score": float(ss.get("asset_agreement_score", 0.0)),
#                     "algo": "stub_linear",
#                     "created_at": datetime.now(timezone.utc).isoformat(),
#                 }

#             # Persist production_meta.json (not yet promoted)
#             prod_meta = {
#                 "has_production": False,
#                 "model_path": model_path,
#                 "meta": meta
#             }
#             meta_path = os.path.join(RUNS_DIR, "production_meta.json")
#             with open(meta_path, "w", encoding="utf-8") as fp:
#                 json.dump(prod_meta, fp, ensure_ascii=False, indent=2)

#             ss["asset_trained_model_meta"] = prod_meta
#             st.success(f"Candidate trained. Model: `{os.path.basename(model_path)}`")
#             st.caption(f"Metadata saved → `{meta_path}`")

#         # Optional promotion
#         if st.button("🚀 Promote Last Trained to PRODUCTION", key="btn_promote_after_train") or (promote_after and st.session_state.get("asset_trained_model_meta")):
#             try:
#                 r = requests.post(f"{API_URL}/v1/agents/asset_appraisal/training/promote_last", timeout=90)
#                 if r.ok:
#                     st.success("✅ Model promoted to PRODUCTION.")
#                     # Update local production_meta.json to reflect promotion
#                     j = r.json() if r.text else {}
#                     promoted_path = (j.get("meta") or {}).get("model_path") or (ss.get("asset_trained_model_meta") or {}).get("model_path")
#                     prod_meta = {
#                         "has_production": True,
#                         "model_path": promoted_path,
#                         "meta": j.get("meta") or (ss.get("asset_trained_model_meta") or {}).get("meta") or {}
#                     }
#                     meta_path = os.path.join(RUNS_DIR, "production_meta.json")
#                     with open(meta_path, "w", encoding="utf-8") as fp:
#                         json.dump(prod_meta, fp, ensure_ascii=False, indent=2)
#                     ss["asset_trained_model_meta"] = prod_meta
#                 else:
#                     try:
#                         st.error(f"❌ Promotion failed: {r.status_code} {r.reason}")
#                         st.code(r.json())
#                     except Exception:
#                         st.code(r.text[:2000])
#             except Exception as e:
#                 st.error(f"❌ Promotion error: {e}")
    

    # # ========== 5) TRAINING (Feedback → Retrain) ==========
    # with tab5:
    #     st.subheader("🧪 Stage 5 — Train from Feedback & Promote to PRODUCTION")

    #     staged = []
    #     if "asset_human_feedback_df" in ss and ss["asset_human_feedback_df"] is not None:
    #         buf = ss["asset_human_feedback_df"].to_csv(index=False).encode("utf-8")
    #         staged.append(("from_stage4.csv", buf))

    #     up_fb = st.file_uploader("Upload feedback CSV(s)", type=["csv"], accept_multiple_files=True, key="fb_csvs")
    #     if up_fb:
    #         for f in up_fb:
    #             staged.append((f.name, f.getvalue()))

    #     if staged:
    #         st.success(f"Staged {len(staged)} feedback file(s) for training.")
    #         st.json([name for name, _ in staged])

    #         meta = {
    #             "user_name": ss["asset_user"]["name"],
    #             "agent_name": "asset_appraisal",
    #             "algo_name": "asset_lr"  # adjust to your actual backend algo id
    #         }
    #         st.markdown("**Launch Retrain — payload preview**")
    #         st.code(json.dumps(meta, indent=2))

    #         if st.button("🚀 Train candidate model", key="btn_train_candidate"):
    #             files = [("files", (name, io.BytesIO(content), "text/csv")) for name, content in staged]
    #             data = {"meta": json.dumps(meta)}
    #             job = None
    #             for agent_id in discover_asset_agents():
    #                 try:
    #                     resp = requests.post(f"{API_URL}/v1/agents/{agent_id}/training/train_asset",
    #                                          files=files, data=data, timeout=180)
    #                     if resp.ok:
    #                         job = resp.json(); break
    #                     else:
    #                         st.error(f"[{agent_id}] {resp.status_code} {resp.reason}")
    #                         try:
    #                             st.code(resp.json())
    #                         except Exception:
    #                             st.code(resp.text[:2000])

    #                 except Exception:
    #                     pass
    #             if job is None:
    #                 st.error("Training endpoint failed on all discovered agent ids.")
    #             else:
    #                 st.success("Training job submitted.")
    #                 st.json(job)

    #         if st.button("📈 Promote last candidate to PRODUCTION", key="btn_promote_prod"):
    #             promoted = None
    #             for agent_id in discover_asset_agents():
    #                 try:
    #                     r = requests.post(f"{API_URL}/v1/agents/{agent_id}/training/promote_last", timeout=60)
    #                     if r.ok:
    #                         promoted = r.json(); break
    #                 except Exception:
    #                     pass
    #             if promoted:
    #                 st.success("Model promoted.")
    #                 st.json(promoted)
    #             else:
    #                 st.error("Promotion failed on all discovered agent ids.")
    #     else:
    #         st.info("Drop at least one feedback CSV here or generate from Stage 4.")



    

# ─────────────────────────────────────────
# 📚 Unified Portfolio View (color-coded) + Handoff and Exports
# ─────────────────────────────────────────
st.markdown("### 🗂️ Unified Portfolio — Validated / Risky / Fraud")

import os, json
from datetime import datetime, timezone
import numpy as np
import pandas as pd  # make sure pd is available in this scope

RUNS_DIR = "./.tmp_runs"
os.makedirs(RUNS_DIR, exist_ok=True)
_ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

# Choose best available table (do this ONCE)
portfolio = first_nonempty_df(
    ss.get("asset_decision_df"),
    ss.get("asset_policy_df"),
    ss.get("asset_verified_df"),
    ss.get("asset_ai_df"),
)

if not is_nonempty_df(portfolio):
    st.info("No portfolio data available yet. Run Stages C/D or load demo upstream.")
else:
    dfv = portfolio.copy()

    # Ensure commonly used columns exist
    defaults = {
        "verification_status": "verified",
        "encumbrance_flag": False,
        "policy_breaches": "",
        "confidence": 80.0,
        "decision": "review",
        "valuation_gap_pct": 0.0,
        "fraud_flag": False,  # optional (if upstream sets)
    }
    for k, v in defaults.items():
        if k not in dfv.columns:
            dfv[k] = v

    # Normalize types
    conf = pd.to_numeric(dfv["confidence"], errors="coerce").fillna(0)
    gap  = pd.to_numeric(dfv.get("valuation_gap_pct", 0), errors="coerce").fillna(0)
    enc  = dfv["encumbrance_flag"].astype(bool)
    brea = dfv["policy_breaches"].astype(str)
    deci = dfv["decision"].astype(str).str.lower()
    vstat= dfv["verification_status"].astype(str).str.lower()
    fraud= dfv.get("fraud_flag", False)
    if not isinstance(fraud, pd.Series):
        fraud = pd.Series([bool(fraud)] * len(dfv))

    # Use policy profile thresholds when available
    pp = ss.get("policy_profile") or {"min_confidence": 70, "risky_gap_abs_pct": 10}

    # Labeling rules
    def label_row(i: int) -> str:
        if fraud.iat[i] or ("fraud" in vstat.iat[i]) or (enc.iat[i] and "verified" not in vstat.iat[i]):
            return "FRAUD / ENCUMBRANCE"
        if (len(brea.iat[i]) > 0) or (conf.iat[i] < float(pp["min_confidence"])) \
        or (abs(gap.iat[i]) >= float(pp["risky_gap_abs_pct"])) or (deci.iat[i] in ("review","reject")):
            return "RISKY"
        return "VALIDATED"

    dfv["status_label"] = [label_row(i) for i in range(len(dfv))]

    # Row colors
    def color_for(s: str) -> str:
        if s == "VALIDATED": return "#DCFCE7"  # pale green
        if s == "RISKY":     return "#FEF3C7"  # pale orange
        return "#FEE2E2"                      # pale red

    row_colors = [color_for(s) for s in dfv["status_label"]]

    # Columns to show prominently
    cols_main = [c for c in [
        "status_label",
        "application_id","asset_id","asset_type","city",
        "fmv","ai_adjusted","realizable_value",
        "loan_amount","ltv_ai","ltv_cap",
        "confidence","condition_score","legal_penalty",
        "verification_status","encumbrance_flag",
        "valuation_gap_pct","policy_breaches","decision"
    ] if c in dfv.columns]
    view = dfv[cols_main].copy()

    # Style rows by status
    def _style_rows(row):
        return [f"background-color: {row_colors[row.name]}" for _ in row]

    try:
        st.dataframe(view.style.apply(_style_rows, axis=1), use_container_width=True)
    except Exception:
        st.dataframe(view, use_container_width=True)

    # ── Exports for downstream agents
    st.markdown("#### 📤 Exports for Next Workflows")

    # CREDIT: subset
    cols_credit = [c for c in [
        "application_id","asset_id","asset_type","city",
        "fmv","ai_adjusted","realizable_value",
        "loan_amount","ltv_ai","ltv_cap",
        "confidence","condition_score","legal_penalty",
        "verification_status","encumbrance_flag","decision","policy_breaches"
    ] if c in dfv.columns]
    out_credit = dfv[cols_credit].copy()

    # LEGAL: verification-centric
    cols_legal = [c for c in [
        "application_id","asset_id","asset_type","city",
        "verification_status","encumbrance_flag","legal_penalty",
        "confidence","decision","policy_breaches","notes","verified_owner"
    ] if c in dfv.columns]
    out_legal = dfv[cols_legal].copy()

    # RISK: policy & metrics
    cols_risk = [c for c in [
        "application_id","asset_id","asset_type","city",
        "ai_adjusted","realizable_value","loan_amount",
        "ltv_ai","ltv_cap","valuation_gap_pct",
        "confidence","condition_score","legal_penalty",
        "policy_breaches","decision","status_label"
    ] if c in dfv.columns]
    out_risk = dfv[cols_risk].copy()

    # Download buttons (CSV + JSON each)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Credit Appraisal Agent")
        st.download_button("⬇️ Credit CSV", data=out_credit.to_csv(index=False).encode("utf-8"),
                        file_name=f"to_credit_{_ts}.csv", mime="text/csv")
        st.download_button("⬇️ Credit JSON", data=out_credit.to_json(orient="records").encode("utf-8"),
                        file_name=f"to_credit_{_ts}.json", mime="application/json")
    with c2:
        st.caption("Legal Services")
        st.download_button("⬇️ Legal CSV", data=out_legal.to_csv(index=False).encode("utf-8"),
                        file_name=f"to_legal_{_ts}.csv", mime="text/csv")
        st.download_button("⬇️ Legal JSON", data=out_legal.to_json(orient="records").encode("utf-8"),
                        file_name=f"to_legal_{_ts}.json", mime="application/json")
    with c3:
        st.caption("Risk Management Agent")
        st.download_button("⬇️ Risk CSV", data=out_risk.to_csv(index=False).encode("utf-8"),
                        file_name=f"to_risk_{_ts}.csv", mime="text/csv")
        st.download_button("⬇️ Risk JSON", data=out_risk.to_json(orient="records").encode("utf-8"),
                        file_name=f"to_risk_{_ts}.json", mime="application/json")



