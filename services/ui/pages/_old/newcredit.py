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
import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
import logging
import sys
import streamlit as st
import pandas as pd

from services.ui.utils.style import apply_theme, ensure_keys, render_nav_bar_app

# ---- Page config & theme
st.set_page_config(page_title="💳 Credit Appraisal", page_icon="💳",
                   layout="wide", initial_sidebar_state="collapsed")
ensure_keys()
apply_theme(st.session_state.get("theme", "dark"))

# ---- Hide the left sidebar
st.markdown("""
<style>
[data-testid="stSidebar"], section[data-testid="stSidebar"]{display:none!important}
[data-testid="stAppViewContainer"]{margin-left:0!important;padding-left:0!important}
</style>""", unsafe_allow_html=True)

# ---- Navbar (identical to landing)
render_nav_bar_app()

# ---- Login gate
def login_block():
    st.title("🔐 Login to AI Credit Appraisal Platform")
    c1, c2, c3 = st.columns([1,1,1])
    with c1: user  = st.text_input("Username", placeholder="e.g. dzoan")
    with c2: email = st.text_input("Email", placeholder="e.g. dzoan@demo.local")
    with c3: pwd   = st.text_input("Password", type="password", placeholder="Enter any password")
    if st.button("Login", key="btn_credit_login", use_container_width=True):
        if (user or "").strip() and (email or "").strip():
            st.session_state["user_info"] = {
                "name": user.strip(), "email": email.strip(),
                "flagged": False, "timestamp": datetime.now(timezone.utc).isoformat()
            }
            st.session_state["credit_logged_in"] = True
            st.session_state["stage"] = "credit_agent"
            st.rerun()
        else:
            st.error("⚠️ Please fill all fields before continuing.")

# ---- Header (moved from app.py)
def render_credit_header():
    ss = st.session_state
    user = (ss.get("user_info") or {}).get("name") or "guest"
    st.title("🏦 Credit Appraisal Agent")
    st.caption(
        "A→F pipeline — Intake → Privacy → Modelling → Policy → Review → Reporting "
        f"| 👋 {user}"
    )
    st.markdown("""
    <div style="display:flex;gap:.6rem;flex-wrap:wrap;margin:.35rem 0 1rem 0;">
      <span style="padding:.28rem .6rem;border-radius:.6rem;background:#1d4ed8;color:#fff;font-weight:600;">A) Intake & Evidence</span>
      <span style="padding:.28rem .6rem;border-radius:.6rem;background:#059669;color:#fff;font-weight:600;">B) Privacy & Features</span>
      <span style="padding:.28rem .6rem;border-radius:.6rem;background:#d97706;color:#fff;font-weight:600;">C) Modelling & Scoring</span>
      <span style="padding:.28rem .6rem;border-radius:.6rem;background:#7c3aed;color:#fff;font-weight:600;">D) Policy & Decision</span>
      <span style="padding:.28rem .6rem;border-radius:.6rem;background:#a16207;color:#fff;font-weight:600;">E) Review</span>
      <span style="padding:.28rem .6rem;border-radius:.6rem;background:#64748b;color:#fff;font-weight:600;">F) Reporting & Handoff</span>
    </div>
    """, unsafe_allow_html=True)



# ────────────────────────────────
# SESSION STATE INIT
# ────────────────────────────────
if "stage" not in st.session_state:
    st.session_state.stage = "landing"
if "user_info" not in st.session_state:
    st.session_state.user_info = {"name": "", "email": "", "flagged": False}
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "flagged" not in st.session_state.user_info:
    st.session_state.user_info["flagged"] = False
if "timestamp" not in st.session_state.user_info:
    st.session_state.user_info["timestamp"] = datetime.now(timezone.utc).isoformat()

# ────────



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






# ---- Tabs scaffold (drop your code per stage)
def tab_A():
    st.subheader("A) Intake & Evidence")
    st.info("TODO: paste your Credit Intake code here (uploads, schema normalization, validation).")

def tab_B():
    st.subheader("B) Privacy & Features")
    st.info("TODO: PII anonymization + feature engineering.")

