#!/usr/bin/env python3
"""
⚖️ Legal & Compliance Agent — Beautiful Dashboard
Checks regulatory compliance, sanctions, PEP, licensing requirements
Feeds into Credit Appraisal and Asset Appraisal agents
"""
from __future__ import annotations

import os
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

from services.ui.theme_manager import (
    apply_theme as apply_global_theme,
    get_theme,
    render_theme_toggle,
)
from services.ui.components.operator_banner import render_operator_banner
from services.ui.components.telemetry_dashboard import render_telemetry_dashboard
from services.ui.components.feedback import render_feedback_tab
from services.ui.components.chat_assistant import render_chat_assistant

st.set_page_config(page_title="⚖️ Legal & Compliance Agent", layout="wide")
apply_global_theme()

API_URL = os.getenv("API_URL", "http://localhost:8090")

# ─────────────────────────────────────────────
# NAVIGATION BAR (consistent across all agents)
# ─────────────────────────────────────────────
def _go_stage(target: str):
    """Navigate to a stage/page."""
    ss = st.session_state
    ss["stage"] = target
    try:
        st.switch_page("app.py")
    except Exception:
        try:
            st.query_params["stage"] = target
        except Exception:
            pass
        st.rerun()

def render_nav_bar_app():
    """Top navigation bar with Home, Agents, and Theme switch."""
    ss = st.session_state
    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if st.button("🏠 Back to Home", key=f"btn_home_legal_compliance"):
            _go_stage("landing")
    with c2:
        if st.button("🤖 Back to Agents", key=f"btn_agents_legal_compliance"):
            _go_stage("agents")
    with c3:
        render_theme_toggle(
            label="🌗 Dark mode",
            key="legal_compliance_theme_toggle",
            help="Switch theme",
        )
    st.markdown("---")

render_nav_bar_app()

# ─────────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────
ss = st.session_state
ss.setdefault("legal_compliance_logged_in", True)
ss.setdefault("legal_compliance_user", {"name": "Operator", "email": "operator@demo.local"})
ss.setdefault("legal_compliance_df", None)
ss.setdefault("legal_compliance_results", None)

