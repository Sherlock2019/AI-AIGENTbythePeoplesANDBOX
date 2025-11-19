#!/usr/bin/env python3
"""
💳 Credit Scoring Agent (Stage-only orchestrator)
-----------------------------------------------
This Streamlit page mirrors the Asset Appraisal structure but focuses on the
credit scoring layer that sits between Anti-Fraud/KYC intake and the existing
credit appraisal agent. The UI keeps the flow lightweight (stages only) while
still wiring outputs back into ``st.session_state["credit_scored_df"]`` so the
main credit appraisal experience can pick up the latest results.

Each stage surfaces context to the embedded Gemma‑2 assistant so operators can
ask stage-aware questions directly from the page.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

import numpy as np
import pandas as pd
import streamlit as st

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
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# PAGE + SESSION INITIALIZATION
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Credit Scoring Agent", layout="wide")
ss = st.session_state


def _init_defaults() -> None:
    llm_lookup = get_llm_lookup()
    default_label = llm_lookup["labels"][0]
    ss.setdefault("stage", "credit_scoring_agent")
    ss.setdefault("credit_scoring_stage", "stages_only")
    ss.setdefault(
        "credit_scoring_user",
        ss.get("credit_user")
        or ss.get("asset_user")
        or ss.get("afk_user")
        or {"name": "Operator", "email": "operator@demo.local"},
    )
    ss.setdefault("credit_scoring_pending", 24)
    ss.setdefault("credit_scoring_flagged", 6)
    ss.setdefault("credit_scoring_avg_time", "8 min")
    ss.setdefault("credit_scoring_last_run_ts", None)
    ss.setdefault("credit_scoring_llm_label", default_label)
    ss.setdefault("credit_scoring_llm_model", llm_lookup["value_by_label"][default_label])
    ss.setdefault("credit_scoring_llm_score", 85.0)
    ss.setdefault("credit_scoring_status", "idle")
    ss.setdefault("credit_scoring_notes", [])


_init_defaults()
apply_global_theme(get_theme())


def _safe_switch(target: str) -> None:
    """Route back to main app stage safely."""
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
    stage = ss.get("stage", "credit_scoring_agent")
    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if st.button("🏠 Home", key=f"cs_nav_home_{stage}"):
            _safe_switch("landing")
    with c2:
        if st.button("🤖 Agents", key=f"cs_nav_agents_{stage}"):
            _safe_switch("agents")
    with c3:
        render_theme_toggle("🌗 Theme", key="credit_scoring_theme_toggle")


_render_nav()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def _coerce_minutes(value: Any, fallback: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch == ".")
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            pass
    return float(fallback)


def _select_source_dataframe() -> pd.DataFrame:
    """
    Pull the freshest dataframe created by Anti-Fraud/KYC. We check multiple
    well-known session keys before falling back to a synthetic dataset so the
    stage demo never blocks.
    """
    candidate_keys = [
        "credit_scoring_source_df",
        "afk_fraud_df",
        "afk_kyc_df",
        "afk_anonymized_df",
        "afk_intake_df",
    ]
    for key in candidate_keys:
        df = ss.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()

    # Synthetic fallback (mirrors the Asset template behaviour of always
    # keeping something on screen for demos).
    rng = np.random.default_rng(20251110)
    base = pd.DataFrame(
        {
            "customer_id": [f"CUST-{1000 + i}" for i in range(12)],
            "full_name": [
                "Amani Mbatha",
                "Lucas Alvarez",
                "Noor Al-Hassan",
                "Maya Chen",
                "Mateo Silva",
                "Yara Ibrahim",
                "Emilia Rossi",
                "Kwame Mensah",
                "Ines Dubois",
                "Sora Tanaka",
                "Hugo Jensen",
                "Priya Kapoor",
            ],
            "country": rng.choice(["NG", "ZA", "BR", "SG", "AE", "VN", "FR", "MX"], 12),
            "monthly_income": rng.integers(500, 9000, 12),
            "existing_loans": rng.integers(0, 4, 12),
            "fraud_probability": rng.uniform(0.01, 0.45, 12).round(3),
            "kyc_risk_score": rng.uniform(0.05, 0.65, 12).round(3),
            "bank_relationship_years": rng.integers(0, 15, 12),
        }
    )
    ss["credit_scoring_source_df"] = base.copy()
    return base


def _score_with_risk_ensemble(source_df: pd.DataFrame) -> pd.DataFrame:
    """Simulate the shared scoring ensemble (same features Asset uses)."""
    rng = np.random.default_rng(321)
    df = source_df.copy()
    if "kyc_risk_score" not in df:
        df["kyc_risk_score"] = rng.uniform(0.05, 0.6, len(df)).round(3)
    if "fraud_probability" not in df:
        df["fraud_probability"] = rng.uniform(0.01, 0.4, len(df)).round(3)

    # Derived credit features
    df["debt_to_income"] = np.clip(
        (df.get("existing_loans", 0) * 0.12) + (df.get("monthly_income", 1) / 10000),
        0.05,
        0.95,
    ).round(3)
    df["utilization_ratio"] = rng.uniform(0.1, 0.92, len(df)).round(3)
    df["credit_score"] = (
        780
        - (df["kyc_risk_score"] * 220)
        - (df["fraud_probability"] * 180)
        - (df["debt_to_income"] * 140)
        + rng.normal(0, 25, len(df))
    )
    df["credit_score"] = df["credit_score"].clip(320, 875).round().astype(int)
    df["recommendation"] = np.where(
        df["credit_score"] >= 680,
        "✅ Pre-Approve",
        np.where(df["credit_score"] >= 620, "🕵️ Manual Review", "❌ Decline"),
    )
    df["ensemble_stage_notes"] = [
        f"Stage {idx%3 + 1}: Shared model flagged DTI={d:.2f}, risk={r:.2f}"
        for idx, (d, r) in enumerate(zip(df["debt_to_income"], df["kyc_risk_score"]))
    ]
    df["stage"] = "Credit Scoring"
    return df


def _build_chat_context() -> Dict[str, Any]:
    ctx = {
        "agent_type": "credit_scoring",
        "stage": ss.get("credit_scoring_stage"),
        "user": (ss.get("credit_scoring_user") or {}).get("name"),
        "pending_cases": ss.get("credit_scoring_pending"),
        "flagged_cases": ss.get("credit_scoring_flagged"),
        "avg_time": ss.get("credit_scoring_avg_time"),
        "ai_performance": ss.get("credit_ai_performance") or 0.92,
        "last_run": ss.get("credit_scoring_last_run_ts"),
        "status": ss.get("credit_scoring_status"),
        "llm_model": ss.get("credit_scoring_llm_model"),
        "llm_label": ss.get("credit_scoring_llm_label"),
        "ollama_url": os.getenv("OLLAMA_URL", f"http://localhost:{os.getenv('GEMMA_PORT', '7001')}"),
    }
    return {k: v for k, v in ctx.items() if v not in (None, "", [])}


# ---------------------------------------------------------------------------
# HEADER + STAGE OVERVIEW
# ---------------------------------------------------------------------------
pal = get_palette()
render_operator_banner(
    operator_name=(ss["credit_scoring_user"] or {}).get("name", "Operator"),
    title="Credit Scoring Agent",
    summary="Bridges Anti-Fraud/KYC evidence into the shared scoring ensemble (same lineup as Asset) so Credit Appraisal inherits consistent signals.",
    bullets=[
        "Stage 1 → sync Anti-Fraud/KYC verdicts & trust signals",
        "Stage 2 → Shared LLM scoring ensemble (Phi/Mistral/Gemma/etc.)",
        "Stage 3 → push normalized credit scores into Credit Appraisal",
    ],
    metrics=[
        {"label": "Pending apps", "value": ss.get("credit_scoring_pending"), "delta": "+4 vs yesterday"},
        {"label": "Flagged queue", "value": ss.get("credit_scoring_flagged"), "delta": "-2 risk hits"},
        {"label": "Avg SLA", "value": ss.get("credit_scoring_avg_time"), "delta": "‑11%"},
    ],
)

source_df = _select_source_dataframe()
fraud_hits = int((source_df.get("fraud_probability", 0) > 0.25).sum())
kyc_feeds = len(source_df)
agreement_pct = float(ss.get("credit_ai_performance", 0.92) or 0.92) * 100
agreement_pct = max(0, min(100, agreement_pct))

refresh_age_val = 12.0
ts = ss.get("credit_scoring_last_run_ts")
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

llm_score_value = float(ss.get("credit_scoring_llm_score", telemetry["agreement"]) or telemetry["agreement"])
llm_score_value = max(0.0, min(100.0, llm_score_value))
ss["credit_scoring_llm_score"] = llm_score_value

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
    with st.expander("🧠 Local/HF lineup (shared with Asset)", expanded=False):
        st.dataframe(hf_models_df, use_container_width=True)
        c1, c2 = st.columns([1.2, 1])
        labels = llm_lookup_ui["labels"]
        value_by_label = llm_lookup_ui["value_by_label"]
        hint_by_label = llm_lookup_ui["hint_by_label"]
        saved_label = ss.get("credit_scoring_llm_label", labels[0])
        if saved_label not in labels:
            saved_label = labels[0]
        with c1:
            selected_label = st.selectbox(
                "🔥 Local/HF LLM (narratives + explainability)",
                labels,
                index=labels.index(saved_label),
                key="credit_scoring_llm_label",
            )
            st.caption(f"Hint: {hint_by_label[selected_label]}")
        with c2:
            flavor = st.selectbox(
                "OpenStack flavor / host profile",
                list(OPENSTACK_FLAVORS.keys()),
                index=0,
                key="credit_scoring_flavor",
            )
            st.caption(OPENSTACK_FLAVORS[flavor])
        ss["credit_scoring_llm_model"] = value_by_label[selected_label]

OPENSTACK_FLAVORS = {
    "m4.medium": "4 vCPU / 8 GB RAM (CPU-only small)",
    "m8.large": "8 vCPU / 16 GB RAM (CPU-only medium)",
    "g1.a10.1": "8 vCPU / 32 GB RAM + 1×A10 24 GB",
    "g1.l40.1": "16 vCPU / 64 GB RAM + 1×L40 48 GB",
    "g2.a100.1": "24 vCPU / 128 GB RAM + 1×A100 80 GB",
}
selected_llm = render_llm_selector(context="credit_scoring")
ss["credit_scoring_llm_label"] = selected_llm["model"]
ss["credit_scoring_llm_model"] = selected_llm["value"]

flavor = st.selectbox(
    "OpenStack flavor / host profile",
    list(OPENSTACK_FLAVORS.keys()),
    index=0,
    key="credit_scoring_flavor",
)
st.caption(OPENSTACK_FLAVORS[flavor])

st.markdown("### Stage-Only Flow")
st.caption("Every control below corresponds to one stage in the risk ladder. Run them top-to-bottom to keep downstream agents in sync.")


# ---------------------------------------------------------------------------
# STAGE 1 — INTAKE
# ---------------------------------------------------------------------------
with st.container():
    st.subheader("Stage 1 · Anti-Fraud & KYC intake")
    st.write(
        "Pull the freshest applicant dossier from the Anti-Fraud/KYC agent. "
        "We persist the snapshot locally so operators can re-score without hitting external systems."
    )
    col_left, col_right = st.columns([3, 1], gap="large")
    with col_left:
        st.dataframe(
            source_df.head(15),
            use_container_width=True,
            height=360,
        )
    with col_right:
        st.metric("Rows available", len(source_df))
        st.metric(
            "High fraud suspicion",
            int((source_df.get("fraud_probability", 0) > 0.35).sum()),
        )
        st.metric(
            "Avg KYC risk",
            f"{source_df.get('kyc_risk_score', pd.Series(dtype=float)).mean():.2f}" if "kyc_risk_score" in source_df else "—",
        )
        if st.button("🔄 Refresh from Anti-Fraud/KYC", use_container_width=True):
            ss["credit_scoring_source_df"] = source_df.copy()
            ss["credit_scoring_status"] = "refreshed"
            st.success("Source snapshot refreshed from session state / fallback dataset.")


# ---------------------------------------------------------------------------
# STAGE 2 — SHARED CREDIT SCORING ENSEMBLE
# ---------------------------------------------------------------------------
with st.container():
    st.subheader("Stage 2 · Shared scoring ensemble")
    st.write(
        "Uses the shared Phi/Mistral/Gemma lineup (selected above) to derive a normalized credit score per applicant. "
        "Outputs land both in this page and in ``credit_scored_df`` for the main credit agent."
    )

    scored_df = ss.get("credit_scoring_df")
    run_scoring = st.button("🚀 Run scoring ensemble", use_container_width=True)
    if run_scoring or (isinstance(scored_df, pd.DataFrame) and not scored_df.empty):
        if run_scoring:
            scored_df = _score_with_risk_ensemble(source_df)
            ts = datetime.now(timezone.utc).isoformat()
            ss["credit_scoring_df"] = scored_df.copy()
            ss["credit_scored_df"] = scored_df.copy()
            ss["credit_scoring_last_run_ts"] = ts
            ss["credit_scoring_status"] = "completed"
            st.success(f"Scoring ensemble completed at {ts} using {ss['credit_scoring_llm_label']}. Results piped to Credit Appraisal.")

        if isinstance(scored_df, pd.DataFrame) and not scored_df.empty:
            st.dataframe(scored_df.head(15), use_container_width=True, height=360)
            st.download_button(
                "⬇️ Export scored applicants",
                data=scored_df.to_csv(index=False).encode("utf-8"),
                file_name=f"credit_scoring_{datetime.now():%Y%m%d-%H%M}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.warning("Run the scoring ensemble to populate this stage.")
    else:
        st.info("Click the button above to trigger the scoring ensemble.")


# ---------------------------------------------------------------------------
# STAGE 3 — HANDOFF TO CREDIT APPRAISAL
# ---------------------------------------------------------------------------
with st.container():
    st.subheader("Stage 3 · Push to Credit Appraisal Agent")
    st.write(
        "Normalize schema + send the staged dataframe to the existing credit appraisal workflow. "
        "Any downstream Streamlit tab that relies on ``credit_scored_df`` will instantly see the new values."
    )
    scored_df = ss.get("credit_scoring_df")
    if isinstance(scored_df, pd.DataFrame) and not scored_df.empty:
        st.success(
            f"{len(scored_df)} applicants ready. Open the Credit Appraisal page to continue the multi-stage review."
        )
        st.markdown(
            """
            - 📘 [Launch Credit Appraisal](/credit_appraisal)  
            - 🧾 `credit_scored_df` updated in session state  
            - ✅ Selected LLM: `{label}` (`{model}`) | Endpoint: `{endpoint}`
            """.format(
                label=ss.get("credit_scoring_llm_label"),
                model=ss.get("credit_scoring_llm_model"),
                endpoint=os.getenv("OLLAMA_URL", f"http://localhost:{os.getenv('GEMMA_PORT', '7001')}"),
            )
        )
    else:
        st.warning("Run Stage 2 before attempting the handoff.")


# ---------------------------------------------------------------------------
# GEMMA CHAT (STAGE-AWARE)
# ---------------------------------------------------------------------------
CHAT_FAQ = [
    "Stage 1 → how do we trust the KYC feed?",
    "Stage 2 → what features influence the scoring ensemble the most?",
    "Stage 3 → what schema is required by Credit Appraisal?",
    "List the last 10 applicants scored and their PD.",
    "Show the last 10 loans the scoring model recommended declining.",
    "Show the last 10 loans the scoring model approved along with score bands.",
    "What volume of loans were scored in the past month?",
]
render_chat_assistant(
    page_id="credit_scoring",
    context=_build_chat_context(),
    title="💬 Shared LLM stage assistant",
    default_open=False,
    faq_questions=CHAT_FAQ,
)


# ---------------------------------------------------------------------------
# FOOTER CONTROLS
# ---------------------------------------------------------------------------
st.divider()
cols = st.columns([1, 1, 1, 2])
with cols[0]:
    render_theme_toggle("🌗 Theme", key="credit_scoring_theme_footer")
with cols[1]:
    if st.button("↩️ Back to Agents", use_container_width=True, key="credit_scoring_back_agents"):
        ss["stage"] = "agents"
        try:
            st.switch_page("app.py")
        except Exception:
            st.experimental_set_query_params(stage="agents")
            st.experimental_rerun()
with cols[2]:
    if st.button("🏠 Back to Home", use_container_width=True, key="credit_scoring_back_home"):
        ss["stage"] = "landing"
        try:
            st.switch_page("app.py")
        except Exception:
            st.experimental_set_query_params(stage="landing")
            st.experimental_rerun()