def tab_C():
    st.subheader("C) Modelling & Scoring")
    st.info("TODO: Train/Load model, infer, SHAP visualizations.")

def tab_D():
    st.subheader("D) Policy & Decision")
    st.info("TODO: Policy thresholds, LTV/DTI caps, final decision.")

def tab_E():
    st.subheader("E) Human Review & Feedback")
    st.info("TODO: Overrides, notes, export feedback CSV.")

def tab_F():
    st.subheader("F) Reporting & Handoff")
    st.info("TODO: Audit JSON/PDF, create credit handoff zip.")

# ---- Page flow
if not st.session_state.get("credit_logged_in", False):
    login_block()
    st.stop()


# ─────────────────────────────────────────────
# 🏦 TAB 1 — Synthetic Data Generator

def tab_A():
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
    #with c2:
        #st.info(f"Amounts will be generated in **{st.session_state['currency_label']}**.", icon="💰")
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
def tab_B():
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

def tab_C():
    st.subheader("🤖 Credit appraisal by AI assistant")
    # Anchor for loopback link from Training tab
    st.markdown('<a name="credit-appraisal-stage"></a>', unsafe_allow_html=True)

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

    # Hardcoded absolute paths (your confirmed working setup)
    trained_dir = "/home/dzoan/AI-AIGENTbythePeoplesANDBOX/HUGKAG/agents/credit_appraisal/models/trained"
    production_dir = "/home/dzoan/AI-AIGENTbythePeoplesANDBOX/HUGKAG/agents/credit_appraisal/models/production"

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

        selected_display = st.selectbox("📦 Select trained model to use", display_names)
        selected_model = models[display_names.index(selected_display)][1]
        st.success(f"✅ Using model: {os.path.basename(selected_model)}")

        st.session_state["selected_trained_model"] = selected_model

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



    # 1) Model + Hardware selection (UI hints)
    LLM_MODELS = [
        ("Phi-3 Mini (3.8B) — CPU OK", "phi3:3.8b", "CPU 8GB RAM (fast)"),
        ("Mistral 7B Instruct — CPU slow / GPU OK", "mistral:7b-instruct", "CPU 16GB (slow) or GPU ≥8GB"),
        ("Gemma-2 7B — CPU slow / GPU OK", "gemma2:7b", "CPU 16GB (slow) or GPU ≥8GB"),
        ("LLaMA-3 8B — GPU recommended", "llama3:8b-instruct", "GPU ≥12GB (CPU very slow)"),
        ("Qwen2 7B — GPU recommended", "qwen2:7b-instruct", "GPU ≥12GB (CPU very slow)"),
        ("Mixtral 8x7B — GPU only (big)", "mixtral:8x7b-instruct", "GPU 24–48GB"),
    ]
    LLM_LABELS = [l for (l, _, _) in LLM_MODELS]
    LLM_VALUE_BY_LABEL = {l: v for (l, v, _) in LLM_MODELS}
    LLM_HINT_BY_LABEL = {l: h for (l, _, h) in LLM_MODELS}

    OPENSTACK_FLAVORS = {
        "m4.medium":  "4 vCPU / 8 GB RAM — CPU-only small",
        "m8.large":   "8 vCPU / 16 GB RAM — CPU-only medium",
        "g1.a10.1":   "8 vCPU / 32 GB RAM + 1×A10 24GB",
        "g1.l40.1":   "16 vCPU / 64 GB RAM + 1×L40 48GB",
        "g2.a100.1":  "24 vCPU / 128 GB RAM + 1×A100 80GB",
    }

    with st.expander("🧠 Local LLM & Hardware Profile", expanded=True):
        c1, c2 = st.columns([1.2, 1])
        with c1:
            model_label = st.selectbox("Local LLM (used for narratives/explanations)", LLM_LABELS, index=1)
            llm_value = LLM_VALUE_BY_LABEL[model_label]
            st.caption(f"Hint: {LLM_HINT_BY_LABEL[model_label]}")
        with c2:
            flavor = st.selectbox("OpenStack flavor / host profile", list(OPENSTACK_FLAVORS.keys()), index=0)
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
        ]
    )
    use_llm = st.checkbox("Use LLM narrative", value=False)
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
        help="NDI = income - all monthly obligations. Approve if NDI and NDI ratio pass thresholds."
    )

    CLASSIC_DEFAULTS = {
        "max_dti": 0.45, "min_emp_years": 2, "min_credit_hist": 3, "salary_floor": 3000,
        "max_delinquencies": 2, "max_current_loans": 3, "req_min": 1000, "req_max": 200000,
        "loan_terms": [12, 24, 36, 48, 60], "threshold": 0.45, "target_rate": None, "random_band": True,
        "min_income_debt_ratio": 0.35, "compounded_debt_factor": 1.0, "monthly_debt_relief": 0.50,
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
                rc["salary_floor"] = st.number_input("Minimum Monthly Salary", 0, 1_000_000_000, rc["salary_floor"], step=1000, help=fmt_currency_label("in local currency"))
                rc["max_delinquencies"] = st.number_input("Max Delinquencies", 0, 10, rc["max_delinquencies"])
                rc["max_current_loans"] = st.number_input("Max Current Loans", 0, 10, rc["max_current_loans"])
            with r3:
                rc["req_min"] = st.number_input(fmt_currency_label("Requested Amount Min"), 0, 10_000_000_000, rc["req_min"], step=1000)
                rc["req_max"] = st.number_input(fmt_currency_label("Requested Amount Max"), 0, 10_000_000_000, rc["req_max"], step=1000)
                rc["loan_terms"] = st.multiselect("Allowed Loan Terms (months)", [12,24,36,48,60,72], default=rc["loan_terms"])

            st.markdown("#### 🧮 Debt Pressure Controls")
            d1, d2, d3 = st.columns(3)
            with d1:
                rc["min_income_debt_ratio"] = st.slider("Min Income / (Compounded Debt) Ratio", 0.10, 2.00, rc["min_income_debt_ratio"], 0.01)
            with d2:
                rc["compounded_debt_factor"] = st.slider("Compounded Debt Factor (× requested)", 0.5, 3.0, rc["compounded_debt_factor"], 0.1)
            with d3:
                rc["monthly_debt_relief"] = st.slider("Monthly Debt Relief Factor", 0.10, 1.00, rc["monthly_debt_relief"], 0.05)

            st.markdown("---")
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                use_target = st.toggle("🎯 Use target approval rate", value=(rc["target_rate"] is not None))
            with c2:
                rc["random_band"] = st.toggle("🎲 Randomize approval band (20–60%) when no target", value=rc["random_band"])
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
                rn["ndi_value"] = st.number_input(fmt_currency_label("Min NDI (Net Disposable Income) per month"), 0.0, 1e12, float(rn["ndi_value"]), step=50.0)
            with n2:
                rn["ndi_ratio"] = st.slider("Min NDI / Income ratio", 0.0, 1.0, float(rn["ndi_ratio"]), 0.01)
            st.caption("NDI = income - all monthly obligations (rent, food, loans, cards, etc.).")

            st.markdown("---")
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                use_target = st.toggle("🎯 Use target approval rate", value=(rn["target_rate"] is not None))
            with c2:
                rn["random_band"] = st.toggle("🎲 Randomize approval band (20–60%) when no target", value=rn["random_band"])
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
                data.update({
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
                })
            else:
                rn = st.session_state.ndi_rules
                data.update({
                    "ndi_value": str(rn["ndi_value"]),
                    "ndi_ratio": str(rn["ndi_ratio"]),
                    "threshold": "" if rn["threshold"] is None else str(rn["threshold"]),
                    "target_approval_rate": "" if rn["target_rate"] is None else str(rn["target_rate"]),
                    "random_band": str(rn["random_band"]).lower(),
                    "random_approval_band": str(rn["random_band"]).lower(),
                    "rule_mode": "ndi",
                })

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
                    st.warning("No ANON synthetic dataset found. Generate it in the first tab."); st.stop()
                files = prep_and_pack(st.session_state.synthetic_df, "synthetic_anon.csv")

            elif data_choice == "Use synthetic (RAW – auto-sanitize)":
                if "synthetic_raw_df" not in st.session_state:
                    st.warning("No RAW synthetic dataset found. Generate it in the first tab."); st.stop()
                files = prep_and_pack(st.session_state.synthetic_raw_df, "synthetic_raw_sanitized.csv")

            elif data_choice == "Use anonymized dataset":
                if "anonymized_df" not in st.session_state:
                    st.warning("No anonymized dataset found. Create it in the second tab."); st.stop()
                files = prep_and_pack(st.session_state.anonymized_df, "anonymized.csv")

            elif data_choice == "Upload manually":
                up_name = st.session_state.get("manual_upload_name")
                up_bytes = st.session_state.get("manual_upload_bytes")
                if not up_name or not up_bytes:
                    st.warning("Please upload a CSV first."); st.stop()
                try:
                    tmp_df = pd.read_csv(io.BytesIO(up_bytes))
                    files = prep_and_pack(tmp_df, up_name)
                except Exception:
                    files = {"file": (up_name, up_bytes, "text/csv")}
            else:
                st.error("Unknown data source selection."); st.stop()

            # ---- RUN REQUEST ----
            r = requests.post(
                f"{API_URL}/v1/agents/{agent_name}/run",
                data=data,
                files=files,
                timeout=180
            )

            if r.status_code != 200:
                st.error(f"Run failed ({r.status_code}): {r.text}")
                st.stop()

            res = r.json()

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
def tab_D()
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
def tab_E()
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
    st.subheader("🤖 Choose training model")

    model_choice = st.selectbox(
        "Select model:",
        ["LogisticRegression", "RandomForest", "LightGBM", "XGBoost"]
    )

    # ---------------------------------------------------------
    # ✅ TRAINING LOGIC
    # ---------------------------------------------------------
    if st.button("🚀 Train Credit Model Now"):
        with st.spinner("Training model…"):

            # ✅ TARGET COLUMN = score
            TARGET_COL = "score"

            if TARGET_COL not in train_df.columns:
                st.error(f"❌ Target '{TARGET_COL}' not found.")
                st.stop()

            # ✅ Clean target
            y_cont = pd.to_numeric(train_df[TARGET_COL], errors="coerce")
            df_clean = train_df.dropna(subset=[TARGET_COL]).copy()
            y_cont = df_clean[TARGET_COL].astype(float)

            # ✅ Binarize score
            threshold = float(y_cont.median())
            y_bin = (y_cont >= threshold).astype(int)

            st.info(f"✅ Auto-threshold for binarization = {threshold:.4f}")

            # ✅ Feature selection (remove target + leakage)
            LEAKAGE_COLS = [
                TARGET_COL,
                "decision", "confidence",
                "top_feature", "explanation",
                "proposed_loan_option", "proposed_consolidation_loan",
                "rule_reasons"
            ]

            X = df_clean.drop(columns=[c for c in LEAKAGE_COLS if c in df_clean.columns])

            
            # ---------------------------------------------------------
            # ✅ FEATURE SELECTION — DROP ALL NON-NUMERIC COLUMNS
            # ---------------------------------------------------------

            # Columns that MUST NOT be used as features
            BAD_COLS = [
                TARGET_COL,                   # remove score
                "application_id",
                "asset_id",
                "customer_id",
                "currency_code",
                "collateral_type",
                "customer_type",
                "created_at",
                "session_flagged",
                "decision", "confidence",
                "top_feature", "explanation",
                "proposed_loan_option", "proposed_consolidation_loan",
                "rule_reasons"
            ]

            # Drop all known non-features
            df_fe = df_clean.drop(columns=[c for c in BAD_COLS if c in df_clean.columns])

            # ✅ Keep ONLY numeric columns
            X = df_fe.select_dtypes(include=["number"]).copy()

            # ✅ Safety check
            if X.empty:
                st.error("❌ No numeric features available for training. Check your dataset.")
                st.stop()

            st.success(f"✅ Using {X.shape[1]} numeric features for training.")
            st.dataframe(X.head())

            
            # ✅ Split
            Xtr, Xte, ytr, yte = train_test_split(
                X, y_bin, test_size=0.2, random_state=42
            )

            # ✅ Model selection
            if model_choice == "LogisticRegression":
                from sklearn.linear_model import LogisticRegression
                model = LogisticRegression(max_iter=2000)
            elif model_choice == "RandomForest":
                from sklearn.ensemble import RandomForestClassifier
                model = RandomForestClassifier(n_estimators=300)
            elif model_choice == "LightGBM":
                from lightgbm import LGBMClassifier
                model = LGBMClassifier()
            else:
                from xgboost import XGBClassifier
                model = XGBClassifier()

            # ✅ Train
            model.fit(Xtr, ytr)

            # ✅ Predictions
            preds_proba = model.predict_proba(Xte)[:, 1]
            preds = (preds_proba >= 0.5).astype(int)

            # ✅ Metrics
            new_m = {
                "AUC": roc_auc_score(yte, preds_proba),
                "Accuracy": accuracy_score(yte, preds),
                "Precision": precision_score(yte, preds),
                "Recall": recall_score(yte, preds),
                "F1": f1_score(yte, preds),
            }

            # -----------------------------------------------------
            # ✅ LOAD PRODUCTION BASELINE IF EXISTS
            # -----------------------------------------------------
            PROD_DIR = Path("./agents/credit_appraisal/models/production")
            prod_meta_path = PROD_DIR / "production_meta.json"

            if prod_meta_path.exists():
                prod_m = json.load(open(prod_meta_path))["metrics"]
            else:
                prod_m = None

            st.markdown("---")
            st.subheader("📊 A/B Model Comparison")

            # ✅ COMPARISON TABLE
            cmp_df = pd.DataFrame({
                "Metric": list(new_m.keys()),
                "New Model": [f"{v:.4f}" for v in new_m.values()],
                "Production": [
                    f"{prod_m[k]:.4f}" if prod_m else "—"
                    for k in new_m.keys()
                ]
            })
            st.table(cmp_df)

            # -----------------------------------------------------
            # ✅ EXECUTIVE SUMMARY (WHAT → SO WHAT → NOW WHAT)
            # -----------------------------------------------------
            st.markdown("## 🧭 Executive Summary (WHAT → SO WHAT → NOW WHAT)")

            if prod_m:
                auc_delta = new_m["AUC"] - prod_m["AUC"]
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
                imp = pd.DataFrame({
                    "feature": X.columns,
                    "importance": model.feature_importances_
                }).sort_values("importance", ascending=False)
                st.bar_chart(imp.set_index("feature"))
            elif hasattr(model, "coef_"):
                coef = pd.DataFrame({
                    "feature": X.columns,
                    "coef": np.ravel(model.coef_)
                }).sort_values("coef", key=np.abs, ascending=False)
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
                "metrics": new_m,
                "model_path": str(model_path),
                "features": list(X.columns),
                "threshold": threshold,
            }

            rep_path = RUNS_DIR / f"credit_training_report_{ts}.json"
            json.dump(report, open(rep_path, "w"), indent=2)

            # store for next stage
            st.session_state["credit_last_model_path"] = str(model_path)
            st.session_state["credit_last_metrics"] = new_m
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
                        "metrics": new_m,
                        "model_path": str(model_path),
                        "model_choice": model_choice
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
def tab_B()
    import os, json, shutil, zipfile
    from pathlib import Path
    from datetime import datetime, timezone

    st.markdown("## 🚀 Stage G — Model Deployment")
    st.caption("Promote trained model → publish → export deployment bundle")

    last_model = st.session_state.get("credit_last_model_path")
    metrics = st.session_state.get("credit_last_metrics")
    report = st.session_state.get("credit_last_report")

    if not last_model:
        st.warning("⚠️ Train a model in Stage F before deploying.")
        st.stop()

    st.success(f"✅ Latest trained model detected:\n`{last_model}`")
    st.json(metrics)

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

    # 1) Primary: dataset saved by Stage C/E
    df = st.session_state.get("credit_scored_df")

    # 2) Fallback: Stage C merged output
    if df is None or df.empty:
        df = st.session_state.get("last_merged_df")

    # 3) Optional: user upload
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
    if df is None or df.empty:
        st.warning("⚠️ Missing scored dataset. Run Stage 3 (Credit appraisal) or upload a scored CSV above.")
        st.stop()

    # Persist for other tabs
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

    # # ---------------------------------------------------------
    # # ✅ Approval distribution
    # # ---------------------------------------------------------
    # # st.markdown("### 📈 Approval Distribution")
    # # fig = px.histogram(df, x="decision", color="decision", title="Approval vs Rejection")
    # # st.plotly_chart(fig, use_container_width=True)
    # fig = px.histogram(
    # df, x="decision", color="decision",
    # color_discrete_sequence=PALETTE,
    # title="Approval vs Rejection"
    # )
    # fig = apply_dark(fig)
    # fig.update_traces(marker_line_width=0.5)
    # fig.update_xaxes(title=None, gridcolor="rgba(255,255,255,0.08)")
    # fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    # st.plotly_chart(fig, use_container_width=True)

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
            # numeric/bool
            try:
                return "approve" if float(v) >= 1 else "reject"
            except Exception:
                return "unknown"

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
        use_container_width=True
    )

    # st.markdown("### 🧩 Department Package Map")
    # st.json({k: list(df[list(credit.columns)].columns)})
    st.markdown("### 🧩 Department Package Map")
    st.json({
        "credit":   list(credit.columns),
        "risk":     list(risk.columns),
        "compliance": list(compliance.columns),
        "customer_service": list(customer.columns),
    })

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



