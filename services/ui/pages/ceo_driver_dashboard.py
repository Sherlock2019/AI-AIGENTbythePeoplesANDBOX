#!/usr/bin/env python3
"""🚗 CEO Driver Dashboard — AI-powered business cockpit."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from services.common.company_profiles import (
    COMPANY_PRESETS,
    format_currency,
    get_company_snapshot,
)
st.set_page_config(
    page_title="🚗 CEO Driver Dashboard",
    page_icon="🚗",
    layout="wide",
)

THEME_BG = "#0E1117"
st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {THEME_BG};
        color: #f5f7fb;
    }}
    div[data-testid="stMetricValue"] {{
        color: #13B0F5;
    }}
    .mode-chip {{
        padding: 0.45rem 0.9rem;
        border-radius: 999px;
        border: 1px solid rgba(19, 176, 245, 0.4);
        margin-right: 0.6rem;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        cursor: pointer;
        background: rgba(19, 176, 245, 0.08);
    }}
    .mode-chip.active {{
        background: linear-gradient(120deg,#13B0F5,#5C3CFF);
        color: #0E1117;
        font-weight: 700;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _plot_gauge(value: float, title: str, min_val: float, max_val: float, unit: str = "") -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=value,
            title={"text": title, "font": {"color": "#f5f7fb"}},
            delta={"reference": 75, "relative": True},
            number={"suffix": unit, "font": {"color": "#f5f7fb"}},
            gauge={
                "axis": {"range": [min_val, max_val], "tickcolor": "#7b8190"},
                "bar": {"color": "#13B0F5"},
                "bgcolor": "#1b1f2a",
                "borderwidth": 2,
                "bordercolor": "#2b3041",
                "steps": [
                    {"range": [min_val, (min_val + max_val) / 2], "color": "#1d2330"},
                    {"range": [(min_val + max_val) / 2, max_val], "color": "#252b3c"},
                ],
                "threshold": {"line": {"color": "#F38BA0", "width": 4}, "value": max_val * 0.85},
            },
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=320,
    )
    return fig


def _mock_map_df(center: Tuple[float, float]) -> pd.DataFrame:
    np.random.seed(42)
    base_lat, base_lon = center
    clusters = []
    for idx in range(12):
        clusters.append(
            {
                "lat": base_lat + np.random.randn() * 0.2,
                "lon": base_lon + np.random.randn() * 0.2,
                "intensity": random.choice([20, 40, 60, 80]),
                "label": random.choice(["Demand", "Competitor", "Lead"]),
            }
        )
    return pd.DataFrame(clusters)


def _mock_reviews(company: str) -> pd.DataFrame:
    sentiments = ["🚀 Evangelist", "🙂 Promoter", "😐 Passive", "⚠️ Detractor"]
    company_notes = {
        "Amazon": [
            "Prime Ops feels sharper with the cockpit upgrades.",
            "Need proactive alerts on logistics congestion.",
            "Advertising push is paying off — keep the pace.",
            "Robotics pilot lowered ops heat noticeably.",
        ],
        "Palantir": [
            "Foundry autopilot scheduling is a hit with gov clients.",
            "Need clearer pricing signals before Storm mode engagements.",
            "AI narratives resonate — growth mode justified.",
            "Please keep Ops coolant on during defense surges.",
        ],
        "Rackspace": [
            "Managed cloud teams love the new radar insights.",
            "Legacy migrations still trigger heat spikes.",
            "Customers want faster refuel recommendations.",
            "Exploration mode unlocked new partner plays.",
        ],
    }
    notes = company_notes.get(company, company_notes["Amazon"])
    rows = []
    for idx in range(4):
        rows.append(
            {
                "Customer": f"Account {chr(65+idx)}",
                "NPS": random.randint(4, 10),
                "Sentiment": sentiments[idx % len(sentiments)],
                "Note": notes[idx],
            }
        )
    return pd.DataFrame(rows)


def _mock_calendar(company: str) -> pd.DataFrame:
    base = datetime.utcnow()
    templates = {
        "Amazon": [
            ("Prime Pulse", "Global growth sync & supply balancing"),
            ("Ops Pit Stop", "Automation cooldown + crew reset"),
            ("Marketplace GPS", "Route recalibration for EU/US"),
            ("Storm Drill", "Logistics risk simulation"),
        ],
        "Palantir": [
            ("Gov QBR", "Defense portfolio checkpoint"),
            ("Foundry Sprint", "AI model alignment workshop"),
            ("Exploration Lab", "Regulatory scenario planning"),
            ("Storm Mode Prep", "Crisis communications rehearsal"),
        ],
        "Rackspace": [
            ("Cloud Pulse", "Customer success + churn huddle"),
            ("Service Pit-Stop", "Ops maintenance window"),
            ("Partner Recon", "New alliances discovery"),
            ("Storm Triage", "Incident readiness tabletop"),
        ],
    }
    events = templates.get(company, templates["Amazon"])
    return pd.DataFrame(
        [
            {
                "When": (base + timedelta(days=i)).strftime("%b %d • %H:%M"),
                "Title": events[i][0],
                "Description": events[i][1],
                "Impact": random.choice(["High", "Medium", "Low"]),
            }
            for i in range(len(events))
        ]
    )


st.title("🚗 CEO Driver Dashboard")
st.caption("AI-powered command seat for CEOs — align revenue speed, cash fuel, ops heat, and market traffic in one cockpit.")

company_choice = st.selectbox("Company cockpit", list(COMPANY_PRESETS.keys()))
use_live = st.toggle("Use live market scrape", value=False, help="Pulls Yahoo Finance snapshot when enabled.")
snapshot = get_company_snapshot(company_choice, prefer_live=use_live)
metrics: Dict[str, float] = snapshot["metrics"]
financials = snapshot["financials"]
hq_lat, hq_lon = snapshot["hq"]

st.subheader(f"{company_choice} • {snapshot['symbol']} • {snapshot['sector']}")
fin_cols = st.columns(4)
fin_values = [
    ("Revenue (TTM)", format_currency(financials.get("revenue"))),
    ("Cash", format_currency(financials.get("cash"))),
    ("Debt", format_currency(financials.get("debt"))),
    ("P/E", f"{financials.get('pe_ratio'):.1f}" if financials.get("pe_ratio") else "—"),
]
for c, (label, value) in zip(fin_cols, fin_values):
    with c:
        st.metric(label, value)

mode = st.selectbox(
    "Driving mode",
    ["Eco", "Sport", "Autopilot", "Storm", "Exploration", "Pit-Stop"],
    index=2,
)
mode_bio = {
    "Eco": "Cash preservation: efficiency first, gentle acceleration.",
    "Sport": "Growth push: aggressive GTM, bold spend.",
    "Autopilot": "Routine AI control: decisions optimized automatically.",
    "Storm": "Crisis response: risks and cash overrides take precedence.",
    "Exploration": "Market expansion: scenario labs + sandbox budgets.",
    "Pit-Stop": "Maintenance focus: ops cooldown, team recharge.",
}
st.info(f"**{mode} Mode** — {mode_bio[mode]}")

metrics = _mock_kpis()
left, center, right = st.columns([1, 1, 1])
with left:
    st.plotly_chart(_plot_gauge(metrics["rev_speed"], "Revenue Speed", 0, 160, " km/h"), use_container_width=True)
with center:
    st.plotly_chart(_plot_gauge(metrics["cash_months"], "Cash Fuel (Months)", 0, 18, " mo"), use_container_width=True)
with right:
    st.plotly_chart(_plot_gauge(metrics["ops_heat"], "Engine Temp °C", 0, 120, " °C"), use_container_width=True)

map_df = _mock_map_df((hq_lat, hq_lon))
st.pydeck_chart(
    pdk.Deck(
        map_style="mapbox://styles/mapbox/dark-v10",
        initial_view_state=pdk.ViewState(latitude=hq_lat, longitude=hq_lon, zoom=8, pitch=50),
        layers=[
            pdk.Layer(
                "HexagonLayer",
                data=map_df,
                get_position="[lon, lat]",
                auto_highlight=True,
                elevation_scale=30,
                pickable=True,
                elevation_range=[0, 5000],
                extruded=True,
                coverage=1,
                get_fill_color="[255, 128, 0, 165]",
            )
        ],
        tooltip={"text": "{label}: {intensity}"},
    )
)

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    radar_noise = pd.DataFrame(
        {
            "angle": np.linspace(0, 2 * math.pi, 60),
            "radius": np.abs(np.sin(np.linspace(0, 2 * math.pi, 60)) * metrics["traffic"]),
        }
    )
    st.area_chart(radar_noise, height=220, use_container_width=True)
    st.caption("Traffic radar — market congestion pulses")
with col2:
    st.metric("Trip ETA", f"{metrics['eta_days']:.0f} days", delta=-7 if metrics["eta_days"] < 80 else +3)
    st.metric("Customer Pulse (NPS)", f"{metrics['nps']:.1f}/10", delta=+0.4)
    st.metric("Trip Timer", value=str(timedelta(days=max(0, metrics["eta_days"]))), delta="-2d vs plan")
with col3:
    alerts = pd.DataFrame(
        [
            {"Alert": "Refuel soon", "Severity": "⚠️ Medium", "Detail": "Cash runway < 4 months"},
            {"Alert": "Heat rising", "Severity": "🔥 High", "Detail": "Ops temp at 85 °C"},
            {"Alert": "Market jam", "Severity": "🛑 Critical", "Detail": "Traffic > 70 in EMEA"},
        ]
    )
    st.dataframe(alerts, use_container_width=True, hide_index=True)

st.subheader("Passenger Reviews & Sentiment")
st.dataframe(_mock_reviews(), use_container_width=True, hide_index=True)

st.subheader("Autopilot Copilot")
auto_col1, auto_col2 = st.columns([2, 1])
with auto_col1:
    autopilot_actions = st.multiselect(
        "AI Copilot toggles",
        ["Smart Pricing", "Marketing Boost", "Ops Coolant", "Route Optimizer", "Meeting Dispatcher"],
        default=["Smart Pricing", "Route Optimizer"],
    )
    st.write(
        f"**Active automations ({len(autopilot_actions)})** — "
        + ", ".join(autopilot_actions)
        if autopilot_actions
        else "No automations enabled."
    )
    user_prompt = st.chat_input("Ask the copilot (e.g., 'How far to target Q4?')")
    if user_prompt:
        adjusted_eta = max(30, metrics["eta_days"] - (10 if "accelerate" in user_prompt.lower() else 0))
        response = (
            f"{company_choice} is pacing toward the next milestone in ~{adjusted_eta:.0f} days.\n"
            f"Given {company_choice}'s {snapshot['sector']} posture, consider engaging **{mode}** mode or enable "
            f"{', '.join(autopilot_actions) if autopilot_actions else 'an autopilot routine'} to stay on course."
        )
        with st.chat_message("user"):
            st.write(user_prompt)
        with st.chat_message("assistant"):
            st.write(response)
with auto_col2:
    st.write("**AI situational advice**")
    for insight in snapshot["insights"]:
        st.markdown(f"- {insight}")

st.subheader("Smart Calendar")
calendar_df = _mock_calendar(company_choice)
st.dataframe(calendar_df, hide_index=True, use_container_width=True)

col_a, col_b = st.columns(2)
with col_a:
    st.write("**Approve AI booking**")
    selected_event = st.selectbox("Choose proposed event", list(calendar_df["Title"]))
    if st.button("Approve & Sync"):
        st.success(f"{selected_event} booked. Timeline updated and ETA recalculated.")
with col_b:
    st.write("**Next 7-day timeline**")
    timeline = pd.DataFrame(
        {
            "Day": [ (datetime.utcnow()+timedelta(days=i)).strftime("%a") for i in range(7)],
            "Speed_Target": [random.randint(70, 120) for _ in range(7)],
            "Fuel_Target": [random.uniform(3.5, 6.5) for _ in range(7)],
        }
    )
    st.line_chart(timeline.set_index("Day"))

st.caption("© 2025 CEO Driver AI Seat — Built for adaptive leadership.")
