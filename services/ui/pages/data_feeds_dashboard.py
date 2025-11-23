#!/usr/bin/env python3
"""📊 Data Feeds Dashboard — 3-column layout with gauges and logo uploads."""
from __future__ import annotations

import os
import base64
from pathlib import Path
from typing import Optional

import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="📊 Data Feeds Dashboard",
    page_icon="📊",
    layout="wide",
)

# Theme styling
THEME_BG = "#0E1117"
st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {THEME_BG};
        color: #f5f7fb;
    }}
    .data-feed-column {{
        background: linear-gradient(135deg, rgba(19, 176, 245, 0.1) 0%, rgba(92, 60, 255, 0.1) 100%);
        border: 1px solid rgba(19, 176, 245, 0.3);
        border-radius: 16px;
        padding: 20px;
        margin: 10px;
    }}
    .logo-upload-container {{
        text-align: center;
        margin-bottom: 20px;
    }}
    .logo-preview {{
        max-width: 150px;
        max-height: 100px;
        border-radius: 8px;
        margin: 10px auto;
        display: block;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Base directory for storing logos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_DIR = os.path.join(BASE_DIR, "assets", "data_feeds_logos")
os.makedirs(LOGO_DIR, exist_ok=True)

# Initialize session state for logos and data
if "data_feed_logos" not in st.session_state:
    st.session_state.data_feed_logos = {
        "col1": None,
        "col2": None,
        "col3": None,
    }

if "data_feed_values" not in st.session_state:
    st.session_state.data_feed_values = {
        "col1": 65.0,
        "col2": 78.0,
        "col3": 45.0,
    }

if "api_feed_url" not in st.session_state:
    st.session_state.api_feed_url = ""


def plot_electric_charger_gauge(value: float, title: str) -> go.Figure:
    """Gauge styled like an electric charger plug."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"color": "#f5f7fb", "size": 18}},
            number={"suffix": "%", "font": {"color": "#22c55e", "size": 32}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#7b8190"},
                "bar": {"color": "#22c55e"},  # Green for electric
                "bgcolor": "#1b1f2a",
                "borderwidth": 2,
                "bordercolor": "#22c55e",
                "steps": [
                    {"range": [0, 50], "color": "#1d2330"},
                    {"range": [50, 100], "color": "#252b3c"},
                ],
                "threshold": {
                    "line": {"color": "#fbbf24", "width": 4},
                    "value": 85,
                },
            },
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
    )
    return fig


def plot_ev_charger_station_gauge(value: float, title: str) -> go.Figure:
    """Gauge styled like an EV charger station."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"color": "#f5f7fb", "size": 18}},
            number={"suffix": "%", "font": {"color": "#3b82f6", "size": 32}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#7b8190"},
                "bar": {"color": "#3b82f6"},  # Blue for EV
                "bgcolor": "#1b1f2a",
                "borderwidth": 2,
                "bordercolor": "#3b82f6",
                "steps": [
                    {"range": [0, 50], "color": "#1d2330"},
                    {"range": [50, 100], "color": "#252b3c"},
                ],
                "threshold": {
                    "line": {"color": "#fbbf24", "width": 4},
                    "value": 85,
                },
            },
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
    )
    return fig


def render_logo_upload(key: str, column_name: str) -> Optional[str]:
    """Render logo upload button and preview."""
    logo_path = os.path.join(LOGO_DIR, f"{key}_logo.png")
    
    # Check if logo exists
    existing_logo = None
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            existing_logo = base64.b64encode(f.read()).decode()
    
    # Display existing logo or placeholder
    if existing_logo:
        st.markdown(
            f'<img src="data:image/png;base64,{existing_logo}" class="logo-preview" />',
            unsafe_allow_html=True,
        )
    else:
        # Show emoji placeholder based on column
        emoji_map = {"col1": "🔌", "col2": "⚡", "col3": "⛽"}
        st.markdown(
            f'<div style="font-size:48px; text-align:center; padding:20px;">{emoji_map.get(key, "📊")}</div>',
            unsafe_allow_html=True,
        )
    
    # Upload button
    uploaded_file = st.file_uploader(
        f"Upload {column_name} Logo",
        type=["png", "jpg", "jpeg", "webp"],
        key=f"logo_upload_{key}",
    )
    
    if uploaded_file is not None:
        # Save uploaded logo
        with open(logo_path, "wb") as f:
            f.write(uploaded_file.read())
        st.success(f"✅ {column_name} logo updated!")
        st.rerun()
    
    return logo_path if os.path.exists(logo_path) else None


def render_l3_panels():
    """Render L3 panels for column 3."""
    st.markdown("### 📋 L3 Panels")
    
    panel_data = st.session_state.get("l3_panel_data", {
        "panel1": {"label": "Panel 1", "value": 0},
        "panel2": {"label": "Panel 2", "value": 0},
        "panel3": {"label": "Panel 3", "value": 0},
    })
    
    for panel_key, panel_info in panel_data.items():
        with st.container():
            st.text_input(
                f"Label",
                value=panel_info["label"],
                key=f"l3_label_{panel_key}",
            )
            panel_data[panel_key]["value"] = st.number_input(
                f"Value",
                min_value=0.0,
                max_value=100.0,
                value=panel_info["value"],
                key=f"l3_value_{panel_key}",
            )
            st.divider()
    
    st.session_state.l3_panel_data = panel_data


# Main layout
st.title("📊 Data Feeds Dashboard")
st.caption("Monitor and manage your data feeds across three lanes")

# Create 3 columns
col1, col2, col3 = st.columns(3, gap="large")

# ────────────────────────────────
# COLUMN 1: Lane 1 - API Feed
# ────────────────────────────────
with col1:
    st.markdown('<div class="data-feed-column">', unsafe_allow_html=True)
    
    # Logo upload at top
    st.markdown("### 🔌 Lane 1 - API Feed")
    render_logo_upload("col1", "Lane 1")
    
    # Description
    st.markdown("**Description:** API feed input for real-time data monitoring")
    
    # API Feed Input
    st.markdown("#### 🔗 API Feed URL")
    api_url = st.text_input(
        "Enter API endpoint",
        value=st.session_state.api_feed_url,
        key="api_feed_input",
        placeholder="https://api.example.com/data",
    )
    st.session_state.api_feed_url = api_url
    
    if st.button("🔄 Fetch Data", key="fetch_api_data"):
        # Simulate API fetch
        import random
        st.session_state.data_feed_values["col1"] = random.uniform(50, 90)
        st.success("✅ Data fetched successfully!")
        st.rerun()
    
    # Gauge 1 - Electric Charger Plug Style
    st.markdown("#### 📊 Gauge 1 - Electric Charger")
    gauge_value = st.session_state.data_feed_values["col1"]
    fig1 = plot_electric_charger_gauge(gauge_value, "API Feed Status")
    st.plotly_chart(fig1, use_container_width=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# ────────────────────────────────
# COLUMN 2: Lane 2 - Bi Feed
# ────────────────────────────────
with col2:
    st.markdown('<div class="data-feed-column">', unsafe_allow_html=True)
    
    # Logo upload at top
    st.markdown("### ⚡ Lane 2 - Bi Feed")
    render_logo_upload("col2", "Lane 2")
    
    # Description
    st.markdown("**Description:** Bi-directional feed for data synchronization")
    
    # Manual value adjustment
    st.markdown("#### ⚙️ Manual Adjustment")
    gauge_value = st.slider(
        "Adjust value",
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.data_feed_values["col2"],
        key="col2_slider",
    )
    st.session_state.data_feed_values["col2"] = gauge_value
    
    # Gauge 2 - EV Charger Station Style
    st.markdown("#### 📊 Gauge 2 - EV Charger Station")
    fig2 = plot_ev_charger_station_gauge(gauge_value, "Bi Feed Status")
    st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# ────────────────────────────────
# COLUMN 3: Lane 3 - Manual Input
# ────────────────────────────────
with col3:
    st.markdown('<div class="data-feed-column">', unsafe_allow_html=True)
    
    # Logo upload at top
    st.markdown("### ⛽ Lane 3 - Manual Input")
    render_logo_upload("col3", "Lane 3")
    
    # Description
    st.markdown("**Description:** Manual input with gas station-style monitoring")
    
    # Manual input value
    st.markdown("#### ✏️ Manual Input")
    manual_value = st.number_input(
        "Enter value",
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.data_feed_values["col3"],
        key="col3_manual_input",
    )
    st.session_state.data_feed_values["col3"] = manual_value
    
    # Gas station style indicator
    st.markdown("#### ⛽ Gas Station Indicator")
    gas_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=manual_value,
            title={"text": "Manual Input Status", "font": {"color": "#f5f7fb", "size": 18}},
            number={"suffix": "%", "font": {"color": "#f59e0b", "size": 32}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#7b8190"},
                "bar": {"color": "#f59e0b"},  # Orange/amber for gas
                "bgcolor": "#1b1f2a",
                "borderwidth": 2,
                "bordercolor": "#f59e0b",
                "steps": [
                    {"range": [0, 33], "color": "#1d2330"},
                    {"range": [33, 66], "color": "#252b3c"},
                    {"range": [66, 100], "color": "#2d3441"},
                ],
                "threshold": {
                    "line": {"color": "#ef4444", "width": 4},
                    "value": 90,
                },
            },
        )
    )
    gas_gauge.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
    )
    st.plotly_chart(gas_gauge, use_container_width=True)
    
    # L3 Panels
    render_l3_panels()
    
    st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown("---")
st.caption("💡 Tip: Upload logos for each lane to customize your dashboard appearance")
