#!/usr/bin/env python3
"""
⚖️ Legal & Compliance Agent (Stage-only view)
---------------------------------------------
Lightweight Streamlit page derived from the Asset Appraisal template. It presents
only the compliance stages that sit between KYC / Anti-Fraud / Asset intel and
the downstream Credit Appraisal decisioning stack.

Outputs are stored in ``st.session_state["credit_policy_df"]`` so Credit Appraisal
can overlay hard-policy constraints onto the shared scoring outputs.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from services.ui.theme_manager import (
    apply_theme as apply_global_theme,
    get_palette,
    get_theme,
    render_theme_toggle,
)
from services.ui.components.operator_banner import render_operator_banner
from services.ui.components.chat_assistant import render_chat_assistant
from services.common.model_registry import get_hf_models, get_llm_lookup, get_llm_display_info
from services.ui.utils.llm_selector import render_llm_selector
from services.ui.utils.ai_insights import llm_generate_summary


st.set_page_config(page_title="Legal Compliance Agent", layout="wide")
ss = st.session_state


def _init_state() -> None:
    llm_lookup = get_llm_lookup()
    default_label = llm_lookup["labels"][0]
    ss.setdefault("stage", "legal_compliance_agent")
    ss.setdefault("legal_compliance_stage", "stages_only")
    ss.setdefault(
        "legal_compliance_user",
        ss.get("compliance_user")
        or ss.get("credit_scoring_user")
        or ss.get("credit_user")
        or {"name": "Operator", "email": "operator@demo.local"},
    )
    ss.setdefault("legal_compliance_pending", 11)
    ss.setdefault("legal_compliance_flags", 2)
    ss.setdefault("legal_compliance_avg_time", "6 min")
    ss.setdefault("legal_compliance_last_run_ts", None)
    ss.setdefault("legal_compliance_status", "idle")
    ss.setdefault("legal_compliance_llm_label", default_label)
    ss.setdefault("legal_compliance_llm_model", llm_lookup["value_by_label"][default_label])
    ss.setdefault("legal_compliance_llm_score", 88.0)


_init_state()
apply_global_theme(get_theme())


def _safe_switch(target: str) -> None:
    ss["stage"] = target
    try:
        st.switch_page("app.py")
        return
    except Exception:
        pass
    try:
        st.query_params["stage"] = target
    except Exception:
        pass
    try:
        st.experimental_rerun()
    except Exception:
        pass


def _render_nav():
    stage = ss.get("stage", "legal_compliance_agent")
    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if st.button("🏠 Home", key=f"lc_nav_home_{stage}"):
            _safe_switch("landing")
    with c2:
        if st.button("🤖 Agents", key=f"lc_nav_agents_{stage}"):
            _safe_switch("agents")
    with c3:
        render_theme_toggle("🌗 Theme", key="legal_compliance_top_theme")


_render_nav()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _collect_multi_source_view() -> pd.DataFrame:
    """
    Merge whatever artefacts are present in session state. Priority:
    1) Real compliance df
    2) Credit policy df
    3) Anti-fraud / KYC
    4) Asset policy exposures
    5) Synthetic fallback
    """
    candidate_keys = [
        "legal_compliance_df",
        "credit_policy_df",
        "afk_kyc_df",
        "afk_fraud_df",
        "asset_policy_df",
        "credit_scoring_df",
    ]
    frames: List[pd.DataFrame] = []
    for key in candidate_keys:
        df = ss.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            frames.append(df.copy())

    if frames:
        base = frames[0]
    else:
        rng = np.random.default_rng(20251110)
        base = pd.DataFrame(
            {
                "customer_id": [f"CUST-{2000 + i}" for i in range(8)],
                "jurisdiction": rng.choice(["US", "UK", "NG", "ZA", "AE", "SG", "MX"], 8),
                "pep_flag": rng.choice([0, 1], 8, p=[0.84, 0.16]),
                "sanctions_match": rng.choice([0, 1], 8, p=[0.92, 0.08]),
                "license_required": rng.choice([0, 1], 8, p=[0.55, 0.45]),
                "ticket_type": rng.choice(["Retail", "SME", "Project Finance"], 8),
                "ask_amount": rng.integers(50_000, 3_500_000, 8),
            }
        )
    return base.reset_index(drop=True)


def _run_compliance_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Simulate the shared compliance reasoning pass (same signals as Asset)."""
    df = df.copy()
    rng = np.random.default_rng(42)
    if "pep_flag" not in df:
        df["pep_flag"] = rng.choice([0, 1], len(df), p=[0.82, 0.18])
    if "sanctions_match" not in df:
        df["sanctions_match"] = rng.choice([0, 1], len(df), p=[0.93, 0.07])
    if "license_required" not in df:
        df["license_required"] = rng.choice([0, 1], len(df), p=[0.58, 0.42])

    df["kyc_risk_score"] = df.get("kyc_risk_score", rng.uniform(0.05, 0.55, len(df))).astype(float)
    df["llm_alignment_score"] = (1 - df["kyc_risk_score"]) * (1 - df["sanctions_match"] * 0.6)
    df["llm_alignment_score"] = df["llm_alignment_score"].clip(0.15, 0.99).round(3)

    def _status(row: pd.Series) -> str:
        if row["sanctions_match"] >= 1 or row["pep_flag"] >= 1:
            return "🚫 Hold – escalate"
        if row["license_required"] >= 1 and row["llm_alignment_score"] < 0.55:
            return "🟠 Conditional"
        return "✅ Cleared"

    df["compliance_status"] = df.apply(_status, axis=1)
    df["stage"] = np.where(df["compliance_status"] == "✅ Cleared", "Compliance OK", "Compliance Hold")
    df["legal_reason"] = [
        f"Stage {idx%3 + 1}: Shared model highlighted {('PEP' if pep else 'policy match')} w/ score {score:.2f}"
        for idx, (pep, score) in enumerate(zip(df["pep_flag"], df["llm_alignment_score"]))
    ]
    df["last_reviewed_at"] = datetime.now(timezone.utc).isoformat()
    return df


