#!/usr/bin/env python3
"""
💳 Credit Score Agent — Beautiful Dashboard
Calculates credit scores (300-850) and feeds into Credit Appraisal Agent
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

st.set_page_config(page_title="💳 Credit Score Agent", layout="wide")
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
        if st.button("🏠 Back to Home", key=f"btn_home_credit_score"):
            _go_stage("landing")
    with c2:
        if st.button("🤖 Back to Agents", key=f"btn_agents_credit_score"):
            _go_stage("agents")
    with c3:
        render_theme_toggle(
            label="🌗 Dark mode",
            key="credit_score_theme_toggle",
            help="Switch theme",
        )
    st.markdown("---")

render_nav_bar_app()

# ─────────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ─────────────────────────────────────────────
ss = st.session_state
ss.setdefault("credit_score_logged_in", True)
ss.setdefault("credit_score_user", {"name": "Operator", "email": "operator@demo.local"})
ss.setdefault("credit_score_df", None)
ss.setdefault("credit_score_results", None)

# ─────────────────────────────────────────────
# AUTO-LOAD DEMO DATA (if no data exists)
# ─────────────────────────────────────────────
if ss.get("credit_score_df") is None and ss.get("credit_score_results") is None:
    # Auto-generate demo data on first load
    rng = np.random.default_rng(42)
    demo_df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, 51)],
        "customer_id": [f"CUST_{i:04d}" for i in range(1, 51)],
        "income": rng.integers(20000, 150000, 50),
        "DTI": rng.uniform(0.15, 0.65, 50).round(3),
        "credit_history_length": rng.integers(0, 25, 50),
        "num_delinquencies": rng.integers(0, 5, 50),
        "current_loans": rng.integers(0, 8, 50),
        "employment_years": rng.integers(0, 30, 50),
        "existing_debt": rng.integers(0, 50000, 50),
        "assets_owned": rng.integers(0, 200000, 50),
        "monthly_income": rng.integers(2000, 12000, 50),
        "utilization_ratio": rng.uniform(0.1, 0.92, 50).round(3),
    })
    ss["credit_score_df"] = demo_df
    # Auto-run scoring if demo data is loaded
    try:
        from agents.credit_score.runner import calculate_credit_score
        scored_df = calculate_credit_score(demo_df)
        ss["credit_score_results"] = scored_df
        ss["credit_scored_df"] = scored_df.copy()  # For Credit Appraisal integration
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

def _render_score_gauge(score: float, key: str = None):
    """Render credit score gauge with color coding."""
    # Determine color based on score
    if score >= 750:
        color = "#10b981"  # green
        tier = "Excellent"
    elif score >= 700:
        color = "#3b82f6"  # blue
        tier = "Very Good"
    elif score >= 650:
        color = "#8b5cf6"  # purple
        tier = "Good"
    elif score >= 600:
        color = "#f59e0b"  # orange
        tier = "Fair"
    elif score >= 500:
        color = "#ef4444"  # red
        tier = "Poor"
    else:
        color = "#991b1b"  # dark red
        tier = "Very Poor"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f'Credit Score<br><span style="font-size:0.8em;color:{color}">{tier}</span>'},
        gauge={
            'axis': {'range': [300, 850]},
            'bar': {'color': color},
            'steps': [
                {'range': [300, 500], 'color': "#fee2e2"},
                {'range': [500, 600], 'color': "#fef3c7"},
                {'range': [600, 650], 'color': "#dbeafe"},
                {'range': [650, 700], 'color': "#e0e7ff"},
                {'range': [700, 750], 'color': "#d1fae5"},
                {'range': [750, 850], 'color': "#a7f3d0"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 700
            }
        }
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, use_container_width=True, key=key)

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
operator_name = ss.get("credit_score_user", {}).get("name", "Operator")

render_operator_banner(
    operator_name=operator_name,
    title="Credit Score Command",
    summary="Calculate standardized credit scores (300-850 range) based on borrower financial data. Output feeds directly into Credit Appraisal Agent.",
    bullets=[
        "Analyze payment history, debt levels, credit history, and credit mix.",
        "Generate FICO-like scores (300-850) with detailed component breakdowns.",
        "Export scored data seamlessly to Credit Appraisal Agent for loan decisions.",
    ],
    metrics=[
        {
            "label": "Score Range",
            "value": "300-850",
            "context": "FICO-like scoring",
        },
        {
            "label": "Status",
            "value": "Available",
            "context": "Production ready",
        },
    ],
    icon="💳",
)

st.title("💳 Credit Score Agent")
st.caption("Calculate credit scores (300-850) → Feed into Credit Appraisal Agent")

# ─────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────
tab_howto, tab_input, tab_dashboard, tab_export, tab_feedback = st.tabs([
    "📘 How-To",
    "📥 Data Input",
    "📊 Dashboard & Analytics",
    "📤 Export to Credit Appraisal",
    "🗣️ Feedback"
])

with tab_howto:
    st.title("📘 How to Use Credit Score Agent")
    st.markdown("""
    ### What
    A specialized agent that calculates credit scores (300-850 range) based on borrower financial data.
    This agent complements the Credit Appraisal Agent by providing standardized credit scores.

    ### Goal
    To generate accurate, explainable credit scores that feed directly into the Credit Appraisal Agent
    for comprehensive loan decision-making.

    ### How
    1. **Upload Data**: Import borrower data (CSV) or use synthetic data generator
    2. **Calculate Scores**: Agent analyzes payment history, debt levels, credit history, and more
    3. **View Dashboard**: Beautiful visualizations with gauges, KPIs, and score breakdowns
    4. **Export**: Send scored data directly to Credit Appraisal Agent

    ### Scoring Factors
    - **Payment History (35%)**: Delinquencies, late payments
    - **Amounts Owed (30%)**: DTI ratio, current loans
    - **Credit History Length (15%)**: Years of credit history
    - **Credit Mix (10%)**: Types of credit accounts
    - **New Credit (10%)**: Recent inquiries and accounts

    ### Score Ranges
    - **750-850**: Excellent
    - **700-749**: Very Good
    - **650-699**: Good
    - **600-649**: Fair
    - **500-599**: Poor
    - **300-499**: Very Poor

    ### Integration
    The Credit Score Agent feeds its output directly into the Credit Appraisal Agent,
    which uses these scores along with other factors for final loan decisions.
    """)

with tab_input:
    st.header("📥 Data Input")
    
    input_method = st.radio(
        "Choose input method:",
        ["Upload CSV", "Generate Synthetic Data", "Manual Entry"],
        horizontal=True
    )
    
    if input_method == "Upload CSV":
        uploaded_file = st.file_uploader("Upload borrower data CSV", type=["csv"])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ Loaded {len(df)} records")
                st.dataframe(df.head(), use_container_width=True)
                ss["credit_score_df"] = df
            except Exception as e:
                st.error(f"Error loading CSV: {e}")
    
    elif input_method == "Generate Synthetic Data":
        num_records = st.number_input("Number of records", min_value=1, max_value=1000, value=50)
        if st.button("Generate Synthetic Data"):
            rng = np.random.default_rng(42)
            df = pd.DataFrame({
                "application_id": [f"APP_{i:04d}" for i in range(1, num_records + 1)],
                "income": rng.integers(20000, 150000, num_records),
                "DTI": rng.uniform(0.15, 0.65, num_records),
                "credit_history_length": rng.integers(0, 25, num_records),
                "num_delinquencies": rng.integers(0, 5, num_records),
                "current_loans": rng.integers(0, 8, num_records),
                "employment_years": rng.integers(0, 30, num_records),
                "existing_debt": rng.integers(0, 50000, num_records),
                "assets_owned": rng.integers(0, 200000, num_records),
            })
            ss["credit_score_df"] = df
            st.success(f"✅ Generated {len(df)} synthetic records")
            st.dataframe(df.head(), use_container_width=True)
    
    elif input_method == "Manual Entry":
        st.info("Manual entry form coming soon. Use CSV upload or synthetic data for now.")
    
    # Calculate scores button
    if ss.get("credit_score_df") is not None:
        st.divider()
        if st.button("🚀 Calculate Credit Scores", type="primary", use_container_width=True):
            with st.spinner("Calculating credit scores..."):
                try:
                    from agents.credit_score.runner import calculate_credit_score
                    df_scored = calculate_credit_score(ss["credit_score_df"])
                    ss["credit_score_results"] = df_scored
                    st.success(f"✅ Calculated scores for {len(df_scored)} borrowers")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error calculating scores: {e}")
                    import traceback
                    st.code(traceback.format_exc())

with tab_dashboard:
    st.header("📊 Credit Score Dashboard")
    
    if ss.get("credit_score_results") is None:
        st.warning("⚠️ No scored data available. Please calculate scores in the Data Input tab.")
    else:
        df = ss["credit_score_results"]
        
        # ─────────────────────────────────────────────
        # TOP KPI METRICS
        # ─────────────────────────────────────────────
        st.subheader("📈 Key Performance Indicators")
        kpi_cols = st.columns(5)
        
        avg_score = df["credit_score"].mean()
        median_score = df["credit_score"].median()
        min_score = df["credit_score"].min()
        max_score = df["credit_score"].max()
        excellent_count = len(df[df["credit_score"] >= 750])
        
        with kpi_cols[0]:
            st.metric("Average Score", f"{avg_score:.0f}", delta=f"{avg_score - 700:.0f}")
        with kpi_cols[1]:
            st.metric("Median Score", f"{median_score:.0f}")
        with kpi_cols[2]:
            st.metric("Score Range", f"{min_score:.0f} - {max_score:.0f}")
        with kpi_cols[3]:
            excellent_pct = (excellent_count / len(df)) * 100
            st.metric("Excellent (≥750)", f"{excellent_count}", delta=f"{excellent_pct:.1f}%")
        with kpi_cols[4]:
            total_records = len(df)
            st.metric("Total Records", f"{total_records}")
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # GAUGE CHARTS
        # ─────────────────────────────────────────────
        st.subheader("🎯 Score Gauges")
        gauge_cols = st.columns(3)
        
        with gauge_cols[0]:
            _render_score_gauge(avg_score, key="avg_gauge")
        with gauge_cols[1]:
            _render_score_gauge(median_score, key="median_gauge")
        with gauge_cols[2]:
            _render_score_gauge(max_score, key="max_gauge")
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # DISTRIBUTION CHARTS
        # ─────────────────────────────────────────────
        st.subheader("📊 Score Distribution")
        chart_cols = st.columns(2)
        
        with chart_cols[0]:
            # Histogram
            fig_hist = px.histogram(
                df,
                x="credit_score",
                nbins=30,
                title="Credit Score Distribution",
                labels={"credit_score": "Credit Score", "count": "Frequency"},
                color_discrete_sequence=["#3b82f6"]
            )
            fig_hist.update_layout(height=400)
            st.plotly_chart(fig_hist, use_container_width=True)
        
        with chart_cols[1]:
            # Box plot by risk category
            if "risk_category" in df.columns:
                fig_box = px.box(
                    df,
                    x="risk_category",
                    y="credit_score",
                    title="Score Distribution by Risk Category",
                    labels={"risk_category": "Risk Category", "credit_score": "Credit Score"},
                    color="risk_category",
                    color_discrete_map={
                        "Poor": "#ef4444",
                        "Fair": "#f59e0b",
                        "Good": "#3b82f6",
                        "Excellent": "#10b981"
                    }
                )
                fig_box.update_layout(height=400)
                st.plotly_chart(fig_box, use_container_width=True)
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # SCORE BREAKDOWN ANALYSIS
        # ─────────────────────────────────────────────
        st.subheader("🔍 Score Component Breakdown")
        
        if all(col in df.columns for col in ["score_payment_history", "score_amounts_owed", 
                                              "score_credit_history", "score_credit_mix", "score_new_credit"]):
            breakdown_cols = st.columns(5)
            
            components = {
                "Payment History": df["score_payment_history"].mean(),
                "Amounts Owed": df["score_amounts_owed"].mean(),
                "Credit History": df["score_credit_history"].mean(),
                "Credit Mix": df["score_credit_mix"].mean(),
                "New Credit": df["score_new_credit"].mean()
            }
            
            weights = [0.35, 0.30, 0.15, 0.10, 0.10]
            
            for idx, (name, value) in enumerate(components.items()):
                with breakdown_cols[idx]:
                    _render_gauge(
                        name,
                        value,
                        0,
                        100,
                        key=f"component_{idx}"
                    )
            
            # Weighted average visualization
            st.markdown("#### Weighted Component Analysis")
            component_df = pd.DataFrame({
                "Component": list(components.keys()),
                "Average Score": list(components.values()),
                "Weight": weights
            })
            component_df["Weighted Contribution"] = component_df["Average Score"] * component_df["Weight"]
            
            fig_bar = px.bar(
                component_df,
                x="Component",
                y="Weighted Contribution",
                title="Weighted Contribution to Final Score",
                labels={"Weighted Contribution": "Contribution", "Component": "Component"},
                color="Component",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_bar.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig_bar, use_container_width=True)
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # RISK CATEGORY BREAKDOWN
        # ─────────────────────────────────────────────
        st.subheader("🎯 Risk Category Analysis")
        
        if "risk_category" in df.columns:
            risk_cols = st.columns(2)
            
            with risk_cols[0]:
                risk_counts = df["risk_category"].value_counts()
                fig_pie = px.pie(
                    values=risk_counts.values,
                    names=risk_counts.index,
                    title="Distribution by Risk Category",
                    color_discrete_map={
                        "Poor": "#ef4444",
                        "Fair": "#f59e0b",
                        "Good": "#3b82f6",
                        "Excellent": "#10b981"
                    }
                )
                fig_pie.update_layout(height=400)
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with risk_cols[1]:
                risk_stats = df.groupby("risk_category")["credit_score"].agg(["mean", "count", "min", "max"])
                risk_stats.columns = ["Avg Score", "Count", "Min", "Max"]
                st.dataframe(risk_stats, use_container_width=True)
        
        st.divider()
        
        # ─────────────────────────────────────────────
        # DETAILED DATA TABLE
        # ─────────────────────────────────────────────
        st.subheader("📋 Detailed Results")
        
        display_cols = ["application_id", "credit_score", "risk_category", "score_tier"]
        if "score_payment_history" in df.columns:
            display_cols.extend(["score_payment_history", "score_amounts_owed", "score_credit_history"])
        
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available_cols].sort_values("credit_score", ascending=False),
            use_container_width=True,
            height=400
        )
        
        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Scored Data (CSV)",
            data=csv,
            file_name=f"credit_scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

with tab_export:
    st.header("📤 Export to Credit Appraisal Agent")
    
    if ss.get("credit_score_results") is None:
        st.warning("⚠️ No scored data available. Please calculate scores first.")
    else:
        df = ss["credit_score_results"]
        
        st.info("""
        💡 **Integration Flow**: Credit Score Agent → Credit Appraisal Agent
        
        The Credit Appraisal Agent will use these credit scores along with other factors
        (DTI, LTV, employment history, etc.) to make final loan approval decisions.
        """)
        
        # Preview data to be exported
        st.subheader("Preview Export Data")
        export_cols = ["application_id", "credit_score", "risk_category"]
        if all(c in df.columns for c in ["score_payment_history", "score_amounts_owed"]):
            export_cols.extend(["score_payment_history", "score_amounts_owed", "score_credit_history"])
        
        st.dataframe(df[export_cols].head(10), use_container_width=True)
        
        # Export options
        export_method = st.radio(
            "Export Method:",
            ["Save to Session State", "Download CSV", "API Integration"],
            horizontal=True
        )
        
        if export_method == "Save to Session State":
            if st.button("💾 Save to Session State", type="primary"):
                ss["credit_appraisal_input_df"] = df.copy()
                st.success("✅ Data saved to session state. Navigate to Credit Appraisal Agent to use it.")
        
        elif export_method == "Download CSV":
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download for Credit Appraisal",
                data=csv,
                file_name=f"credit_scores_for_appraisal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        elif export_method == "API Integration":
            st.info("API integration with Credit Appraisal Agent coming soon.")
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
    render_feedback_tab("💳 Credit Score Agent")

# ─────────────────────────────────────────────
# SIDEBAR CHAT ASSISTANT
# ─────────────────────────────────────────────
with st.sidebar:
    render_chat_assistant(
        page_id="credit_score",
        context={"agent_type": "credit_score", "stage": "scoring"},
        faq_questions=[
            "How does the Credit Score agent calculate scores?",
            "What factors are used in credit score calculation?",
            "What is the scoring range (300-850)?",
            "How does Payment History (35%) affect the score?",
            "How does Amounts Owed (30%) affect the score?",
            "What are the score tiers (Excellent, Good, Fair, Poor)?",
            "How do I export credit scores to Credit Appraisal Agent?",
        ],
    )
