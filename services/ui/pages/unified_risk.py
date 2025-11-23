#!/usr/bin/env python3
"""Streamlit dashboard for the Unified Risk Orchestration agent."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Any
from copy import deepcopy

import pandas as pd
import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
from services.ui.theme_manager import apply_theme, render_theme_toggle
from services.ui.components.feedback import render_feedback_tab
# Try to import chat_assistant component if available
try:
    from services.ui.components.chat_assistant import render_chat_assistant
except ImportError:
    render_chat_assistant = None

st.set_page_config(page_title="🧩 Unified Risk Orchestration Agent", layout="wide")
apply_theme()

API_URL = os.getenv("AGENT_API_URL", "http://localhost:8090")


def _go_stage(target: str):
    """Navigate to a different stage/page."""
    try:
        st.switch_page("app.py")
    except Exception:
        try:
            st.query_params["stage"] = target
        except Exception:
            pass
        st.rerun()


def render_nav_bar():
    """Top navigation bar with Home, Agents, and Theme switch."""
    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if st.button("🏠 Back to Home", key="btn_home_unified_risk", use_container_width=True):
            _go_stage("landing")
            st.stop()
    with c2:
        if st.button("🤖 Back to Agents", key="btn_agents_unified_risk", use_container_width=True):
            _go_stage("agents")
            st.stop()
    with c3:
        render_theme_toggle(
            label="🌗 Dark mode",
            key="unified_risk_nav_theme",
            help="Switch theme",
        )
    st.markdown("---")

SAMPLE_UNIFIED_RUNS = [
    {
        "run_id": "RUN-20251110-001",
        "decision": {
            "borrower_id": "BORR-001",
            "loan_id": "LN-1001",
            "loan_amount": 150000,
            "generated_at": "2025-11-10T06:39:18.105237+00:00",
            "asset": {
                "fmv": 250000,
                "ai_adjusted": 235000,
                "realizable_value": 210000,
                "encumbrance_flags": [],
            },
            "fraud": {
                "risk_score": 0.20,
                "risk_tier": "low",
                "sanction_hits": [],
                "kyc_passed": True,
            },
            "credit": {
                "credit_score": 720,
                "probability_default": 0.08,
                "approval": "approve",
                "ndi": 1.4,
            },
            "metadata": {
                "submitted_from": "sample",
                "asset_city": "San Jose",
                "asset_type": "Residential",
            },
        },
        "risk_summary": {
            "aggregated_score": 0.871,
            "risk_tier": "low",
            "recommendation": "approve",
        },
    },
    {
        "run_id": "RUN-20251109-004",
        "decision": {
            "borrower_id": "BORR-007",
            "loan_id": "LN-2045",
            "loan_amount": 420000,
            "generated_at": "2025-11-09T12:10:05.200000+00:00",
            "asset": {
                "fmv": 480000,
                "ai_adjusted": 450000,
                "realizable_value": 390000,
                "encumbrance_flags": ["Secondary lien"],
            },
            "fraud": {
                "risk_score": 0.42,
                "risk_tier": "medium",
                "sanction_hits": ["Internal_watchlist"],
                "kyc_passed": True,
            },
            "credit": {
                "credit_score": 655,
                "probability_default": 0.19,
                "approval": "review",
                "ndi": 0.95,
            },
            "metadata": {
                "submitted_from": "sample",
                "asset_city": "Los Angeles",
                "asset_type": "Multifamily",
            },
        },
        "risk_summary": {
            "aggregated_score": 0.62,
            "risk_tier": "medium",
            "recommendation": "review",
        },
    },
    {
        "run_id": "RUN-20251108-003",
        "decision": {
            "borrower_id": "BORR-021",
            "loan_id": "LN-3002",
            "loan_amount": 90000,
            "generated_at": "2025-11-08T08:55:40.000000+00:00",
            "asset": {
                "fmv": 100000,
                "ai_adjusted": 92000,
                "realizable_value": 70000,
                "encumbrance_flags": ["Pending tax lien"],
            },
            "fraud": {
                "risk_score": 0.68,
                "risk_tier": "high",
                "sanction_hits": [],
                "kyc_passed": False,
            },
            "credit": {
                "credit_score": 605,
                "probability_default": 0.27,
                "approval": "reject",
                "ndi": 0.65,
            },
            "metadata": {
                "submitted_from": "sample",
                "asset_city": "Houston",
                "asset_type": "Industrial",
            },
        },
        "risk_summary": {
            "aggregated_score": 0.41,
            "risk_tier": "high",
            "recommendation": "reject",
        },
    },
]

ss = st.session_state
ss.setdefault("unified_runs", [])
ss.setdefault("selected_unified_index", 0)
ss.setdefault("prefill_unified_form", None)
if not ss.unified_runs:
    ss.unified_runs = deepcopy(SAMPLE_UNIFIED_RUNS)
    ss["unified_demo_loaded"] = True
else:
    ss.setdefault("unified_demo_loaded", False)


def _call_unified_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_URL.rstrip('/')}/v1/unified/decision"
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _render_gauge(title: str, value: float, min_val: float, max_val: float, suffix: str = "", key: str | None = None):
    span = max_val - min_val
    if span <= 0:
        max_val = value if value else 1
        min_val = 0
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": suffix},
            title={"text": title},
            gauge={
                "axis": {"range": [min_val, max_val]},
                "bar": {"color": "#38bdf8"},
                "bgcolor": "#0f172a",
                "borderwidth": 1,
                "bordercolor": "#1e293b",
            },
        )
    )
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key or title)


def _flatten_for_table(value: Any, parent_key: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, val in value.items():
            new_key = f"{parent_key}.{key}" if parent_key else key
            rows.extend(_flatten_for_table(val, new_key))
    elif isinstance(value, list):
        if not value:
            rows.append((parent_key or "[]", "[]"))
        else:
            for idx, item in enumerate(value):
                new_key = f"{parent_key}[{idx}]" if parent_key else f"[{idx}]"
                rows.extend(_flatten_for_table(item, new_key))
    else:
        rows.append((parent_key or "value", value))
    return rows


def _dict_to_table(data: Dict[str, Any]) -> pd.DataFrame:
    rows = _flatten_for_table(data)
    return pd.DataFrame(rows, columns=["Field", "Value"])


def _build_runs_dataframe(runs: list[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for idx, record in enumerate(runs):
        decision = record["decision"]
        summary = record["risk_summary"]
        fraud = decision.get("fraud", {})
        asset = decision.get("asset", {})
        credit = decision.get("credit", {})
        generated_raw = decision.get("generated_at") or record.get("generated_at")
        generated_dt = None
        if generated_raw:
            try:
                generated_dt = datetime.fromisoformat(generated_raw)
            except Exception:
                generated_dt = None
        loan_amount = decision.get("loan_amount") or decision.get("metadata", {}).get("loan_amount")
        ai_adjusted = asset.get("ai_adjusted") or asset.get("fmv") or 1
        ltv = None
        if loan_amount and ai_adjusted:
            try:
                ltv = loan_amount / ai_adjusted
            except ZeroDivisionError:
                ltv = None
        rows.append(
            {
                "index": idx,
                "run_id": record.get("run_id"),
                "borrower": decision.get("borrower_id"),
                "loan_id": decision.get("loan_id"),
                "generated": generated_dt,
                "aggregated_score": summary.get("aggregated_score"),
                "risk_tier": summary.get("risk_tier", "").lower(),
                "recommendation": summary.get("recommendation", "").lower(),
                "fraud_score": fraud.get("risk_score"),
                "fraud_tier": fraud.get("risk_tier", ""),
                "credit_score": credit.get("credit_score"),
                "credit_pd": credit.get("probability_default"),
                "credit_approval": credit.get("approval", ""),
                "asset_fmv": asset.get("fmv"),
                "asset_ai": ai_adjusted,
                "asset_realizable": asset.get("realizable_value"),
                "ltv": ltv,
                "loan_amount": loan_amount,
                "asset_city": decision.get("metadata", {}).get("asset_city", "Unknown"),
                "asset_type": decision.get("metadata", {}).get("asset_type", "Unknown"),
                "record": record,
            }
        )
    df = pd.DataFrame(rows)
    return df


def _launch_page(target: str):
    mapping = {
        "app": "app.py",
        "agent_template": "pages/agent_template.py",
        "anti_fraud": "pages/anti_fraud_kyc.py",
        "asset": "pages/asset_appraisal.py",
        "credit": "pages/credit_appraisal.py",
        "troubleshooter": "pages/troubleshooter_agent.py",
        "unified": "pages/unified_risk.py",
    }
    page = mapping.get(target)
    if not page:
        return
    try:
        st.switch_page(page)
    except Exception:
        pass


render_nav_bar()

st.title("🧩 Unified Risk Orchestration Agent")
st.caption(
    "Master coordinator that compounds Asset, Credit, and Anti-Fraud agents into a single bank-grade decision package."
)

# Auto-show dashboard if demo data was loaded
if ss.get("unified_demo_loaded") and ss.get("unified_runs"):
    st.info("💡 Demo data loaded automatically. Dashboard shows sample unified risk decisions.")

nav_cols = st.columns([1, 1, 1, 1, 1])
with nav_cols[0]:
    if st.button("🏠 Home", use_container_width=True):
        _launch_page("app")
with nav_cols[1]:
    if st.button("🏦 Asset", use_container_width=True):
        _launch_page("asset")
with nav_cols[2]:
    if st.button("💳 Credit", use_container_width=True):
        _launch_page("credit")
with nav_cols[3]:
    if st.button("🛡️ Anti-Fraud", use_container_width=True):
        _launch_page("anti_fraud")
with nav_cols[4]:
    render_theme_toggle(key="unified_theme_toggle")

# Add tabs for better organization
tab_dashboard, tab_feedback = st.tabs([
    "📊 Dashboard",
    "🗣️ Feedback & Feature Requests"
])

with tab_dashboard:
    st.markdown(
        """
        > **Unified Risk Checklist**  
        > ✅ Is the borrower real & safe? (KYC/Fraud)  
        > ✅ Is the collateral worth enough? (Asset)  
        > ✅ Can they afford the loan? (Credit)  
        > ✅ Should the bank approve overall? (Unified agent)
        """
    )

    with st.expander("ℹ️ How this agent works", expanded=False):
        st.markdown(
            """
            **Step 1 — Portfolio Triage**
            * Start at **Global Portfolio Overview** to review high-risk cases, trendlines, and recommendation mix.
            * Use **Open Case** on any flagged borrower to jump straight into their unified summary.

            **Step 2 — Borrower Case Summary**
            * Review the KPI row (recommendation, aggregated score, tier, credit approval, fraud tier, collateral status).
            * Inspect the gauges (FMV, fraud score, credit score) and the mini status panels for asset, fraud/KYC, and credit.

            **Step 3 — Drill-Down**
            * Expand Asset / Fraud / Credit panels for detailed metrics, risk flags, and raw tables.
            * Download the full `unified_risk_decision.json` if you need to attach it to credit committee notes.

            **Step 4 — Take Action**
            * Click **Re-run this borrower** to prefill the submission form with the current data.
            * Scroll to **Submit A Unified Run**, adjust any values, and regenerate the unified decision.
            """
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Identity", "KYC/Fraud", "Is borrower real & safe?")
    with c2:
        st.metric("Collateral", "Asset", "Is the collateral worth enough?")
    with c3:
        st.metric("Credit", "Loan", "Can they afford it?")
    with c4:
        st.metric("Unified", "Decision", "Approve / Review / Reject")

    st.divider()

    st.divider()
    st.header("Global Portfolio Overview")
if not ss.unified_runs:
    st.info("No unified runs yet. Submit the form above to generate your first decision.")
else:
    runs_df = _build_runs_dataframe(ss.unified_runs)
    total_borrowers = len(runs_df)
    avg_portfolio_score = runs_df["aggregated_score"].mean()
    rec_counts = runs_df["recommendation"].value_counts(normalize=True)
    approve_pct = rec_counts.get("approve", 0.0)
    review_pct = rec_counts.get("review", 0.0)
    reject_pct = rec_counts.get("reject", 0.0)
    high_risk_count = (runs_df["risk_tier"] == "high").sum()
    avg_pd = runs_df["credit_pd"].mean()
    avg_ltv = runs_df["ltv"].mean(skipna=True)
    avg_realizable = runs_df["asset_realizable"].mean()

    kpi_row1 = st.columns(4)
    kpi_row1[0].metric("Total Active Borrowers", total_borrowers)
    kpi_row1[1].metric("Portfolio Aggregated Score", f"{avg_portfolio_score:.2f}" if pd.notna(avg_portfolio_score) else "—")
    kpi_row1[2].metric("High-Risk Borrowers", int(high_risk_count))
    kpi_row1[3].metric("Avg PD", f"{avg_pd:.1%}" if pd.notna(avg_pd) else "—")

    kpi_row2 = st.columns(3)
    kpi_row2[0].metric("% Approve / Review / Reject", f"{approve_pct:.0%} / {review_pct:.0%} / {reject_pct:.0%}")
    kpi_row2[1].metric("Avg Loan-to-Value", f"{avg_ltv:.2f}x" if pd.notna(avg_ltv) else "—")
    kpi_row2[2].metric("Avg Realizable Value", f"${avg_realizable:,.0f}" if pd.notna(avg_realizable) else "—")

    chart_cols = st.columns(3)
    with chart_cols[0]:
        st.caption("Aggregated Score Trend")
        trend_df = runs_df.dropna(subset=["generated", "aggregated_score"]).sort_values("generated")
        if not trend_df.empty:
            fig_trend = px.line(trend_df, x="generated", y="aggregated_score", markers=True)
            fig_trend.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=0))
            st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("More runs needed for a trendline.")
    with chart_cols[1]:
        st.caption("Recommendation Mix")
        status_counts = runs_df["recommendation"].value_counts().reset_index()
        status_counts.columns = ["Recommendation", "Count"]
        if not status_counts.empty:
            fig_mix = px.bar(status_counts, x="Recommendation", y="Count", color="Recommendation")
            fig_mix.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=0))
            st.plotly_chart(fig_mix, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No recommendations yet.")
    with chart_cols[2]:
        st.caption("Heatmap by City")
        heat_df = runs_df.groupby(["asset_city", "recommendation"]).size().reset_index(name="count")
        if not heat_df.empty:
            fig_heat = px.density_heatmap(heat_df, x="recommendation", y="asset_city", z="count", color_continuous_scale="Blues")
            fig_heat.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=0))
            st.plotly_chart(fig_heat, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Need more cases for heatmap.")

    st.subheader("Top 10 High-Risk Cases")
    priority_map = {"high": 3, "medium": 2, "low": 1}
    runs_df["risk_rank"] = runs_df["risk_tier"].map(priority_map).fillna(0)
    high_risk_df = runs_df.sort_values(["risk_rank", "credit_pd", "fraud_score"], ascending=[False, False, False]).head(10)
    if high_risk_df.empty:
        st.info("No high-risk cases yet.")
    else:
        header_cols = st.columns([1.1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.8])
        header_cols[0].markdown("**Borrower ID**")
        header_cols[1].markdown("**Risk Score**")
        header_cols[2].markdown("**Risk Tier**")
        header_cols[3].markdown("**PD**")
        header_cols[4].markdown("**Fraud Score**")
        header_cols[5].markdown("**Recommendation**")
        header_cols[6].markdown("**Action**")
        for _, row in high_risk_df.iterrows():
            cols = st.columns([1.1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.8])
            borrower_label = f"**{row['borrower']}**" if isinstance(row["borrower"], str) else "—"
            tier_label = row["risk_tier"].title() if isinstance(row["risk_tier"], str) else "Unknown"
            reco_label = row["recommendation"].upper() if isinstance(row["recommendation"], str) else "N/A"
            cols[0].markdown(borrower_label)
            cols[1].write(f"{row['aggregated_score']:.2f}" if pd.notna(row['aggregated_score']) else "—")
            cols[2].write(tier_label)
            cols[3].write(f"{row['credit_pd']:.1%}" if pd.notna(row['credit_pd']) else "—")
            cols[4].write(f"{row['fraud_score']:.2f}" if pd.notna(row['fraud_score']) else "—")
            cols[5].write(reco_label)
            if cols[6].button("Open Case", key=f"open_{row['index']}"):
                ss.selected_unified_index = int(row["index"])
                st.session_state["unified_case_selector"] = ss.selected_unified_index
                st.rerun()

st.divider()
st.header("Borrower Unified Case Summary")
if not ss.unified_runs:
    st.info("Generate a decision to unlock borrower insights.")
else:
    options = list(range(len(ss.unified_runs)))
    current_idx = min(ss.selected_unified_index, len(options) - 1)

    selector_key = "unified_case_selector"
    if selector_key not in st.session_state:
        st.session_state[selector_key] = current_idx
    elif ss.selected_unified_index != st.session_state[selector_key]:
        st.session_state[selector_key] = current_idx

    selected_idx = st.selectbox(
        "Select Borrower",
        options,
        index=st.session_state[selector_key],
        format_func=lambda idx: f"{ss.unified_runs[idx]['decision']['borrower_id']} — {ss.unified_runs[idx]['risk_summary']['recommendation'].upper()}",
        key=selector_key,
    )
    ss.selected_unified_index = selected_idx
    selected_record = ss.unified_runs[selected_idx]
    decision = selected_record["decision"]
    summary = selected_record["risk_summary"]
    fraud = decision.get("fraud", {})
    asset = decision.get("asset", {})
    credit = decision.get("credit", {})

    flag_messages = []
    if asset.get("encumbrance_flags"):
        flag_messages.append("Encumbrance alerts")
    if fraud.get("sanction_hits"):
        flag_messages.append("Sanction list hits")
    if not fraud.get("kyc_passed", True):
        flag_messages.append("KYC review required")
    if fraud.get("risk_score", 0) >= 0.5:
        flag_messages.append("Fraud risk elevated")
    if credit.get("probability_default", 0) >= 0.2:
        flag_messages.append("High probability of default")
    if asset.get("realizable_value") and decision.get("loan_amount"):
        coverage = asset["realizable_value"] / decision["loan_amount"] if decision["loan_amount"] else None
        if coverage and coverage < 1:
            flag_messages.append("Collateral below loan amount")
    flags_text = ", ".join(flag_messages) if flag_messages else "All systems normal."

    st.markdown(
        f"**Borrower:** `{decision.get('borrower_id', '—')}` &nbsp;&nbsp; | &nbsp;&nbsp; "
        f"**Loan ID:** `{decision.get('loan_id', '—')}` &nbsp;&nbsp; | &nbsp;&nbsp; "
        f"**Decision Generated:** `{decision.get('generated_at', 'n/a')}`"
    )

    badge_cols = st.columns(6)
    badge_cols[0].metric("Recommendation", summary.get("recommendation", "").upper())
    badge_cols[1].metric("Aggregated Score", f"{summary.get('aggregated_score', 0):.2f}")
    badge_cols[2].metric("Unified Risk Tier", summary.get("risk_tier", "").title())
    badge_cols[3].metric("Credit Approval", credit.get("approval", "").upper())
    badge_cols[4].metric("Fraud Tier", fraud.get("risk_tier", "n/a").title())
    collateral_label = (
        "Encumbrance" if asset.get("encumbrance_flags") else "Clear"
    )
    badge_cols[5].metric("Collateral Status", collateral_label)

    st.info(f"**Summary Flags:** {flags_text}")

    gauge_cols = st.columns(3)
    asset_ai = asset.get("ai_adjusted") or asset.get("fmv") or 0
    asset_cap = max((asset.get("fmv") or 0) * 1.2, asset_ai or 1)
    with gauge_cols[0]:
        _render_gauge(
            "AI-Adjusted FMV",
            asset_ai,
            0,
            asset_cap,
            suffix=" USD",
            key=f"gauge_asset_ai_{selected_record['run_id']}",
        )
    with gauge_cols[1]:
        _render_gauge(
            "Fraud Risk Score",
            fraud.get("risk_score", 0.0),
            0,
            1,
            key=f"gauge_fraud_score_{selected_record['run_id']}",
        )
    with gauge_cols[2]:
        _render_gauge(
            "Credit Score",
            credit.get("credit_score", 0),
            300,
            900,
            key=f"gauge_credit_score_{selected_record['run_id']}",
        )

    panels = st.columns(3)
    with panels[0]:
        st.subheader("Asset Status")
        st.write(f"FMV: ${asset.get('fmv', 0):,.0f}")
        st.write(f"AI Adjusted: ${asset_ai:,.0f}")
        st.write(f"Realizable: ${asset.get('realizable_value', 0):,.0f}")
        st.write("Encumbrances: " + (", ".join(asset.get("encumbrance_flags", [])) or "None"))
    with panels[1]:
        st.subheader("Fraud Status")
        st.write(f"Risk Score: {fraud.get('risk_score', 0):.2f} ({fraud.get('risk_tier', 'n/a')})")
        st.write(f"KYC Passed: {'Yes' if fraud.get('kyc_passed', True) else 'No'}")
        st.write("Sanction Hits: " + (", ".join(fraud.get("sanction_hits", [])) or "None"))
    with panels[2]:
        st.subheader("Credit Status")
        st.write(f"Credit Score: {credit.get('credit_score', 0)}")
        st.write(f"PD: {credit.get('probability_default', 0):.1%}")
        st.write(f"NDI: {credit.get('ndi', 'n/a')}")
        st.write(f"Approval: {credit.get('approval', 'n/a').upper()}")

    st.divider()
    st.header("Drill-Down Details")
    with st.expander("Asset Drill-Down", True):
        kpi_cols = st.columns(3)
        kpi_cols[0].metric("FMV", f"${asset.get('fmv', 0):,.0f}")
        kpi_cols[1].metric("AI Adjusted", f"${(asset.get('ai_adjusted') or asset.get('fmv') or 0):,.0f}")
        kpi_cols[2].metric("Realizable Value", f"${asset.get('realizable_value', 0):,.0f}")

        st.subheader("Encumbrance Flags")
        enc_flags = asset.get("encumbrance_flags", []) or []
        if not enc_flags:
            st.success("✅ No encumbrances detected.")
        else:
            for flag in enc_flags:
                st.error(f"❌ {flag}")

        st.subheader("Valuation Details")
        metadata = decision.get("metadata", {})
        valuation_details = [
            ("Confidence Score", asset.get("confidence_score", "n/a")),
            ("Asset Type", metadata.get("asset_type", "n/a")),
            ("Condition", asset.get("condition", metadata.get("asset_condition", "n/a"))),
            ("Location", metadata.get("asset_city", "n/a")),
            ("Comps Used", ", ".join(asset.get("comps", [])) or "Not provided"),
            ("Evidence Quality", asset.get("evidence_quality", "Not provided")),
            ("Valuation Comments", asset.get("valuation_comment", "No adjustments recorded.")),
        ]
        st.table(pd.DataFrame(valuation_details, columns=["Item", "Description"]))

        asset_lat = asset.get("lat") or metadata.get("asset_lat")
        asset_lon = asset.get("lon") or metadata.get("asset_lon")
        if asset_lat and asset_lon:
            st.map(pd.DataFrame({"lat": [asset_lat], "lon": [asset_lon]}))

        with st.expander("🔍 Raw Asset Data", False):
            st.table(_dict_to_table(asset))
    with st.expander("Fraud / KYC Drill-Down", True):
        st.subheader("🕵️ Fraud & KYC Risks")
        fraud_cols = st.columns([1.2, 1, 1, 1])
        with fraud_cols[0]:
            _render_gauge(
                "Fraud Risk Score",
                fraud.get("risk_score", 0.0),
                0,
                1,
                key=f"gauge_fraud_drill_{selected_record['run_id']}",
            )
        with fraud_cols[1]:
            tier = (fraud.get("risk_tier") or "n/a").title()
            tier_color = {"Low": "🟩 Low", "Medium": "🟧 Medium", "High": "🟥 High"}.get(tier, tier)
            st.metric("Fraud Tier", tier_color)
        with fraud_cols[2]:
            st.metric("Sanction Hits", len(fraud.get("sanction_hits", [])))
        with fraud_cols[3]:
            kyc_passed = fraud.get("kyc_passed", True)
            st.metric("KYC Passed", "✅ Yes" if kyc_passed else "❌ No")

        hits = fraud.get("sanction_hits", [])
        if hits:
            chips = " ".join(f"`{hit}`" for hit in hits)
            st.warning(f"Sanctions: {chips}")
        else:
            st.success("No sanction hits on record.")

        with st.expander("🔍 Raw Fraud Data", False):
            st.table(_dict_to_table(fraud))

    with st.expander("Credit Drill-Down", True):
        st.subheader("💳 Credit Risk Details")
        credit_cols = st.columns([1.2, 1, 1, 1])
        with credit_cols[0]:
            _render_gauge(
                "Credit Score",
                credit.get("credit_score", 0),
                300,
                900,
                key=f"gauge_credit_drill_{selected_record['run_id']}",
            )
        with credit_cols[1]:
            st.metric("Probability of Default", f"{credit.get('probability_default', 0):.1%}")
        with credit_cols[2]:
            ndi_val = credit.get("ndi")
            ndi_display = f"{ndi_val:.2f}" if isinstance(ndi_val, (int, float)) else ndi_val or "n/a"
            st.metric("NDI", ndi_display)
        with credit_cols[3]:
            approval = (credit.get("approval") or "n/a").upper()
            badge = {
                "APPROVE": "🟩 APPROVE",
                "REVIEW": "🟧 REVIEW",
                "REJECT": "🟥 REJECT",
            }.get(approval, approval)
            st.metric("Approval Status", badge)

        with st.expander("🔍 Raw Credit Data", False):
            st.table(_dict_to_table(credit))
    with st.expander("Full Unified Decision Data", True):
        st.table(_dict_to_table(decision))
        st.download_button(
            "Download unified_risk_decision.json",
            data=json.dumps(decision, indent=2).encode("utf-8"),
            file_name=f"{selected_record['run_id']}.json",
            mime="application/json",
        )

    st.divider()
    st.subheader("Submit A Unified Run")

    with st.form("unified_form"):
        prefill = ss.get("prefill_unified_form") or {}
        prefill_asset = prefill.get("asset", {})
        prefill_fraud = prefill.get("fraud", {})
        prefill_credit = prefill.get("credit", {})

        existing_borrowers = sorted({run["decision"].get("borrower_id") for run in ss.unified_runs if run.get("decision")})
        default_borrower = prefill.get("borrower_id") or (existing_borrowers[0] if existing_borrowers else "BORR-001")
        if default_borrower and default_borrower not in existing_borrowers:
            existing_borrowers = [default_borrower] + existing_borrowers
        borrower_select_options = existing_borrowers + ["➕ Custom entry"] if existing_borrowers else ["➕ Custom entry"]
        default_index = borrower_select_options.index(default_borrower) if default_borrower in borrower_select_options else len(borrower_select_options) - 1
        borrower_choice = st.selectbox("Borrower ID", borrower_select_options, index=default_index, key="borrower_select")
        if borrower_choice == "➕ Custom entry":
            borrower_id = st.text_input("Enter Borrower ID", value=default_borrower, key="borrower_text_input")
        else:
            borrower_id = borrower_choice

        loan_id = st.text_input("Loan ID", value=prefill.get("loan_id", "LN-1001"))
        loan_amount = st.number_input("Loan Amount", value=float(prefill.get("loan_amount", 150000.0)), step=5000.0)

        col_asset_a, col_asset_b, col_asset_c = st.columns(3)
        with col_asset_a:
            fmv = st.number_input("Asset FMV", value=float(prefill_asset.get("fmv", 250000.0)), step=1000.0)
        with col_asset_b:
            ai_adjusted = st.number_input("AI Adjusted", value=float(prefill_asset.get("ai_adjusted", 235000.0)), step=1000.0)
        with col_asset_c:
            realizable = st.number_input("Realizable Value", value=float(prefill_asset.get("realizable_value", 210000.0)), step=1000.0)

        col_fraud_a, col_fraud_b = st.columns(2)
        with col_fraud_a:
            fraud_score = st.slider("Fraud Risk Score", 0.0, 1.0, float(prefill_fraud.get("risk_score", 0.2)), 0.01)
        with col_fraud_b:
            default_tier = prefill_fraud.get("risk_tier", "low")
            fraud_tier = st.selectbox("Fraud Tier", ["low", "medium", "high"], index=["low","medium","high"].index(default_tier) if default_tier in ["low","medium","high"] else 0)
        sanctions_prefill = ", ".join(prefill_fraud.get("sanction_hits", [])) if prefill_fraud.get("sanction_hits") else ""
        sanctions_text = st.text_input("Sanction hits (comma separated)", value=sanctions_prefill)
        sanctions = [s.strip() for s in sanctions_text.split(",") if s.strip()]

        col_credit_a, col_credit_b, col_credit_c = st.columns(3)
        with col_credit_a:
            credit_score = st.number_input("Credit Score", min_value=300, max_value=900, value=int(prefill_credit.get("credit_score", 720)))
        with col_credit_b:
            probability_default = st.slider("Probability of Default", 0.0, 1.0, float(prefill_credit.get("probability_default", 0.08)), 0.01)
        with col_credit_c:
            default_credit = prefill_credit.get("approval", "approve")
            credit_decision = st.selectbox("Credit Decision", ["approve", "review", "reject"], index=["approve","review","reject"].index(default_credit) if default_credit in ["approve","review","reject"] else 0)

        submitted = st.form_submit_button("Generate Unified Decision", use_container_width=True)

        if submitted:
            payload = {
                "borrower_id": borrower_id,
                "loan_id": loan_id,
                "loan_amount": loan_amount,
                "asset": {
                    "fmv": fmv,
                    "ai_adjusted": ai_adjusted,
                    "realizable_value": realizable,
                    "encumbrance_flags": [],
                },
                "fraud": {
                    "risk_score": fraud_score,
                    "risk_tier": fraud_tier,
                    "sanction_hits": sanctions,
                    "kyc_passed": fraud_score < 0.6,
                },
                "credit": {
                    "credit_score": credit_score,
                    "probability_default": probability_default,
                    "approval": credit_decision,
                    "ndi": None,
                },
                "metadata": {"submitted_from": "streamlit"},
            }
            try:
                response = _call_unified_api(payload)
                ss.unified_runs.insert(0, response)
                ss.selected_unified_index = 0
                ss.prefill_unified_form = None
                st.success(f"Unified decision created for {borrower_id} ({response['risk_summary']['recommendation'].upper()}).")
            except requests.HTTPError as exc:  # pragma: no cover - network
                st.error(f"API error: {exc.response.text}")
            except Exception as exc:  # pragma: no cover - network
                st.error(f"Unexpected error: {exc}")

st.subheader("Re-run Unified Decision")
st.caption("Need to refresh the orchestration with updated borrower data? Re-run directly from this case.")
if st.button("↺ Re-run this borrower", key="btn_rerun_selected"):
    ss.prefill_unified_form = deepcopy(
        {
            "borrower_id": decision.get("borrower_id"),
            "loan_id": decision.get("loan_id"),
            "loan_amount": decision.get("loan_amount"),
            "asset": asset,
            "fraud": fraud,
            "credit": credit,
        }
    )
    st.info("Prefilled the submission form with this borrower's latest data. Complete the form below to finalize the rerun.")
    st.rerun()


def _build_unified_chat_context() -> Dict[str, Any]:
    """Build context for chat assistant on unified risk page."""
    ss = st.session_state
    context = {
        "agent_type": "unified_risk",
        "stage": "orchestration",
    }
    if hasattr(ss, "selected_unified_index") and ss.selected_unified_index is not None:
        if ss.unified_runs and 0 <= ss.selected_unified_index < len(ss.unified_runs):
            run = ss.unified_runs[ss.selected_unified_index]
            context["run_id"] = run.get("run_id")
            decision = run.get("decision", {})
            if decision:
                context["borrower_id"] = decision.get("borrower_id")
                context["loan_id"] = decision.get("loan_id")
                risk_summary = run.get("risk_summary", {})
                if risk_summary:
                    context["recommendation"] = risk_summary.get("recommendation")
    return context


# Render chat assistant for unified risk page (if available)
    if render_chat_assistant is not None:
        render_chat_assistant(
            page_id="unified_risk",
            context=_build_unified_chat_context(),
            faq_questions=[
                "How does the Unified Risk agent combine fraud, credit, and asset data?",
                "What is the final recommendation for this borrower?",
                "Explain the risk summary calculation.",
                "How do I rerun the unified decision?",
            ],
        )

with tab_feedback:
    render_feedback_tab("🧩 Unified Risk Orchestration Agent")