def _build_chat_context() -> Dict[str, Any]:
    ctx = {
        "agent_type": "legal_compliance",
        "stage": ss.get("legal_compliance_stage"),
        "user": (ss.get("legal_compliance_user") or {}).get("name"),
        "pending_cases": ss.get("legal_compliance_pending"),
        "flagged_cases": ss.get("legal_compliance_flags"),
        "avg_time": ss.get("legal_compliance_avg_time"),
        "last_run": ss.get("legal_compliance_last_run_ts"),
        "status": ss.get("legal_compliance_status"),
        "llm_model": ss.get("legal_compliance_llm_model"),
        "llm_label": ss.get("legal_compliance_llm_label"),
        "ollama_url": os.getenv("OLLAMA_URL", f"http://localhost:{os.getenv('GEMMA_PORT', '7001')}"),
    }
    return {k: v for k, v in ctx.items() if v not in (None, "", [])}


# ---------------------------------------------------------------------------
# HEADER + OVERVIEW
# ---------------------------------------------------------------------------
pal = get_palette()
render_operator_banner(
    operator_name=(ss["legal_compliance_user"] or {}).get("name", "Operator"),
    title="Legal & Compliance Agent",
    summary="Confirms regulatory readiness before the Credit Appraisal agent finalizes a decision.",
    bullets=[
        "Stage 1 → Align Anti-Fraud/KYC + Asset/Collateral context",
        "Stage 2 → Shared LLM legal reasoning (sanctions, PEP, licensing)",
        "Stage 3 → Push compliance verdicts to Credit Appraisal / unified agent",
    ],
    metrics=[
        {"label": "Pending reviews", "value": ss.get("legal_compliance_pending"), "delta": "+1 new"},
        {"label": "Flags", "value": ss.get("legal_compliance_flags"), "delta": "stable"},
        {"label": "Avg SLA", "value": ss.get("legal_compliance_avg_time"), "delta": "-6%"},
    ],
)