# ─────────────────────────────────────────────
# 🗣️ TAB 8 — Feedback & Feature Requests
# ─────────────────────────────────────────────
with tab_feedback:
    st.subheader("🗣️ Share Your Feedback and Feature Ideas")

    FEEDBACK_FILE = os.path.join(BASE_DIR, "agents_feedback.json")

    def load_feedback() -> dict:
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_feedback(data: dict):
        try:
            with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"Could not save feedback: {e}")

    feedback_data = load_feedback()

    # View all current agent feedback
    st.markdown("### 💬 Current Agent Reviews & Ratings")
    for agent, fb in feedback_data.items():
        with st.expander(f"⭐ {agent} — {fb.get('rating', 0)}/5  |  👥 {fb.get('users', 0)} users"):
            st.markdown("#### Recent Comments:")
            for cmt in reversed(fb.get("comments", [])):
                st.markdown(f"- {cmt}")
            st.markdown("---")

    st.markdown("### ✍️ Submit Your Own Feedback or Feature Request")

    agent_choice = st.selectbox("Select Agent", list(feedback_data.keys()))
    new_comment = st.text_area("Your Comment or Feature Suggestion", placeholder="e.g. Add multi-language support for reports...")
    new_rating = st.slider("Your Rating", 1, 5, 5)


    if st.button("📨 Submit Feedback"):
        if new_comment.strip():
            fb = feedback_data.get(agent_choice, {"rating": 0, "users": 0, "comments": []})
            fb["comments"].append(new_comment.strip())
            fb["rating"] = round((fb.get("rating", 0) + new_rating) / 2, 2)
            fb["users"] = fb.get("users", 0) + 1
            feedback_data[agent_choice] = fb
            save_feedback(feedback_data)

            # ✅ Sync latest feedback globally
            st.session_state["feedback_data"] = feedback_data

            # ✅ Force full reload so Landing updates instantly
            st.success("✅ Feedback submitted successfully!")
            st.rerun()
        else:
            st.warning("Please enter a comment before submitting.")





render_credit_header()
tA, tB, tC, tD, tE, tF = st.tabs([
    "🟦 A) Intake", "🟩 B) Privacy & Features", "🟨 C) Modelling",
    "🟧 D) Policy & Decision", "🟪 E) Review", "🟫 F) Reporting"
])
with tA: tab_A()
with tB: tab_B()
with tC: tab_C()
with tD: tab_D()
with tE: tab_E()
with tF: tab_F()
