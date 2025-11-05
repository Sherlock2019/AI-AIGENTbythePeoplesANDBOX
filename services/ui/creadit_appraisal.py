# services/ui/app.py
# ─────────────────────────────────────────────
# 🌐 OpenSource AI Agent Library + Credit Appraisal PoC by Dzoan
# ─────────────────────────────────────────────
from __future__ import annotations
import os
import re
import io
import json
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import pandas as pd
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone


# ─────────────────────────────────────────────
# PAGE CONFIG + SESSION
# ─────────────────────────────────────────────
st.set_page_config(page_title="Credit Appraisal Agent", layout="wide")
# ss = st.session_state
# ss.setdefault("credit_logged_in", False)
# ss.setdefault("credit_stage", "login")
# ss.setdefault("credit_user", {"name":"Guest","email":None})
# for k in [
#   "credit_intake_df","credit_anon_df","credit_ai_df","credit_review_df",
#   "credit_feedback_csv","credit_model_meta"
# ]:
#   ss.setdefault(k, None)
# os.makedirs("./.tmp_runs", exist_ok=True)

# ────────────────────────────────
# SESSION STATE INIT
# ────────────────────────────────
if "credit_stage" not in st.session_state:
    st.session_state.credit_stage = "login"
if "credit_logged_in" not in st.session_state:
    st.session_state.credit_logged_in = False


# ─────────────────────────────────────────────
# THEME SWITCHER (identical to asset_appraisal)
# ─────────────────────────────────────────────
if "ui_theme" not in st.session_state:
    st.session_state["ui_theme"] = "light"

def apply_theme(theme: str = "light"):
    if theme == "light":
        bg, text, sub, accent = "#ffffff", "#0f172a", "#334155", "#2563eb"
    else:
        bg, text, sub, accent = "#0E1117", "#f1f5f9", "#93a4b8", "#3b82f6"
    st.markdown(f"""
    <style>
      .stApp {{background:{bg}!important;color:{text}!important;}}
      .stCaption,p,li {{color:{sub}!important;}}
      .stButton>button {{background:{accent}!important;color:white!important;}}
    </style>
    """, unsafe_allow_html=True)

apply_theme(st.session_state["ui_theme"])

# ────────────────────────────────
# GLOBAL UTILS (from asset agent)
# ────────────────────────────────
BASE_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/ui")
RUNS_DIR = os.path.join(BASE_DIR, ".tmp_runs")
TMP_FEEDBACK_DIR = os.path.join(BASE_DIR, ".tmp_feedback")
for d in (RUNS_DIR, TMP_FEEDBACK_DIR):
    os.makedirs(d, exist_ok=True)

API_URL = os.getenv("API_URL", "http://localhost:8090")

def extract_run_id(obj) -> Optional[str]:
    if isinstance(obj, dict):
        if isinstance(obj.get("run_id"), str):
            return obj["run_id"]
        res = obj.get("result")
        if isinstance(res, dict) and isinstance(res.get("run_id"), str):
            return res["run_id"]
    if isinstance(obj, list):
        for it in obj:
            rid = extract_run_id(it)
            if rid:
                return rid
    return None

def json_to_dataframe(payload) -> Optional[pd.DataFrame]:
    if isinstance(payload, dict):
        res = payload.get("result") or {}
        if isinstance(res, list):
            return pd.DataFrame(res)
        if isinstance(res, dict):
            return pd.json_normalize(res)
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    return None

def _extract_run_fields(raw_json):
    run_id = extract_run_id(raw_json)
    payload = raw_json if isinstance(raw_json, dict) else {"result": raw_json}
    return run_id, payload

# ────────────────────────────────
# GLOBAL UTILITIES (extended)
# ────────────────────────────────
def quick_synth(n: int = 20) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    return pd.DataFrame([
        {
            "application_id": f"APP_{now.strftime('%H%M%S')}_{i:04d}",
            "asset_id": f"A{now.strftime('%M%S')}{i:04d}",
            "customer_name": f"Customer {i}",
            "credit_score": random.randint(550, 820),
            "loan_amount": random.randint(5000, 50000),
            "income": random.randint(1000, 10000),
            "city": random.choice(["HCMC", "Hanoi", "Da Nang", "Can Tho"]),
            "status": random.choice(["pending", "approved", "rejected"]),
        }
        for i in range(n)
    ])

def sha1_of_filelike(fobj) -> str:
    pos = fobj.tell() if hasattr(fobj, "tell") else None
    fobj.seek(0)
    h = hashlib.sha1()
    for chunk in iter(lambda: fobj.read(8192), b""):
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")
        h.update(chunk)
    if pos is not None:
        fobj.seek(pos)
    return h.hexdigest()

def save_to_runs(df: pd.DataFrame, name: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RUNS_DIR, f"{name}_{ts}.csv")
    df.to_csv(path, index=False)
    return path

# ─────────────────────────────────────────────
# NAV BAR + THEME TOGGLE
# ─────────────────────────────────────────────
def render_nav_bar_app():
  c1, c2 = st.columns([1, 1])
  with c1:
    if st.button("🏠 Back to Home"):
      st.switch_page("../../landing_page.py")
  with c2:
    is_dark = (ss.get("ui_theme","dark") == "dark")
    new = st.toggle("🌙 Dark mode", value=is_dark)
    if new != is_dark:
      ss["ui_theme"] = "dark" if new else "light"
      apply_theme(ss["ui_theme"])
  st.markdown("---")

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
if ss["credit_stage"] == "login" and not ss["credit_logged_in"]:
  render_nav_bar_app()
  st.title("🔐 Login to Credit Appraisal Platform")
  c1,c2,c3 = st.columns([1,1,1])
  with c1: user = st.text_input("Username")
  with c2: email = st.text_input("Email")
  with c3: pwd = st.text_input("Password", type="password")
  if st.button("Login"):
    if user and email:
      ss["credit_user"] = {"name":user,"email":email,
        "timestamp":datetime.now(timezone.utc).isoformat()}
      ss["credit_logged_in"]=True
      ss["credit_stage"]="credit_flow"
      st.rerun()

# ─────────────────────────────────────────────
# MAIN WORKFLOW (A → F stages similar to asset agent)
# ─────────────────────────────────────────────
elif ss["credit_logged_in"]:
  render_nav_bar_app()
  st.title("💳 Credit Appraisal Agent")
  st.caption(f"E2E flow — Intake → Anonymize → AI → Review → Training | 👋 {ss['credit_user']['name']}")

  tabA, tabB, tabC, tabD, tabE, tabF = st.tabs([
    "📥 A) Data Input",
    "🧹 B) Anonymize",
    "🤖 C) AI Credit Scoring",
    "🧑‍⚖️ D) Human Review",
    "🧪 E) Training",
    "📤 F) Reporting"
  ])

  with tabA:
    st.subheader("A. Data Input & Validation")
    st.write("Upload loan applications or synthetic data for credit analysis.")
  with tabB:
    st.subheader("B. Anonymization & Feature Engineering")
    st.write("Mask PII fields and derive features for model training.")
  with tabC:
    st.subheader("C. AI Credit Scoring")
    st.write("Run AI model to score creditworthiness and explain results.")
  with tabD:
    st.subheader("D. Human Review")
    st.write("Compare AI vs human decisions, export feedback CSV.")
  with tabE:
    st.subheader("E. Training (Feedback → Retrain)")
    st.write("Upload feedback to train a new model candidate.")
  with tabF:
    st.subheader("F. Reporting & Handoff")
    st.write("Generate credit appraisal report and handoff to CRM.")