source_df = _collect_multi_source_view()
fraud_hits = int(source_df.get("sanctions_match", pd.Series(dtype=int)).sum() or 0)
kyc_feeds = len(source_df)
agreement_pct = float(ss.get("legal_compliance_confidence", 0.95) or 0.95) * 100
agreement_pct = max(0, min(100, agreement_pct))
refresh_age_val = 10.0
ts = ss.get("legal_compliance_last_run_ts")
if isinstance(ts, str):
    try:
        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        refresh_age_val = max(
            0.0, (datetime.now(timezone.utc) - ts_dt).total_seconds() / 3600.0
        )
    except Exception:
        pass
telemetry = {
    "kyc_feeds": kyc_feeds,
    "fraud_hits": fraud_hits,
    "refresh_age": min(72.0, refresh_age_val),
    "agreement": agreement_pct,
}

llm_score_value = float(ss.get("legal_compliance_llm_score", telemetry["agreement"]) or telemetry["agreement"])
llm_score_value = max(0.0, min(100.0, llm_score_value))
ss["legal_compliance_llm_score"] = llm_score_value

llm_confidence_fig = go.Figure(
    go.Indicator(
        mode="gauge+number",
        value=llm_score_value,
        title={"text": "LLM Confidence / Explanation Strength"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "lime"},
            "steps": [
                {"range": [0, 30], "color": "#f87171"},
                {"range": [30, 70], "color": "#fb923c"},
                {"range": [70, 100], "color": "#4ade80"},
            ],
        },
    )
)
llm_confidence_fig.update_layout(
    height=300,
    margin=dict(l=0, r=0, t=60, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(llm_confidence_fig, use_container_width=True)

donut = go.Figure(
    data=[
        go.Pie(
            values=[telemetry["agreement"], 100 - telemetry["agreement"]],
            labels=["Agreement", "Gap"],
            hole=0.65,
            marker_colors=["#3b82f6", "#1e293b"],
        )
    ]
)
donut.update_layout(
    height=320,
    showlegend=False,
    margin=dict(l=0, r=0, t=40, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

bullet = go.Figure(
    go.Indicator(
        mode="number+gauge",
        value=telemetry["refresh_age"],
        title={"text": "Data Refresh Age (hours)"},
        gauge={
            "shape": "bullet",
            "axis": {"range": [0, 72]},
            "bar": {"color": "#22c55e"},
            "steps": [
                {"range": [0, 24], "color": "#4ade80"},
                {"range": [24, 48], "color": "#fbbf24"},
                {"range": [48, 72], "color": "#f87171"},
            ],
        },
        domain={"x": [0, 1], "y": [0, 1]},
    )
)
bullet.update_layout(
    height=160,
    margin=dict(l=0, r=0, t=40, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

bar = go.Figure(
    go.Bar(
        x=[telemetry["kyc_feeds"], telemetry["fraud_hits"]],
        y=["KYC Feeds", "Fraud Hits"],
        orientation="h",
        marker=dict(color=["#0ea5e9", "#ef4444"]),
    )
)
bar.update_layout(
    height=260,
    margin=dict(l=0, r=0, t=40, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

c1, c2 = st.columns(2)
with c1:
    st.markdown("<div class='metric-title'>LLM ↔ Human Agreement</div>", unsafe_allow_html=True)
    st.plotly_chart(donut, use_container_width=True)
    st.markdown(
        "<div class='metric-explain'>How closely the LLM's valuation/explanation matches human analysts. "
        "90%+ = high alignment; <70% = review for drift or inconsistencies.</div>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown("<div class='metric-title'>Data Freshness (Hours Since Last Sync)</div>", unsafe_allow_html=True)
    st.plotly_chart(bullet, use_container_width=True)
    st.markdown(
        "<div class='metric-explain'>Measures how recent Anti-Fraud / KYC signals were last synchronized. "
        "Green <24h = fresh, Yellow <48h = acceptable, Red >48h = stale data risk.</div>",
        unsafe_allow_html=True,
    )
st.markdown("<div class='metric-title'>Operational Signals (KYC / Fraud)</div>", unsafe_allow_html=True)
st.plotly_chart(bar, use_container_width=True)
st.markdown(
    "<div class='metric-explain'>Live operational workload indicators. Fraud hits represent flagged anomalies. "
    "KYC feeds show validated identity signals.</div>",
    unsafe_allow_html=True,
)

ai_summary_text = llm_generate_summary(telemetry)
st.markdown("### 🧠 AI Recommendation Summary")
st.write(ai_summary_text)

if False:
    st.markdown("### Shared LLM & Hardware Profile")
    hf_models_df = pd.DataFrame(get_hf_models())
    llm_lookup_ui = get_llm_lookup()
    OPENSTACK_FLAVORS = {
        "m4.medium": "4 vCPU / 8 GB RAM (CPU-only small)",
        "m8.large": "8 vCPU / 16 GB RAM (CPU-only medium)",
        "g1.a10.1": "8 vCPU / 32 GB RAM + 1×A10 24 GB",
        "g1.l40.1": "16 vCPU / 64 GB RAM + 1×L40 48 GB",
        "g2.a100.1": "24 vCPU / 128 GB RAM + 1×A100 80 GB",
    }
    with st.expander("🧠 Local/HF lineup (shared with Asset & Credit)", expanded=False):
        st.dataframe(hf_models_df, use_container_width=True)
        c1, c2 = st.columns([1.2, 1])
        labels = llm_lookup_ui["labels"]
        value_by_label = llm_lookup_ui["value_by_label"]
        hint_by_label = llm_lookup_ui["hint_by_label"]
        saved_label = ss.get("legal_compliance_llm_label", labels[0])
        if saved_label not in labels:
            saved_label = labels[0]
        with c1:
            selected_label = st.selectbox(
                "🔥 Local/HF LLM (legal reasoning)",
                labels,
                index=labels.index(saved_label),
                key="legal_compliance_llm_label",
            )
            st.caption(f"Hint: {hint_by_label[selected_label]}")
        with c2:
            flavor = st.selectbox(
                "OpenStack flavor / host profile",
                list(OPENSTACK_FLAVORS.keys()),
                index=0,
                key="legal_compliance_flavor",
            )
            st.caption(OPENSTACK_FLAVORS[flavor])
        ss["legal_compliance_llm_model"] = value_by_label[selected_label]

OPENSTACK_FLAVORS = {
    "m4.medium": "4 vCPU / 8 GB RAM (CPU-only small)",
    "m8.large": "8 vCPU / 16 GB RAM (CPU-only medium)",
    "g1.a10.1": "8 vCPU / 32 GB RAM + 1×A10 24 GB",
    "g1.l40.1": "16 vCPU / 64 GB RAM + 1×L40 48 GB",
    "g2.a100.1": "24 vCPU / 128 GB RAM + 1×A100 80 GB",
}

selected_llm = render_llm_selector(context="legal_compliance")
ss["legal_compliance_llm_label"] = selected_llm["model"]
ss["legal_compliance_llm_model"] = selected_llm["value"]

flavor = st.selectbox(
    "OpenStack flavor / host profile",
    list(OPENSTACK_FLAVORS.keys()),
    index=0,
    key="legal_compliance_flavor",
)
st.caption(OPENSTACK_FLAVORS[flavor])

st.markdown("### Stage-Only Compliance Flow")


# ---------------------------------------------------------------------------
# STAGE 1 — MULTI-SOURCE ALIGNMENT
# ---------------------------------------------------------------------------
with st.container():
    st.subheader("Stage 1 · Align Anti-Fraud/KYC + Asset context")
    st.write(
        "We expose only the necessary columns for compliance to keep the scope tight. "
        "This table reflects whichever upstream agent populated session_state most recently."
    )
    st.dataframe(source_df.head(12), use_container_width=True, height=320)
    st.caption(
        "Tip: refresh Anti-Fraud/KYC or Asset pages first to propagate their most recent outputs here."
    )


# ---------------------------------------------------------------------------
# STAGE 2 — SHARED LEGAL REASONING
# ---------------------------------------------------------------------------
with st.container():
    st.subheader("Stage 2 · Shared legal reasoning")
    st.write(
        "Leverages the shared Phi/Mistral/Gemma lineup (selected above) to summarise sanctions, PEP and licensing gates."
    )
    run_checks = st.button("⚖️ Run compliance pass", use_container_width=True)
    compliance_df = ss.get("legal_compliance_df")
    if run_checks:
        compliance_df = _run_compliance_checks(source_df)
        ts = datetime.now(timezone.utc).isoformat()
        ss["legal_compliance_df"] = compliance_df.copy()
        ss["credit_policy_df"] = compliance_df.copy()
        ss["legal_compliance_last_run_ts"] = ts
        ss["legal_compliance_status"] = "completed"
        st.success(
            f"Compliance sweep completed at {ts} using {ss['legal_compliance_llm_label']}. Stored in credit_policy_df for downstream use."
        )

    if isinstance(compliance_df, pd.DataFrame) and not compliance_df.empty:
        st.dataframe(compliance_df.head(12), use_container_width=True, height=340)
        st.download_button(
            "⬇️ Export compliance log",
            data=compliance_df.to_csv(index=False).encode("utf-8"),
            file_name=f"legal_compliance_{datetime.now():%Y%m%d-%H%M}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("Run the compliance pass to populate this stage.")


# ---------------------------------------------------------------------------
# STAGE 3 — HANDOFF
# ---------------------------------------------------------------------------
with st.container():
    st.subheader("Stage 3 · Handoff to Credit Appraisal")
    if isinstance(compliance_df, pd.DataFrame) and not compliance_df.empty:
        ready_count = len(compliance_df)
        st.success(f"{ready_count} compliance verdicts synchronized. Credit Appraisal can now layer policy checks.")
        st.markdown(
            """
            - 📘 [Launch Credit Appraisal](/credit_appraisal)  
            - ✅ ``credit_policy_df`` updated in session state  
            - 🧠 Selected LLM: `{label}` (`{model}`)
            """.format(
                label=ss.get("legal_compliance_llm_label"),
                model=ss.get("legal_compliance_llm_model"),
            )
        )
    else:
        st.warning("Generate compliance verdicts before attempting the handoff.")


# ---------------------------------------------------------------------------
# SHARED CHAT
# ---------------------------------------------------------------------------
FAQ = [
    "Stage 1 → What docs are mandatory for jurisdiction mapping?",
    "Stage 2 → How does the shared LLM justify a sanctions escalation?",
    "Stage 3 → What columns does Credit Appraisal read from credit_policy_df?",
    "Show the last 10 loans that failed compliance review.",
    "Show the last 10 loans cleared by compliance and their jurisdictions.",
    "What is the total count of loans escalated to legal over the past month?",
    "List the most recent suspect entities flagged in compliance runs.",
]
render_chat_assistant(
    page_id="legal_compliance",
    context=_build_chat_context(),
    title="💬 Compliance assistant",
    default_open=False,
    faq_questions=FAQ,
)


# ---------------------------------------------------------------------------
# FOOTER CONTROLS
# ---------------------------------------------------------------------------
st.divider()
footer_cols = st.columns([1, 1, 1, 2])
with footer_cols[0]:
    render_theme_toggle("🌗 Theme", key="legal_compliance_theme_footer")
with footer_cols[1]:
    if st.button("↩️ Back to Agents", use_container_width=True, key="legal_compliance_back_agents"):
        ss["stage"] = "agents"
        try:
            st.switch_page("app.py")
        except Exception:
            st.experimental_set_query_params(stage="agents")
            st.experimental_rerun()
with footer_cols[2]:
    if st.button("🏠 Back to Home", use_container_width=True, key="legal_compliance_back_home"):
        ss["stage"] = "landing"
        try:
            st.switch_page("app.py")
        except Exception:
            st.experimental_set_query_params(stage="landing")
            st.experimental_rerun()
st.markdown(
    "<h1 style='font-size:2.2rem;font-weight:700;'>🔥 Local/HF LLM (narratives + explainability)</h1>",
    unsafe_allow_html=True,
)