# ─────────────────────────────────────────────
# AUTO-LOAD DEMO DATA (if no data exists)
# ─────────────────────────────────────────────
if ss.get("legal_compliance_df") is None and ss.get("legal_compliance_results") is None:
    # Auto-generate demo data on first load
    rng = np.random.default_rng(42)
    demo_df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, 51)],
        "customer_id": [f"CUST_{i:04d}" for i in range(1, 51)],
        "jurisdiction": rng.choice(["US", "UK", "NG", "ZA", "AE", "SG", "MX"], 50),
        "pep_flag": rng.choice([0, 1], 50, p=[0.85, 0.15]),
        "sanctions_match": rng.choice([0, 1], 50, p=[0.93, 0.07]),
        "license_required": rng.choice([0, 1], 50, p=[0.55, 0.45]),
        "kyc_risk_score": rng.uniform(0.05, 0.65, 50).round(3),
        "fraud_probability": rng.uniform(0.01, 0.45, 50).round(3),
    })
    ss["legal_compliance_df"] = demo_df
    # Auto-run compliance checks if demo data is loaded
    try:
        from agents.legal_compliance.runner import run_compliance_checks
        checked_df = run_compliance_checks(demo_df)
        ss["legal_compliance_results"] = checked_df
        ss["credit_policy_df"] = checked_df.copy()  # For Credit Appraisal integration
    except Exception:
        pass  # If runner fails, just show the demo data

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────
def _render_gauge(title: str, value: float, min_val: float, max_val: float, key: str = None):
    """Render a beautiful gauge chart."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 16}},
        delta={'reference': (min_val + max_val) / 2},
        gauge={
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [min_val, min_val + (max_val - min_val) * 0.33], 'color': "lightgray"},
                {'range': [min_val + (max_val - min_val) * 0.33, min_val + (max_val - min_val) * 0.66], 'color': "gray"},
                {'range': [min_val + (max_val - min_val) * 0.66, max_val], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': min_val + (max_val - min_val) * 0.7
            }
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig, use_container_width=True, key=key)

def _render_compliance_gauge(score: float, key: str = None):
    """Render compliance score gauge with color coding."""
    # Determine color based on score
    if score >= 0.8:
        color = "#10b981"  # green
        tier = "Excellent"
    elif score >= 0.6:
        color = "#3b82f6"  # blue
        tier = "Good"
    elif score >= 0.4:
        color = "#f59e0b"  # orange
        tier = "Fair"
    else:
        color = "#ef4444"  # red
        tier = "Poor"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score * 100,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f'Compliance Score<br><span style="font-size:0.8em;color:{color}">{tier}</span>'},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, 40], 'color': "#fee2e2"},
                {'range': [40, 60], 'color': "#fef3c7"},
                {'range': [60, 80], 'color': "#dbeafe"},
                {'range': [80, 100], 'color': "#a7f3d0"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 60
            }
        }
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, use_container_width=True, key=key)

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
operator_name = ss.get("legal_compliance_user", {}).get("name", "Operator")

render_operator_banner(
    operator_name=operator_name,
    title="Legal & Compliance Command",
    summary="Check regulatory compliance, sanctions, PEP flags, and licensing requirements. Output feeds into Credit Appraisal and Asset Appraisal agents.",
    bullets=[
        "Verify sanctions matches, PEP flags, and licensing requirements.",
        "Generate compliance scores and policy flags for downstream agents.",
        "Export compliance verdicts to Credit Appraisal and Asset Appraisal workflows.",
    ],
    metrics=[
        {
            "label": "Compliance Rate",
            "value": "85%",
            "context": "Last 30 days",
        },
        {
            "label": "Status",
            "value": "Available",
            "context": "Production ready",
        },
    ],
    icon="⚖️",
)

st.title("⚖️ Legal & Compliance Agent")
st.caption("Regulatory compliance checks → Feed into Credit Appraisal & Asset Appraisal Agents")

# ─────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────
tab_howto, tab_input, tab_dashboard, tab_export, tab_feedback = st.tabs([
    "📘 How-To",
    "📥 Data Input",
    "📊 Dashboard & Analytics",
    "📤 Export to Agents",
    "🗣️ Feedback"
])

with tab_howto:
    st.title("📘 How to Use Legal & Compliance Agent")
    st.markdown("""
    ### What
    A specialized agent that checks regulatory compliance, sanctions, PEP (Politically Exposed Person) flags,
    and licensing requirements. This agent complements Credit Appraisal and Asset Appraisal agents.

    ### Goal
    To ensure all loan applications meet regulatory requirements before final approval decisions.

    ### How
    1. **Upload Data**: Import application data from KYC/Anti-Fraud, Asset, or Credit agents
    2. **Run Compliance Checks**: Agent analyzes sanctions, PEP, licensing, and KYC risk
    3. **View Dashboard**: Beautiful visualizations with compliance scores, flags, and verdicts
    4. **Export**: Send compliance verdicts to Credit Appraisal and Asset Appraisal agents

    ### Compliance Checks
    - **Sanctions Matching**: Check against sanctions lists
    - **PEP Detection**: Identify Politically Exposed Persons
    - **Licensing Requirements**: Verify jurisdiction-specific licensing
    - **KYC Risk Assessment**: Evaluate Know Your Customer risk scores
    - **Regulatory Alignment**: Overall compliance scoring

    ### Compliance Statuses
    - **✅ Cleared**: No compliance issues, ready for approval
    - **🟡 Review Required**: Moderate risk, requires review
    - **🟠 Conditional**: Conditional approval with requirements
    - **🚫 Hold – Escalate**: Critical issues, escalate to legal team

    ### Integration
    The Legal Compliance Agent feeds its output directly into Credit Appraisal and Asset Appraisal agents,
    which use compliance verdicts in their final decision-making process.
    """)

with tab_input:
    st.header("📥 Data Input")
    
    input_method = st.radio(
        "Choose input method:",
        ["Upload CSV", "Load from Session State", "Generate Synthetic Data"],
        horizontal=True
    )
    
    if input_method == "Upload CSV":
        uploaded_file = st.file_uploader("Upload application data CSV", type=["csv"])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ Loaded {len(df)} records")
                st.dataframe(df.head(), use_container_width=True)
                ss["legal_compliance_df"] = df
            except Exception as e:
                st.error(f"Error loading CSV: {e}")
    
    elif input_method == "Load from Session State":
        st.info("Loading from upstream agents (KYC, Asset, Credit)...")
        
        # Try to get data from various sources
        source_keys = [
            "afk_kyc_df", "afk_fraud_df", "credit_scored_df", 
            "asset_decision_df", "credit_policy_df"
        ]
        
        found_df = None
        for key in source_keys:
            df = ss.get(key)
            if isinstance(df, pd.DataFrame) and not df.empty:
                found_df = df.copy()
                st.success(f"✅ Found data from: {key} ({len(df)} records)")
                break
        
        if found_df is not None:
            ss["legal_compliance_df"] = found_df
            st.dataframe(found_df.head(), use_container_width=True)
        else:
            st.warning("⚠️ No data found in session state. Use Upload CSV or Generate Synthetic Data.")
    
    elif input_method == "Generate Synthetic Data":
        num_records = st.number_input("Number of records", min_value=1, max_value=1000, value=50)
        if st.button("Generate Synthetic Data"):
            rng = np.random.default_rng(42)
            df = pd.DataFrame({
                "application_id": [f"APP_{i:04d}" for i in range(1, num_records + 1)],
                "customer_id": [f"CUST_{i:04d}" for i in range(1, num_records + 1)],
                "jurisdiction": rng.choice(["US", "UK", "NG", "ZA", "AE", "SG", "MX"], num_records),
                "pep_flag": rng.choice([0, 1], num_records, p=[0.85, 0.15]),
                "sanctions_match": rng.choice([0, 1], num_records, p=[0.93, 0.07]),
                "license_required": rng.choice([0, 1], num_records, p=[0.55, 0.45]),
                "kyc_risk_score": rng.uniform(0.05, 0.65, num_records).round(3),
                "fraud_probability": rng.uniform(0.01, 0.45, num_records).round(3),
            })
            ss["legal_compliance_df"] = df
            st.success(f"✅ Generated {len(df)} synthetic records")
            st.dataframe(df.head(), use_container_width=True)
    
    # Run compliance checks button
    if ss.get("legal_compliance_df") is not None:
        st.divider()
        if st.button("⚖️ Run Compliance Checks", type="primary", use_container_width=True):
            with st.spinner("Running compliance checks..."):
                try:
                    from agents.legal_compliance.runner import run_compliance_checks
                    df_checked = run_compliance_checks(ss["legal_compliance_df"])
                    ss["legal_compliance_results"] = df_checked
                    # Also update credit_policy_df for Credit Appraisal integration
                    ss["credit_policy_df"] = df_checked.copy()
                    st.success(f"✅ Compliance checks completed for {len(df_checked)} applications")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error running compliance checks: {e}")
                    import traceback
                    st.code(traceback.format_exc())

with tab_dashboard:
    st.header("📊 Compliance Dashboard")
    
    if ss.get("legal_compliance_results") is None:
        st.warning("⚠️ No compliance results available. Please run compliance checks in the Data Input tab.")
    else:
        df = ss["legal_compliance_results"]
        
        # ─────────────────────────────────────────────
        # TOP KPI METRICS
        # ─────────────────────────────────────────────
        st.subheader("📈 Key Performance Indicators")
        kpi_cols = st.columns(5)
        
        cleared_count = len(df[df["compliance_status"] == "✅ Cleared"])
        hold_count = len(df[df["compliance_status"] == "🚫 Hold – Escalate"])
        conditional_count = len(df[df["compliance_status"] == "🟠 Conditional"])
        avg_score = df["compliance_score"].mean()
        pep_count = int(df["pep_flag"].sum()) if "pep_flag" in df.columns else 0
        
        with kpi_cols[0]:
            st.metric("Cleared", f"{cleared_count}", delta=f"{(cleared_count/len(df)*100):.1f}%")
        with kpi_cols[1]:
            st.metric("On Hold", f"{hold_count}", delta=f"{(hold_count/len(df)*100):.1f}%")
        with kpi_cols[2]:
            st.metric("Conditional", f"{conditional_count}", delta=f"{(conditional_count/len(df)*100):.1f}%")
        with kpi_cols[3]:
            st.metric("Avg Compliance Score", f"{avg_score:.2f}", delta=f"{(avg_score-0.6)*100:.1f}%")
        with kpi_cols[4]:
            st.metric("PEP Flags", f"{pep_count}")
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # GAUGE CHARTS
        # ─────────────────────────────────────────────
        st.subheader("🎯 Compliance Gauges")
        gauge_cols = st.columns(3)
        
        with gauge_cols[0]:
            _render_compliance_gauge(avg_score, key="avg_compliance_gauge")
        with gauge_cols[1]:
            cleared_pct = (cleared_count / len(df)) * 100
            _render_gauge("Clearance Rate", cleared_pct, 0, 100, key="clearance_gauge")
        with gauge_cols[2]:
            if "kyc_risk_score" in df.columns:
                avg_kyc = df["kyc_risk_score"].mean() * 100
                _render_gauge("Avg KYC Risk", avg_kyc, 0, 100, key="kyc_gauge")
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # DISTRIBUTION CHARTS
        # ─────────────────────────────────────────────
        st.subheader("📊 Compliance Distribution")
        chart_cols = st.columns(2)
        
        with chart_cols[0]:
            # Status distribution
            status_counts = df["compliance_status"].value_counts()
            fig_pie = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Compliance Status Distribution",
                color_discrete_map={
                    "✅ Cleared": "#10b981",
                    "🟡 Review Required": "#f59e0b",
                    "🟠 Conditional": "#f97316",
                    "🚫 Hold – Escalate": "#ef4444"
                }
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with chart_cols[1]:
            # Compliance score histogram
            fig_hist = px.histogram(
                df,
                x="compliance_score",
                nbins=20,
                title="Compliance Score Distribution",
                labels={"compliance_score": "Compliance Score", "count": "Frequency"},
                color_discrete_sequence=["#3b82f6"]
            )
            fig_hist.update_layout(height=400)
            st.plotly_chart(fig_hist, use_container_width=True)
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # FLAGS ANALYSIS
        # ─────────────────────────────────────────────
        st.subheader("🚩 Policy Flags Analysis")
        
        if "policy_flags" in df.columns:
            # Count flags
            all_flags = []
            for flags_str in df["policy_flags"]:
                if flags_str and flags_str != "NONE":
                    all_flags.extend([f.strip() for f in flags_str.split(",")])
            
            if all_flags:
                flag_counts = pd.Series(all_flags).value_counts()
                fig_bar = px.bar(
                    x=flag_counts.values,
                    y=flag_counts.index,
                    orientation='h',
                    title="Policy Flags Frequency",
                    labels={"x": "Count", "y": "Flag Type"},
                    color=flag_counts.values,
                    color_continuous_scale="Reds"
                )
                fig_bar.update_layout(height=300)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.success("✅ No policy flags detected")
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # DETAILED DATA TABLE
        # ─────────────────────────────────────────────
        st.subheader("📋 Detailed Results")
        
        display_cols = ["application_id", "compliance_status", "compliance_score", "compliance_stage"]
        if "legal_reason" in df.columns:
            display_cols.append("legal_reason")
        if "policy_flags" in df.columns:
            display_cols.append("policy_flags")
        
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available_cols].sort_values("compliance_score", ascending=False),
            use_container_width=True,
            height=400
        )
        
        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Compliance Results (CSV)",
            data=csv,
            file_name=f"legal_compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

with tab_export:
    st.header("📤 Export to Credit Appraisal & Asset Appraisal Agents")
    
    if ss.get("legal_compliance_results") is None:
        st.warning("⚠️ No compliance results available. Please run compliance checks first.")
    else:
        df = ss["legal_compliance_results"]
        
        st.info("""
        💡 **Integration Flow**: Legal Compliance Agent → Credit Appraisal Agent & Asset Appraisal Agent
        
        The compliance verdicts are automatically stored in session state and can be accessed by:
        - Credit Appraisal Agent (via `credit_policy_df`)
        - Asset Appraisal Agent (via `legal_compliance_df`)
        """)
        
        # Preview data to be exported
        st.subheader("Preview Export Data")
        export_cols = ["application_id", "compliance_status", "compliance_score", "compliance_stage"]
        if "policy_flags" in df.columns:
            export_cols.append("policy_flags")
        
        st.dataframe(df[export_cols].head(10), use_container_width=True)
        
        # Export options
        export_method = st.radio(
            "Export Method:",
            ["Save to Session State", "Download CSV", "API Integration"],
            horizontal=True
        )
        
        if export_method == "Save to Session State":
            if st.button("💾 Save to Session State", type="primary"):
                ss["credit_policy_df"] = df.copy()
                ss["legal_compliance_df"] = df.copy()
                st.success("✅ Data saved to session state. Navigate to Credit Appraisal or Asset Appraisal agents to use it.")
        
        elif export_method == "Download CSV":
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download for Agents",
                data=csv,
                file_name=f"legal_compliance_for_agents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        elif export_method == "API Integration":
            st.info("API integration coming soon.")
            if st.button("🔄 Test API Connection"):
                try:
                    health = requests.get(f"{API_URL}/health", timeout=3)
                    if health.status_code == 200:
                        st.success("✅ API connection successful")
                    else:
                        st.warning(f"⚠️ API returned status {health.status_code}")
                except Exception as e:
                    st.error(f"❌ API connection failed: {e}")

with tab_feedback:
    render_feedback_tab("⚖️ Legal & Compliance Agent")

# ─────────────────────────────────────────────
# SIDEBAR CHAT ASSISTANT
# ─────────────────────────────────────────────
with st.sidebar:
    render_chat_assistant(
        page_id="legal_compliance",
        context={"agent_type": "legal_compliance", "stage": "compliance_check"},
        faq_questions=[
            "How does the Legal Compliance agent check sanctions?",
            "What is PEP (Politically Exposed Person) detection?",
            "How are licensing requirements verified?",
            "What compliance scores indicate approval readiness?",
            "How do compliance verdicts feed into Credit Appraisal?",
            "What policy flags trigger escalation?",
            "How does Legal Compliance integrate with Asset Appraisal?",
        ],
    )
