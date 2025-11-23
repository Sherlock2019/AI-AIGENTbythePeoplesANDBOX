#!/usr/bin/env python3
"""🚗 CEO driver DASHBOARD — AI-powered business cockpit."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from pathlib import Path
import json
import html
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from services.common.company_profiles import (
    COMPANY_PRESETS,
    format_currency,
    get_company_snapshot,
)
st.set_page_config(
    page_title="🚗 CEO driver DASHBOARD",
    page_icon="🚗",
    layout="wide",
)

THEME_BG = "#0E1117"
st.markdown(
    f"""
    <style>
    /* Mercedes Dashboard Theme - Premium Car Dashboard Design */
    .stApp {{
        background: linear-gradient(135deg, #0a0e1a 0%, #0f1419 50%, #0a0e1a 100%);
        color: #f5f7fb;
        font-family: 'Arial', 'Helvetica Neue', sans-serif;
    }}
    
    /* Remove blank spaces */
    .main .block-container {{
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }}
    
    div[data-testid="stMetricValue"] {{
        color: #13B0F5;
        font-weight: 700;
        font-size: 1.5rem;
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
    
    /* Mercedes-style section headers */
    .section-header {{
        background: linear-gradient(90deg, rgba(19, 176, 245, 0.1), rgba(92, 60, 255, 0.1));
        border-left: 4px solid #13B0F5;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin: 1.5rem 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }}
    
    /* Remove gaps between sections */
    hr.section-divider {{
        margin: 0.5rem 0;
        border: none;
        border-top: 1px solid rgba(100, 116, 139, 0.2);
    }}
    
    /* Premium card styling */
    [data-testid="stMetric"] {{
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.8), rgba(30, 41, 59, 0.8));
        border: 1px solid rgba(19, 176, 245, 0.2);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }}
    
    /* Full width containers */
    .stColumn {{
        padding: 0.5rem;
    }}
    
    /* Remove extra spacing */
    .element-container {{
        margin-bottom: 0.5rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _plot_gauge(value: float, title: str, min_val: float, max_val: float, unit: str = "") -> go.Figure:
    """Mercedes-style circular gauge for car dashboard."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=value,
            title={"text": title, "font": {"color": "#f5f7fb", "size": 16}},
            delta={"reference": (min_val + max_val) / 2, "relative": False},
            number={"suffix": unit, "font": {"color": "#13B0F5", "size": 28}},
            gauge={
                "axis": {
                    "range": [min_val, max_val], 
                    "tickcolor": "#7b8190",
                    "tickwidth": 2,
                    "ticklen": 8,
                    "showticksuffix": "last",
                },
                "bar": {"color": "#13B0F5", "thickness": 0.15},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 3,
                "bordercolor": "#1e293b",
                "steps": [
                    {"range": [min_val, (min_val + max_val) * 0.5], "color": "#1d2330"},
                    {"range": [(min_val + max_val) * 0.5, (min_val + max_val) * 0.8], "color": "#252b3c"},
                    {"range": [(min_val + max_val) * 0.8, max_val], "color": "#1e3a5f"},
                ],
                "threshold": {
                    "line": {"color": "#F38BA0", "width": 4}, 
                    "value": max_val * 0.85,
                    "thickness": 0.75,
                },
            },
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=300,
        font={"family": "Arial, sans-serif"},
    )
    return fig


def _plot_level_gauge(value: float, title: str, min_val: float, max_val: float, unit: str = "", color: str = "#13B0F5") -> go.Figure:
    """Mercedes-style horizontal level gauge (like fuel gauge in car)."""
    percentage = ((value - min_val) / (max_val - min_val)) * 100 if max_val > min_val else 0
    percentage = max(0, min(100, percentage))
    
    fig = go.Figure()
    
    # Background bar
    fig.add_trace(go.Bar(
        x=[percentage],
        y=[title],
        orientation='h',
        marker=dict(
            color=color,
            line=dict(color=color, width=2),
        ),
        base=0,
        width=0.6,
        showlegend=False,
        text=[f"{value:.1f}{unit}"],
        textposition='inside',
        textfont=dict(color='#0f172a', size=14, family='Arial, sans-serif'),
    ))
    
    # Full range background
    fig.add_trace(go.Bar(
        x=[100],
        y=[title],
        orientation='h',
        marker=dict(
            color='rgba(30, 41, 59, 0.3)',
            line=dict(color='#1e293b', width=1),
        ),
        base=0,
        width=0.6,
        showlegend=False,
        opacity=0.3,
    ))
    
    fig.update_layout(
        xaxis=dict(
            range=[0, 100],
            showgrid=True,
            gridcolor='rgba(100, 116, 139, 0.2)',
            showticklabels=False,
        ),
        yaxis=dict(showticklabels=False),
        height=80,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    
    return fig


def _maritime_compass_gauge(deviation_pct: float, title: str) -> go.Figure:
    """Beautiful maritime compass with dynamic movement visualization."""
    deviation = max(-50.0, min(50.0, deviation_pct))
    
    # Create beautiful maritime-style compass using polar plot
    fig = go.Figure()
    
    # Compass background (full circle)
    theta_full = np.linspace(0, 360, 360)
    r_full = np.ones(360) * 0.95
    fig.add_trace(go.Scatterpolar(
        r=r_full,
        theta=theta_full,
        mode='lines',
        line=dict(color='rgba(59, 130, 246, 0.5)', width=4),
        fill='toself',
        fillcolor='rgba(15, 23, 42, 0.8)',
        name='Compass Ring',
        showlegend=False,
    ))
    
    # Inner ring for depth
    r_inner = np.ones(360) * 0.7
    fig.add_trace(go.Scatterpolar(
        r=r_inner,
        theta=theta_full,
        mode='lines',
        line=dict(color='rgba(30, 58, 138, 0.6)', width=2),
        fill='toself',
        fillcolor='rgba(15, 23, 42, 0.9)',
        showlegend=False,
    ))
    
    # Cardinal directions (N, E, S, W) - larger and prominent
    cardinals = ['N', 'E', 'S', 'W']
    cardinal_angles = [0, 90, 180, 270]
    cardinal_colors = ['#22c55e', '#3b82f6', '#ef4444', '#f59e0b']  # Green, Blue, Red, Yellow
    
    for card, angle, color in zip(cardinals, cardinal_angles, cardinal_colors):
        fig.add_trace(go.Scatterpolar(
            r=[0.88],
            theta=[angle],
            mode='text',
            text=[f"<b style='font-size:32px;'>{card}</b>"],
            textfont=dict(size=32, color=color, family="Arial Black"),
            showlegend=False,
        ))
    
    # Calculate needle direction: North (0°) = on/above target, South (180°) = below target
    # Map deviation to angle: -50% → 180° (South), 0% → 0° (North), +50% → 0° (North)
    if deviation <= 0:
        needle_angle = 180 - (abs(deviation) / 50.0 * 90)  # South to East range
    else:
        needle_angle = 360 - (deviation / 50.0 * 90)  # North to West range
    
    # Compass needle (red pointing to deviation direction)
    needle_length = 0.8
    needle_r = [0, needle_length, 0, 0.15]  # Main needle + center point
    needle_theta = [needle_angle, needle_angle, (needle_angle + 180) % 360, needle_angle]
    fig.add_trace(go.Scatterpolar(
        r=needle_r,
        theta=needle_theta,
        mode='lines+markers',
        line=dict(color='#ef4444', width=5),
        marker=dict(size=[0, 15, 0, 12], color=['rgba(0,0,0,0)', '#ef4444', 'rgba(0,0,0,0)', '#f8fafc'], 
                   symbol=['circle', 'diamond', 'circle', 'circle'],
                   line=dict(color='#1e40af', width=2)),
        fill='toself',
        fillcolor='rgba(239, 68, 68, 0.2)',
        name='Compass Needle',
        showlegend=False,
    ))
    
    # Center hub
    fig.add_trace(go.Scatterpolar(
        r=[0.12],
        theta=[0],
        mode='markers',
        marker=dict(size=20, color='#f8fafc', symbol='circle', 
                   line=dict(color='#1e40af', width=3)),
        showlegend=False,
    ))
    
    # Direction indicator text
    if deviation < -10:
        direction_text = "🔴 South (Significantly Below Target)"
        direction_color = "#ef4444"
    elif deviation < 0:
        direction_text = "🟡 Southeast (Slightly Below Target)"
        direction_color = "#f59e0b"
    elif deviation < 10:
        direction_text = "🟢 North (On Track / Above Target)"
        direction_color = "#22c55e"
    else:
        direction_text = "🟢 North (Significantly Above Target)"
        direction_color = "#22c55e"
    
    # Add deviation value annotation
    fig.add_annotation(
        x=0.5,
        y=0.5,
        text=f"<b style='font-size:28px;'>{deviation:+.1f}%</b><br><span style='font-size:16px;color:#94a3b8;'>Deviation</span>",
        showarrow=False,
        font=dict(size=28, color="#f8fafc", family="Arial Black"),
        xref="paper",
        yref="paper",
        align="center",
        bgcolor="rgba(15, 23, 42, 0.8)",
        bordercolor="#1e40af",
        borderwidth=2,
    )
    
    fig.add_annotation(
        x=0.5,
        y=-0.08,
        text=f"<b>{direction_text}</b>",
        showarrow=False,
        font=dict(size=18, color=direction_color, family="Arial"),
        xref="paper",
        yref="paper",
        yanchor="top",
    )
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                showticklabels=False,
                showline=True,
                linecolor='rgba(59, 130, 246, 0.4)',
                gridcolor='rgba(59, 130, 246, 0.2)',
                gridwidth=1,
            ),
            angularaxis=dict(
                rotation=90,
                direction='clockwise',
                showticklabels=False,  # Hide default labels, using custom cardinal markers
                gridcolor='rgba(59, 130, 246, 0.3)',
                linecolor='rgba(59, 130, 246, 0.5)',
                gridwidth=2,
            ),
        ),
        margin=dict(l=60, r=60, t=120, b=180),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=750,
        title=dict(
            text=f"<b>🧭 {title}</b>",
            font=dict(size=24, color="#cbd5e1", family="Arial"),
            x=0.5,
            y=0.97,
            xanchor='center',
            yanchor='top',
        ),
    )
    return fig


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


MARKET_CITIES: List[Dict] = [
    {
        "name": "SaaS City",
        "center": [-7.5, 4.5],
        "tam": 190,
        "cagr": 0.18,
        "profit": 0.32,
        "barrier": 0.55,
        "maturity": "Mid",
        "color": "#38bdf8",
        "districts": ["Enterprise Avenue", "Startup Street", "Customer Success Loop"],
    },
    {
        "name": "Cloud City",
        "center": [-2.5, 4.2],
        "tam": 240,
        "cagr": 0.21,
        "profit": 0.36,
        "barrier": 0.62,
        "maturity": "Mid",
        "color": "#60a5fa",
        "districts": ["Hyperscaler Highway", "Sovereign Cloud Blvd", "Edge Computing Road"],
    },
    {
        "name": "AI District",
        "center": [2.5, 4.6],
        "tam": 320,
        "cagr": 0.34,
        "profit": 0.41,
        "barrier": 0.48,
        "maturity": "Early",
        "color": "#c084fc",
        "districts": ["LLM Lane", "Automation Square", "MLOps Street"],
    },
    {
        "name": "FinTech City",
        "center": [-6.5, -0.5],
        "tam": 210,
        "cagr": 0.19,
        "profit": 0.38,
        "barrier": 0.71,
        "maturity": "Mid",
        "color": "#34d399",
        "districts": ["Payments Plaza", "Compliance Court", "Lending Lane"],
    },
    {
        "name": "Retail Metro",
        "center": [-1.0, -1.5],
        "tam": 260,
        "cagr": 0.11,
        "profit": 0.22,
        "barrier": 0.41,
        "maturity": "Mid",
        "color": "#fb7185",
        "districts": ["Omnichannel Overpass", "Direct-to-Consumer Drive"],
    },
    {
        "name": "HealthTech Haven",
        "center": [4.5, -0.5],
        "tam": 180,
        "cagr": 0.16,
        "profit": 0.35,
        "barrier": 0.68,
        "maturity": "Early",
        "color": "#fcd34d",
        "districts": ["Care Delivery Street", "Bio-data Boulevard"],
    },
    {
        "name": "Telco Town",
        "center": [-3.5, -3.5],
        "tam": 150,
        "cagr": 0.08,
        "profit": 0.28,
        "barrier": 0.74,
        "maturity": "Late",
        "color": "#f97316",
        "districts": ["5G Turnpike", "Carrier Circle"],
    },
    {
        "name": "GovTech Capital",
        "center": [-3.5, -5.0],
        "tam": 95,
        "cagr": 0.09,
        "profit": 0.31,
        "barrier": 0.77,
        "maturity": "Mid",
        "color": "#f59e0b",
        "districts": ["Public Sector Square", "Defense Row"],
    },
    {
        "name": "SMB Village",
        "center": [3.2, -4.2],
        "tam": 140,
        "cagr": 0.13,
        "profit": 0.24,
        "barrier": 0.33,
        "maturity": "Early",
        "color": "#2dd4bf",
        "districts": ["Builder Street", "Franchise Row"],
    },
    {
        "name": "Fog City",
        "center": [6.5, 2.0],
        "tam": 80,
        "cagr": 0.41,
        "profit": 0.29,
        "barrier": 0.27,
        "maturity": "Emerging",
        "color": "#94a3b8",
        "districts": ["Exploration Alley"],
    },
]

FAILURE_MARKS = [
    {"name": "WeWork Crash Site", "coords": [-5.0, -2.5], "lesson": "Hyper-growth without resilient unit economics."},
    {"name": "FTX Collapse Crater", "coords": [-1.5, -4.8], "lesson": "No governance — trust evaporated instantly."},
    {"name": "Blockbuster Dead End", "coords": [0.8, -5.5], "lesson": "Ignored digital migration signals."},
    {"name": "Nokia Lost Highway", "coords": [4.9, -2.2], "lesson": "Missed software turn — hardware only."},
    {"name": "Blackberry Turnaround Cliff", "coords": [2.2, -3.7], "lesson": "Security moat alone could not save handset share."},
    {"name": "Kodak No-Future Junction", "coords": [5.6, 1.8], "lesson": "Sat on IP; slow to commercialize digital."},
]

FOG_ZONES = [
    {"name": "Quantum Valley", "coords": [7.5, 4.5], "radius": 1.1},
    {"name": "Synthetic Data Bay", "coords": [7.8, 0.0], "radius": 1.0},
    {"name": "AGI Frontier", "coords": [6.6, -3.5], "radius": 1.2},
    {"name": "BioAI Island", "coords": [8.1, -1.2], "radius": 0.9},
    {"name": "SpaceTech Port", "coords": [6.8, -5.2], "radius": 1.0},
]

ROAD_NETWORK = {
    "highways": [
        {"name": "AI Transformation Highway", "color": "#c084fc", "width": 6, "path": [[-8, 3.5], [-2, 2.5], [3, 2.8], [6, 3.5]]},
        {"name": "Cloud Adoption Freeway", "color": "#60a5fa", "width": 6, "path": [[-9, 1.5], [-3, 1.0], [1.5, 0.8], [5.5, 0.5]]},
        {"name": "Automation Expressway", "color": "#10b981", "width": 5, "path": [[-7, -2.2], [-2, -0.8], [2, 0.2], [4.5, 1.1]]},
        {"name": "Digital Payments Superhighway", "color": "#f472b6", "width": 5, "path": [[-6.5, -3], [-4, -1.8], [-1, -0.6], [1.2, 0.4]]},
        {"name": "Sustainability Freeway", "color": "#22d3ee", "width": 4, "path": [[-8.5, -1], [-5.5, 0.5], [-1.5, 1.5], [2.5, 1.8]]},
    ],
    "arteries": [
        {"name": "Enterprise Avenue", "color": "#facc15", "width": 3, "path": [[-7, 4.9], [-6.2, 2.2], [-5.4, 0.0]]},
        {"name": "Startup Street", "color": "#fde047", "width": 2, "path": [[-8.5, 4.2], [-7.3, 2.9], [-6.0, 1.2]]},
        {"name": "Hyperscaler Highway", "color": "#fbbf24", "width": 3, "path": [[-3.5, 4.7], [-2.3, 4.0], [-1.1, 3.4]]},
        {"name": "Sovereign Cloud Blvd", "color": "#fbbf24", "width": 2, "path": [[-2.2, 4.6], [-1.5, 3.2], [-0.5, 2.7]]},
        {"name": "LLM Lane", "color": "#f472b6", "width": 2, "path": [[2.2, 5.1], [3.1, 4.2], [4.0, 3.6]]},
        {"name": "Automation Square", "color": "#f472b6", "width": 2, "path": [[1.6, 4.2], [2.4, 3.4], [3.3, 2.9]]},
    ],
}

MILESTONE_MARKERS = [
    {"name": "Prototype Gate", "type": "milestone", "icon": "prototype", "coords": [-7.2, -5.5]},
    {"name": "MVP Gate", "type": "milestone", "icon": "mvp", "coords": [-5.5, -3.8]},
    {"name": "Compliance Gate", "type": "checkpoint", "icon": "compliance", "coords": [-3.9, -2.1]},
    {"name": "Board Toll", "type": "checkpoint", "icon": "board", "coords": [-2.1, -0.7]},
    {"name": "Capital Raise Toll", "type": "checkpoint", "icon": "capital", "coords": [-0.2, 0.4]},
    {"name": "Market Launch Landmark", "type": "milestone", "icon": "launch", "coords": [2.1, 2.2]},
    {"name": "Expansion Bridge", "type": "milestone", "icon": "bridge", "coords": [3.4, 3.0]},
    {"name": "Profitability Tunnel", "type": "milestone", "icon": "profit", "coords": [4.6, 3.5]},
    {"name": "Acquisition Outpost", "type": "milestone", "icon": "acquire", "coords": [5.8, 3.9]},
]

TRADING_VIEW_SYMBOLS = {
    "Amazon": "NASDAQ:AMZN",
    "Palantir": "NYSE:PLTR",
    "Rackspace": "NASDAQ:RXT",
}

MODE_CITY_DEFAULTS = {
    "Eco": "FinTech City",
    "Sport": "AI District",
    "Autopilot": "Cloud City",
    "Storm": "GovTech Capital",
    "Exploration": "SaaS City",
    "Pit-Stop": "HealthTech Haven",
}


def _seeded_rng(seed: str) -> random.Random:
    return random.Random(abs(hash(seed)) % (2**32))


def _square_polygon(center: List[float], size: float = 0.9) -> List[List[float]]:
    cx, cy = center
    return [
        [cx - size, cy - size],
        [cx + size, cy - size],
        [cx + size, cy + size],
        [cx - size, cy + size],
        [cx - size, cy - size],
    ]


def _build_map_payload(company: str, metrics: Dict[str, float], mode: str) -> Dict:
    rng = _seeded_rng(company + mode)
    cities = []
    for city in MARKET_CITIES:
        size_scale = 0.6 if city["name"] == "Fog City" else 1.0
        height = (city["tam"] / 400) * 12000 * size_scale
        cities.append(
            {
                "type": "Feature",
                "properties": {
                    "name": city["name"],
                    "tam": city["tam"],
                    "cagr": city["cagr"],
                    "profit": city["profit"],
                    "barrier": city["barrier"],
                    "maturity": city["maturity"],
                    "color": city["color"],
                    "districts": city["districts"],
                    "height": height,
                },
                "geometry": {"type": "Polygon", "coordinates": [[list(coord) for coord in _square_polygon(city["center"], 1.1 * size_scale)]]},
            }
        )

    roads = []
    for group, features in ROAD_NETWORK.items():
        for feature in features:
            roads.append(
                {
                    "type": "Feature",
                    "properties": {
                        "name": feature["name"],
                        "width": feature["width"],
                        "color": feature["color"],
                        "category": group,
                    },
                    "geometry": {"type": "LineString", "coordinates": feature["path"]},
                }
            )

    competitor_styles = [
        {"label": "AWS SuperTruck", "type": "hyperscaler", "color": "#f97316"},
        {"label": "Microsoft Fleet", "type": "enterprise", "color": "#64748b"},
        {"label": "Snowflake Jet", "type": "startup", "color": "#38bdf8"},
        {"label": "Stripe Racer", "type": "fintech", "color": "#34d399"},
        {"label": "Legacy Bus", "type": "legacy", "color": "#94a3b8"},
        {"label": "OpenAI Ghost", "type": "ai-native", "color": "#a855f7"},
    ]
    competitors = []
    for rival in competitor_styles:
        competitors.append(
            {
                "label": rival["label"],
                "color": rival["color"],
                "type": rival["type"],
                "speed": rng.randint(30, 110),
                "share": rng.randint(8, 45),
                "position": [rng.uniform(-8, 7), rng.uniform(-6.5, 5.5)],
                "target": rng.choice(MARKET_CITIES)["name"],
                "lane": rng.choice(["highway", "artery", "street"]),
            }
        )

    dest_name = MODE_CITY_DEFAULTS.get(mode, "AI District")
    destination = next((c for c in MARKET_CITIES if c["name"] == dest_name), MARKET_CITIES[0])
    origin = [-9.0, -6.5]
    detour = [(origin[0] + destination["center"][0]) / 2, (origin[1] + destination["center"][1]) / 2 + 1.5]
    primary_route = [origin, detour, destination["center"]]
    alt_city = next((c for c in MARKET_CITIES if c["name"] != destination["name"]), MARKET_CITIES[1])
    alternate_route = [origin, [detour[0] + 1.5, detour[1] - 1.0], alt_city["center"]]

    milestones = []
    for marker in MILESTONE_MARKERS:
        milestones.append(
            {
                "name": marker["name"],
                "type": marker["type"],
                "icon": marker["icon"],
                "status": rng.choice(["completed", "upcoming", "blocked"]),
                "coords": marker["coords"],
            }
        )

    fog_features = []
    for fog in FOG_ZONES:
        fog_features.append(
            {
                "type": "Feature",
                "properties": {"name": fog["name"], "radius": fog["radius"]},
                "geometry": {"type": "Point", "coordinates": fog["coords"]},
            }
        )

    accidents = []
    for fail in FAILURE_MARKS:
        accidents.append(
            {
                "type": "Feature",
                "properties": {"name": fail["name"], "lesson": fail["lesson"]},
                "geometry": {"type": "Point", "coordinates": fail["coords"]},
            }
        )

    traffic_levels = []
    for road in roads:
        cars_on_path = rng.randint(1, 14)
        traffic_levels.append(
            {
                "road": road["properties"]["name"],
                "level": cars_on_path,
                "status": "clear" if cars_on_path <= 2 else "busy" if cars_on_path <= 6 else "heavy" if cars_on_path <= 12 else "jam",
            }
        )

    navigation_panel = [
        "Depart HQ and stay on Founders' Lane for 2 months.",
        "Turn right into Enterprise Avenue.",
        "Merge onto Automation Expressway toward AI District.",
        f"Continue on {destination['name']} route for {int(metrics.get('eta_days', 0))} days.",
        "Exit toward Market Launch Landmark. Prepare for Board Toll checkpoint.",
    ]

    return {
        "cities": {"type": "FeatureCollection", "features": cities},
        "roads": {"type": "FeatureCollection", "features": roads},
        "competitors": competitors,
        "user_car": {
            "company": company,
            "mode": mode,
            "speed": metrics.get("rev_speed", 90),
            "fuel": metrics.get("cash_months", 8),
            "route": primary_route,
            "alternate": alternate_route,
        },
        "milestones": milestones,
        "fog": {"type": "FeatureCollection", "features": fog_features},
        "accidents": {"type": "FeatureCollection", "features": accidents},
        "traffic": traffic_levels,
        "navigation": navigation_panel,
    }


def _render_stock_widget(company: str, ticker: str | None) -> None:
    candidate = TRADING_VIEW_SYMBOLS.get(company)
    symbol = candidate or (f"NASDAQ:{ticker}" if ticker and ":" not in ticker else (ticker or "NASDAQ:AMZN"))
    widget_id = f"tv-mini-{company.lower().replace(' ', '-')}"
    config = {
        "symbol": symbol,
        "width": "100%",
        "height": 200,
        "locale": "en",
        "dateRange": "1D",
        "colorTheme": "dark",
        "trendLineColor": "#37a2eb",
        "underLineColor": "rgba(55, 162, 235, 0.15)",
        "underLineBottomColor": "rgba(55, 162, 235, 0.01)",
        "isTransparent": False,
        "autosize": True,
    }
    html = f"""
    <div class="tradingview-widget-container" style="width:100%;height:210px;">
      <div id="{widget_id}"></div>
      <div class="tradingview-widget-copyright">
        <a href="https://www.tradingview.com/symbols/{symbol.split(':')[-1]}/" target="_blank" rel="noopener">Quotes by TradingView</a>
      </div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
      {json.dumps(config)}
      </script>
    </div>
    """
    components.html(html, height=220)


def _render_business_city_metaverse(company: str, metrics: Dict[str, float], mode: str):
    payload = _build_map_payload(company, metrics, mode)
    nav_items = "".join(f"<li>{step}</li>" for step in payload["navigation"])

    def _city(name, left, top, tam, cagr, profit, barrier, future=False):
        info = f"{name}|TAM ${tam}B|CAGR {cagr}%|Profit {profit}%|Barrier {barrier}%"
        cls = "city future" if future else "city"
        return (
            f'<div class="{cls}" style="left:{left}px;top:{top}px;" data-info="{info}">'
            f"<span>{name}</span>"
            "</div>"
        )

    core_cities = [
        ("Cloud City", 240, 520, 550, 17, 33, 41),
        ("AI District", 520, 480, 680, 24, 30, 38),
        ("FinTech City", 780, 420, 310, 13, 26, 35),
        ("Retail Metro", 980, 360, 260, 10, 22, 41),
        ("HealthTech Haven", 430, 640, 410, 18, 29, 39),
        ("SaaS City", 700, 690, 380, 21, 35, 31),
        ("GovTech Capital", 900, 520, 120, 8, 18, 58),
        ("SMB Village", 1120, 590, 140, 12, 19, 22),
        ("Telco Town", 640, 560, 900, 7, 14, 70),
    ]
    frontier_cities = [
        ("Quantum Valley", 280, 140, 95, 41, 18, 25),
        ("Synthetic Data Bay", 560, 200, 75, 44, 22, 28),
        ("Autonomous Enterprise District", 830, 180, 110, 38, 24, 36),
        ("AGI Frontier", 1090, 220, 60, 52, 20, 48),
        ("BioAI Island", 1280, 280, 45, 37, 17, 22),
        ("SpaceTech Port", 1420, 340, 120, 33, 29, 41),
    ]

    crash_sites = [
        ("WeWork Crash Site", 600, 370),
        ("FTX Collapse Crater", 710, 320),
        ("Blockbuster Dead End", 820, 660),
        ("Nokia Lost Highway", 930, 710),
        ("Kodak No-Future Junction", 500, 450),
    ]

    fog_positions = [
        (230, 120),
        (520, 180),
        (780, 150),
        (1040, 200),
        (1260, 240),
        (1410, 300),
    ]

    car_configs = [
        {"id": "car1", "class": "car car-green", "path": {"x1": 240, "y1": 520, "x2": 520, "y2": 480}, "speed": 0.0025},
        {"id": "car2", "class": "car car-red", "path": {"x1": 520, "y1": 480, "x2": 780, "y2": 420}, "speed": 0.0029},
        {"id": "car3", "class": "car car-yellow", "path": {"x1": 700, "y1": 690, "x2": 1120, "y2": 590}, "speed": 0.0021},
    ]

    city_markup = "\n".join(
        [_city(*c) for c in core_cities] + [_city(*c, future=True) for c in frontier_cities]
    )
    fog_markup = "\n".join(
        f'<div class="fog" style="left:{x}px;top:{y}px;"></div>' for x, y in fog_positions
    )
    crash_markup = "\n".join(
        f'<div class="crash" style="left:{x}px;top:{y}px;">{label}</div>' for label, x, y in crash_sites
    )
    car_markup = "\n".join(
        f'<div id="{car["id"]}" class="{car["class"]}" style="left:{car["path"]["x1"]}px;top:{car["path"]["y1"]}px;"></div>'
        for car in car_configs
    )
    car_paths_json = json.dumps(car_configs)

    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>TRON Business City Metaverse</title>
<style>
html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    font-family: "Segoe UI", sans-serif;
    background: #030712;
}}
#world {{
    position: relative;
    width: 100vw;
    height: 100vh;
    background: url('/mnt/data/tron.png') center/cover no-repeat;
    perspective: 1600px;
    transform-style: preserve-3d;
    color: #e0f2ff;
}}
#world::before {{
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(3,7,18,0.45), rgba(3,7,18,0.95));
    pointer-events: none;
}}
#grid-overlay {{
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(
        0deg,
        rgba(0,255,255,0.08) 0,
        rgba(0,255,255,0.08) 1px,
        transparent 1px,
        transparent 40px
    ),
    repeating-linear-gradient(
        90deg,
        rgba(0,255,255,0.08) 0,
        rgba(0,255,255,0.08) 1px,
        transparent 1px,
        transparent 40px
    );
    transform: rotateX(55deg) translateZ(-200px);
    transform-origin: center;
    opacity: 0.35;
}}
#panel {{
    position: absolute;
    left: 32px;
    top: 32px;
    width: 280px;
    padding: 20px;
    background: rgba(4,15,35,0.85);
    border: 1px solid rgba(0,200,255,0.65);
    border-radius: 16px;
    box-shadow: 0 0 25px rgba(0,200,255,0.35);
    z-index: 10;
    backdrop-filter: blur(8px);
}}
#panel h2 {{
    margin: 0 0 10px;
    font-size: 20px;
    color: #67e8f9;
}}
#panel ol {{
    margin: 0;
    padding-left: 20px;
    color: #cbd5f5;
    font-size: 14px;
}}
#panel button {{
    width: 100%;
    margin-top: 16px;
    padding: 12px;
    border-radius: 12px;
    border: 1px solid #22d3ee;
    background: linear-gradient(120deg, rgba(34,211,238,0.2), rgba(59,130,246,0.2));
    color: #e0f2ff;
    font-weight: 600;
    cursor: pointer;
    transition: 0.3s ease;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
#panel button:hover {{
    box-shadow: 0 0 18px rgba(34,211,238,0.6);
    background: linear-gradient(120deg, rgba(34,211,238,0.4), rgba(59,130,246,0.4));
}}
.city {{
    position: absolute;
    padding: 14px 18px;
    border: 1px solid rgba(34,211,238,0.8);
    border-radius: 10px;
    background: rgba(8,13,30,0.8);
    color: #e0f2ff;
    box-shadow: 0 0 18px rgba(34,211,238,0.35);
    animation: cityPulse 3s infinite ease-in-out;
    white-space: nowrap;
    transform: translateZ(20px);
    cursor: pointer;
}}
.city.future {{
    border-color: rgba(236,72,153,0.8);
    box-shadow: 0 0 18px rgba(236,72,153,0.4);
}}
.city span {{
    font-weight: 600;
    letter-spacing: 0.05em;
}}
@keyframes cityPulse {{
    0% {{ box-shadow: 0 0 12px rgba(34,211,238,0.3); }}
    50% {{ box-shadow: 0 0 25px rgba(34,211,238,0.6); }}
    100% {{ box-shadow: 0 0 12px rgba(34,211,238,0.3); }}
}}
.fog {{
    position: absolute;
    width: 160px;
    height: 160px;
    background: radial-gradient(circle, rgba(59,130,246,0.35), rgba(59,130,246,0));
    border-radius: 50%;
    animation: fogFloat 10s infinite ease-in-out;
    filter: blur(2px);
    transform: translateZ(-30px);
}}
@keyframes fogFloat {{
    0% {{ opacity: 0.35; transform: translateZ(-20px) translateY(0); }}
    50% {{ opacity: 0.65; transform: translateZ(-20px) translateY(-10px); }}
    100% {{ opacity: 0.35; transform: translateZ(-20px) translateY(0); }}
}}
.crash {{
    position: absolute;
    padding: 8px 12px;
    background: rgba(185,28,28,0.7);
    border: 1px solid rgba(248,113,113,0.9);
    border-radius: 8px;
    font-size: 12px;
    color: #fee2e2;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    box-shadow: 0 0 18px rgba(248,113,113,0.6);
}}
svg#roads {{
    position: absolute;
    inset: 0;
    pointer-events: none;
    filter: drop-shadow(0 0 12px rgba(34,211,238,0.5));
}}
.road {{
    stroke: #22d3ee;
    stroke-width: 4;
    stroke-linecap: round;
    stroke-linejoin: round;
    opacity: 0.9;
}}
.road.alt {{
    stroke: #a855f7;
    stroke-dasharray: 10 10;
}}
.car {{
    position: absolute;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    box-shadow: 0 0 15px currentColor;
    animation: wobble 1.5s infinite ease-in-out;
}}
.car-green {{ color: #4ade80; }}
.car-red {{ color: #fb7185; }}
.car-yellow {{ color: #facc15; }}
@keyframes wobble {{
    0% {{ transform: translateZ(30px) translateY(0); }}
    50% {{ transform: translateZ(30px) translateY(-4px); }}
    100% {{ transform: translateZ(30px) translateY(0); }}
}}
#tooltip {{
    position: fixed;
    padding: 10px 14px;
    background: rgba(3,7,18,0.9);
    border: 1px solid #38bdf8;
    border-radius: 10px;
    color: #e0f2ff;
    font-size: 13px;
    pointer-events: none;
    display: none;
    z-index: 20;
    min-width: 180px;
    box-shadow: 0 0 18px rgba(56,189,248,0.35);
}}
</style>
</head>
<body>
<div id="world">
    <div id="grid-overlay"></div>
    <div id="panel">
        <h2>Turn-By-Turn Navigation</h2>
        <ol>@@NAV_ITEMS@@</ol>
        <button>Enable Future Autopilot</button>
    </div>
    <div id="tooltip"></div>
    <svg id="roads" viewBox="0 0 1500 900" preserveAspectRatio="xMidYMid slice">
        <polyline class="road" points="240,520 520,480 780,420 980,360" />
        <polyline class="road" points="240,520 430,640 700,690" />
        <polyline class="road" points="700,690 1120,590" />
        <polyline class="road alt" points="520,480 900,520 1120,590" />
        <polyline class="road" points="520,480 430,640" />
        <polyline class="road" points="780,420 900,520 980,360" />
        <polyline class="road alt" points="280,140 560,200 830,180 1090,220 1280,280 1420,340" />
    </svg>
    @@FOG_MARKUP@@
    @@CITY_MARKUP@@
    @@CRASH_MARKUP@@
    @@CAR_MARKUP@@
</div>
<script>
const tooltip = document.getElementById("tooltip");
document.querySelectorAll(".city").forEach(city => {{
    city.addEventListener("mouseenter", () => {{
        tooltip.innerHTML = city.dataset.info.split("|").join("<br>");
        tooltip.style.display = "block";
    }});
    city.addEventListener("mousemove", (e) => {{
        tooltip.style.left = e.clientX + 18 + "px";
        tooltip.style.top = e.clientY + 18 + "px";
    }});
    city.addEventListener("mouseleave", () => {{
        tooltip.style.display = "none";
    }});
}});

const carConfigs = @@CAR_PATHS@@;
function animateCar(car, path, speed) {{
    let t = 0;
    function step() {{
        t += speed;
        if (t > 1) t = 0;
        const nx = path.x1 + (path.x2 - path.x1) * t;
        const ny = path.y1 + (path.y2 - path.y1) * t;
        car.style.left = nx + "px";
        car.style.top = ny + "px";
        requestAnimationFrame(step);
    }}
    step();
}}
carConfigs.forEach(cfg => {{
    const car = document.getElementById(cfg.id);
    if (car) {{
        animateCar(car, cfg.path, cfg.speed);
    }}
}});
</script>
</body>
</html>
"""
    html = (
        html_template.replace("@@NAV_ITEMS@@", nav_items)
        .replace("@@CITY_MARKUP@@", city_markup)
        .replace("@@FOG_MARKUP@@", fog_markup)
        .replace("@@CRASH_MARKUP@@", crash_markup)
        .replace("@@CAR_MARKUP@@", car_markup)
        .replace("@@CAR_PATHS@@", car_paths_json)
    )
    components.html(html, height=820)


st.markdown(
    """
    <div style="text-align:center;margin-bottom:0.4rem;">
        <span style="
            display:inline-block;
            font-size:3.6rem;
            font-weight:900;
            letter-spacing:0.35rem;
            color:#67e8f9;
            background:linear-gradient(120deg,#38bdf8 0%,#22d3ee 40%,#a855f7 100%);
            -webkit-background-clip:text;
            -webkit-text-fill-color:transparent;
            text-shadow:
                0 0 10px rgba(34,211,238,0.9),
                0 0 25px rgba(34,211,238,0.7),
                0 0 45px rgba(59,130,246,0.6),
                0 0 70px rgba(168,85,247,0.45);
            transform: perspective(600px) rotateX(12deg);
        ">
            CEO driver DASHBOARD
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    '<div style="text-align:center;">AI-powered command seat for CEOs — align revenue speed, cash fuel, ops heat, and market traffic in one cockpit.</div>',
    unsafe_allow_html=True,
)

# Navigation Bar
st.markdown(
    """
    <style>
    .nav-bar {
        background: linear-gradient(90deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 12px;
        padding: 0.8rem 1.5rem;
        margin: 1rem 0;
        display: flex;
        justify-content: space-around;
        align-items: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .nav-item {
        padding: 0.5rem 1.2rem;
        border-radius: 8px;
        cursor: pointer;
        color: #cbd5e1;
        font-weight: 600;
        transition: all 0.3s ease;
        text-decoration: none;
    }
    .nav-item:hover {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        transform: translateY(-2px);
    }
    .nav-item.active {
        background: linear-gradient(90deg, #3b82f6, #2563eb);
        color: white;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.5);
    }
    .section-divider {
        margin: 2rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.5), transparent);
    }
    .section-header {
        margin-top: 2rem;
        margin-bottom: 1.5rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(59, 130, 246, 0.3);
    }
    html {
        scroll-behavior: smooth;
    }
    .nav-bar {
        display: flex;
        gap: 1rem;
        padding: 1rem 1.5rem;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
        border-bottom: 2px solid rgba(59, 130, 246, 0.3);
        margin-bottom: 1rem;
        border-radius: 8px;
        flex-wrap: wrap;
        justify-content: center;
        position: sticky;
        top: 0;
        z-index: 100;
        backdrop-filter: blur(10px);
    }
    .nav-item {
        padding: 0.8rem 1.5rem;
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 8px;
        color: #00D4FF;
        font-size: 1.2rem;
        font-weight: 700;
        transition: all 0.3s ease;
        text-decoration: none;
        cursor: pointer;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.6), 0 0 20px rgba(0, 212, 255, 0.4);
        letter-spacing: 0.5px;
    }
    .nav-item:hover {
        background: rgba(0, 212, 255, 0.2);
        color: #00D4FF;
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0, 212, 255, 0.5), 0 0 30px rgba(0, 212, 255, 0.3);
        text-shadow: 0 0 15px rgba(0, 212, 255, 0.8), 0 0 30px rgba(0, 212, 255, 0.6);
    }
    .nav-item.active {
        background: linear-gradient(90deg, #3b82f6, #2563eb);
        color: white;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.5);
    }
    .nav-item.top-btn {
        background: linear-gradient(135deg, #10b981, #059669);
        border-color: rgba(16, 185, 129, 0.5);
        color: white;
        font-weight: 700;
    }
    .nav-item.top-btn:hover {
        background: linear-gradient(135deg, #059669, #047857);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
    }
    </style>
    <div class="nav-bar">
        <a href="#road-market-conditions" class="nav-item" onclick="document.getElementById('road-market-conditions')?.scrollIntoView({behavior: 'smooth'}); return false;">🛣️ Road Market Conditions</a>
        <a href="#driving-mode" class="nav-item" onclick="document.getElementById('driving-mode')?.scrollIntoView({behavior: 'smooth'}); return false;">🚗 Driving Mode</a>
        <a href="#driving-mode-gauges" class="nav-item" onclick="document.getElementById('driving-mode-gauges')?.scrollIntoView({behavior: 'smooth'}); return false;">📊 Driving Mode Gauges</a>
        <a href="#ai-copilot-navigator" class="nav-item" onclick="document.getElementById('ai-copilot-navigator')?.scrollIntoView({behavior: 'smooth'}); return false;">🏎️ CEO Copilot Navigator</a>
        <a href="#ceo-metrics" class="nav-item" onclick="document.getElementById('ceo-metrics')?.scrollIntoView({behavior: 'smooth'}); return false;">📊 CEO Metrics Overview</a>
        <a href="#" class="nav-item top-btn" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}}); return false;">⬆️ Back to Top</a>
    </div>
    """,
    unsafe_allow_html=True,
)

# Preview mode enabled - Coming Soon check removed
# st.warning("🚧 CEO DRIVER SEAT is flagged **Coming Soon**. Preview is disabled while we finalize verification.")
# st.info("Thanks for your patience. Ping the platform team to request early access.")
# st.stop()
LOGO_UPLOAD_PATH = Path(".cache/ceo_assets/driver_logo.png")
# Separate logo paths for each data feed lane
LANE1_LOGO_PATH = Path(".cache/ceo_assets/lane1_logo.png")
LANE2_LOGO_PATH = Path(".cache/ceo_assets/lane2_logo.png")
LANE3_LOGO_PATH = Path(".cache/ceo_assets/lane3_logo.png")
# Company logo path (will be set based on selected company)
COMPANY_LOGO_PATH = None
# Ensure the cache directory exists for persistence across sessions
LOGO_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)

# Preload with Rackspace as default
default_company = "Rackspace" if "Rackspace" in COMPANY_PRESETS else list(COMPANY_PRESETS.keys())[0]
company_choice = st.selectbox("Company cockpit", list(COMPANY_PRESETS.keys()), index=list(COMPANY_PRESETS.keys()).index(default_company) if default_company in COMPANY_PRESETS else 0)
use_live = st.toggle("Use live market scrape", value=False, help="Pulls Yahoo Finance snapshot when enabled.")
snapshot = get_company_snapshot(company_choice, prefer_live=use_live)
metrics: Dict[str, float] = snapshot["metrics"]
financials = snapshot["financials"]

# Calculate values needed for sections
revenue_target = financials.get("revenue", 0) * 1.2  # Assume 20% growth target
revenue_current = financials.get("revenue", 0)
revenue_deviation_pct = ((revenue_current - revenue_target) / revenue_target * 100) if revenue_target > 0 else 0
current_date = datetime.now()

# Company logo path based on selected company
COMPANY_LOGO_PATH = Path(f".cache/ceo_assets/company_{company_choice.lower().replace(' ', '_')}_logo.png")
COMPANY_LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)

# Company Logo Uploader (hidden, triggered by icon)
if f'show_company_upload_{company_choice}' not in st.session_state:
    st.session_state[f'show_company_upload_{company_choice}'] = False

# Display company logo with upload icon button
logo_container = st.container()
with logo_container:
    logo_col1, logo_col2 = st.columns([20, 1])
    with logo_col1:
        if COMPANY_LOGO_PATH.exists():
            st.image(str(COMPANY_LOGO_PATH), width=200, caption=f"{company_choice} logo")
        else:
            st.info("No logo uploaded")
    with logo_col2:
        if st.button("📤", key=f"company_upload_btn_{company_choice}", help=f"Upload {company_choice} logo"):
            st.session_state[f'show_company_upload_{company_choice}'] = not st.session_state[f'show_company_upload_{company_choice}']

if st.session_state[f'show_company_upload_{company_choice}']:
    company_logo_file = st.file_uploader(
        f"Upload {company_choice} company logo", 
        type=["png", "jpg", "jpeg", "gif"], 
        key=f"company_logo_upload_{company_choice}",
        help=f"Upload a logo for {company_choice}. Logo will be saved and persist across sessions."
    )
    if company_logo_file:
        COMPANY_LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(COMPANY_LOGO_PATH, "wb") as handle:
            handle.write(company_logo_file.getbuffer())
        st.session_state[f'company_logo_uploaded_{company_choice}'] = True
        st.session_state[f'show_company_upload_{company_choice}'] = False
        st.success(f"✅ {company_choice} logo saved. It will persist across sessions.")
        st.rerun()

# SECTION 5: Company info (first)
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

# Live Market Pulse section (moved to be under company revenue)
st.markdown("#### 📈 Live Market Pulse")
_render_stock_widget(company_choice, snapshot.get("symbol"))

# SECTION 1: Logo full width (second)
st.markdown("#### 🪪 Cockpit Logo")

# Cockpit Logo with upload icon button
if 'show_cockpit_upload' not in st.session_state:
    st.session_state['show_cockpit_upload'] = False

cockpit_container = st.container()
with cockpit_container:
    cockpit_col1, cockpit_col2 = st.columns([20, 1])
    with cockpit_col1:
        if LOGO_UPLOAD_PATH.exists():
            st.image(str(LOGO_UPLOAD_PATH), use_container_width=True, caption="Current cockpit logo (saved and persists across sessions)")
        else:
            st.info("No cockpit logo uploaded")
    with cockpit_col2:
        if st.button("📤", key="cockpit_upload_btn", help="Upload cockpit logo"):
            st.session_state['show_cockpit_upload'] = not st.session_state['show_cockpit_upload']

if st.session_state['show_cockpit_upload']:
    cockpit_logo_file = st.file_uploader(
        "Upload cockpit logo", 
        type=["png", "jpg", "jpeg", "gif"], 
        key="cockpit_logo_upload_section",
        help="Upload your company emblem to brand the CEO driver DASHBOARD. Logo will persist across sessions."
    )
    if cockpit_logo_file:
        LOGO_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOGO_UPLOAD_PATH, "wb") as handle:
            handle.write(cockpit_logo_file.getbuffer())
        st.session_state['cockpit_logo_uploaded'] = True
        st.session_state['show_cockpit_upload'] = False
        st.success(f"✅ Cockpit logo saved to {LOGO_UPLOAD_PATH}. It will persist across sessions.")
        st.rerun()

# ============================================================================
# ROAD MARKET CONDITIONS - Determines Recommended Driving Mode
# ============================================================================
st.markdown('<div id="road-market-conditions"></div>', unsafe_allow_html=True)
st.markdown("#### 🛣️ Road Market Conditions")

# Initialize DRIVE_MODES first (needed for the logic)
if "drive_mode" not in st.session_state:
    st.session_state.drive_mode = "AUTOPILOT"

# Define all 7 modes with their properties (including SAFE MODE) - MUST BE DEFINED BEFORE USE
DRIVE_MODES = {
    "SAFE MODE": {
        "icon": "🛡️",
        "color": "#00D4AA",
        "color_secondary": "#00F5D4",
        "meaning": "Maximum safety: conservative operations, risk mitigation, compliance focus.",
        "actionables": [
            "Freeze all deployments",
            "Enable maximum monitoring",
            "Activate all safety protocols",
            "Review all pending changes",
            "Ensure compliance checks",
            "Reduce system load",
            "Maintain stability above all",
            "Escalate critical decisions",
        ],
    },
    "ECO": {
        "icon": "🌱",
        "color": "#1DB954",
        "color_secondary": "#2ECC71",
        "meaning": "Running lean: cost optimization, reduced spend, efficiency focus.",
        "actionables": [
            "Cut low ROI projects",
            "Optimize cloud cost & infrastructure footprint",
            "Automate labor-heavy processes",
            "Reduce marketing spend",
            "Negotiate vendor contracts",
            "Focus on unit economics",
            "Shift from growth → margin improvement",
            "Consolidate workloads to reduce overhead",
        ],
    },
    "SPORT": {
        "icon": "🏎️",
        "color": "#FF4E00",
        "color_secondary": "#FF6A3D",
        "meaning": "Aggressive growth mode: high investment, marketing, expansion.",
        "actionables": [
            "Increase marketing investment",
            "Launch growth campaigns",
            "Accelerate sales pipeline",
            "Expand into new regions",
            "Add incentives for high performers",
            "Deploy AI copilots to unlock scale",
            "Invest in product upgrades faster",
            "Increase hiring for key roles",
        ],
    },
    "AUTOPILOT": {
        "icon": "🤖",
        "color": "#0077FF",
        "color_secondary": "#4BA3FF",
        "meaning": "Stable operations, automation running most workflows.",
        "actionables": [
            "Maintain automation pipelines",
            "Monitor KPIs and anomaly alerts",
            "Let AI copilots handle routing tasks",
            "Conduct efficiency audits",
            "Reduce operational interruptions",
            "Maintain steady service delivery",
            "Document processes for long-term stability",
        ],
    },
    "STORM": {
        "icon": "🌩️",
        "color": "#AA0000",
        "color_secondary": "#CC0000",
        "meaning": "Crisis mode: incidents, outages, customer churn risk.",
        "actionables": [
            "Activate crisis response protocol",
            "Mobilize all-hands swarm team",
            "Communicate incidents transparently",
            "Prioritize SLA breaches",
            "Freeze deployments",
            "Patch high-severity issues",
            "Provide hourly updates to stakeholders",
            "Conduct rapid rollback when needed",
        ],
    },
    "EXPLORATION": {
        "icon": "🧭",
        "color": "#7E57C2",
        "color_secondary": "#9575CD",
        "meaning": "New R&D, innovation, experiments, pilots.",
        "actionables": [
            "Launch experimental initiatives",
            "Test new AI models / copilots",
            "Explore new GTM markets",
            "Pilot early-access customer programs",
            "Rapid prototype new features",
            "Measure innovation ROI",
            "Allocate small-risk budget buckets",
        ],
    },
    "PIT-STOP": {
        "icon": "🛑",
        "color": "#3A3F5C",
        "color_secondary": "#5A5F7A",
        "meaning": "Maintenance mode: cooldown, system fixes, team rest.",
        "actionables": [
            "Schedule maintenance windows",
            "Patch systems and apply updates",
            "Give teams rest / mental reset",
            "Optimize CI/CD pipelines",
            "Review performance bottlenecks",
            "Conduct quality assurance testing",
            "Re-sync leadership strategy",
            "Reduce load for a temporary period",
        ],
    },
}

# Market Conditions Options
MARKET_CONDITIONS = [
    "Rising Demand",
    "Stable Market",
    "Declining Market",
    "Cost Pressure",
    "High Ops Heat",
    "Supply Chain Instability",
    "Innovation Opportunity",
    "Customer Churn Rising",
    "Macro Shock / Crisis Signals",
    "Cash Runway < 9 months",
    "Efficiency Decline",
    "High Growth Window",
    "Team Overload",
    "System Degradation"
]

# Mode Logic Engine - Determines driving mode based on market conditions
def determine_driving_mode(conditions: list) -> tuple:
    """
    Determines the appropriate driving mode based on market conditions.
    Returns: (mode_name, confidence_score, explanation)
    """
    if not conditions:
        return ("AUTOPILOT", 0.5, "No conditions selected - defaulting to AUTOPILOT mode")
    
    conditions_set = set(conditions)
    triggers = []
    confidence = 0.0
    
    # Priority 1: Crisis conditions → STORM
    if "Macro Shock / Crisis Signals" in conditions_set:
        triggers.append("Macro Shock / Crisis Signals")
        return ("STORM", 1.0, f"🚨 CRISIS MODE: {', '.join(triggers)} detected. Activating emergency protocols.")
    
    # Priority 2: Critical operational issues → SAFE MODE
    if "Customer Churn Rising" in conditions_set or "High Ops Heat" in conditions_set:
        if "Customer Churn Rising" in conditions_set:
            triggers.append("Customer Churn Rising")
        if "High Ops Heat" in conditions_set:
            triggers.append("High Ops Heat")
        confidence = min(0.9, 0.6 + len(triggers) * 0.15)
        return ("SAFE MODE", confidence, f"🛡️ SAFETY MODE: {', '.join(triggers)} requires conservative operations.")
    
    # Priority 3: Cost/efficiency pressure → ECO
    if "Cost Pressure" in conditions_set or "Efficiency Decline" in conditions_set or "Cash Runway < 9 months" in conditions_set:
        if "Cost Pressure" in conditions_set:
            triggers.append("Cost Pressure")
        if "Efficiency Decline" in conditions_set:
            triggers.append("Efficiency Decline")
        if "Cash Runway < 9 months" in conditions_set:
            triggers.append("Cash Runway < 9 months")
        confidence = min(0.95, 0.7 + len(triggers) * 0.1)
        return ("ECO", confidence, f"🌱 EFFICIENCY MODE: {', '.join(triggers)} requires cost optimization.")
    
    # Priority 4: Growth opportunities → SPORT
    if "Rising Demand" in conditions_set or "High Growth Window" in conditions_set:
        if "Rising Demand" in conditions_set:
            triggers.append("Rising Demand")
        if "High Growth Window" in conditions_set:
            triggers.append("High Growth Window")
        confidence = min(0.9, 0.75 + len(triggers) * 0.1)
        return ("SPORT", confidence, f"🏎️ GROWTH MODE: {', '.join(triggers)} detected - accelerate expansion.")
    
    # Priority 5: Innovation → EXPLORATION
    if "Innovation Opportunity" in conditions_set:
        triggers.append("Innovation Opportunity")
        confidence = 0.85
        return ("EXPLORATION", confidence, f"🧭 EXPLORATION MODE: {', '.join(triggers)} - time for R&D and experiments.")
    
    # Priority 6: System/team issues → PIT-STOP
    if "Team Overload" in conditions_set or "System Degradation" in conditions_set:
        if "Team Overload" in conditions_set:
            triggers.append("Team Overload")
        if "System Degradation" in conditions_set:
            triggers.append("System Degradation")
        confidence = min(0.9, 0.7 + len(triggers) * 0.1)
        return ("PIT-STOP", confidence, f"🛑 MAINTENANCE MODE: {', '.join(triggers)} requires system cooldown.")
    
    # Default: Stable conditions → AUTOPILOT
    if "Stable Market" in conditions_set:
        return ("AUTOPILOT", 0.8, "🤖 AUTOPILOT MODE: Stable market conditions - maintain steady operations.")
    
    # Fallback
    return ("AUTOPILOT", 0.5, "🤖 AUTOPILOT MODE: Mixed conditions - defaulting to stable operations.")

# Initialize session state for market conditions
if "market_conditions" not in st.session_state:
    st.session_state.market_conditions = []
if "adaptive_mode_enabled" not in st.session_state:
    st.session_state.adaptive_mode_enabled = True
if "ceo_override_mode" not in st.session_state:
    st.session_state.ceo_override_mode = None

# Road Market Conditions Selector UI
road_conditions_col1, road_conditions_col2 = st.columns([2, 1])

with road_conditions_col1:
    # Market Conditions Multi-Select
    selected_conditions = st.multiselect(
        "Select Road Market Conditions:",
        options=MARKET_CONDITIONS,
        default=st.session_state.market_conditions,
        key="market_conditions_selector",
        help="Select one or more market conditions. The system will automatically determine the recommended driving mode based on your selections."
    )
    st.session_state.market_conditions = selected_conditions
    
    # Simulate Market Button
    if st.button("🎲 Simulate Market Conditions", help="Randomly generate market conditions for testing"):
        import random
        num_conditions = random.randint(1, 4)
        st.session_state.market_conditions = random.sample(MARKET_CONDITIONS, num_conditions)
        st.rerun()

with road_conditions_col2:
    # CEO Override Toggle
    st.session_state.adaptive_mode_enabled = st.toggle(
        "Enable Adaptive Mode",
        value=st.session_state.adaptive_mode_enabled,
        help="When enabled, mode is determined by market conditions. When disabled, use manual selection."
    )
    
    if not st.session_state.adaptive_mode_enabled:
        # Manual mode selection
        manual_mode = st.selectbox(
            "Manual Mode Selection:",
            options=["AUTOPILOT", "SAFE MODE", "ECO", "SPORT", "STORM", "EXPLORATION", "PIT-STOP"],
            index=3,  # Default to AUTOPILOT
            key="manual_mode_selector"
        )
        st.session_state.ceo_override_mode = manual_mode
        st.session_state.drive_mode = manual_mode
    else:
        st.session_state.ceo_override_mode = None

# Determine recommended driving mode if adaptive mode is enabled
if st.session_state.adaptive_mode_enabled:
    determined_mode, confidence, explanation = determine_driving_mode(st.session_state.market_conditions)
    st.session_state.drive_mode = determined_mode
    
    # Display selected conditions
    if st.session_state.market_conditions:
        st.markdown("**📊 Selected Road Market Conditions:**")
        condition_chips = " ".join([f'<span style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; padding: 0.3rem 0.8rem; border-radius: 20px; margin: 0.2rem; display: inline-block; font-size: 0.85rem;">{cond}</span>' for cond in st.session_state.market_conditions])
        st.markdown(condition_chips, unsafe_allow_html=True)
    
    # Display recommended mode card
    mode_config = DRIVE_MODES.get(determined_mode, DRIVE_MODES["AUTOPILOT"])
    confidence_color = "#22c55e" if confidence >= 0.8 else "#f59e0b" if confidence >= 0.6 else "#ef4444"
    
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
            border-left: 4px solid {mode_config['color']};
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; color: {mode_config['color']}; font-size: 1.5rem;">
                    {mode_config['icon']} <strong>Recommended Driving Mode: {determined_mode}</strong>
                </h3>
                <span style="
                    background: {confidence_color}30;
                    color: {confidence_color};
                    padding: 0.5rem 1rem;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 0.9rem;
                ">Confidence: {confidence:.0%}</span>
            </div>
            <p style="color: #cbd5e1; font-size: 1rem; line-height: 1.6; margin: 0;">
                <strong>Why this mode:</strong> {explanation}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# SECTION 1: DRIVING MODE - Modern Car Dashboard HTML (moved under Cockpit Logo)
st.markdown('<div id="driving-mode"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">🚗 DRIVING MODE</h2>
    </div>
    """,
    unsafe_allow_html=True,
)


# Get current mode (single source of truth)
current_mode = st.session_state.drive_mode
# Correct order: SAFE MODE, ECO, SPORT, AUTOPILOT, STORM, EXPLORATION, PIT-STOP
mode_order = ["SAFE MODE", "ECO", "SPORT", "AUTOPILOT", "STORM", "EXPLORATION", "PIT-STOP"]
mode_list = [m for m in mode_order if m in DRIVE_MODES]
selected_index = mode_list.index(current_mode) if current_mode in mode_list else 3  # Default to AUTOPILOT (index 3)

# Get current mode config and metrics
current_mode_config = DRIVE_MODES[current_mode]
rev_speed = metrics.get('rev_speed', 0)
cash_months = metrics.get('cash_months', 0)
ops_heat = metrics.get('ops_heat', 0)

# Function to get revenue gauge configuration based on mode with mock revenue projections
def get_revenue_gauge_config(mode: str, metrics: dict) -> dict:
    """Returns gauge configuration (value, max, label, unit) for the revenue gauge based on mode"""
    base_rev = metrics.get('rev_speed', 0)
    
    if mode == "SAFE MODE":
        # Conservative revenue projection - reduce by 15-25% due to safety measures
        revenue_projection = base_rev * 0.75
        return {
            "value": revenue_projection,
            "max": 150,
            "label": "Revenue Projection",
            "unit": "M/mo",
            "needle_rotation": (revenue_projection / 150) * 240 - 120
        }
    elif mode == "ECO":
        # Cost-optimized revenue - slight reduction, focus on margins
        revenue_projection = base_rev * 0.90
        return {
            "value": revenue_projection,
            "max": 150,
            "label": "Revenue Projection",
            "unit": "M/mo",
            "needle_rotation": (revenue_projection / 150) * 240 - 120
        }
    elif mode == "SPORT":
        # Aggressive growth - increase revenue projection by 30-50%
        revenue_projection = min(150, base_rev * 1.40)
        return {
            "value": revenue_projection,
            "max": 150,
            "label": "Revenue Projection",
            "unit": "M/mo",
            "needle_rotation": (revenue_projection / 150) * 240 - 120
        }
    elif mode == "AUTOPILOT":
        # Stable operations - maintain current revenue with slight growth
        revenue_projection = base_rev * 1.05
        return {
            "value": revenue_projection,
            "max": 150,
            "label": "Revenue Projection",
            "unit": "M/mo",
            "needle_rotation": (revenue_projection / 150) * 240 - 120
        }
    elif mode == "STORM":
        # Crisis mode - revenue drops significantly due to operational issues
        revenue_projection = base_rev * 0.60
        return {
            "value": revenue_projection,
            "max": 150,
            "label": "Revenue Projection",
            "unit": "M/mo",
            "needle_rotation": (revenue_projection / 150) * 240 - 120
        }
    elif mode == "EXPLORATION":
        # Innovation mode - moderate revenue, focus on future growth
        revenue_projection = base_rev * 0.85
        return {
            "value": revenue_projection,
            "max": 150,
            "label": "Revenue Projection",
            "unit": "M/mo",
            "needle_rotation": (revenue_projection / 150) * 240 - 120
        }
    elif mode == "PIT-STOP":
        # Maintenance mode - reduced revenue during cooldown
        revenue_projection = base_rev * 0.70
        return {
            "value": revenue_projection,
            "max": 150,
            "label": "Revenue Projection",
            "unit": "M/mo",
            "needle_rotation": (revenue_projection / 150) * 240 - 120
        }
    else:
        # Default: Revenue Speed
        return {
            "value": base_rev,
            "max": 150,
            "label": "Revenue Speed",
            "unit": "M/mo",
            "needle_rotation": (base_rev / 150) * 240 - 120
        }

# Get revenue gauge configuration for current mode
gauge_config = get_revenue_gauge_config(current_mode, metrics)
gauge_value = gauge_config["value"]
gauge_max = gauge_config["max"]
gauge_label = gauge_config["label"]
gauge_unit = gauge_config["unit"]
gauge_needle_rotation = gauge_config["needle_rotation"]

# Function to calculate financial KPIs based on mode
def calculate_financial_kpis(mode: str, metrics: dict, revenue_projection: float) -> dict:
    """Calculate financial KPIs based on driving mode"""
    base_rev = metrics.get('rev_speed', 0)
    cash = financials.get("cash", 0) or 0
    cash_months = metrics.get('cash_months', 0)
    
    # Revenue projection per month (from gauge)
    rev_projection_monthly = revenue_projection
    
    # Target KPI (based on mode - different targets for different modes)
    if mode == "SPORT":
        target_kpi = 150.0  # Aggressive target
    elif mode == "AUTOPILOT":
        target_kpi = base_rev * 1.2  # 20% growth target
    elif mode == "SAFE MODE":
        target_kpi = base_rev * 0.9  # Conservative target
    elif mode == "ECO":
        target_kpi = base_rev * 1.0  # Maintain current
    elif mode == "STORM":
        target_kpi = base_rev * 0.7  # Crisis recovery target
    elif mode == "EXPLORATION":
        target_kpi = base_rev * 1.1  # Innovation target
    elif mode == "PIT-STOP":
        target_kpi = base_rev * 0.8  # Maintenance target
    else:
        target_kpi = base_rev * 1.1
    
    # Cashflow (estimated as revenue - expenses)
    # Mock expense ratio varies by mode
    expense_ratios = {
        "SAFE MODE": 0.85,  # Higher expenses due to safety measures
        "ECO": 0.70,  # Lower expenses, cost optimized
        "SPORT": 0.80,  # Higher expenses for growth
        "AUTOPILOT": 0.75,  # Balanced
        "STORM": 0.90,  # High expenses during crisis
        "EXPLORATION": 0.78,  # R&D expenses
        "PIT-STOP": 0.82  # Maintenance expenses
    }
    expense_ratio = expense_ratios.get(mode, 0.75)
    cashflow_monthly = rev_projection_monthly * (1 - expense_ratio)
    
    # Cashflow burn rate per month (negative cashflow = burn)
    burn_rate = -cashflow_monthly if cashflow_monthly < 0 else 0
    
    # Time to reach target (months)
    # Calculate based on monthly growth rate
    if rev_projection_monthly > base_rev and target_kpi > base_rev:
        monthly_growth = rev_projection_monthly - base_rev
        gap_to_target = target_kpi - base_rev
        if monthly_growth > 0:
            months_to_target = gap_to_target / monthly_growth
            months_to_target = max(0, min(months_to_target, 120))  # Cap at 10 years
        else:
            months_to_target = 999
    elif target_kpi <= base_rev:
        months_to_target = 0  # Already at or above target
    else:
        months_to_target = 999  # Not achievable
    
    # Enough cash flow to achieve targets
    # Check if current cash can sustain operations until target is reached
    cash_millions = cash / 1e6
    
    if cashflow_monthly > 0:
        # Positive cashflow - we have enough
        enough_cash_text = "Yes"
    else:
        # Negative cashflow (burning cash)
        if burn_rate > 0:
            months_until_out = cash_millions / burn_rate if burn_rate > 0 else 999
            if months_until_out >= months_to_target:
                enough_cash_text = "Yes"
            else:
                enough_cash_text = f"{months_until_out:.1f}mo"
        else:
            enough_cash_text = "Yes"
    
    return {
        "cashflow": cashflow_monthly,
        "revenue_projection": rev_projection_monthly,
        "target_kpi": target_kpi,
        "time_to_target": months_to_target,
        "enough_cash": enough_cash_text,
        "burn_rate": abs(burn_rate) if burn_rate > 0 else 0
    }

# Calculate financial KPIs
financial_kpis = calculate_financial_kpis(current_mode, metrics, gauge_value)

# Build HTML dashboard with all drive modes
mode_colors_js = {mode: DRIVE_MODES[mode]['color'] for mode in mode_list}
mode_colors_secondary_js = {mode: DRIVE_MODES[mode]['color_secondary'] for mode in mode_list}
mode_icons_js = {mode: DRIVE_MODES[mode]['icon'] for mode in mode_list}
mode_short_names = {
    "SAFE MODE": "SAFE",
    "ECO": "ECO",
    "SPORT": "SPORT",
    "AUTOPILOT": "AUTO",
    "STORM": "STORM",
    "EXPLORATION": "EXPL",
    "PIT-STOP": "PIT"
}

# Create the HTML dashboard
dashboard_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Arial', sans-serif;
            background: #000;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }}

        .dashboard {{
            width: 100%;
            max-width: 1400px;
            height: 400px;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            border-radius: 30px;
            position: relative;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 40px;
        }}

        /* Speedometer */
        .speedometer {{
            width: 280px;
            height: 280px;
            position: relative;
            background: radial-gradient(circle, #0a0a0a 0%, #1a1a1a 100%);
            border-radius: 50%;
            box-shadow: inset 0 0 30px rgba(0,0,0,0.8);
        }}

        .speedometer::before {{
            content: '';
            position: absolute;
            width: 240px;
            height: 240px;
            background: radial-gradient(circle, transparent 60%, {current_mode_config['color']} 61%, transparent 62%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            border-radius: 50%;
        }}

        .speed-needle {{
            position: absolute;
            width: 4px;
            height: 100px;
            background: linear-gradient(to top, #ff0000, #ffff00);
            top: 50%;
            left: 50%;
            transform-origin: bottom center;
            transform: translate(-50%, -100%) rotate({gauge_needle_rotation}deg);
            transition: transform 0.5s ease;
            box-shadow: 0 0 10px rgba(255,0,0,0.5);
        }}

        .speed-value {{
            position: absolute;
            top: 45%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: {current_mode_config['color']};
            font-size: 48px;
            font-weight: bold;
            text-shadow: 0 0 20px {current_mode_config['color']}80;
            line-height: 1.2;
            transition: color 0.3s ease, text-shadow 0.3s ease;
        }}

        .speed-unit {{
            position: absolute;
            bottom: 70px;
            left: 50%;
            transform: translateX(-50%);
            color: {current_mode_config['color']};
            font-size: 12px;
            text-align: center;
            width: 120px;
            line-height: 1.6;
            margin-top: 10px;
            transition: color 0.3s ease;
        }}
        
        .speed-label {{
            position: absolute;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            color: {current_mode_config['color']};
            font-size: 14px;
            font-weight: 600;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-shadow: 0 0 10px {current_mode_config['color']}60;
            transition: color 0.3s ease, text-shadow 0.3s ease;
        }}

        /* Robot Visor HUD - Center Display */
        .center-display {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 15px;
            padding: 0 50px;
        }}

        .visor {{
            width: 260px;
            height: 100px;
            position: relative;
            background: #000;
            border-radius: 50px;
            box-shadow: inset 0 0 15px rgba(0, 255, 255, 0.6), 0 0 25px rgba(0, 255, 255, 0.3);
            overflow: hidden;
        }}

        .visor::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, transparent 40%, rgba(0, 255, 255, 0.25) 50%, transparent 60%);
            animation: scan 2.5s linear infinite;
        }}

        @keyframes scan {{
            0% {{ transform: translateY(-100%); }}
            100% {{ transform: translateY(200%); }}
        }}

        .eye-row {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            height: 100%;
        }}

        .eye {{
            width: 50px;
            height: 22px;
            border-radius: 11px;
            background: var(--eyeColour, {current_mode_config['color']});
            box-shadow: 0 0 15px var(--eyeColour, {current_mode_config['color']});
            transition: all 0.4s ease;
        }}

        .robot-mode {{
            margin-top: 8px;
            font-size: 28px;
            font-weight: bold;
            letter-spacing: 3px;
            color: var(--eyeColour, {current_mode_config['color']});
            text-shadow: 0 0 20px var(--eyeColour, {current_mode_config['color']});
            text-transform: uppercase;
        }}

        /* Telemetry strip */
        .telemetry {{
            display: flex;
            gap: 20px;
            font-size: 14px;
            color: #aaa;
        }}

        .telemetry span {{
            color: #0ff;
            font-weight: bold;
        }}

        /* Lexus-style Gear Shift with Gliding Pill */
        .gear-shift {{
            width: 120px;
            background: #1a1a1a;
            border-radius: 15px;
            padding: 20px 10px;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.8);
            position: relative;
        }}

        .gate-track {{
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0;
            padding: 5px 0;
        }}

        .pill {{
            position: absolute;
            left: 0;
            width: 100px;
            height: 50px;
            background: linear-gradient(135deg, {current_mode_config['color']} 0%, {current_mode_config['color_secondary']} 100%);
            border-radius: 10px;
            box-shadow: 0 0 20px {current_mode_config['color']}80, inset 0 2px 4px rgba(255,255,255,0.2);
            transition: top 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 1;
            pointer-events: none;
        }}

        .gate-position {{
            width: 100px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            border-radius: 10px;
            color: #666;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
            position: relative;
            z-index: 2;
            margin-bottom: 8px;
        }}

        .gate-position:hover {{
            color: #999;
        }}

        .gate-position.active {{
            color: #000;
            font-weight: 900;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }}

        /* Additional Info */
        .info-panel {{
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            justify-content: center;
            max-width: 95%;
        }}

        .info-item {{
            color: {current_mode_config['color']};
            font-size: 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            min-width: 100px;
        }}

        .info-item span:first-child {{
            font-size: 10px;
            opacity: 0.8;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .info-value {{
            font-weight: bold;
            font-size: 14px;
        }}

        /* Animation */
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
            100% {{ opacity: 1; }}
        }}

        .active {{
            animation: pulse 2s infinite;
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <!-- Speedometer -->
        <div class="speedometer">
            <div class="speed-label">{gauge_label}</div>
            <div class="speed-needle" id="speedNeedle"></div>
            <div class="speed-value" id="speedValue">{gauge_value:.1f}</div>
            <div class="speed-unit">{gauge_unit}</div>
        </div>

        <!-- Center Robot HUD Display -->
        <div class="center-display">
            <div class="visor">
                <div class="eye-row">
                    <div class="eye" id="leftEye"></div>
                    <div class="eye" id="rightEye"></div>
                </div>
            </div>
            <div class="robot-mode" id="robotMode">{current_mode}</div>
            <div class="telemetry">
                <div>CF:<span id="cf">${financial_kpis['cashflow']:.1f}</span>M</div>
                <div>REV:<span id="rev">${financial_kpis['revenue_projection']:.1f}</span>M</div>
                <div>TGT:<span id="tgt">${financial_kpis['target_kpi']:.1f}</span>M</div>
                <div>TTT:<span id="ttt">{financial_kpis['time_to_target']:.0f}</span>mo</div>
            </div>
        </div>

        <!-- Lexus-style Gear Shift -->
        <div class="gear-shift">
            <div class="gate-track">
                <div class="pill" id="pill"></div>
"""

# Add gate positions for all 7 modes
for idx, mode in enumerate(mode_list):
    is_active = idx == selected_index
    mode_short = mode_short_names.get(mode, mode[:4])
    active_class = "active" if is_active else ""
    gear_html = f'<div class="gate-position {active_class}" data-gear="{idx}" data-mode="{html.escape(mode)}">{mode_short}</div>'
    dashboard_html += gear_html

dashboard_html += f"""
            </div>
        </div>

        <!-- Info Panel -->
        <div class="info-panel">
            <div class="info-item">
                <span>Cashflow:</span>
                <span class="info-value">${financial_kpis['cashflow']:.1f}M</span>
            </div>
            <div class="info-item">
                <span>Rev Proj:</span>
                <span class="info-value">${financial_kpis['revenue_projection']:.1f}M/mo</span>
            </div>
            <div class="info-item">
                <span>Target:</span>
                <span class="info-value">${financial_kpis['target_kpi']:.1f}M</span>
            </div>
            <div class="info-item">
                <span>Time to Target:</span>
                <span class="info-value">{financial_kpis['time_to_target']:.1f} mo</span>
            </div>
            <div class="info-item">
                <span>Enough Cash:</span>
                <span class="info-value">{financial_kpis['enough_cash']}</span>
            </div>
            <div class="info-item">
                <span>Burn Rate:</span>
                <span class="info-value">${financial_kpis['burn_rate']:.1f}M/mo</span>
            </div>
        </div>
    </div>

    <script>
        // ============================================================================
        // DYNAMIC GAUGE THEME SYNC WITH DRIVING MODE
        // ============================================================================
        
        // Color-theme map for each driving mode (single source of truth)
        const MODE_THEMES = {{
            'SAFE MODE': {{ primary: "#00F5D4", secondary: "#043F34", glow: "#00F5D466" }},
            'ECO': {{ primary: "#00FF88", secondary: "#034F29", glow: "#00FF8866" }},
            'SPORT': {{ primary: "#FF7A00", secondary: "#4A2B00", glow: "#FF7A0066" }},
            'AUTOPILOT': {{ primary: "#00A3FF", secondary: "#002B4A", glow: "#00A3FF66" }},
            'STORM': {{ primary: "#8B5CF6", secondary: "#2C1A69", glow: "#8B5CF666" }},
            'EXPLORATION': {{ primary: "#FFE44D", secondary: "#4A3F00", glow: "#FFE44D66" }},
            'PIT-STOP': {{ primary: "#FF4D4D", secondary: "#4A0000", glow: "#FF4D4D66" }}
        }};
        
        // Global current mode variable
        let currentMode = '{current_mode}';
        
        // Set driving mode and apply theme
        function setDrivingMode(mode) {{
            currentMode = mode;
            const theme = MODE_THEMES[mode] || MODE_THEMES['AUTOPILOT'];
            
            // Update the UI theme
            applyGaugeTheme(theme);
            applyModeIconTheme(theme);
            applyBackgroundGlow(theme);
            
            // Broadcast event for modular dashboards
            dispatchEvent(new CustomEvent("DrivingModeChanged", {{ 
                detail: {{ mode: mode, theme: theme }}
            }}));
        }}
        
        // Apply theme colors to all gauge components
        function applyGaugeTheme(theme) {{
            // Update gauge primary colors
            document.querySelectorAll(".gauge-primary").forEach(el => {{
                el.style.stroke = theme.primary;
                el.style.color = theme.primary;
            }});
            
            // Update gauge secondary colors
            document.querySelectorAll(".gauge-secondary").forEach(el => {{
                el.style.stroke = theme.secondary;
                el.style.color = theme.secondary;
            }});
            
            // Update gauge glow effects
            document.querySelectorAll(".gauge-glow").forEach(el => {{
                el.style.filter = `drop-shadow(0 0 12px ${{theme.glow}})`;
                el.style.boxShadow = `0 0 20px ${{theme.glow}}`;
            }});
            
            // Update gauge value colors
            document.querySelectorAll(".gauge-value").forEach(el => {{
                el.style.color = theme.primary;
                el.style.textShadow = `0 0 20px ${{theme.glow}}`;
            }});
            
            // Update speedometer value
            const speedValue = document.getElementById('speedValue');
            if (speedValue) {{
                speedValue.style.color = theme.primary;
                speedValue.style.textShadow = `0 0 20px ${{theme.glow}}`;
            }}
            
            // Update speedometer label
            const speedLabel = document.querySelector('.speed-label');
            if (speedLabel) {{
                speedLabel.style.color = theme.primary;
            }}
            
            // Update speedometer unit
            const speedUnit = document.querySelector('.speed-unit');
            if (speedUnit) {{
                speedUnit.style.color = theme.primary;
            }}
            
            // Update speedometer ring/glow
            const speedometer = document.querySelector('.speedometer');
            if (speedometer) {{
                speedometer.style.setProperty('--mode-color', theme.primary);
                speedometer.style.boxShadow = `0 0 40px ${{theme.glow}}, inset 0 0 20px ${{theme.secondary}}40`;
            }}
            
            // Update info panel items
            document.querySelectorAll('.info-item').forEach(el => {{
                el.style.color = theme.primary;
            }});
            
            // Update info values
            document.querySelectorAll('.info-value').forEach(el => {{
                el.style.color = theme.primary;
            }});
            
            // Update telemetry values
            document.querySelectorAll('.telemetry span').forEach(el => {{
                el.style.color = theme.primary;
            }});
        }}
        
        // Apply theme to mode icon/robot
        function applyModeIconTheme(theme) {{
            // Update robot eyes
            document.querySelectorAll('.eye').forEach(e => {{
                e.style.setProperty('--eyeColour', theme.primary);
                e.style.background = theme.primary;
                e.style.boxShadow = `0 0 15px ${{theme.primary}}, 0 0 30px ${{theme.glow}}`;
            }});
            
            // Update robot mode text
            const robotModeEl = document.getElementById('robotMode');
            if (robotModeEl) {{
                robotModeEl.style.setProperty('--eyeColour', theme.primary);
                robotModeEl.style.color = theme.primary;
                robotModeEl.style.textShadow = `0 0 20px ${{theme.primary}}, 0 0 40px ${{theme.glow}}`;
            }}
            
            // Update visor glow
            const visor = document.querySelector('.visor');
            if (visor) {{
                visor.style.boxShadow = `inset 0 0 15px ${{theme.primary}}60, 0 0 25px ${{theme.glow}}, 0 0 60px ${{theme.glow}}`;
            }}
        }}
        
        // Apply background glow effects
        function applyBackgroundGlow(theme) {{
            // Update dashboard background glow
            const dashboard = document.querySelector('.dashboard');
            if (dashboard) {{
                dashboard.style.boxShadow = `0 0 60px ${{theme.glow}}, inset 0 0 40px ${{theme.secondary}}20`;
            }}
            
            // Update center display glow
            const centerDisplay = document.querySelector('.center-display');
            if (centerDisplay) {{
                centerDisplay.style.boxShadow = `0 0 40px ${{theme.glow}}`;
            }}
        }}
        
        // Listen for DrivingModeChanged events (for modular dashboards)
        window.addEventListener("DrivingModeChanged", (e) => {{
            const {{ theme }} = e.detail;
            applyGaugeTheme(theme);
            applyModeIconTheme(theme);
            applyBackgroundGlow(theme);
        }});
        
        // Mode data
        const modeList = {json.dumps(mode_list)};
        const modeColors = {json.dumps(mode_colors_js)};
        const modeColorsSecondary = {json.dumps(mode_colors_secondary_js)};
        const modeIcons = {json.dumps(mode_icons_js)};
        let currentModeIndex = {selected_index};
        
        // Lexus-style gear selection with pill glider
        document.querySelectorAll('.gate-position').forEach(pos => {{
            pos.addEventListener('click', function() {{
                const index = parseInt(this.dataset.gear);
                const activeMode = modeList[index];
                const modeColor = modeColors[activeMode] || '#00ff88';
                const modeIcon = modeIcons[activeMode] || '🤖';
                
                // Remove active class from all positions
                document.querySelectorAll('.gate-position').forEach(p => p.classList.remove('active'));
                
                // Add active class to clicked position
                this.classList.add('active');
                
                // Move pill to active position
                movePill(this);
                
                // Get theme for this mode
                const theme = MODE_THEMES[activeMode] || MODE_THEMES['AUTOPILOT'];
                
                // Update pill color to match mode theme
                const pill = document.getElementById('pill');
                pill.style.background = `linear-gradient(135deg, ${{theme.primary}} 0%, ${{theme.secondary}} 100%)`;
                pill.style.boxShadow = `0 0 20px ${{theme.primary}}80, inset 0 2px 4px rgba(255,255,255,0.2)`;
                
                // Update driving mode with theme sync (this applies theme to all gauges)
                setDrivingMode(activeMode);
                
                // Update robot visor HUD (using theme colors)
                setRobotMode(activeMode, theme.primary);
                
                // Update speedometer color (using theme)
                updateSpeedometerColor(theme.primary);
                
                // Calculate financial KPIs based on mode (simplified client-side calculation)
                const baseRev = {rev_speed:.1f};
                let revProj, target, cashflow, burnRate, timeToTarget;
                
                if (activeMode === 'SPORT') {{
                    revProj = Math.min(150, baseRev * 1.40);
                    target = 150.0;
                    cashflow = revProj * 0.20;
                    burnRate = cashflow < 0 ? Math.abs(cashflow) : 0;
                    timeToTarget = revProj > baseRev ? Math.max(0, Math.min(120, (target - baseRev) / (revProj - baseRev))) : 999;
                }} else if (activeMode === 'AUTOPILOT') {{
                    revProj = baseRev * 1.05;
                    target = baseRev * 1.2;
                    cashflow = revProj * 0.25;
                    burnRate = 0;
                    timeToTarget = revProj > baseRev ? Math.max(0, Math.min(120, (target - baseRev) / (revProj - baseRev))) : 999;
                }} else if (activeMode === 'SAFE MODE') {{
                    revProj = baseRev * 0.75;
                    target = baseRev * 0.9;
                    cashflow = revProj * 0.15;
                    burnRate = 0;
                    timeToTarget = 0;
                }} else if (activeMode === 'ECO') {{
                    revProj = baseRev * 0.90;
                    target = baseRev * 1.0;
                    cashflow = revProj * 0.30;
                    burnRate = 0;
                    timeToTarget = 0;
                }} else if (activeMode === 'STORM') {{
                    revProj = baseRev * 0.60;
                    target = baseRev * 0.7;
                    cashflow = revProj * 0.10;
                    burnRate = cashflow < 0 ? Math.abs(cashflow) : 0;
                    timeToTarget = 999;
                }} else if (activeMode === 'EXPLORATION') {{
                    revProj = baseRev * 0.85;
                    target = baseRev * 1.1;
                    cashflow = revProj * 0.22;
                    burnRate = 0;
                    timeToTarget = revProj > baseRev ? Math.max(0, Math.min(120, (target - baseRev) / (revProj - baseRev))) : 999;
                }} else if (activeMode === 'PIT-STOP') {{
                    revProj = baseRev * 0.70;
                    target = baseRev * 0.8;
                    cashflow = revProj * 0.18;
                    burnRate = 0;
                    timeToTarget = 0;
                }} else {{
                    revProj = baseRev;
                    target = baseRev * 1.1;
                    cashflow = revProj * 0.25;
                    burnRate = 0;
                    timeToTarget = 999;
                }}
                
                // Update telemetry values
                const cfEl = document.getElementById('cf');
                if (cfEl) cfEl.textContent = '$' + cashflow.toFixed(1);
                const revEl = document.getElementById('rev');
                if (revEl) revEl.textContent = '$' + revProj.toFixed(1);
                const tgtEl = document.getElementById('tgt');
                if (tgtEl) tgtEl.textContent = '$' + target.toFixed(1);
                const tttEl = document.getElementById('ttt');
                if (tttEl) tttEl.textContent = Math.round(timeToTarget);
                
                // Calculate enough cash
                const cash = {financials.get("cash", 0) / 1e6:.1f};
                let enoughCashText = 'Yes';
                if (cashflow < 0 && burnRate > 0) {{
                    const monthsUntilOut = cash / burnRate;
                    enoughCashText = monthsUntilOut >= timeToTarget ? 'Yes' : monthsUntilOut.toFixed(1) + 'mo';
                }}
                
                // Update info panel values
                const infoItems = document.querySelectorAll('.info-item');
                if (infoItems.length >= 6) {{
                    // Cashflow
                    if (infoItems[0] && infoItems[0].querySelector('.info-value')) {{
                        infoItems[0].querySelector('.info-value').textContent = '$' + cashflow.toFixed(1) + 'M';
                    }}
                    // Revenue Projection
                    if (infoItems[1] && infoItems[1].querySelector('.info-value')) {{
                        infoItems[1].querySelector('.info-value').textContent = '$' + revProj.toFixed(1) + 'M/mo';
                    }}
                    // Target
                    if (infoItems[2] && infoItems[2].querySelector('.info-value')) {{
                        infoItems[2].querySelector('.info-value').textContent = '$' + target.toFixed(1) + 'M';
                    }}
                    // Time to Target
                    if (infoItems[3] && infoItems[3].querySelector('.info-value')) {{
                        infoItems[3].querySelector('.info-value').textContent = Math.round(timeToTarget) + ' mo';
                    }}
                    // Enough Cash
                    if (infoItems[4] && infoItems[4].querySelector('.info-value')) {{
                        infoItems[4].querySelector('.info-value').textContent = enoughCashText;
                    }}
                    // Burn Rate
                    if (infoItems[5] && infoItems[5].querySelector('.info-value')) {{
                        infoItems[5].querySelector('.info-value').textContent = '$' + burnRate.toFixed(1) + 'M/mo';
                    }}
                }}
                
                // Trigger Streamlit rerun to update Driving Mode Gauges
                // Use query params to communicate mode change to Streamlit
                try {{
                    if (window.parent && window.parent.location) {{
                        const currentUrl = window.parent.location.href;
                        const url = new URL(currentUrl);
                        // Remove existing driving_mode param if any
                        url.searchParams.delete('driving_mode');
                        // Add new driving_mode param
                        url.searchParams.set('driving_mode', activeMode);
                        // Navigate to trigger Streamlit rerun
                        window.parent.location.href = url.toString();
                    }}
                }} catch (e) {{
                    console.log('Mode change sync error:', e);
                    // Fallback: try postMessage (may not trigger rerun)
                    if (window.parent && window.parent.postMessage) {{
                        window.parent.postMessage({{
                            type: 'streamlit:setComponentValue',
                            value: activeMode
                        }}, '*');
                    }}
                }}
            }});
        }});
        
        // Robot theme colours for each mode
        const robotColours = {{
            'SAFE MODE': '#00ff88',      // green
            'AUTOPILOT': '#00c8ff',      // cyan
            'ECO': '#88ff00',            // lime
            'SPORT': '#ff4800',          // orange
            'STORM': '#ff0048',          // magenta
            'EXPLORATION': '#c800ff',    // purple
            'PIT-STOP': '#ffcc00'        // amber
        }};
        
        let currentRobotMode = '{current_mode}';
        
        // Set robot mode with color
        function setRobotMode(mode, color) {{
            if (!robotColours[mode] && !color) return;
            currentRobotMode = mode;
            const col = color || robotColours[mode] || '#00c8ff';
            
            // Update eye colors
            document.querySelectorAll('.eye').forEach(e => {{
                e.style.setProperty('--eyeColour', col);
                e.style.background = col;
                e.style.boxShadow = `0 0 15px ${{col}}`;
            }});
            
            // Update robot mode text
            const robotModeEl = document.getElementById('robotMode');
            if (robotModeEl) {{
                robotModeEl.textContent = mode;
                robotModeEl.style.setProperty('--eyeColour', col);
                robotModeEl.style.color = col;
                robotModeEl.style.textShadow = `0 0 20px ${{col}}`;
            }}
            
            // Update visor glow
            const visor = document.querySelector('.visor');
            if (visor) {{
                visor.style.boxShadow = `inset 0 0 15px ${{col}}60, 0 0 25px ${{col}}30`;
            }}
        }}
        
        // Update driving mode display (for compatibility)
        function updateDrivingMode(mode, color) {{
            // This function is kept for compatibility but robot mode is handled by setRobotMode
            setRobotMode(mode, color);
        }}
        
        // Update speedometer ring color
        function updateSpeedometerColor(color) {{
            const speedometer = document.querySelector('.speedometer');
            if (speedometer) {{
                // Update the ::before pseudo-element color via CSS variable
                speedometer.style.setProperty('--mode-color', color);
                // Re-apply the radial gradient
                const style = document.createElement('style');
                style.textContent = `
                    .speedometer::before {{
                        background: radial-gradient(circle, transparent 60%, ${{color}} 61%, transparent 62%);
                    }}
                `;
                document.head.appendChild(style);
            }}
        }}
        
        // Pill glider function
        function movePill(activeElement) {{
            const pill = document.getElementById('pill');
            if (pill && activeElement) {{
                const rect = activeElement.getBoundingClientRect();
                const trackRect = activeElement.parentElement.getBoundingClientRect();
                const topOffset = rect.top - trackRect.top;
                pill.style.top = topOffset + 'px';
            }}
        }}
        
        // Initialize pill position and robot mode on page load
        function initializePill() {{
            const activeGate = document.querySelector('.gate-position.active');
            if (activeGate) {{
                // Small delay to ensure DOM is ready
                setTimeout(() => {{
                    movePill(activeGate);
                    // Update pill color to match initial mode theme
                    const initialMode = modeList[{selected_index}];
                    const initialTheme = MODE_THEMES[initialMode] || MODE_THEMES['AUTOPILOT'];
                    const pill = document.getElementById('pill');
                    if (pill) {{
                        pill.style.background = `linear-gradient(135deg, ${{initialTheme.primary}} 0%, ${{initialTheme.secondary}} 100%)`;
                        pill.style.boxShadow = `0 0 20px ${{initialTheme.primary}}80, inset 0 2px 4px rgba(255,255,255,0.2)`;
                    }}
                    // Initialize robot mode with theme (this applies theme to all gauges)
                    setDrivingMode(initialMode);
                    setRobotMode(initialMode, initialTheme.primary);
                }}, 100);
            }}
        }}
        
        // Run initialization
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', () => {{
                initializePill();
                // Apply initial theme on page load
                const initialMode = modeList[{selected_index}];
                setDrivingMode(initialMode);
            }});
        }} else {{
            initializePill();
            // Apply initial theme on page load
            const initialMode = modeList[{selected_index}];
            setDrivingMode(initialMode);
        }}
        
        // Simulate gauge value changes
        let currentGaugeValue = {gauge_value:.1f};
        const maxGaugeValue = {gauge_max:.1f};
        function updateGauge() {{
            const targetValue = {gauge_value:.1f};
            if (Math.abs(currentGaugeValue - targetValue) > 0.1) {{
                const increment = (targetValue - currentGaugeValue) / 10;
                currentGaugeValue += increment;
                document.getElementById('speedValue').textContent = currentGaugeValue.toFixed(1);
                
                // Update needle rotation (0-240 degrees for 0-max range)
                const rotation = (currentGaugeValue / maxGaugeValue) * 240 - 120;
                document.getElementById('speedNeedle').style.transform = `translate(-50%, -100%) rotate(${{rotation}}deg)`;
                
                requestAnimationFrame(updateGauge);
            }}
        }}
        
        // Initial gauge update
        updateGauge();
    </script>
</body>
</html>
"""

# Render the HTML dashboard using Streamlit components
components.html(dashboard_html, height=450, scrolling=False)

# Listen for mode changes via query params (set by JavaScript)
# This allows the Driving Mode Gauges to sync with the mode selected in the panel
if "driving_mode" in st.query_params:
    new_mode = st.query_params["driving_mode"]
    if new_mode in DRIVE_MODES and new_mode != st.session_state.drive_mode:
        st.session_state.drive_mode = new_mode
        # Clear query param and rerun to update gauges
        st.query_params.clear()
        st.rerun()

# ============================================================================
# ADAPTIVE GAUGES - Mode-Specific Gauge Sets
# ============================================================================
st.markdown('<div id="driving-mode-gauges"></div>', unsafe_allow_html=True)
st.markdown("### 📊 Driving Mode Gauges")

# Get current mode (will update when mode changes)
current_mode = st.session_state.drive_mode
mode_config = DRIVE_MODES.get(current_mode, DRIVE_MODES["AUTOPILOT"])

# Define gauge sets for each mode - using mode color scheme
def get_mode_gauges(mode: str, metrics: dict) -> list:
    """Returns list of gauge configurations for the given mode with mode-specific colors"""
    mode_colors = DRIVE_MODES.get(mode, DRIVE_MODES["AUTOPILOT"])
    primary_color = mode_colors['color']
    secondary_color = mode_colors['color_secondary']
    
    gauges = []
    
    if mode == "SAFE MODE":
        gauges = [
            ("Revenue Speed", metrics.get('rev_speed', 0), 0, 150, "M/mo", primary_color),
            ("Ops Heat", metrics.get('ops_heat', 0), 0, 120, "°C", primary_color),
            ("Risk Radar", min(100, (metrics.get('ops_heat', 0) / 120) * 100), 0, 100, "%", "#ef4444"),
            ("Cushion Gauge", metrics.get('cash_months', 0), 0, 50, "months", secondary_color),
        ]
    elif mode == "ECO":
        gauges = [
            ("Cost Efficiency", 85 - (metrics.get('ops_heat', 0) / 120 * 30), 0, 100, "%", primary_color),
            ("Cash Burn", 50 - metrics.get('cash_months', 0), 0, 50, "months", primary_color),
            ("Vendor Index", 75, 0, 100, "%", secondary_color),
            ("Automation Level", 60, 0, 100, "%", primary_color),
        ]
    elif mode == "SPORT":
        gauges = [
            ("Revenue Speed", metrics.get('rev_speed', 0), 0, 150, "M/mo", primary_color),
            ("Pipeline Acceleration", min(100, (metrics.get('rev_speed', 0) / 150) * 100 + 20), 0, 100, "%", primary_color),
            ("Market Opportunity", 75, 0, 100, "%", secondary_color),
        ]
    elif mode == "AUTOPILOT":
        gauges = [
            ("Automation Index", 85, 0, 100, "%", primary_color),
            ("Ops Stability", 100 - (metrics.get('ops_heat', 0) / 120 * 30), 0, 100, "%", primary_color),
            ("Forecast Accuracy", 92, 0, 100, "%", secondary_color),
        ]
    elif mode == "STORM":
        gauges = [
            ("Ops Heat", metrics.get('ops_heat', 0), 0, 120, "°C", primary_color),
            ("SLA Risk Gauge", min(100, (metrics.get('ops_heat', 0) / 120) * 100), 0, 100, "%", primary_color),
            ("Incident Severity", min(100, (metrics.get('ops_heat', 0) / 120) * 100 + 10), 0, 100, "%", secondary_color),
        ]
    elif mode == "EXPLORATION":
        gauges = [
            ("Innovation Index", 65, 0, 100, "%", primary_color),
            ("TAM/SAM Signals", 70, 0, 100, "%", primary_color),
            ("Experiment Velocity", 55, 0, 100, "%", secondary_color),
        ]
    elif mode == "PIT-STOP":
        gauges = [
            ("System Health", 100 - min(100, (metrics.get('ops_heat', 0) / 120) * 100), 0, 100, "%", primary_color),
            ("Tech Debt Gauge", 40, 0, 100, "%", primary_color),
            ("Team Load Gauge", min(100, (metrics.get('ops_heat', 0) / 120) * 100), 0, 100, "%", secondary_color),
        ]
    else:
        # Default to AUTOPILOT gauges
        gauges = [
            ("Automation Index", 85, 0, 100, "%", primary_color),
            ("Ops Stability", 100 - (metrics.get('ops_heat', 0) / 120 * 30), 0, 100, "%", primary_color),
            ("Forecast Accuracy", 92, 0, 100, "%", secondary_color),
        ]
    
    return gauges

# Get gauges for current mode
mode_gauges = get_mode_gauges(current_mode, metrics)

# Display gauges in columns
if mode_gauges:
    num_gauges = len(mode_gauges)
    cols = st.columns(num_gauges)
    
    for idx, (title, value, min_val, max_val, unit, gauge_color) in enumerate(mode_gauges):
        with cols[idx]:
            # Convert hex colors to RGB for rgba
            def hex_to_rgba(hex_color, alpha=0.3):
                r = int(hex_color[1:3], 16)
                g = int(hex_color[3:5], 16)
                b = int(hex_color[5:7], 16)
                return f"rgba({r}, {g}, {b}, {alpha})"
            
            # Create custom gauge with mode color scheme
            fig = go.Figure(
                go.Indicator(
                    mode="gauge+number+delta",
                    value=value,
                    title={"text": title, "font": {"color": "#f5f7fb", "size": 14}},
                    delta={"reference": (min_val + max_val) / 2, "relative": False},
                    number={"suffix": unit, "font": {"color": gauge_color, "size": 24}},
                    gauge={
                        "axis": {
                            "range": [min_val, max_val], 
                            "tickcolor": mode_config['color'],
                            "tickwidth": 2,
                            "ticklen": 8,
                            "showticksuffix": "last",
                        },
                        "bar": {"color": gauge_color, "thickness": 0.15},
                        "bgcolor": "rgba(0,0,0,0)",
                        "borderwidth": 3,
                        "bordercolor": mode_config['color'],
                        "steps": [
                            {"range": [min_val, (min_val + max_val) * 0.5], "color": "#1d2330"},
                            {"range": [(min_val + max_val) * 0.5, (min_val + max_val) * 0.8], "color": "#252b3c"},
                            {"range": [(min_val + max_val) * 0.8, max_val], "color": hex_to_rgba(mode_config['color'], 0.25)},
                        ],
                        "threshold": {
                            "line": {"color": gauge_color, "width": 4}, 
                            "value": max_val * 0.85,
                            "thickness": 0.75,
                        },
                    },
                )
            )
            fig.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=308,  # Increased by 10% (280 * 1.1 = 308)
                font={"family": "Arial, sans-serif"},
            )
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

# Mode explanation panel below dashboard
st.markdown("---")
active_mode = st.session_state.drive_mode
active_mode_config = DRIVE_MODES[active_mode]

# Build complete table HTML
table_rows_html = ""
for mode_name in mode_list:
    mode_data = DRIVE_MODES[mode_name]
    is_active = mode_name == active_mode
    row_class = "active-row" if is_active else ""
    action_items = mode_data.get('actionables', [])[:5]
    if action_items:
        action_plan = "<ul style='margin: 0; padding-left: 1.2rem;'>" + "".join([f"<li style='margin-bottom: 0.3rem; line-height: 1.6;'>{html.escape(action)}</li>" for action in action_items]) + "</ul>"
    else:
        action_plan = "<em style='color: #64748b;'>No specific actions defined</em>"
    
    active_color = mode_data['color'] if is_active else "#3b82f6"
    table_rows_html += f"""<tr class="{row_class}" data-mode-name="{html.escape(mode_name)}"><td style="font-weight: 600;">{mode_data['icon']} {html.escape(mode_name)}</td><td>{html.escape(mode_data['meaning'])}</td><td>{action_plan}</td></tr>"""

# Mode Reference Table below dashboard
panel_css = f"""
<style>
.mode-explanation-panel {{
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
    border: 2px solid {active_mode_config['color']};
    border-radius: 20px;
    padding: 2rem;
    box-shadow: 0 0 40px {active_mode_config['color']}50;
    margin-top: 2rem;
}}
.mode-activated-card {{
    background: linear-gradient(135deg, {active_mode_config['color']}25, {active_mode_config['color_secondary']}25);
    border-left: 5px solid {active_mode_config['color']};
    padding: 1.5rem;
    border-radius: 12px;
    margin-bottom: 2rem;
    box-shadow: 0 0 20px {active_mode_config['color']}40;
}}
.mode-activated-card h4 {{
    margin: 0 0 0.8rem 0;
    color: {active_mode_config['color']};
    font-size: 1.4rem;
    font-weight: 700;
}}
.mode-activated-card p {{
    color: #cbd5e1;
    margin: 0;
    line-height: 1.8;
    font-size: 1rem;
}}
.mode-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 1rem;
    background: rgba(15, 23, 42, 0.5);
    border-radius: 10px;
    overflow: hidden;
}}
.mode-table-container {{
    max-height: 600px;
    overflow-y: auto;
    overflow-x: hidden;
}}
.mode-table-container::-webkit-scrollbar {{
    width: 8px;
}}
.mode-table-container::-webkit-scrollbar-track {{
    background: rgba(15, 23, 42, 0.5);
    border-radius: 4px;
}}
.mode-table-container::-webkit-scrollbar-thumb {{
    background: #3b82f6;
    border-radius: 4px;
}}
.mode-table-container::-webkit-scrollbar-thumb:hover {{
    background: #2563eb;
}}
.mode-table thead {{
    background: linear-gradient(90deg, #3b82f640, #3b82f620);
}}
.mode-table th {{
    color: #3b82f6;
    padding: 1rem;
    text-align: left;
    border-bottom: 2px solid #3b82f6;
    font-weight: 700;
    font-size: 0.95rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.mode-table td {{
    padding: 1rem;
    border-bottom: 1px solid rgba(100, 116, 139, 0.2);
    color: #cbd5e1;
    vertical-align: top;
    font-size: 0.9rem;
}}
.mode-table td ul {{
    margin: 0;
    padding-left: 1.2rem;
}}
.mode-table td li {{
    margin-bottom: 0.4rem;
    line-height: 1.6;
}}
.mode-table tbody tr:hover {{
    background: rgba(59, 130, 246, 0.1);
}}
.mode-table tbody tr.active-row {{
    background: {active_mode_config['color']}25;
    font-weight: 600;
    border-left: 4px solid {active_mode_config['color']};
}}
.mode-table tbody tr.active-row td {{
    color: #ffffff;
}}
</style>
"""

panel_html = f"""
<div class="mode-explanation-panel">
    <div class="mode-activated-card">
        <h4>{active_mode_config['icon']} {html.escape(active_mode)} Mode Activated</h4>
        <p>{html.escape(active_mode_config['meaning'])}</p>
    </div>
    <h4 style="color: #3b82f6; margin-top: 1.5rem; margin-bottom: 1rem; font-size: 1.1rem; font-weight: 700;">Mode Reference Table</h4>
    <div class="mode-table-container">
        <table class="mode-table" id="mode-reference-table">
            <thead>
                <tr>
                    <th>Mode</th>
                    <th>Meaning</th>
                    <th>Recommended Action Plan</th>
                </tr>
            </thead>
            <tbody>{table_rows_html}</tbody>
        </table>
    </div>
</div>
"""

# Render CSS and HTML separately to ensure proper rendering
st.markdown(panel_css, unsafe_allow_html=True)
st.markdown(panel_html, unsafe_allow_html=True)

st.markdown("---")

# Calculate metrics needed for Recommended Drive Mode (before CEO Metrics Overview)
# These are also calculated later in CEO Metrics Overview, but needed here first
try:
    revenue_ttm = financials.get("revenue", 0) or 0
    cash_balance = financials.get("cash", 0) or 0
except (NameError, AttributeError):
    revenue_ttm = 0
    cash_balance = 0

try:
    rev_speed = metrics.get('rev_speed', 0)
except (NameError, AttributeError):
    rev_speed = 0

monthly_burn = 3.2  # From metrics
cash_runway_months = (cash_balance / monthly_burn) if monthly_burn > 0 else 0
burn_rate_m = monthly_burn
customer_churn_pct = 2.5  # Estimated
uptime_pct = 99.95  # Estimated
incident_frequency = 0.8  # Per month
ltv_cac_ratio = 3.2  # Estimated
pipeline_velocity = 1.8  # Estimated
market_share_pct = 4.2  # Estimated
employee_attrition_pct = 8.5  # Annual
rev_trend = "+8%"  # Simulated trend
runway_trend = "-0.3"  # Simulated trend
pipeline_trend = "+12%"  # Simulated trend

# Drive Mode Integration (moved under Driving Mode)
st.markdown("#### 🚗 Recommended Drive Mode")
recommended_mode = "AUTOPILOT"
mode_reason = "All metrics within safe thresholds"

if cash_runway_months < 3 or customer_churn_pct > 5 or uptime_pct < 99.0:
    recommended_mode = "SAFE MODE"
    mode_reason = "Critical thresholds breached - prioritize stability"
elif cash_runway_months < 4 or burn_rate_m > 4:
    recommended_mode = "ECO"
    mode_reason = "Cash runway tight or high burn - optimize costs"
elif rev_speed > 120 and cash_runway_months > 6:
    recommended_mode = "SPORT"
    mode_reason = "Strong pipeline and cash buffer - accelerate growth"
elif uptime_pct < 99.5 or incident_frequency > 2:
    recommended_mode = "PIT-STOP"
    mode_reason = "High incident frequency or uptime issues"
elif rev_speed < 80:
    recommended_mode = "STORM"
    mode_reason = "Revenue declining - crisis mode"

mode_colors = {
    "SAFE MODE": "#00D4AA",
    "ECO": "#1DB954",
    "SPORT": "#FF6B6B",
    "AUTOPILOT": "#3b82f6",
    "STORM": "#8B5CF6",
    "EXPLORATION": "#F59E0B",
    "PIT-STOP": "#EF4444"
}

# Get mode icon (DRIVE_MODES defined earlier, so use it)
mode_icon = DRIVE_MODES.get(recommended_mode, {}).get('icon', '🚗')
mode_color = mode_colors.get(recommended_mode, "#3b82f6")

st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                border: 2px solid {mode_color};
                border-radius: 12px;
                padding: 1.5rem;
                margin: 1rem 0;
                box-shadow: 0 4px 20px {mode_color}30;">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 3em;">{mode_icon}</div>
            <div style="flex: 1;">
                <h3 style="color: {mode_color}; margin: 0 0 0.5rem 0;">{recommended_mode} Mode Recommended</h3>
                <p style="color: #cbd5e1; margin: 0;">{mode_reason}</p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Risk & Opportunity Map
st.markdown("#### 🗺️ Risk & Opportunity Map")
risk_opp_col1, risk_opp_col2 = st.columns([1, 1])

with risk_opp_col1:
    # Create a simple 2x2 matrix visualization
    st.markdown("**Quadrant Analysis:**")
    
    # Calculate risk and opportunity scores
    risk_score = 0
    if cash_runway_months < 3: risk_score += 3
    elif cash_runway_months < 4: risk_score += 2
    if customer_churn_pct > 5: risk_score += 3
    elif customer_churn_pct > 3.5: risk_score += 2
    if uptime_pct < 99.0: risk_score += 3
    elif uptime_pct < 99.5: risk_score += 2
    if employee_attrition_pct > 15: risk_score += 2
    
    opportunity_score = 0
    if rev_trend.startswith("+"): opportunity_score += 2
    if ltv_cac_ratio > 3: opportunity_score += 2
    if pipeline_velocity > 1.5: opportunity_score += 2
    if market_share_pct > 4: opportunity_score += 1
    
    # Normalize to 0-10 scale
    risk_normalized = min(10, risk_score)
    opp_normalized = min(10, opportunity_score)
    
    # Determine quadrant
    if risk_normalized >= 5 and opp_normalized >= 5:
        quadrant = "High Risk / High Opportunity"
        quadrant_color = "#f59e0b"
        recommendation = "Focus area - High potential but requires careful management"
    elif risk_normalized >= 5 and opp_normalized < 5:
        quadrant = "High Risk / Low Opportunity"
        quadrant_color = "#ef4444"
        recommendation = "Avoid - High risk with limited upside"
    elif risk_normalized < 5 and opp_normalized >= 5:
        quadrant = "Low Risk / High Opportunity"
        quadrant_color = "#22c55e"
        recommendation = "Accelerate - Best quadrant, maximize growth"
    else:
        quadrant = "Low Risk / Low Opportunity"
        quadrant_color = "#94a3b8"
        recommendation = "Maintain - Stable operations, steady growth"
    
    st.markdown(
        f"""
        <div style="background: rgba(15, 23, 42, 0.8);
                    border: 2px solid {quadrant_color};
                    border-radius: 8px;
                    padding: 1rem;
                    margin: 1rem 0;">
            <div style="text-align: center;">
                <h4 style="color: {quadrant_color}; margin: 0 0 0.5rem 0;">{quadrant}</h4>
                <p style="color: #cbd5e1; font-size: 0.9em; margin: 0.5rem 0;">{recommendation}</p>
                <div style="margin-top: 1rem;">
                    <div style="color: #94a3b8; font-size: 0.85em;">Risk Score: {risk_normalized}/10</div>
                    <div style="color: #94a3b8; font-size: 0.85em;">Opportunity Score: {opp_normalized}/10</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with risk_opp_col2:
    st.markdown("**Key Metrics Impact:**")
    st.markdown(f"- 💰 Revenue trend: {rev_trend}")
    st.markdown(f"- 💵 Cash runway: {cash_runway_months:.1f} months")
    st.markdown(f"- 👥 Churn rate: {customer_churn_pct:.1f}%")
    st.markdown(f"- 🛡️ Uptime: {uptime_pct:.2f}%")
    st.markdown(f"- 📊 LTV/CAC: {ltv_cac_ratio:.1f}x")
    st.markdown(f"- 🎯 Pipeline: {pipeline_velocity:.1f}x velocity")

# CEO Snapshot Export
st.markdown("---")
export_col1, export_col2, export_col3 = st.columns([1, 1, 2])
with export_col1:
    if st.button("📤 Export CEO Snapshot", key="export_snapshot"):
        st.session_state['show_export_options'] = True

if st.session_state.get('show_export_options', False):
    st.success("📤 **CEO Snapshot Export**")
    st.markdown("**Snapshot includes:**")
    st.markdown("✅ All metrics with current values")
    st.markdown("✅ AI interpretations for each group")
    st.markdown("✅ Active alerts and risk flags")
    st.markdown("✅ Recommended actions per group")
    st.markdown("✅ Drive mode recommendation")
    st.markdown("✅ Risk & Opportunity analysis")
    st.markdown("\n**Export formats:**")
    st.markdown("- 📄 PDF Report (for board meetings)")
    st.markdown("- 📧 Email Summary (for weekly updates)")
    st.markdown("- 📊 CSV Data (for analysis)")
    st.info("💡 **Note:** Full export functionality requires additional implementation. This is a preview of what would be included.")

st.markdown("---")

# ============================================================================
# 🏎️ CEO COPILOT NAVIGATOR - Formula 1 Strategy System (moved under Recommended Drive Mode)
# ============================================================================
st.markdown('<div id="ai-copilot-navigator"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">🏎️ CEO Copilot Navigator — Formula 1 Strategy System</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

# 🧭 1. Main Copilot Navigator Block (Hero Section)
st.markdown("#### 🚦 Current Race Status")
copilot_hero_col1, copilot_hero_col2 = st.columns([2, 1])

with copilot_hero_col1:
    # Calculate race status indicators
    track_status = "Safe" if uptime_pct > 99.5 and incident_frequency < 1 else "Caution" if uptime_pct > 99.0 else "Danger"
    track_color = "#22c55e" if track_status == "Safe" else "#f59e0b" if track_status == "Caution" else "#ef4444"
    
    grip_status = "High" if customer_churn_pct < 2.0 and ltv_cac_ratio > 3 else "Medium" if customer_churn_pct < 3.5 else "Low"
    grip_color = "#22c55e" if grip_status == "High" else "#f59e0b" if grip_status == "Medium" else "#ef4444"
    
    weather_status = "Clear" if uptime_pct > 99.5 and incident_frequency < 0.5 else "Storm Risk" if uptime_pct < 99.0 or incident_frequency > 1.5 else "Cloudy"
    weather_color = "#22c55e" if weather_status == "Clear" else "#ef4444" if weather_status == "Storm Risk" else "#f59e0b"
    
    current_drive_mode = st.session_state.get("drive_mode", "AUTOPILOT")
    eta_days = metrics.get('eta_days', 93)
    
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                    border: 2px solid #3b82f6;
                    border-radius: 12px;
                    padding: 2rem;
                    margin: 1rem 0;
                    box-shadow: 0 8px 32px rgba(59, 130, 246, 0.3);">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem;">
                <div>
                    <div style="color: #94a3b8; font-size: 0.9em; margin-bottom: 0.5rem;">🟢 Track:</div>
                    <div style="color: {track_color}; font-size: 1.3em; font-weight: 700;">{track_status}</div>
                </div>
                <div>
                    <div style="color: #94a3b8; font-size: 0.9em; margin-bottom: 0.5rem;">🟡 Grip:</div>
                    <div style="color: {grip_color}; font-size: 1.3em; font-weight: 700;">{grip_status} (market uncertainty)</div>
                </div>
                <div>
                    <div style="color: #94a3b8; font-size: 0.9em; margin-bottom: 0.5rem;">🔴 Weather:</div>
                    <div style="color: {weather_color}; font-size: 1.3em; font-weight: 700;">{weather_status} (ops overload)</div>
                </div>
                <div>
                    <div style="color: #94a3b8; font-size: 0.9em; margin-bottom: 0.5rem;">⚙️ Drive Mode:</div>
                    <div style="color: #3b82f6; font-size: 1.3em; font-weight: 700;">{current_drive_mode}</div>
                </div>
            </div>
            <div style="text-align: center; padding-top: 1rem; border-top: 1px solid rgba(59, 130, 246, 0.3);">
                <div style="color: #94a3b8; font-size: 0.9em; margin-bottom: 0.5rem;">🏁 ETA to Target:</div>
                <div style="color: #13B0F5; font-size: 2em; font-weight: 700;">{eta_days:.0f} days</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with copilot_hero_col2:
    # Quick stats
    st.markdown("**📊 Race Metrics:**")
    st.metric("Revenue Speed", f"${rev_speed:.1f}M", f"{rev_trend}")
    st.metric("Cash Runway", f"{cash_runway_months:.1f} mo", f"{runway_trend}")
    st.metric("Pipeline Velocity", f"{pipeline_velocity:.1f}x", f"{pipeline_trend}")

st.markdown("---")

# 🧙‍♂️ 2. "Next Curve Ahead" (Foresight Panel)
st.markdown("#### 🏎️ Next Curve Ahead")
next_curve_days = 18  # Simulated
next_curve_type = "Churn curve"
next_curve_detail = "Customer sentiment dip detected — prepare for tighter steering"

st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                border-left: 4px solid #f59e0b;
                border-radius: 8px;
                padding: 1.5rem;
                margin: 1rem 0;
                box-shadow: 0 4px 16px rgba(245, 158, 11, 0.2);">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2.5em;">🏎️</div>
            <div style="flex: 1;">
                <h4 style="color: #f59e0b; margin: 0 0 0.5rem 0;">{next_curve_type} approaching in {next_curve_days} days</h4>
                <p style="color: #cbd5e1; margin: 0;">{next_curve_detail}</p>
                <div style="margin-top: 0.8rem; color: #94a3b8; font-size: 0.85em;">
                    <div>• Customer sentiment dip</div>
                    <div>• NPS anomaly detected</div>
                    <div>• Critical accounts trending downward</div>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# ⚠️ 3. "Danger Zones" (Critical Threat Radar)
st.markdown("#### ⚠️ Danger Zones — Critical Threat Radar")
danger_zones = [
    {
        "name": "Cash Overheating",
        "severity": "High",
        "icon": "🔥",
        "color": "#f59e0b",
        "detail": f"{cash_runway_months:.1f} months runway",
        "action": "Consider ECO mode or fundraising"
    },
    {
        "name": "Ops Storm Incoming",
        "severity": "Critical" if uptime_pct < 99.0 else "High",
        "icon": "🛑",
        "color": "#ef4444" if uptime_pct < 99.0 else "#f59e0b",
        "detail": f"Incident spike in APAC" if incident_frequency > 1 else "Uptime at {uptime_pct:.2f}%",
        "action": "Activate cooling protocols"
    },
    {
        "name": "Gridlock Ahead",
        "severity": "Medium",
        "icon": "⚡",
        "color": "#f59e0b",
        "detail": "Sales velocity slowing",
        "action": "Review pipeline bottlenecks"
    },
    {
        "name": "Competitor Surge",
        "severity": "High",
        "icon": "🧨",
        "color": "#f59e0b",
        "detail": "Pricing pressure in EMEA",
        "action": "Monitor competitive landscape"
    }
]

danger_cols = st.columns(len(danger_zones))
for idx, danger in enumerate(danger_zones):
    with danger_cols[idx]:
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                        border: 2px solid {danger['color']};
                        border-radius: 8px;
                        padding: 1rem;
                        margin-bottom: 1rem;
                        box-shadow: 0 4px 16px {danger['color']}30;">
                <div style="text-align: center; margin-bottom: 0.8rem;">
                    <div style="font-size: 2em;">{danger['icon']}</div>
                    <div style="color: {danger['color']}; font-weight: 700; font-size: 0.9em; margin-top: 0.3rem;">{danger['severity']}</div>
                </div>
                <div style="color: #f5f7fb; font-weight: 600; font-size: 0.95em; margin-bottom: 0.5rem;">{danger['name']}</div>
                <div style="color: #94a3b8; font-size: 0.8em; margin-bottom: 0.5rem;">{danger['detail']}</div>
                <div style="color: #64748b; font-size: 0.75em; font-style: italic;">{danger['action']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("---")

# 🎯 4. "Overtake Opportunity Alerts" (Growth Windows)
st.markdown("#### 🎯 Overtake Opportunity Alerts — Growth Windows")
overtake_opportunities = [
    {
        "title": "Market gap: competitor outages",
        "action": "Seize APAC SMB segment",
        "icon": "🟢",
        "urgency": "High"
    },
    {
        "title": "Pricing elasticity spike detected",
        "action": "Raise premium tiers +8%",
        "icon": "🟢",
        "urgency": "Medium"
    },
    {
        "title": "Pipeline seasonality tailwind",
        "action": "Ramp marketing for 3 weeks",
        "icon": "🟢",
        "urgency": "High"
    }
]

for opp in overtake_opportunities:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(22, 163, 74, 0.1));
                    border-left: 4px solid #22c55e;
                    border-radius: 8px;
                    padding: 1rem;
                    margin-bottom: 0.8rem;
                    box-shadow: 0 2px 8px rgba(34, 197, 94, 0.2);">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div style="font-size: 1.5em;">{opp['icon']}</div>
                <div style="flex: 1;">
                    <div style="color: #22c55e; font-weight: 600; margin-bottom: 0.3rem;">{opp['title']}</div>
                    <div style="color: #cbd5e1; font-size: 0.9em;">→ {opp['action']}</div>
                </div>
                <div style="color: #22c55e; font-size: 0.85em; font-weight: 600;">{opp['urgency']}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")

# 🛠️ 5. "AI Course Correction" (Dynamic Steering Advice)
st.markdown("#### 🛠️ AI Course Correction — Dynamic Steering Advice")
course_corrections = [
    {
        "action": "Steer left",
        "detail": "Rebalance engineering load from EMEA to AMER to reduce burnout",
        "icon": "⬅️",
        "color": "#3b82f6"
    },
    {
        "action": "Brake lightly",
        "detail": "Reduce spend in low-ROI campaigns by 12%",
        "icon": "🛑",
        "color": "#f59e0b"
    },
    {
        "action": "Maintain line",
        "detail": "Automations performing with +14% impact. Stay on Autopilot",
        "icon": "➡️",
        "color": "#22c55e"
    }
]

correction_cols = st.columns(len(course_corrections))
for idx, correction in enumerate(course_corrections):
    with correction_cols[idx]:
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                        border-left: 4px solid {correction['color']};
                        border-radius: 8px;
                        padding: 1.2rem;
                        margin-bottom: 1rem;
                        box-shadow: 0 4px 12px {correction['color']}20;">
                <div style="text-align: center; margin-bottom: 0.8rem;">
                    <div style="font-size: 2.5em;">{correction['icon']}</div>
                </div>
                <div style="color: {correction['color']}; font-weight: 700; font-size: 1.1em; text-align: center; margin-bottom: 0.5rem;">{correction['action']}</div>
                <div style="color: #cbd5e1; font-size: 0.85em; text-align: center;">{correction['detail']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("---")

# ⚙️ 6. Recommended Speed, Lane & Strategy
st.markdown("#### ⚙️ Recommended Speed, Lane & Strategy")

# Calculate recommended speed
if cash_runway_months > 6 and rev_speed > 100 and customer_churn_pct < 2.5:
    recommended_speed = "FAST"
    speed_color = "#22c55e"
    speed_detail = "Aggressive expansion"
elif cash_runway_months < 3 or customer_churn_pct > 5:
    recommended_speed = "SLOW"
    speed_color = "#ef4444"
    speed_detail = "Cost protection mode"
else:
    recommended_speed = "MODERATE"
    speed_color = "#f59e0b"
    speed_detail = "Balanced growth"

strategy_col1, strategy_col2, strategy_col3 = st.columns(3)

with strategy_col1:
    st.markdown("**Recommended Speed:**")
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                    border: 2px solid {speed_color};
                    border-radius: 8px;
                    padding: 1.5rem;
                    text-align: center;
                    box-shadow: 0 4px 16px {speed_color}30;">
            <div style="color: {speed_color}; font-size: 2em; font-weight: 700; margin-bottom: 0.5rem;">{recommended_speed}</div>
            <div style="color: #cbd5e1; font-size: 0.9em;">{speed_detail}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with strategy_col2:
    st.markdown("**Recommended Lane:**")
    recommended_lanes = ["Lane 1: Real-time business metrics", "Lane 3: Market intelligence & ingestion"]
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                    border: 2px solid #3b82f6;
                    border-radius: 8px;
                    padding: 1.5rem;
                    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);">
            {"<br>".join([f'<div style="color: #cbd5e1; margin-bottom: 0.5rem;">{lane}</div>' for lane in recommended_lanes])}
        </div>
        """,
        unsafe_allow_html=True
    )

with strategy_col3:
    st.markdown("**Recommended Strategy:**")
    strategy_timeline = "Short: Act now" if recommended_speed == "FAST" else "Medium: Prepare" if recommended_speed == "MODERATE" else "Long: Position for advantage"
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                    border: 2px solid #8B5CF6;
                    border-radius: 8px;
                    padding: 1.5rem;
                    box-shadow: 0 4px 16px rgba(139, 92, 246, 0.3);">
            <div style="color: #8B5CF6; font-weight: 700; margin-bottom: 0.5rem;">{strategy_timeline}</div>
            <div style="color: #cbd5e1; font-size: 0.9em; margin-top: 0.8rem;">
                Take Lane 1 + Lane 3 and accelerate — strong demand indicators.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")

# SECTION 6: KPI Gauges section
st.markdown("#### 🕹️ KPI Gauges")
g_left, g_center, g_right = st.columns(3)
with g_left:
    st.plotly_chart(
        _plot_gauge(metrics.get("rev_speed", 0), "Revenue Speed", 0, 150, " mph"),
        use_container_width=True,
    )
with g_center:
    st.plotly_chart(
        _plot_gauge(metrics.get("cash_months", 0), "Cash Fuel (Flow $M)", 0, 50, " $M"),
        use_container_width=True,
    )
with g_right:
    st.plotly_chart(
        _plot_gauge(metrics.get("ops_heat", 0), "Engine Status (Ops)", 0, 120, " score"),
        use_container_width=True,
    )

# KPI Compass section - includes all compass-related content
st.markdown('<div id="kpi-compass"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">🧭 KPI Compass</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

# Revenue Target Compass & Market Radar under KPI Compass
st.markdown("#### 🧭 Revenue Target Compass & 📡 Market Radar")
compass_radar_col1, compass_radar_col2 = st.columns([1, 1])

with compass_radar_col1:
    st.plotly_chart(
        _maritime_compass_gauge(revenue_deviation_pct, "Deviation from Revenue Target"),
        use_container_width=True,
    )

with compass_radar_col2:
    # Radar chart for upcoming milestones and market events
    st.markdown("**📡 Upcoming Milestones & Market Events**")
    
    # Mockup milestone data
    milestones = [
        {"event": "Q1 Earnings Call", "date": (current_date + timedelta(days=15)).strftime("%Y-%m-%d"), "impact": "High", "type": "Earnings"},
        {"event": "Product Launch: Cloud AI Suite", "date": (current_date + timedelta(days=28)).strftime("%Y-%m-%d"), "impact": "High", "type": "Product"},
        {"event": "Partnership Announcement", "date": (current_date + timedelta(days=42)).strftime("%Y-%m-%d"), "impact": "Medium", "type": "Partnership"},
        {"event": "Industry Conference: CloudExpo", "date": (current_date + timedelta(days=60)).strftime("%Y-%m-%d"), "impact": "Medium", "type": "Event"},
        {"event": "Regulatory Review Deadline", "date": (current_date + timedelta(days=75)).strftime("%Y-%m-%d"), "impact": "High", "type": "Compliance"},
    ]
    
    # Create radar chart for milestones
    categories = ["Earnings", "Product", "Partnership", "Event", "Compliance"]
    values = [0] * len(categories)
    for milestone in milestones:
        if milestone["type"] in categories:
            idx = categories.index(milestone["type"])
            values[idx] += 1 if milestone["impact"] == "High" else 0.5
    
    # Add current metrics to radar
    radar_categories = ["Revenue", "Cash Flow", "Market Share", "Customer Growth", "Ops Efficiency", "Innovation"]
    radar_values = [
        min(100, (metrics.get("rev_speed", 0) / 150) * 100),
        min(100, (metrics.get("cash_months", 0) / 50) * 100),
        min(100, (metrics.get("traffic", 0) / 100) * 100),
        min(100, (metrics.get("nps", 0) / 10) * 100),
        min(100, (100 - metrics.get("ops_heat", 0))),
        min(100, (metrics.get("rev_speed", 0) * 0.6)),
    ]
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_values + [radar_values[0]],  # Close the loop
        theta=radar_categories + [radar_categories[0]],
        fill='toself',
        fillcolor='rgba(59, 130, 246, 0.3)',
        line=dict(color='#3b82f6', width=3),
        name='Current Performance',
    ))
    
    # Add target line
    target_values = [80, 70, 75, 85, 80, 75] + [80]
    fig_radar.add_trace(go.Scatterpolar(
        r=target_values,
        theta=radar_categories + [radar_categories[0]],
        fill='toself',
        fillcolor='rgba(34, 197, 94, 0.1)',
        line=dict(color='#22c55e', width=2, dash='dash'),
        name='Target',
    ))
    
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10, color="#94a3b8"),
                gridcolor='rgba(59, 130, 246, 0.2)',
            ),
            angularaxis=dict(
                tickfont=dict(size=11, color="#cbd5e1"),
                gridcolor='rgba(59, 130, 246, 0.3)',
            ),
        ),
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(x=0.5, y=-0.1, xanchor='center', orientation='h'),
    )
    st.plotly_chart(fig_radar, use_container_width=True)
    
    # List upcoming milestones
    st.markdown("**Upcoming Events:**")
    for milestone in milestones[:3]:  # Show top 3
        impact_color = "#ef4444" if milestone["impact"] == "High" else "#f59e0b"
        st.markdown(
            f"""
            <div style="background: rgba(30, 41, 59, 0.4); padding: 8px; border-radius: 6px; margin-bottom: 6px; border-left: 3px solid {impact_color};">
                <strong>{milestone['event']}</strong><br>
                <span style="color: #94a3b8; font-size: 0.85em;">📅 {milestone['date']} | Impact: {milestone['impact']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# KPI Compass Gauges section (under KPI Compass)
st.markdown("#### 🧭 KPI Compass Gauges")
target_rev = 150.0  # $M run-rate goal over last 3 quarters
target_balance = 1.8e9  # Desired cash-minus-debt cushion
balance_gap = (financials.get("cash") or 0) - (financials.get("debt") or 0)
ops_target = 80.0

rev_deviation = ((metrics.get("rev_speed", 0) - target_rev) / target_rev) * 100 if target_rev > 0 else 0
balance_deviation = (
    ((balance_gap or 0) - target_balance) / target_balance * 100 if target_balance else 0
)
ops_deviation = ((metrics.get("ops_heat", 0) - ops_target) / ops_target) * 100 if ops_target > 0 else 0
compass_col1, compass_col2, compass_col3 = st.columns(3)
with compass_col1:
    st.plotly_chart(
        _maritime_compass_gauge(rev_deviation, "Revenue vs Target"),
        use_container_width=True,
    )
with compass_col2:
    st.plotly_chart(
        _maritime_compass_gauge(balance_deviation, "Balance Cushion vs Target"),
        use_container_width=True,
    )
with compass_col3:
    st.plotly_chart(
        _maritime_compass_gauge(ops_deviation, "Ops Heat vs Target"),
        use_container_width=True,
    )

# KPI Compass Table (under KPI Compass section)
st.markdown("#### 🧭 KPI Compass Table")
target_rev_table = 150.0  # $M run-rate goal over last 3 quarters
target_balance_table = 1.8e9  # Desired cash-minus-debt cushion
balance_gap_table = (financials.get("cash") or 0) - (financials.get("debt") or 0)

def _direction_label(ratio: float) -> str:
    if ratio >= 1.1:
        return "Ahead of plan ↗"
    if ratio >= 0.9:
        return "On course →"
    if ratio >= 0.75:
        return "Needs boost ↘"
    return "Off route ⛔"

compass_rows = [
    {
        "Axis": "Revenue Speed",
        "Actual": f"${metrics.get('rev_speed', 0):.1f}M",
        "Target": f"${target_rev_table:.0f}M",
        "Status": _direction_label(metrics.get("rev_speed", 0) / target_rev_table if target_rev_table > 0 else 0),
    },
    {
        "Axis": "Balance Sheet",
        "Actual": format_currency(balance_gap_table),
        "Target": format_currency(target_balance_table),
        "Status": _direction_label(balance_gap_table / target_balance_table if target_balance_table else 0),
    },
]
st.dataframe(pd.DataFrame(compass_rows), use_container_width=True, hide_index=True)

# Trip ETA & Timer Section - Car Dashboard Style with Gauges (moved right after KPI Compass Table)
st.markdown("#### ⏱️ Trip ETA & Timer")
eta_col1, eta_col2, eta_col3 = st.columns([1, 1, 1])

with eta_col1:
    # Trip ETA Gauge (Circular)
    eta_days = metrics.get('eta_days', 0)
    plan_days = 80
    max_eta = 120
    fig_eta = _plot_gauge(eta_days, "Trip ETA", 0, max_eta, " days")
    st.plotly_chart(fig_eta, use_container_width=True, config={'displayModeBar': False})
    
    # Status indicator below gauge
    delta_days = eta_days - plan_days
    status_tag = "ahead of plan" if delta_days < 0 else "behind plan" if delta_days > 0 else "on plan"
    delta_color = "#22c55e" if delta_days < 0 else "#ef4444" if delta_days > 0 else "#3b82f6"
    st.markdown(
        f"""
        <div style="background: rgba(30, 41, 59, 0.5); padding: 0.8rem; border-radius: 8px; margin-top: 0.5rem; border-left: 3px solid {delta_color}; text-align: center;">
            <div style="color: #cbd5e1; font-size: 0.9rem;">Status: <strong style="color: {delta_color};">{status_tag}</strong></div>
            <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 0.3rem;">Plan: {plan_days} days</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with eta_col2:
    # Trip Timer Gauge (Circular)
    trip_timer_days = max(0, metrics.get("eta_days", 0))
    max_timer = 120
    fig_timer = _plot_gauge(trip_timer_days, "Trip Timer", 0, max_timer, " days")
    st.plotly_chart(fig_timer, use_container_width=True, config={'displayModeBar': False})
    
    # Timer display
    trip_timer = timedelta(days=int(trip_timer_days))
    st.markdown(
        f"""
        <div style="background: rgba(30, 41, 59, 0.5); padding: 0.8rem; border-radius: 8px; margin-top: 0.5rem; border-left: 3px solid #3b82f6; text-align: center;">
            <div style="color: #cbd5e1; font-size: 0.9rem;">Elapsed: <strong style="color: #3b82f6;">{str(trip_timer)}</strong></div>
            <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 0.3rem;">vs Plan: -2d</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with eta_col3:
    # Customer Pulse (NPS) Gauge (Circular)
    nps_value = metrics.get('nps', 0)
    fig_nps = _plot_gauge(nps_value, "Customer Pulse (NPS)", 0, 10, "/10")
    st.plotly_chart(fig_nps, use_container_width=True, config={'displayModeBar': False})
    
    # NPS indicator
    nps_color = "#22c55e" if nps_value >= 8 else "#f59e0b" if nps_value >= 6 else "#ef4444"
    st.markdown(
        f"""
        <div style="background: rgba(30, 41, 59, 0.5); padding: 0.8rem; border-radius: 8px; margin-top: 0.5rem; border-left: 3px solid {nps_color}; text-align: center;">
            <div style="color: #cbd5e1; font-size: 0.9rem;">Rating: <strong style="color: {nps_color};">{nps_value:.1f}/10</strong></div>
            <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 0.3rem;">Change: +0.4</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# Company Health (moved under Trip ETA & Timer)
st.markdown('<div id="company-health"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">🏥 Company Health</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

# Define alerts with full details (mapped to gauges)
alerts_data = {
    "cash_fuel": [
        {
            "title": "Refuel soon",
            "severity": "Medium",
            "severity_icon": "⚠️",
            "severity_color": "#f59e0b",
            "business_impact": "Cash runway below 4 months may limit growth initiatives",
            "recommended_action": "Accelerate revenue collection, reduce non-essential spend, consider financing options",
            "owner": "CFO",
            "risk_score": 65,
            "details": {
                "logs": "Cash balance: $12.5M, Monthly burn: $3.2M",
                "root_cause": "Q4 expansion costs exceeded projections",
                "timeline": "Started 2 weeks ago, expected resolution in 30 days",
                "metrics": {
                    "cash_balance": 12.5,
                    "monthly_burn": 3.2,
                    "runway_months": 3.9,
                    "target": 6.0,
                },
            },
        },
    ],
    "ops_heat": [
        {
            "title": "Heat rising",
            "severity": "High",
            "severity_icon": "🔥",
            "severity_color": "#ef4444",
            "business_impact": "Operations temperature at 85°C may cause service degradation",
            "recommended_action": "Activate cooling protocols, scale infrastructure, review workload distribution",
            "owner": "CTO",
            "risk_score": 82,
            "details": {
                "logs": "Ops heat: 85°C, CPU utilization: 92%, Memory: 88%",
                "root_cause": "Traffic spike in EMEA region, insufficient auto-scaling",
                "timeline": "Detected 4 hours ago, mitigation in progress",
                "metrics": {
                    "ops_heat": 85,
                    "cpu_util": 92,
                    "memory_util": 88,
                    "target": 75,
                },
            },
        },
    ],
    "market_traffic": [
        {
            "title": "Market jam",
            "severity": "Critical",
            "severity_icon": "🛑",
            "severity_color": "#dc2626",
            "business_impact": "Market congestion at 78% may delay customer onboarding",
            "recommended_action": "Reroute traffic, increase capacity, communicate delays to customers",
            "owner": "VP Operations",
            "risk_score": 91,
            "details": {
                "logs": "EMEA traffic: 78%, APAC: 65%, Americas: 45%",
                "root_cause": "Seasonal demand spike, competitor outage redirecting traffic",
                "timeline": "Ongoing for 6 hours, peak expected in next 2 hours",
                "metrics": {
                    "emea_traffic": 78,
                    "apac_traffic": 65,
                    "americas_traffic": 45,
                    "target": 50,
                },
            },
        },
    ],
    "revenue_speed": [],  # No alerts for revenue speed currently
}

# Company Health Gauges with alerts underneath
health_col1, health_col2, health_col3, health_col4 = st.columns(4)

with health_col1:
    # Revenue Speed Gauge
    st.plotly_chart(
        _plot_gauge(metrics.get("rev_speed", 0), "Revenue Speed", 0, 150, " M"),
        use_container_width=True,
    )
    # Display alerts for revenue speed
    if alerts_data["revenue_speed"]:
        for alert in alerts_data["revenue_speed"]:
            with st.expander(f"{alert['severity_icon']} {alert['title']} (Risk: {alert['risk_score']}/100)", expanded=False):
                st.markdown(f"**Severity:** {alert['severity']}")
                st.markdown(f"**Business Impact:** {alert['business_impact']}")
                st.markdown(f"**Recommended Action:** {alert['recommended_action']}")
                st.markdown(f"**Owner:** {alert['owner']}")
                st.markdown("---")
                details = alert['details']
                st.markdown(f"**Logs:** {details['logs']}")
                st.markdown(f"**Root Cause:** {details['root_cause']}")
                st.markdown(f"**Timeline:** {details['timeline']}")
                st.markdown("**Metrics:**")
                for metric, value in details['metrics'].items():
                    if isinstance(value, (int, float)):
                        target = details['metrics'].get('target', 'N/A')
                        st.metric(metric.replace('_', ' ').title(), f"{value:.1f}", delta=f"Target: {target}")
                    else:
                        st.write(f"{metric}: {value}")
    else:
        st.markdown("✅ **No active alerts**", help="Revenue Speed is operating normally")

with health_col2:
    # Cash Fuel Gauge
    st.plotly_chart(
        _plot_gauge(metrics.get("cash_months", 0), "Cash Fuel", 0, 50, " M"),
        use_container_width=True,
    )
    # Display alerts for cash fuel
    if alerts_data["cash_fuel"]:
        for alert in alerts_data["cash_fuel"]:
            with st.expander(f"{alert['severity_icon']} {alert['title']} (Risk: {alert['risk_score']}/100)", expanded=False):
                st.markdown(f"**Severity:** {alert['severity']}")
                st.markdown(f"**Business Impact:** {alert['business_impact']}")
                st.markdown(f"**Recommended Action:** {alert['recommended_action']}")
                st.markdown(f"**Owner:** {alert['owner']}")
                st.markdown("---")
                details = alert['details']
                st.markdown(f"**Logs:** {details['logs']}")
                st.markdown(f"**Root Cause:** {details['root_cause']}")
                st.markdown(f"**Timeline:** {details['timeline']}")
                st.markdown("**Metrics:**")
                for metric, value in details['metrics'].items():
                    if isinstance(value, (int, float)):
                        target = details['metrics'].get('target', 'N/A')
                        st.metric(metric.replace('_', ' ').title(), f"{value:.1f}", delta=f"Target: {target}")
                    else:
                        st.write(f"{metric}: {value}")
    else:
        st.markdown("✅ **No active alerts**", help="Cash Fuel is operating normally")

with health_col3:
    # Ops Heat Gauge
    st.plotly_chart(
        _plot_gauge(metrics.get("ops_heat", 0), "Ops Heat", 0, 120, " °C"),
        use_container_width=True,
    )
    # Display alerts for ops heat
    if alerts_data["ops_heat"]:
        for alert in alerts_data["ops_heat"]:
            with st.expander(f"{alert['severity_icon']} {alert['title']} (Risk: {alert['risk_score']}/100)", expanded=False):
                st.markdown(f"**Severity:** {alert['severity']}")
                st.markdown(f"**Business Impact:** {alert['business_impact']}")
                st.markdown(f"**Recommended Action:** {alert['recommended_action']}")
                st.markdown(f"**Owner:** {alert['owner']}")
                st.markdown("---")
                details = alert['details']
                st.markdown(f"**Logs:** {details['logs']}")
                st.markdown(f"**Root Cause:** {details['root_cause']}")
                st.markdown(f"**Timeline:** {details['timeline']}")
                st.markdown("**Metrics:**")
                for metric, value in details['metrics'].items():
                    if isinstance(value, (int, float)):
                        target = details['metrics'].get('target', 'N/A')
                        st.metric(metric.replace('_', ' ').title(), f"{value:.1f}", delta=f"Target: {target}")
                    else:
                        st.write(f"{metric}: {value}")
    else:
        st.markdown("✅ **No active alerts**", help="Ops Heat is operating normally")

with health_col4:
    # Market Traffic Gauge
    st.plotly_chart(
        _plot_gauge(metrics.get("traffic", 0), "Market Traffic", 0, 100, " %"),
        use_container_width=True,
    )
    # Display alerts for market traffic
    if alerts_data["market_traffic"]:
        for alert in alerts_data["market_traffic"]:
            with st.expander(f"{alert['severity_icon']} {alert['title']} (Risk: {alert['risk_score']}/100)", expanded=False):
                st.markdown(f"**Severity:** {alert['severity']}")
                st.markdown(f"**Business Impact:** {alert['business_impact']}")
                st.markdown(f"**Recommended Action:** {alert['recommended_action']}")
                st.markdown(f"**Owner:** {alert['owner']}")
                st.markdown("---")
                details = alert['details']
                st.markdown(f"**Logs:** {details['logs']}")
                st.markdown(f"**Root Cause:** {details['root_cause']}")
                st.markdown(f"**Timeline:** {details['timeline']}")
                st.markdown("**Metrics:**")
                for metric, value in details['metrics'].items():
                    if isinstance(value, (int, float)):
                        target = details['metrics'].get('target', 'N/A')
                        st.metric(metric.replace('_', ' ').title(), f"{value:.1f}", delta=f"Target: {target}")
                    else:
                        st.write(f"{metric}: {value}")
    else:
        st.markdown("✅ **No active alerts**", help="Market Traffic is operating normally")

# AI Narrative Insight for Company Health
all_alerts = alerts_data["cash_fuel"] + alerts_data["ops_heat"] + alerts_data["market_traffic"] + alerts_data["revenue_speed"]
st.info(
    f"🤖 **AI Insight:** Company Health shows {len([a for a in all_alerts if a['risk_score'] > 75])} critical alerts. "
    f"EMEA congestion reached {metrics.get('traffic', 0):.0f}, impacting SLA. "
    f"Ops heat at {metrics.get('ops_heat', 0):.0f}°C requires immediate attention. "
    f"Recommend activating {'Storm' if metrics.get('ops_heat', 0) > 85 else 'Autopilot'} mode."
)

st.markdown("---")

# ============================================================================
# 📊 CEO METRICS OVERVIEW - Decision-Making Dashboard (moved under KPI Compass Table)
# ============================================================================
st.markdown('<div id="ceo-metrics"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">📊 CEO Metrics Overview</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

# Define rackspace_services early for use in Service Intelligence section
rackspace_services = [
    "AI", "OpenStack", "Hybrid Cloud", "Managed Cloud", "Elastic Engineering",
    "Data Services", "SDDC", "Spot", "Security", "Multi-Cloud"
]

# Generate customer data for Service Intelligence (if not already generated)
if 'customer_data' not in st.session_state or not st.session_state.get('customer_data'):
    customer_names = [
        "Acme Corp", "TechGlobal Inc", "FinanceHub", "HealthData Systems",
        "RetailMax", "Manufacturing Plus", "EduTech Solutions", "MediaStream",
        "Logistics Pro", "EnergyGrid Co", "RealEstate Platform", "TravelTech",
    ]
    
    def generate_customer_satisfaction_data():
        customers = []
        for name in customer_names:
            services = random.sample(rackspace_services, random.randint(2, 5))
            satisfaction = random.uniform(4.0, 10.0)
            trend = random.choice(["⬆", "➡", "⬇"])
            churn_risk = random.uniform(5.0, 45.0)
            
            feedback_snippets = [
                "Great support team, very responsive to our needs.",
                "Experiencing some latency issues with AI services.",
                "OpenStack migration was smooth, happy with the results.",
                "Security features are excellent, peace of mind.",
                "Hybrid cloud solution meets all our requirements.",
                "Need better documentation for Data Services.",
                "Elastic Engineering team is top-notch.",
                "Some concerns about pricing transparency.",
            ]
            
            customers.append({
                "Customer / Passenger Name": name,
                "Rackspace Services Used": ", ".join(services),
                "Satisfaction Score": round(satisfaction, 1),
                "Trend": trend,
                "Recent Feedback Snippet": random.choice(feedback_snippets),
                "Churn Risk %": round(churn_risk, 1),
            })
        return customers
    
    customer_data = generate_customer_satisfaction_data()
    st.session_state['customer_data'] = customer_data
else:
    customer_data = st.session_state['customer_data']

# Calculate CEO metrics
revenue_ttm = financials.get("revenue", 0) or 0
cash_balance = financials.get("cash", 0) or 0
debt_balance = financials.get("debt", 0) or 0
monthly_burn = 3.2  # From metrics
cash_runway_months = (cash_balance / monthly_burn) if monthly_burn > 0 else 0
gross_margin_pct = 65.0  # Estimated
burn_rate_m = monthly_burn
rev_speed = metrics.get('rev_speed', 0)
ltv_cac_ratio = 3.2  # Estimated
customer_churn_pct = 2.5  # Estimated
pipeline_velocity = 1.8  # Estimated
market_share_pct = 4.2  # Estimated
uptime_pct = 99.95  # Estimated
incident_frequency = 0.8  # Per month
employee_attrition_pct = 8.5  # Annual
enps_score = 45  # Employee Net Promoter Score

# Calculate trends (simulated - in real app, compare with previous period)
rev_trend = "+8%"
margin_trend = "+2%"
runway_trend = "-0.3"
burn_trend = "-5%"
churn_trend = "-0.5%"
pipeline_trend = "+12%"
uptime_trend = "+0.1%"
attrition_trend = "-1.2%"

# Determine alert status
def get_alert_status(value, thresholds):
    """Returns alert level: 'critical', 'warning', or 'normal'"""
    if 'critical_max' in thresholds and value >= thresholds['critical_max']:
        return 'critical'
    if 'critical_min' in thresholds and value <= thresholds['critical_min']:
        return 'critical'
    if 'warning_max' in thresholds and value >= thresholds['warning_max']:
        return 'warning'
    if 'warning_min' in thresholds and value <= thresholds['warning_min']:
        return 'warning'
    return 'normal'

# Define thresholds
runway_alert = get_alert_status(cash_runway_months, {'critical_min': 3.0, 'warning_min': 4.0})
churn_alert = get_alert_status(customer_churn_pct, {'critical_max': 5.0, 'warning_max': 3.5})
uptime_alert = get_alert_status(uptime_pct, {'critical_min': 99.0, 'warning_min': 99.5})
attrition_alert = get_alert_status(employee_attrition_pct, {'critical_max': 15.0, 'warning_max': 12.0})

# Helper function to render metric card
def render_metric_card(name, value, trend, interpretation, alert_level="normal", emoji="📊"):
    """Render a CEO-friendly metric card"""
    alert_icons = {
        'critical': '🔥',
        'warning': '🟧',
        'normal': '🟢'
    }
    alert_colors = {
        'critical': '#ef4444',
        'warning': '#f59e0b',
        'normal': '#22c55e'
    }
    alert_icon = alert_icons.get(alert_level, '🟢')
    alert_color = alert_colors.get(alert_level, '#22c55e')
    
    trend_arrow = "⬆" if trend.startswith("+") else "⬇" if trend.startswith("-") else "→"
    trend_color = "#22c55e" if trend.startswith("+") else "#ef4444" if trend.startswith("-") else "#94a3b8"
    
    return f"""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
                border: 1px solid {alert_color}40;
                border-left: 4px solid {alert_color};
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 0.8rem;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
            <div>
                <div style="color: #cbd5e1; font-size: 0.85em; margin-bottom: 0.3rem;">{emoji} {name}</div>
                <div style="color: #f5f7fb; font-size: 1.3em; font-weight: 700;">{value}</div>
            </div>
            <div style="text-align: right;">
                <div style="color: {trend_color}; font-size: 0.9em; font-weight: 600;">{trend_arrow} {trend}</div>
                <div style="color: {alert_color}; font-size: 0.75em; margin-top: 0.2rem;">{alert_icon}</div>
            </div>
        </div>
        <div style="color: #94a3b8; font-size: 0.8em; font-style: italic;">"{interpretation}"</div>
    </div>
    """

# ROW 1: Financial Health
st.markdown("#### 💰 Financial Stability")
fin_row1, fin_row2, fin_row3, fin_row4 = st.columns(4)

with fin_row1:
    st.markdown(render_metric_card(
        "Revenue (ARR)",
        format_currency(revenue_ttm),
        rev_trend + " MoM",
        "Strong momentum",
        "normal",
        "💰"
    ), unsafe_allow_html=True)

with fin_row2:
    st.markdown(render_metric_card(
        "Gross Margin",
        f"{gross_margin_pct:.1f}%",
        margin_trend + " YoY",
        "Healthy profitability",
        "normal",
        "📈"
    ), unsafe_allow_html=True)

with fin_row3:
    st.markdown(render_metric_card(
        "Cash Runway",
        f"{cash_runway_months:.1f} months",
        runway_trend + " months",
        "Monitor closely" if cash_runway_months < 4 else "Adequate buffer",
        runway_alert,
        "💵"
    ), unsafe_allow_html=True)

with fin_row4:
    st.markdown(render_metric_card(
        "Burn Rate",
        f"${burn_rate_m:.1f}M/mo",
        burn_trend + " MoM",
        "Controlled spending",
        "normal",
        "🔥"
    ), unsafe_allow_html=True)

# AI Interpretation for Financial Group
financial_interpretation = f"Runway {'critical' if cash_runway_months < 3 else 'stable' if cash_runway_months >= 4 else 'tight'} ({cash_runway_months:.1f} months), revenue {'accelerating' if rev_trend.startswith('+') else 'stable'}, burn {'moderate' if burn_rate_m < 4 else 'high'}. {'CFO action required' if cash_runway_months < 3 else 'No immediate CFO action required'}."
st.info(f"🤖 **AI Interpretation:** {financial_interpretation}")

# Action button for Financial Group
fin_action_col1, fin_action_col2 = st.columns([1, 4])
with fin_action_col1:
    if st.button("📈 Recommend Actions", key="fin_actions"):
        st.session_state['show_fin_actions'] = not st.session_state.get('show_fin_actions', False)

if st.session_state.get('show_fin_actions', False):
    with st.expander("💡 Recommended Actions for Financial Stability", expanded=True):
        st.markdown("**What Changed:**")
        st.markdown(f"- Revenue: {rev_trend} month-over-month")
        st.markdown(f"- Cash runway: {cash_runway_months:.1f} months ({runway_trend})")
        st.markdown(f"- Burn rate: ${burn_rate_m:.1f}M/month ({burn_trend})")
        st.markdown("\n**What It Means:**")
        if cash_runway_months < 3:
            st.markdown("- ⚠️ **Critical:** Cash runway below 3 months requires immediate action")
            st.markdown("- Consider switching to **ECO Mode** or **SAFE MODE**")
        elif cash_runway_months < 4:
            st.markdown("- 🟧 **Warning:** Cash runway tight, monitor closely")
        else:
            st.markdown("- ✅ Runway is adequate for current operations")
        st.markdown("\n**What to Do:**")
        if cash_runway_months < 3:
            st.markdown("1. **Immediate:** Accelerate revenue collection")
            st.markdown("2. **Short-term:** Reduce non-essential spend")
            st.markdown("3. **Consider:** Financing options or fundraising")
            st.markdown("4. **Mode:** Switch to ECO or SAFE MODE")
        else:
            st.markdown("1. Continue current financial strategy")
            st.markdown("2. Monitor runway monthly")
            st.markdown("3. Maintain current drive mode")

st.markdown("---")

# ROW 2: Customer + Growth
st.markdown("#### 🚀 Growth & Market")
growth_row1, growth_row2, growth_row3, growth_row4 = st.columns(4)

with growth_row1:
    st.markdown(render_metric_card(
        "LTV/CAC Ratio",
        f"{ltv_cac_ratio:.1f}x",
        "+0.3x",
        "Healthy unit economics",
        "normal",
        "📊"
    ), unsafe_allow_html=True)

with growth_row2:
    st.markdown(render_metric_card(
        "Customer Churn",
        f"{customer_churn_pct:.1f}%",
        churn_trend + " MoM",
        "Improving retention" if churn_trend.startswith("-") else "Stable",
        churn_alert,
        "👥"
    ), unsafe_allow_html=True)

with growth_row3:
    st.markdown(render_metric_card(
        "Pipeline Velocity",
        f"{pipeline_velocity:.1f}x",
        pipeline_trend + " MoM",
        "Strong pipeline",
        "normal",
        "🎯"
    ), unsafe_allow_html=True)

with growth_row4:
    st.markdown(render_metric_card(
        "Market Share",
        f"{market_share_pct:.1f}%",
        "+0.2%",
        "Growing presence",
        "normal",
        "🌐"
    ), unsafe_allow_html=True)

# AI Interpretation for Growth Group
growth_interpretation = f"Churn {'trending down' if churn_trend.startswith('-') else 'stable'} ({customer_churn_pct:.1f}%), CAC improving (LTV/CAC {ltv_cac_ratio:.1f}x), pipeline strong ({pipeline_velocity:.1f}x velocity). {'Continue in Autopilot mode' if churn_alert == 'normal' else 'Monitor churn closely'}."
st.info(f"🤖 **AI Interpretation:** {growth_interpretation}")

# Action button for Growth Group
growth_action_col1, growth_action_col2 = st.columns([1, 4])
with growth_action_col1:
    if st.button("📈 Recommend Actions", key="growth_actions"):
        st.session_state['show_growth_actions'] = not st.session_state.get('show_growth_actions', False)

if st.session_state.get('show_growth_actions', False):
    with st.expander("💡 Recommended Actions for Growth & Market", expanded=True):
        st.markdown("**What Changed:**")
        st.markdown(f"- Churn: {customer_churn_pct:.1f}% ({churn_trend})")
        st.markdown(f"- LTV/CAC: {ltv_cac_ratio:.1f}x")
        st.markdown(f"- Pipeline velocity: {pipeline_velocity:.1f}x ({pipeline_trend})")
        st.markdown("\n**What It Means:**")
        if churn_alert == 'critical':
            st.markdown("- ⚠️ **Critical:** High churn requires immediate attention")
        elif churn_alert == 'warning':
            st.markdown("- 🟧 **Warning:** Churn above target, investigate")
        else:
            st.markdown("- ✅ Healthy growth metrics")
        st.markdown("\n**What to Do:**")
        if churn_alert == 'critical':
            st.markdown("1. **Immediate:** Customer retention program")
            st.markdown("2. **Analyze:** Root causes of churn")
            st.markdown("3. **Mode:** Consider SAFE MODE to stabilize")
        else:
            st.markdown("1. Continue growth initiatives")
            st.markdown("2. Focus on high-value deals")
            st.markdown("3. Maintain AUTOPILOT or SPORT mode")

st.markdown("---")

# ROW 3: Operations + Talent
st.markdown("#### ⚙️ Operations & People")
ops_row1, ops_row2, ops_row3, ops_row4 = st.columns(4)

with ops_row1:
    st.markdown(render_metric_card(
        "Uptime/SLA",
        f"{uptime_pct:.2f}%",
        uptime_trend + " MoM",
        "Excellent reliability",
        uptime_alert,
        "🛡️"
    ), unsafe_allow_html=True)

with ops_row2:
    st.markdown(render_metric_card(
        "Incident Frequency",
        f"{incident_frequency:.1f}/mo",
        "-0.2/mo",
        "Low incident rate",
        "normal",
        "🚨"
    ), unsafe_allow_html=True)

with ops_row3:
    st.markdown(render_metric_card(
        "Employee Attrition",
        f"{employee_attrition_pct:.1f}%",
        attrition_trend + " YoY",
        "Within target range",
        attrition_alert,
        "👔"
    ), unsafe_allow_html=True)

with ops_row4:
    st.markdown(render_metric_card(
        "eNPS Score",
        f"{enps_score}",
        "+3",
        "Strong engagement",
        "normal",
        "😊"
    ), unsafe_allow_html=True)

# AI Interpretation for Operations Group
ops_interpretation = f"Uptime excellent ({uptime_pct:.2f}%), incidents low ({incident_frequency:.1f}/mo), attrition {'within target' if attrition_alert == 'normal' else 'elevated'} ({employee_attrition_pct:.1f}%), team engagement strong (eNPS {enps_score}). {'Operations stable' if uptime_alert == 'normal' and attrition_alert == 'normal' else 'Monitor operations closely'}."
st.info(f"🤖 **AI Interpretation:** {ops_interpretation}")

# Action button for Operations Group
ops_action_col1, ops_action_col2 = st.columns([1, 4])
with ops_action_col1:
    if st.button("📈 Recommend Actions", key="ops_actions"):
        st.session_state['show_ops_actions'] = not st.session_state.get('show_ops_actions', False)

if st.session_state.get('show_ops_actions', False):
    with st.expander("💡 Recommended Actions for Operations & People", expanded=True):
        st.markdown("**What Changed:**")
        st.markdown(f"- Uptime: {uptime_pct:.2f}% ({uptime_trend})")
        st.markdown(f"- Incidents: {incident_frequency:.1f}/mo")
        st.markdown(f"- Attrition: {employee_attrition_pct:.1f}% ({attrition_trend})")
        st.markdown(f"- eNPS: {enps_score}")
        st.markdown("\n**What It Means:**")
        if uptime_alert == 'critical' or attrition_alert == 'critical':
            st.markdown("- ⚠️ **Critical:** Operations or people issues require attention")
        elif uptime_alert == 'warning' or attrition_alert == 'warning':
            st.markdown("- 🟧 **Warning:** Monitor operations/people metrics")
        else:
            st.markdown("- ✅ Operations and team are healthy")
        st.markdown("\n**What to Do:**")
        if uptime_alert == 'critical':
            st.markdown("1. **Immediate:** Investigate uptime issues")
            st.markdown("2. **Mode:** Consider PIT-STOP mode")
        elif attrition_alert == 'critical':
            st.markdown("1. **Immediate:** Address retention issues")
            st.markdown("2. **Review:** Compensation and culture")
        else:
            st.markdown("1. Maintain current operations")
            st.markdown("2. Continue monitoring")

# ============================================================================
# Moved sections into CEO Metrics Overview with dark theme
# ============================================================================

# Dark theme styling for moved sections
st.markdown(
    """
    <style>
    /* Dark theme for Product Portfolio, Service Intelligence, Balance Sheet, Smart Calendar */
    .ceo-dark-section {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.98));
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    .ceo-dark-section h4, .ceo-dark-section h3 {
        color: #60a5fa;
        border-bottom: 2px solid rgba(59, 130, 246, 0.3);
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }
    .ceo-dark-section .stDataFrame {
        background: rgba(15, 23, 42, 0.6) !important;
    }
    .ceo-dark-section .stMetric {
        background: rgba(15, 23, 42, 0.4) !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
    }
    .ceo-dark-section .stSelectbox, .ceo-dark-section .stButton {
        background: rgba(15, 23, 42, 0.6) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Product Portfolio Revenue & Performance Analysis (moved into CEO Metrics Overview)
st.markdown('<div class="ceo-dark-section">', unsafe_allow_html=True)
st.markdown("#### 📦 Product Portfolio Revenue & Performance Analysis")
# Generate product portfolio data based on company choice
product_portfolio_data = [
    {
        "Product": "☁️ Managed Cloud Services",
        "Revenue (Q3 2024)": "$1.44B",
        "Revenue %": "60%",
        "Target Customers": "Mid-market enterprises (500-5K employees), Healthcare, Finance",
        "Status": "🏆 Winner",
        "Growth": "+12% YoY",
        "Notes": "Core revenue driver; strong retention"
    },
    {
        "Product": "🔐 Multi-Cloud Solutions",
        "Revenue (Q3 2024)": "$600M",
        "Revenue %": "25%",
        "Target Customers": "Enterprise (5K+ employees), Fortune 500, Government",
        "Status": "🏆 Winner",
        "Growth": "+18% YoY",
        "Notes": "Fastest growing segment; high margin"
    },
    {
        "Product": "🛡️ Security & Compliance",
        "Revenue (Q3 2024)": "$360M",
        "Revenue %": "15%",
        "Target Customers": "Regulated industries (Finance, Healthcare, Government)",
        "Status": "📈 Growing",
        "Growth": "+8% YoY",
        "Notes": "Steady growth; compliance-driven demand"
    },
    {
        "Product": "🤖 AI/ML Services",
        "Revenue (Q3 2024)": "$120M",
        "Revenue %": "5%",
        "Target Customers": "Tech companies, Data-intensive enterprises",
        "Status": "📈 Growing",
        "Growth": "+45% YoY",
        "Notes": "Emerging segment; high potential"
    },
    {
        "Product": "💾 Legacy Hosting Services",
        "Revenue (Q3 2024)": "$180M",
        "Revenue %": "7.5%",
        "Target Customers": "SMBs, Traditional businesses",
        "Status": "📉 Declining",
        "Growth": "-15% YoY",
        "Notes": "Migration to cloud; sunset candidate"
    },
    {
        "Product": "📊 Data Analytics Platform",
        "Revenue (Q3 2024)": "$96M",
        "Revenue %": "4%",
        "Target Customers": "Enterprise analytics teams, BI departments",
        "Status": "📉 Declining",
        "Growth": "-8% YoY",
        "Notes": "Competitive pressure; needs refresh"
    },
    {
        "Product": "🌐 CDN & Edge Services",
        "Revenue (Q3 2024)": "$72M",
        "Revenue %": "3%",
        "Target Customers": "Media companies, E-commerce, Global enterprises",
        "Status": "📈 Growing",
        "Growth": "+22% YoY",
        "Notes": "Strong performance; expanding footprint"
    },
    {
        "Product": "🔧 DevOps & Automation",
        "Revenue (Q3 2024)": "$48M",
        "Revenue %": "2%",
        "Target Customers": "Tech startups, Software companies, DevOps teams",
        "Status": "📈 Growing",
        "Growth": "+35% YoY",
        "Notes": "High growth; strategic focus area"
    }
]

product_df = pd.DataFrame(product_portfolio_data)

# Add styling for winners and losers
def style_product_status(val):
    if "🏆 Winner" in str(val):
        return "background-color: rgba(34, 197, 94, 0.2); color: #22c55e; font-weight: bold;"
    elif "📉 Declining" in str(val):
        return "background-color: rgba(239, 68, 68, 0.2); color: #ef4444; font-weight: bold;"
    elif "📈 Growing" in str(val):
        return "background-color: rgba(59, 130, 246, 0.2); color: #3b82f6; font-weight: bold;"
    return ""

st.dataframe(
    product_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Product": st.column_config.TextColumn(
            "Product",
            width="medium",
            help="Product/service name"
        ),
        "Revenue (Q3 2024)": st.column_config.TextColumn(
            "Revenue (Q3 2024)",
            width="small",
            help="Quarterly revenue for Q3 2024"
        ),
        "Revenue %": st.column_config.TextColumn(
            "Revenue %",
            width="small",
            help="Percentage of total company revenue"
        ),
        "Target Customers": st.column_config.TextColumn(
            "Target Customers",
            width="large",
            help="Primary customer segments for this product"
        ),
        "Status": st.column_config.TextColumn(
            "Status",
            width="small",
            help="Performance status: Winner, Growing, or Declining"
        ),
        "Growth": st.column_config.TextColumn(
            "Growth",
            width="small",
            help="Year-over-year growth rate"
        ),
        "Notes": st.column_config.TextColumn(
            "Notes",
            width="medium",
            help="Key insights and observations"
        ),
    }
)

# Summary statistics
st.markdown("**📊 Portfolio Summary:**")
summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
with summary_col1:
    winners = len([p for p in product_portfolio_data if "🏆 Winner" in p["Status"]])
    st.metric("🏆 Winners", winners)
with summary_col2:
    growing = len([p for p in product_portfolio_data if "📈 Growing" in p["Status"]])
    st.metric("📈 Growing", growing)
with summary_col3:
    declining = len([p for p in product_portfolio_data if "📉 Declining" in p["Status"]])
    st.metric("📉 Declining", declining)
with summary_col4:
    total_revenue_m = 0
    for p in product_portfolio_data:
        rev_str = p["Revenue (Q3 2024)"].replace("$", "").replace(",", "")
        if "B" in rev_str:
            total_revenue_m += float(rev_str.replace("B", "")) * 1000
        elif "M" in rev_str:
            total_revenue_m += float(rev_str.replace("M", ""))
    st.metric("Total Portfolio Revenue", f"${total_revenue_m/1000:.2f}B")
st.markdown('</div>', unsafe_allow_html=True)

# Service Intelligence Section (moved into CEO Metrics Overview)
st.markdown('<div class="ceo-dark-section">', unsafe_allow_html=True)
st.markdown("#### 🔍 Service Intelligence")

# Calculate service-level metrics
service_metrics = {}
for service in rackspace_services:
    service_customers = [c for c in customer_data if service in c["Rackspace Services Used"]]
    if service_customers:
        service_metrics[service] = {
            "customer_count": len(service_customers),
            "customer_pct": (len(service_customers) / len(customer_data)) * 100,
            "avg_satisfaction": sum([c["Satisfaction Score"] for c in service_customers]) / len(service_customers),
            "churn_risk_contribution": sum([c["Churn Risk %"] for c in service_customers]) / len(service_customers),
            "positive_feedback": [
                c["Recent Feedback Snippet"] for c in service_customers 
                if c["Satisfaction Score"] >= 8 and ("great" in c["Recent Feedback Snippet"].lower() or "excellent" in c["Recent Feedback Snippet"].lower() or "love" in c["Recent Feedback Snippet"].lower())
            ][:2] if any(c["Satisfaction Score"] >= 8 for c in service_customers) else ["No positive feedback yet"],
            "complaints": [
                c["Recent Feedback Snippet"] for c in service_customers 
                if c["Satisfaction Score"] < 6 or "issue" in c["Recent Feedback Snippet"].lower() or "concern" in c["Recent Feedback Snippet"].lower() or "need" in c["Recent Feedback Snippet"].lower()
            ][:2] if any(c["Satisfaction Score"] < 6 or "issue" in c["Recent Feedback Snippet"].lower() for c in service_customers) else ["No complaints"],
        }

# Create service intelligence dataframe
service_intel_data = []
for service, service_metric in service_metrics.items():
    service_intel_data.append({
        "Service Name": service,
        "% of Customers Using": f"{service_metric.get('customer_pct', 0):.1f}%",
        "Avg Satisfaction Score": f"{service_metric.get('avg_satisfaction', 0):.1f}/10",
        "Churn Risk Contribution": f"{service_metric.get('churn_risk_contribution', 0):.1f}%",
        "Top Positive Feedback": service_metric.get('positive_feedback', [None])[0] if service_metric.get('positive_feedback') else "N/A",
        "Top Complaint": service_metric.get('complaints', [None])[0] if service_metric.get('complaints') else "N/A",
    })

if service_intel_data:
    df_service_intel = pd.DataFrame(service_intel_data)
    
    # Sort by customer percentage (convert to float for sorting)
    df_service_intel["_sort_pct"] = df_service_intel["% of Customers Using"].str.rstrip('%').astype(float)
    df_service_intel = df_service_intel.sort_values("_sort_pct", ascending=False).drop("_sort_pct", axis=1)
    
    st.dataframe(
        df_service_intel,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Service Name": st.column_config.TextColumn("Service", width="medium"),
            "% of Customers Using": st.column_config.TextColumn("Usage %", width="small"),
            "Avg Satisfaction Score": st.column_config.TextColumn("Satisfaction", width="small"),
            "Churn Risk Contribution": st.column_config.TextColumn("Churn Risk", width="small"),
            "Top Positive Feedback": st.column_config.TextColumn("Positive Theme", width="large"),
            "Top Complaint": st.column_config.TextColumn("Complaint Theme", width="large"),
        }
    )
    
    # AI Narrative Insight for Service Intelligence
    top_service = service_intel_data[0]["Service Name"]
    top_satisfaction = max([m["avg_satisfaction"] for m in service_metrics.values()])
    top_service_name = [s for s, m in service_metrics.items() if m["avg_satisfaction"] == top_satisfaction][0]
    
    st.info(
        f"🤖 **AI Insight:** {top_service_name} customers show highest satisfaction (avg {top_satisfaction:.1f}/10). "
        f"{service_intel_data[0]['Service Name']} is the most used service ({service_intel_data[0]['% of Customers Using']}). "
        f"Service-level health overview shows {len([s for s in service_intel_data if float(s['Churn Risk Contribution'].rstrip('%')) > 25])} services with elevated churn risk."
    )
st.markdown('</div>', unsafe_allow_html=True)

# Balance Sheet Snapshot (moved into CEO Metrics Overview)
st.markdown('<div class="ceo-dark-section">', unsafe_allow_html=True)
st.markdown("#### 📊 Balance Sheet Snapshot")
assets_est = (financials.get("cash") or 0) + max(0.0, (financials.get("revenue") or 0) * 0.25)
liabilities = financials.get("debt") or 0
equity = max(0.0, assets_est - liabilities)
balance_sheet = pd.DataFrame(
    [
        {"Line Item": "Estimated Assets", "Amount": format_currency(assets_est)},
        {"Line Item": "Liabilities (Debt)", "Amount": format_currency(liabilities)},
        {"Line Item": "Shareholder Equity", "Amount": format_currency(equity)},
    ]
)
st.dataframe(balance_sheet, use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)

# Smart Calendar (moved into CEO Metrics Overview)
st.markdown('<div class="ceo-dark-section">', unsafe_allow_html=True)
st.markdown("#### 📅 Smart Calendar")
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
st.markdown('</div>', unsafe_allow_html=True)

# AI-Generated Insights Section
st.markdown("---")
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">🤖 AI-Generated Insights</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("**🤖 AI-Generated Insights:**")
insights = [
    f"🚨 **Critical Alert** ({current_date.strftime('%Y-%m-%d')}): Revenue growth is {abs(revenue_deviation_pct):.1f}% below target. Pipeline value needs $2.6M increase to meet Q1 goals.",
    f"💡 **Opportunity** ({current_date.strftime('%Y-%m-%d')}): Customer acquisition cost is 22.5% above target. Consider optimizing marketing channels and improving conversion rates.",
    f"📈 **Trend** ({current_date.strftime('%Y-%m-%d')}): MRR growth trajectory is positive but needs acceleration. Focus on upselling existing customers and reducing churn.",
]
for insight in insights:
    st.markdown(f"• {insight}")

st.markdown("**Recommended Actions to Meet Revenue Target:**")
st.markdown(f"*Generated: {current_date.strftime('%B %d, %Y')}*")

# Apply theme color to dashboard based on selected mode
mode_config = DRIVE_MODES[st.session_state.drive_mode]
st.markdown(
    f"""
    <style>
    :root {{
        --drive-mode-color: {mode_config['color']};
        --drive-mode-color-secondary: {mode_config['color_secondary']};
    }}
    .stMetric {{
        border-left: 3px solid {mode_config['color']};
    }}
    .stDataFrame {{
        border: 1px solid {mode_config['color']}40;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# SECTION 2: Customer Feedback Survey
st.markdown('<div id="customer-feedback"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">💬 Passenger / Customer Feedback Survey</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

# AI Narrative Insight for Driving Mode
current_mode = st.session_state.get("drive_mode", "AUTOPILOT")
mode_config = DRIVE_MODES.get(current_mode, DRIVE_MODES["AUTOPILOT"])
st.info(
    f"🤖 **AI Insight:** Driving Mode operating in **{current_mode}** mode. "
    f"Revenue speed: ${metrics.get('rev_speed', 0):.1f}M, Cash fuel: ${metrics.get('cash_months', 0):.1f}M. "
    f"Trip ETA: {metrics.get('eta_days', 0):.0f} days ({'ahead' if metrics.get('eta_days', 0) < 80 else 'behind'} of plan). "
    f"Current mode recommendations: {mode_config['actionables'][0]}."
)

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)


# Customer Satisfaction Summary Card
st.markdown("#### 📊 Customer Satisfaction Summary")
summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

# Generate customer data
rackspace_services = [
    "AI", "OpenStack", "Hybrid Cloud", "Managed Cloud", "Elastic Engineering",
    "Data Services", "SDDC", "Spot", "Security", "Multi-Cloud"
]

customer_names = [
    "Acme Corp", "TechGlobal Inc", "FinanceHub", "HealthData Systems",
    "RetailMax", "Manufacturing Plus", "EduTech Solutions", "MediaStream",
    "Logistics Pro", "EnergyGrid Co", "RealEstate Platform", "TravelTech",
]

def generate_customer_satisfaction_data():
    customers = []
    for name in customer_names:
        services = random.sample(rackspace_services, random.randint(2, 5))
        satisfaction = random.uniform(4.0, 10.0)
        trend = random.choice(["⬆", "➡", "⬇"])
        churn_risk = random.uniform(5.0, 45.0)
        
        feedback_snippets = [
            "Great support team, very responsive to our needs.",
            "Experiencing some latency issues with AI services.",
            "OpenStack migration was smooth, happy with the results.",
            "Security features are excellent, peace of mind.",
            "Hybrid cloud solution meets all our requirements.",
            "Need better documentation for Data Services.",
            "Elastic Engineering team is top-notch.",
            "Some concerns about pricing transparency.",
        ]
        
        customers.append({
            "Customer / Passenger Name": name,
            "Rackspace Services Used": ", ".join(services),
            "Satisfaction Score": round(satisfaction, 1),
            "Trend": trend,
            "Recent Feedback Snippet": random.choice(feedback_snippets),
            "Churn Risk %": round(churn_risk, 1),
        })
    return customers

customer_data = generate_customer_satisfaction_data()
df_customers = pd.DataFrame(customer_data)

# Calculate summary metrics
avg_score = df_customers["Satisfaction Score"].mean()
improving_count = len([c for c in customer_data if c["Trend"] == "⬆"])
improving_pct = (improving_count / len(customer_data)) * 100
at_risk_customers = [c for c in customer_data if c["Churn Risk %"] > 20]
at_risk_revenue = sum([random.uniform(50, 500) for _ in at_risk_customers])  # Mock revenue

with summary_col1:
    st.metric("Average Score", f"{avg_score:.1f}/10", delta=f"{avg_score - 7.5:.1f}")
with summary_col2:
    st.metric("% Improving", f"{improving_pct:.0f}%", delta=f"+{improving_pct - 50:.0f}%")
with summary_col3:
    st.metric("At-Risk Customers", len(at_risk_customers), delta=f"{len(at_risk_customers) - 3}")
with summary_col4:
    st.metric("Revenue at Risk", f"${at_risk_revenue:.0f}K", delta=f"-${at_risk_revenue * 0.1:.0f}K")

# Filters
filter_col1, filter_col2, filter_col3 = st.columns(3)
with filter_col1:
    show_ai_customers = st.checkbox("Show only AI service customers", key="filter_ai")
with filter_col2:
    show_openstack = st.checkbox("Show only OpenStack customers", key="filter_openstack")
with filter_col3:
    show_at_risk = st.checkbox("Show only at-risk accounts", key="filter_at_risk")

# Apply filters
filtered_df = df_customers.copy()
if show_ai_customers:
    filtered_df = filtered_df[filtered_df["Rackspace Services Used"].str.contains("AI", na=False)]
if show_openstack:
    filtered_df = filtered_df[filtered_df["Rackspace Services Used"].str.contains("OpenStack", na=False)]
if show_at_risk:
    filtered_df = filtered_df[filtered_df["Churn Risk %"] > 20]

# Color code the dataframe
def color_satisfaction_score(val):
    if val >= 8:
        return "background-color: rgba(34, 197, 94, 0.3); color: #22c55e;"
    elif val >= 5:
        return "background-color: rgba(234, 179, 8, 0.3); color: #eab308;"
    else:
        return "background-color: rgba(239, 68, 68, 0.3); color: #ef4444;"

def color_churn_risk(val):
    if val <= 10:
        return "background-color: rgba(34, 197, 94, 0.3); color: #22c55e;"
    elif val <= 20:
        return "background-color: rgba(234, 179, 8, 0.3); color: #eab308;"
    elif val <= 40:
        return "background-color: rgba(249, 115, 22, 0.3); color: #f97316;"
    else:
        return "background-color: rgba(239, 68, 68, 0.3); color: #ef4444;"

# Display styled dataframe
st.markdown("#### 📋 Customer Satisfaction Details")
styled_df = filtered_df.style.applymap(color_satisfaction_score, subset=["Satisfaction Score"]).applymap(
    color_churn_risk, subset=["Churn Risk %"]
)
st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Customer / Passenger Name": st.column_config.TextColumn("Customer", width="medium"),
        "Rackspace Services Used": st.column_config.TextColumn("Services", width="large"),
        "Satisfaction Score": st.column_config.NumberColumn("Score", width="small", format="%.1f"),
        "Trend": st.column_config.TextColumn("Trend", width="small"),
        "Recent Feedback Snippet": st.column_config.TextColumn("Feedback", width="large"),
        "Churn Risk %": st.column_config.NumberColumn("Churn Risk", width="small", format="%.1f%%"),
    }
)

# AI Narrative Insight for Customer Feedback
st.info(
    f"🤖 **AI Insight:** Customer satisfaction averages {avg_score:.1f}/10 with {improving_pct:.0f}% of accounts improving. "
    f"{len(at_risk_customers)} customers show churn risk >20%, representing ${at_risk_revenue:.0f}K in revenue at risk. "
    f"{'AI service customers show highest satisfaction (avg 8.5/10).' if show_ai_customers else 'Hybrid Cloud customers are the happiest segment (avg 9/10).'} "
    f"{'OpenStack migration accounts remain the highest churn risk.' if show_openstack else 'Focus on top 20% revenue customers to reduce churn.'}"
)

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# SECTION 4: Customer Acquisition & Revenue Pulse
st.markdown('<div id="revenue-pulse"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="section-header">
        <h2 style="color: #60a5fa; margin: 0;">💰 Customer Acquisition & Revenue Pulse</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

# Generate sample customer data for this quarter
current_quarter = f"Q{(current_date.month - 1) // 3 + 1} {current_date.year}"
new_customers_count = random.randint(45, 85)
new_customer_avg_revenue = random.uniform(12.5, 45.0)  # $K per customer
new_customer_revenue = new_customers_count * new_customer_avg_revenue

lost_customers_count = random.randint(8, 25)
lost_customer_avg_revenue = random.uniform(15.0, 35.0)  # $K per customer
lost_customer_revenue = lost_customers_count * lost_customer_avg_revenue

net_customers = new_customers_count - lost_customers_count
net_revenue = new_customer_revenue - lost_customer_revenue

# Toggle between customer count and revenue impact view
view_toggle = st.radio("View Mode", ["Customer Count", "Revenue Impact"], horizontal=True, key="acquisition_view")

st.markdown("#### 👥 Customer Acquisition & Churn Analysis")

acq_col1, acq_col2, acq_col3 = st.columns(3)

with acq_col1:
    # New Customers with mini bar chart
    new_trend = random.choice(["⬆", "➡", "⬇"])
    new_trend_pct = random.uniform(-5, 15)
    st.metric(
        "🟢 New Customers",
        f"{new_customers_count:,}",
        delta=f"{new_trend_pct:+.1f}% {new_trend}",
        delta_color="normal" if new_trend_pct > 0 else "inverse"
    )
    # Mini progress bar
    fig_new = go.Figure(go.Bar(
        x=[new_customers_count],
        y=["New"],
        orientation='h',
        marker_color='#22c55e',
        text=[f"{new_customers_count}"],
        textposition='inside',
    ))
    fig_new.update_layout(
        height=80,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False),
        yaxis=dict(showticklabels=False),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig_new, use_container_width=True, config={'displayModeBar': False})
    if view_toggle == "Revenue Impact":
        st.caption(f"Revenue: {format_currency(new_customer_revenue * 1000)}")

with acq_col2:
    # Lost Customers with mini bar chart
    lost_trend = random.choice(["⬆", "➡", "⬇"])
    lost_trend_pct = random.uniform(-10, 5)
    st.metric(
        "🔴 Lost Customers",
        f"{lost_customers_count:,}",
        delta=f"{lost_trend_pct:+.1f}% {lost_trend}",
        delta_color="inverse" if lost_trend_pct > 0 else "normal"
    )
    # Mini progress bar
    fig_lost = go.Figure(go.Bar(
        x=[lost_customers_count],
        y=["Lost"],
        orientation='h',
        marker_color='#ef4444',
        text=[f"{lost_customers_count}"],
        textposition='inside',
    ))
    fig_lost.update_layout(
        height=80,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False),
        yaxis=dict(showticklabels=False),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig_lost, use_container_width=True, config={'displayModeBar': False})
    if view_toggle == "Revenue Impact":
        st.caption(f"Revenue Lost: {format_currency(lost_customer_revenue * 1000)}")

with acq_col3:
    # Net Change with mini bar chart
    net_trend = "⬆" if net_customers > 0 else "⬇" if net_customers < 0 else "➡"
    st.metric(
        "📊 Net Change",
        f"{net_customers:+,}",
        delta=f"{net_trend} vs last quarter",
        delta_color="normal" if net_customers > 0 else "inverse"
    )
    # Mini progress bar
    fig_net = go.Figure(go.Bar(
        x=[abs(net_customers)],
        y=["Net"],
        orientation='h',
        marker_color='#3b82f6' if net_customers > 0 else '#ef4444',
        text=[f"{net_customers:+}"],
        textposition='inside',
    ))
    fig_net.update_layout(
        height=80,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False),
        yaxis=dict(showticklabels=False),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig_net, use_container_width=True, config={'displayModeBar': False})
    if view_toggle == "Revenue Impact":
        st.caption(f"Net Revenue: {format_currency(net_revenue * 1000)}")

# Quarter-to-Date Forecast Panel
st.markdown("#### 📈 Quarter-to-Date Forecast")
qtd_col1, qtd_col2, qtd_col3 = st.columns(3)

with qtd_col1:
    qtd_days_elapsed = (current_date - datetime(current_date.year, ((current_date.month - 1) // 3) * 3 + 1, 1)).days
    qtd_progress = (qtd_days_elapsed / 90) * 100
    st.metric("QTD Progress", f"{qtd_progress:.0f}%", delta=f"{qtd_days_elapsed} days elapsed")
    
    # QTD forecast chart
    qtd_forecast = pd.DataFrame({
        "Week": [f"W{i}" for i in range(1, 14)],
        "Actual": [random.uniform(40, 60) if i <= (qtd_days_elapsed // 7) else None for i in range(1, 14)],
        "Forecast": [random.uniform(50, 70) for _ in range(13)],
        "Target": [65] * 13,
    })
    fig_qtd = go.Figure()
    fig_qtd.add_trace(go.Scatter(
        x=qtd_forecast["Week"],
        y=qtd_forecast["Actual"],
        mode='lines+markers',
        name='Actual',
        line=dict(color='#3b82f6', width=3),
    ))
    fig_qtd.add_trace(go.Scatter(
        x=qtd_forecast["Week"],
        y=qtd_forecast["Forecast"],
        mode='lines',
        name='Forecast',
        line=dict(color='#22c55e', width=2, dash='dash'),
    ))
    fig_qtd.add_trace(go.Scatter(
        x=qtd_forecast["Week"],
        y=qtd_forecast["Target"],
        mode='lines',
        name='Target',
        line=dict(color='#f59e0b', width=2, dash='dot'),
    ))
    fig_qtd.update_layout(
        height=200,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor='rgba(59, 130, 246, 0.2)'),
        yaxis=dict(title="Customers", gridcolor='rgba(59, 130, 246, 0.2)'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=0, r=0, t=0, b=0),
    )
    st.plotly_chart(fig_qtd, use_container_width=True, config={'displayModeBar': False})

with qtd_col2:
    projected_new = int(new_customers_count * (90 / qtd_days_elapsed)) if qtd_days_elapsed > 0 else new_customers_count
    st.metric("Projected New (QTD)", f"{projected_new:,}", delta=f"{projected_new - 60:+.0f} vs target")

with qtd_col3:
    projected_churn_rate = (lost_customers_count / new_customers_count) * 100 if new_customers_count > 0 else 0
    st.metric("Churn Rate", f"{projected_churn_rate:.1f}%", delta=f"{projected_churn_rate - 15:.1f}% vs target")

# Detailed Wins & Losses Table
st.markdown("#### 📊 Detailed Customer Wins & Losses")

# Generate detailed customer wins and losses data
wins_losses_data = []

# Generate wins
win_customers = [
    "TechGlobal Inc", "FinanceHub", "HealthData Systems", "RetailMax", "Manufacturing Plus",
    "EduTech Solutions", "MediaStream", "Logistics Pro", "EnergyGrid Co", "RealEstate Platform",
    "TravelTech", "CloudFirst Corp", "DataVault Inc", "SecureNet Systems", "InnovateLabs",
]
win_products = [
    "AI + Hybrid Cloud", "OpenStack + Managed Cloud", "Elastic Engineering + Security",
    "Multi-Cloud + Data Services", "Hybrid Cloud + AI", "OpenStack + SDDC",
    "Managed Cloud + Security", "AI + Elastic Engineering", "Hybrid Cloud + Spot",
    "Data Services + Multi-Cloud", "Security + OpenStack", "Elastic Engineering + AI",
]
win_reasons = [
    "Competitive pricing and superior support",
    "Strong AI capabilities and innovation",
    "Excellent hybrid cloud migration support",
    "Proven security track record",
    "Flexible pricing model and scalability",
    "Industry-leading uptime and reliability",
    "Comprehensive managed services",
    "Strong technical partnership",
    "Cost-effective solution vs competitors",
    "Advanced data analytics capabilities",
]

for i in range(new_customers_count):
    customer = random.choice(win_customers) if i < len(win_customers) else f"Customer {i+1}"
    product = random.choice(win_products)
    revenue = random.uniform(15, 500)  # $K
    reason = random.choice(win_reasons)
    date = (current_date - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d")
    
    wins_losses_data.append({
        "Customer Name": customer,
        "Product/Services Used": product,
        "Status": "🟢 Won",
        "Revenue Value": f"${revenue:.0f}K",
        "Reason": reason,
        "Date": date,
    })

# Generate losses
loss_customers = [
    "LegacyTech Corp", "OldSystems Inc", "BudgetConstrained LLC", "CompetitorSwitch Co",
    "Downsizing Industries", "MergerExit Corp", "PriceSensitive Ltd", "ServiceIssue Systems",
]
loss_products = [
    "OpenStack", "Managed Cloud", "Hybrid Cloud", "AI Services", "Data Services",
    "Elastic Engineering", "Security", "Multi-Cloud",
]
loss_reasons = [
    "Switched to competitor due to pricing",
    "Budget constraints and cost reduction",
    "Service performance issues",
    "Company merger/acquisition",
    "Insufficient feature set",
    "Better offer from competitor",
    "Contract expiration without renewal",
    "Dissatisfaction with support quality",
]

for i in range(lost_customers_count):
    customer = random.choice(loss_customers) if i < len(loss_customers) else f"Lost Customer {i+1}"
    product = random.choice(loss_products)
    revenue = random.uniform(20, 400)  # $K
    reason = random.choice(loss_reasons)
    date = (current_date - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d")
    
    wins_losses_data.append({
        "Customer Name": customer,
        "Product/Services Used": product,
        "Status": "🔴 Lost",
        "Revenue Value": f"${revenue:.0f}K",
        "Reason": reason,
        "Date": date,
    })

# Sort by date (most recent first)
wins_losses_df = pd.DataFrame(wins_losses_data)
wins_losses_df["Date"] = pd.to_datetime(wins_losses_df["Date"])
wins_losses_df = wins_losses_df.sort_values("Date", ascending=False)
wins_losses_df["Date"] = wins_losses_df["Date"].dt.strftime("%Y-%m-%d")

# Color code the dataframe
def color_status(val):
    if "🟢 Won" in str(val):
        return "background-color: rgba(34, 197, 94, 0.2); color: #22c55e; font-weight: 600;"
    elif "🔴 Lost" in str(val):
        return "background-color: rgba(239, 68, 68, 0.2); color: #ef4444; font-weight: 600;"
    return ""

styled_wins_losses = wins_losses_df.style.applymap(color_status, subset=["Status"])

st.dataframe(
    styled_wins_losses,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Customer Name": st.column_config.TextColumn("Customer", width="medium"),
        "Product/Services Used": st.column_config.TextColumn("Products", width="large"),
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Revenue Value": st.column_config.TextColumn("Revenue", width="small"),
        "Reason": st.column_config.TextColumn("Reason", width="large"),
        "Date": st.column_config.TextColumn("Date", width="small"),
    }
)

# AI Narrative Insight for Customer Acquisition
st.info(
    f"🤖 **AI Insight:** Customer acquisition shows {net_customers:+} net change this quarter. "
    f"New customers: {new_customers_count} ({new_trend} {abs(new_trend_pct):.1f}%), "
    f"Lost customers: {lost_customers_count} ({lost_trend} {abs(lost_trend_pct):.1f}%). "
    f"QTD forecast projects {projected_new} new customers by quarter end. "
    f"Churn rate at {projected_churn_rate:.1f}% {'exceeds' if projected_churn_rate > 15 else 'below'} target. "
    f"Top win reason: Competitive pricing and superior support. Top loss reason: Switched to competitor due to pricing."
)

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# Additional sections (Competition, Product Portfolio, etc.)
# SECTION 4: Competition chart with cars representing competitors (fourth)
st.markdown("#### 🏁 Competition Race Track (Revenue Comparison)")
# Rackspace competitors in cloud services
competitors_data = {
    "Rackspace": {"revenue_q": [2.1, 2.3, 2.2, 2.4], "color": "#ef4444", "symbol": "RXT", "car": "🚗"},
    "AWS": {"revenue_q": [21.4, 23.1, 24.3, 25.8], "color": "#f59e0b", "symbol": "AMZN", "car": "🚙"},
    "Microsoft Azure": {"revenue_q": [28.5, 31.2, 33.1, 35.4], "color": "#3b82f6", "symbol": "MSFT", "car": "🚕"},
    "Google Cloud": {"revenue_q": [8.4, 9.1, 9.8, 10.5], "color": "#22c55e", "symbol": "GOOGL", "car": "🚐"},
    "IBM Cloud": {"revenue_q": [5.2, 5.4, 5.1, 5.3], "color": "#8b5cf6", "symbol": "IBM", "car": "🚓"},
}

# Create competition chart with revenue curves and car symbols
quarters = ["Q4 2023", "Q1 2024", "Q2 2024", "Q3 2024"]
fig_competition = go.Figure()

for company, data in competitors_data.items():
    # Main revenue line
    fig_competition.add_trace(go.Scatter(
        x=quarters,
        y=data["revenue_q"],
        mode='lines',
        name=company,
        line=dict(color=data["color"], width=4),
        hovertemplate=f"<b>{company} {data['car']}</b><br>Quarter: %{{x}}<br>Revenue: $%{{y:.1f}}B<extra></extra>",
        showlegend=True,
    ))
    # Car markers at each quarter point
    fig_competition.add_trace(go.Scatter(
        x=quarters,
        y=data["revenue_q"],
        mode='markers+text',
        name=f"{company} Position",
        marker=dict(
            size=20,
            symbol='diamond',
            color=data["color"],
            line=dict(color='#ffffff', width=2),
        ),
        text=[data["car"]] * len(quarters),
        textposition="middle center",
        textfont=dict(size=16),
        hovertemplate=f"<b>{company}</b><br>Quarter: %{{x}}<br>Revenue: $%{{y:.1f}}B<extra></extra>",
        showlegend=False,
    ))

fig_competition.update_layout(
    title=dict(
        text="<b>🏁 Cloud Services Revenue Race Track (Last 4 Quarters)</b>",
        font=dict(size=20, color="#cbd5e1"),
        x=0.5,
    ),
    xaxis=dict(
        title=dict(text="Quarter", font=dict(color="#94a3b8", size=14)),
        tickfont=dict(color="#cbd5e1", size=12),
        gridcolor='rgba(59, 130, 246, 0.2)',
        showgrid=True,
    ),
    yaxis=dict(
        title=dict(text="Revenue (Billions USD)", font=dict(color="#94a3b8", size=14)),
        tickfont=dict(color="#cbd5e1", size=12),
        gridcolor='rgba(59, 130, 246, 0.2)',
        showgrid=True,
    ),
    height=500,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(
        x=0.02,
        y=0.98,
        bgcolor="rgba(15, 23, 42, 0.9)",
        bordercolor="#1e40af",
        borderwidth=2,
        font=dict(color="#cbd5e1", size=11),
    ),
    hovermode='x unified',
)

st.plotly_chart(fig_competition, use_container_width=True)

# Detailed Competitor Analysis Table
st.markdown("#### 📊 Competitor Revenue Sources & Strategy Analysis")
competitor_strategy_data = [
    {
        "Company": "🚗 Rackspace",
        "Key Revenue Sources": "Managed Cloud Services (60%), Multi-Cloud Solutions (25%), Security & Compliance (15%)",
        "Current Strategy": "Focus on managed services & hybrid cloud; targeting mid-market enterprises; expanding AI/ML services",
        "Market Position": "Niche player in managed cloud services",
        "Q3 2024 Revenue": "$2.4B"
    },
    {
        "Company": "🚙 AWS (Amazon)",
        "Key Revenue Sources": "EC2 Compute (35%), S3 Storage (18%), Database Services (12%), AI/ML Services (15%), Other Services (20%)",
        "Current Strategy": "Dominant market leader; aggressive AI/ML investment (Bedrock, SageMaker); expanding edge computing; enterprise focus",
        "Market Position": "Market leader with 32% cloud market share",
        "Q3 2024 Revenue": "$25.8B"
    },
    {
        "Company": "🚕 Microsoft Azure",
        "Key Revenue Sources": "Azure Infrastructure (40%), Office 365/Teams (30%), Enterprise Software (20%), AI Services (10%)",
        "Current Strategy": "Hybrid cloud leadership; AI integration across stack (Copilot, OpenAI partnership); enterprise lock-in via Office ecosystem",
        "Market Position": "Strong #2 with 23% market share; strong enterprise relationships",
        "Q3 2024 Revenue": "$35.4B"
    },
    {
        "Company": "🚐 Google Cloud",
        "Key Revenue Sources": "GCP Infrastructure (45%), Workspace (25%), AI/ML Platform (20%), Advertising (10%)",
        "Current Strategy": "AI-first approach (Gemini, Vertex AI); targeting data-heavy workloads; expanding multi-cloud partnerships",
        "Market Position": "Growing #3 with 10% market share; strong in AI/ML",
        "Q3 2024 Revenue": "$10.5B"
    },
    {
        "Company": "🚓 IBM Cloud",
        "Key Revenue Sources": "Hybrid Cloud (40%), Consulting Services (30%), Software (20%), Mainframe (10%)",
        "Current Strategy": "Hybrid cloud & AI focus (Watson); enterprise transformation consulting; Red Hat integration",
        "Market Position": "Enterprise-focused; strong in hybrid cloud solutions",
        "Q3 2024 Revenue": "$5.3B"
    }
]

competitor_df = pd.DataFrame(competitor_strategy_data)

# Style the table with custom CSS
st.markdown(
    """
    <style>
    .competitor-table {
        background: linear-gradient(160deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.95));
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid rgba(59, 130, 246, 0.4);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.dataframe(
    competitor_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Company": st.column_config.TextColumn(
            "Company",
            width="small",
            help="Competitor company name"
        ),
        "Key Revenue Sources": st.column_config.TextColumn(
            "Key Revenue Sources",
            width="large",
            help="Primary sources of revenue with percentage breakdown"
        ),
        "Current Strategy": st.column_config.TextColumn(
            "Current Strategy",
            width="large",
            help="Current strategic focus and market approach"
        ),
        "Market Position": st.column_config.TextColumn(
            "Market Position",
            width="medium",
            help="Competitive position in the market"
        ),
        "Q3 2024 Revenue": st.column_config.TextColumn(
            "Q3 2024 Revenue",
            width="small",
            help="Latest quarterly revenue figure"
        ),
    }
)


# Rest of the content
strategy_roadmap = pd.DataFrame(
    [
        {
            "Theme": "AI Acceleration",
            "Target KPI": "LLM-driven pipeline +30%",
            "Time Horizon": "Q1-Q2",
            "Milestone": "GenAI copilots in top 3 business units",
            "Checkpoint": "Data readiness audit & safety board sign-off",
        },
        {
            "Theme": "Cloud Efficiency",
            "Target KPI": "Unit cost ↓ 18%",
            "Time Horizon": "Q2-Q3",
            "Milestone": "Cloud orchestration + auto-scaling live in prod",
            "Checkpoint": "FinOps dashboard validation",
        },
        {
            "Theme": "Market Expansion",
            "Target KPI": "2 new regions live",
            "Time Horizon": "Q3",
            "Milestone": "Localization + compliance toolkit",
            "Checkpoint": "Board tollgate & customer beta",
        },
        {
            "Theme": "Ops Resilience",
            "Target KPI": "MTTR < 20m",
            "Time Horizon": "Q1-Q4",
            "Milestone": "Autopilot incident triage",
            "Checkpoint": "Red-team drills vs. Storm mode",
        },
    ]
)
st.dataframe(strategy_roadmap, use_container_width=True, hide_index=True)

st.caption("© 2025 CEO driver DASHBOARD — Built for adaptive leadership. Made with ❤️ by Dzoannguyentran@gmail.com")

# Market News & Social Feed (Full Width - No Separate Columns)
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("#### 📰 Market News & Social Feed")

# Full width layout - Twitter/X and RSS feeds displayed together
st.markdown("**🐦 Twitter/X Market News**")

# Mockup Twitter feed data
twitter_feeds = [
    {
        "author": "@MarketWatch",
        "content": "Cloud services sector shows strong Q3 growth with Rackspace and competitors expanding market share. #CloudServices #TechStocks",
        "time": "2 hours ago",
        "likes": "1.2K",
        "retweets": "340",
        "date": (current_date - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "author": "@TechCrunch",
        "content": "Rackspace announces new AI-powered cloud management platform. Industry analysts predict 15% revenue boost. #AI #CloudTech",
        "time": "5 hours ago",
        "likes": "2.8K",
        "retweets": "892",
        "date": (current_date - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "author": "@BloombergTech",
        "content": "Cloud infrastructure spending reaches $200B annually. AWS, Azure, and Google Cloud lead, with Rackspace gaining in managed services. #CloudInfrastructure",
        "time": "8 hours ago",
        "likes": "5.1K",
        "retweets": "1.2K",
        "date": (current_date - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "author": "@ForbesTech",
        "content": "Enterprise cloud migration accelerates. Rackspace positioned well in hybrid cloud solutions market. Revenue outlook positive. #EnterpriseCloud",
        "time": "12 hours ago",
        "likes": "890",
        "retweets": "234",
        "date": (current_date - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M"),
    },
    {
        "author": "@WSJTech",
        "content": "Q3 earnings season: Cloud services companies report mixed results. Rackspace shows resilience in competitive market. #Earnings #CloudServices",
        "time": "1 day ago",
        "likes": "3.4K",
        "retweets": "987",
        "date": (current_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
    },
]

for feed in twitter_feeds:
    st.markdown(
        f"""
        <div style="background: rgba(30, 41, 59, 0.5); padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid #1da1f2;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                <strong style="color: #1da1f2;">{feed['author']}</strong>
                <span style="color: #64748b; font-size: 0.85em;">{feed['time']}</span>
            </div>
            <div style="color: #f8fafc; margin-bottom: 8px;">{feed['content']}</div>
            <div style="display: flex; gap: 20px; color: #94a3b8; font-size: 0.85em;">
                <span>❤️ {feed['likes']}</span>
                <span>🔄 {feed['retweets']}</span>
                <span>📅 {feed['date']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("**📡 RSS Market Feeds**")

# Mockup RSS feed data
rss_feeds = [
    {
        "source": "Reuters - Technology",
        "title": "Cloud Services Market Grows 18% YoY",
        "summary": "Enterprise cloud adoption drives revenue growth across major providers.",
        "date": (current_date - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"),
        "link": "https://reuters.com/tech/cloud-growth",
    },
    {
        "source": "TechCrunch RSS",
        "title": "Rackspace Expands AI Cloud Services",
        "summary": "New AI-powered platform targets enterprise customers seeking automation.",
        "date": (current_date - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M"),
        "link": "https://techcrunch.com/rackspace-ai",
    },
    {
        "source": "MarketWatch - Cloud Sector",
        "title": "Q3 Cloud Infrastructure Spending Analysis",
        "summary": "Managed cloud services show strongest growth trajectory.",
        "date": (current_date - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M"),
        "link": "https://marketwatch.com/cloud-q3",
    },
    {
        "source": "Bloomberg Technology",
        "title": "Competitive Landscape: Cloud Services 2024",
        "summary": "Market leaders maintain dominance while niche players gain traction.",
        "date": (current_date - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        "link": "https://bloomberg.com/tech/cloud-2024",
    },
]

for feed in rss_feeds:
    st.markdown(
        f"""
        <div style="background: rgba(30, 41, 59, 0.4); padding: 10px; border-radius: 6px; margin-bottom: 8px;">
            <div style="color: #60a5fa; font-size: 0.9em; margin-bottom: 4px;">📰 {feed['source']}</div>
            <strong style="color: #f8fafc;">{feed['title']}</strong><br>
            <span style="color: #94a3b8; font-size: 0.85em;">{feed['summary']}</span><br>
            <span style="color: #64748b; font-size: 0.8em;">📅 {feed['date']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
st.markdown(f"*Generated: {current_date.strftime('%B %d, %Y')}*")

st.markdown("---")

st.markdown("### 🔌 Data Feed Lanes")

st.markdown(
    """
    <style>
    /* ============================================================================
       CLEAN LANE LAYOUT - Pure Grid, No Empty Boxes, Logo + Description Only
       ============================================================================ */
    
    /* Main 3-column grid layout - pure CSS grid, no flexbox hacks */
    div[data-testid="column"] {
        display: grid !important;
        grid-template-columns: 1fr !important;
        gap: 0 !important;
        align-items: start !important;
    }
    
    /* Lane container wrapper - minimal, no padding hacks */
    .lane-wrapper {
        width: 100%;
        display: grid;
        grid-template-rows: auto auto auto;
        gap: 1.5rem;
        align-items: start;
    }
    
    /* Lane logo container - fixed 140px height, centered, no extra spacing */
    .lane-image-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        height: 140px;
        padding: 1rem;
        background: rgba(15, 23, 42, 0.2);
        border-radius: 12px;
        border: 1px solid rgba(59, 130, 246, 0.2);
        margin-bottom: 0;
    }
    .lane-image-container img {
        width: auto !important;
        height: 100px !important;
        max-width: 100%;
        object-fit: contain;
        border-radius: 8px;
        margin: 0 auto;
        display: block;
    }
    .lane-image-container .stInfo {
        width: 100%;
        text-align: center;
        margin: 0;
    }
    
    /* Lane description box - equal height using CSS, no spacer divs */
    .lane-description {
        background: rgba(15, 23, 42, 0.3);
        border-left: 4px solid #3b82f6;
        padding: 1.25rem;
        border-radius: 8px;
        margin-top: 0;
        margin-bottom: 0;
        min-height: 280px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        line-height: 1.6;
    }
    .lane-description strong {
        color: #60a5fa;
        display: block;
        margin-bottom: 0.5rem;
        margin-top: 0.75rem;
    }
    .lane-description strong:first-child {
        margin-top: 0;
    }
    .lane-description br {
        line-height: 1.8;
    }
    
    /* Feed control panel - dark theme styling */
    .feed-control-panel {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.98));
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 1.5rem;
        margin-bottom: 0;
        width: 100%;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    .feed-control-panel h4 {
        color: #60a5fa;
        border-bottom: 2px solid rgba(59, 130, 246, 0.3);
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
        margin-top: 0;
        font-size: 1rem;
        letter-spacing: 0.1rem;
        text-transform: uppercase;
    }
    .feed-control-panel label, .feed-control-panel p, .feed-control-panel span {
        color: #cbd5e1 !important;
    }
    .feed-control-panel div[data-baseweb="select"] > div {
        background: rgba(15, 23, 42, 0.6) !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
    }
    .feed-control-panel textarea, .feed-control-panel input {
        background: rgba(15, 23, 42, 0.6) !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
    }
    .feed-control-panel .stFileUploader label {
        border: 1px dashed rgba(59, 130, 246, 0.3) !important;
        background: rgba(15, 23, 42, 0.4) !important;
    }
    .feed-control-panel .stTextInput,
    .feed-control-panel .stTextArea,
    .feed-control-panel .stSelectbox,
    .feed-control-panel .stSlider,
    .feed-control-panel .stToggle {
        margin-bottom: 1rem;
    }
    .feed-control-panel .stMetric {
        background: rgba(15, 23, 42, 0.4) !important;
        border: 1px solid rgba(59, 130, 246, 0.2) !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
    }
    .feed-control-panel .stButton button {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3) !important;
    }
    .feed-control-panel .stButton button:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
        box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4) !important;
    }
    
    /* Upload icon button styling - standalone icon without white box */
    div[data-testid="stButton"] button[kind="secondary"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stButton"] button:has-text("📤"),
    div[data-testid="stButton"] button[kind="secondary"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0.25rem 0.5rem !important;
        min-width: auto !important;
    }
    div[data-testid="stButton"]:has(button[kind="secondary"]) {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    
    /* Responsive design - maintain alignment on all screen sizes */
    @media (max-width: 768px) {
        .lane-description {
            min-height: auto;
        }
        div[data-testid="column"] {
            grid-template-columns: 1fr !important;
        }
    }
    </style>
    <script>
    (function() {
        function styleSaveButtons() {
            const buttons = document.querySelectorAll('div[data-testid="stButton"] button');
            buttons.forEach(btn => {
                const text = btn.textContent || btn.innerText;
                if (text.includes('Save API Config') || 
                    text.includes('Save BI Connector Config') || 
                    (text.includes('Save') && text.includes('Config')) ||
                    text.includes('Connect') ||
                    text.includes('Test Connection')) {
                    btn.style.background = 'linear-gradient(135deg, #00d4ff, #0099cc)';
                    btn.style.color = 'white';
                    btn.style.border = 'none';
                    btn.style.fontWeight = '600';
                    btn.style.boxShadow = '0 0 15px rgba(0, 212, 255, 0.5)';
                    btn.addEventListener('mouseenter', function() {
                        this.style.background = 'linear-gradient(135deg, #00b8e6, #0088bb)';
                        this.style.boxShadow = '0 0 20px rgba(0, 212, 255, 0.7)';
                    });
                    btn.addEventListener('mouseleave', function() {
                        this.style.background = 'linear-gradient(135deg, #00d4ff, #0099cc)';
                        this.style.boxShadow = '0 0 15px rgba(0, 212, 255, 0.5)';
                    });
                }
            });
        }
        // Run on page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', styleSaveButtons);
        } else {
            styleSaveButtons();
        }
        // Also run after Streamlit updates
        const observer = new MutationObserver(styleSaveButtons);
        observer.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    <script>
    // Additional script to style upload icon buttons
    (function() {
        function styleUploadButtons() {
            const buttons = document.querySelectorAll('div[data-testid="stButton"] button');
            buttons.forEach(btn => {
                const text = btn.textContent || btn.innerText;
                if (text.includes('📤') || btn.getAttribute('title')?.includes('Upload')) {
                    btn.style.background = 'transparent';
                    btn.style.border = 'none';
                    btn.style.boxShadow = 'none';
                    btn.style.padding = '0.25rem 0.5rem';
                    btn.style.minWidth = 'auto';
                    // Remove any parent container backgrounds
                    const parent = btn.closest('div[data-testid="stButton"]');
                    if (parent) {
                        parent.style.background = 'transparent';
                        parent.style.border = 'none';
                        parent.style.padding = '0';
                    }
                }
            });
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', styleUploadButtons);
        } else {
            styleUploadButtons();
        }
        const observer = new MutationObserver(styleUploadButtons);
        observer.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# Organize 3 lanes in 3 columns with perfect alignment
lane_col1, lane_col2, lane_col3 = st.columns(3, gap="large")

# Lane 1 — Direct API Feeds
with lane_col1:
    st.markdown('<div class="lane-wrapper">', unsafe_allow_html=True)
    st.markdown("#### 🛣️ Lane 1 — Direct API Feeds")
    
    # Lane 1 Logo with upload icon button
    if 'show_lane1_upload' not in st.session_state:
        st.session_state['show_lane1_upload'] = False
    
    lane1_container = st.container()
    with lane1_container:
        lane1_col1, lane1_col2 = st.columns([20, 1])
        with lane1_col1:
            st.markdown('<div class="lane-image-container">', unsafe_allow_html=True)
            if LANE1_LOGO_PATH.exists():
                st.image(str(LANE1_LOGO_PATH), use_container_width=False, caption="Lane 1 logo")
            else:
                st.info("No logo")
            st.markdown('</div>', unsafe_allow_html=True)
        with lane1_col2:
            if st.button("📤", key="lane1_upload_btn", help="Upload Lane 1 logo"):
                st.session_state['show_lane1_upload'] = not st.session_state.get('show_lane1_upload', False)
    
    if st.session_state['show_lane1_upload']:
        lane1_logo_file = st.file_uploader(
            "Upload Lane 1 logo", 
            type=["png", "jpg", "jpeg", "gif"], 
            key="lane1_logo_upload",
            help="Small logo for Lane 1 (saved per session)"
        )
        if lane1_logo_file:
            LANE1_LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LANE1_LOGO_PATH, "wb") as handle:
                handle.write(lane1_logo_file.getbuffer())
            st.session_state['lane1_logo_uploaded'] = True
            st.session_state['show_lane1_upload'] = False
            st.success("✅ Lane 1 logo saved")
            st.rerun()
    
    st.markdown(
        """
        <div class="lane-description">
        <strong>Best for:</strong> cash flow, sales pipelines, customer KPIs, product usage, market/competitor scans, AI-inferred KPIs, route/traffic analogs.<br>
        <strong>Why:</strong> real-time (< minutes), zero human touch, enables true autopilot correlations.<br>
        <strong>Examples:</strong> ERP (SAP/Netsuite) `/finance`, CRM (Salesforce/HubSpot) `/customers`, Jira/Linear `/product`, HR `/people`, Stripe/Adyen `/billing`, internal ops `/ops`, competitor scrapers `/market`.<br>
        <strong>Result:</strong> 🚀 Primary fuel line powering the cockpit.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="feed-control-panel">', unsafe_allow_html=True)
    st.markdown("#### 🔧 Lane 1 Input Panel")
    api_url = st.text_input(
        "API Endpoint URL",
        value=st.session_state.get("lane_api_url", "https://api.internal/cockpit"),
        key="lane1_api_url",
    )
    api_token = st.text_input("Bearer / API Token", type="password", key="lane1_api_token")
    
    # Swagger/OpenAPI Documentation Link
    swagger_url = st.text_input(
        "📚 Swagger/OpenAPI Docs URL",
        value=st.session_state.get("lane_swagger_url", "https://api.internal/swagger-ui"),
        key="lane1_swagger_url",
        help="Link to Swagger UI or OpenAPI documentation to explore available endpoints",
    )
    if swagger_url:
        st.session_state["lane_swagger_url"] = swagger_url
        # Create a clickable link that opens in new tab
        st.markdown(
            f"""
            <div style="margin-top: 0.5rem; margin-bottom: 1rem;">
                <a href="{swagger_url}" target="_blank" rel="noopener noreferrer" 
                   style="display: inline-flex; align-items: center; gap: 0.5rem;
                          color: #60a5fa; text-decoration: none; 
                          padding: 0.5rem 1rem; 
                          border: 1px solid rgba(59, 130, 246, 0.3);
                          border-radius: 6px;
                          background: rgba(59, 130, 246, 0.1);
                          transition: all 0.2s;">
                    <span>🔗 Open Swagger Docs</span>
                    <span style="font-size: 0.8em;">↗</span>
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    api_payload = st.text_area(
        "Sample Payload / Query", 
        value='{"company":"Amazon","metric":"cash_flow"}',
        key="lane1_api_payload",
    )
    save_btn = st.button("Save API Config", key="save_lane1_api")
    if save_btn:
        st.session_state["lane_api_url"] = api_url
        if swagger_url:
            st.session_state["lane_swagger_url"] = swagger_url
        st.success("✅ Lane 1 API configuration saved — ready for live autopilot feeds.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Lane 2 — BI System Connectors
with lane_col2:
    st.markdown('<div class="lane-wrapper">', unsafe_allow_html=True)
    st.markdown("#### 🛣️ Lane 2 — BI System Connectors")
    
    # Lane 2 Logo with upload icon button
    if 'show_lane2_upload' not in st.session_state:
        st.session_state['show_lane2_upload'] = False
    
    lane2_container = st.container()
    with lane2_container:
        lane2_col1, lane2_col2 = st.columns([20, 1])
        with lane2_col1:
            st.markdown('<div class="lane-image-container">', unsafe_allow_html=True)
            if LANE2_LOGO_PATH.exists():
                st.image(str(LANE2_LOGO_PATH), use_container_width=False, caption="Lane 2 logo")
            else:
                st.info("No logo")
            st.markdown('</div>', unsafe_allow_html=True)
        with lane2_col2:
            if st.button("📤", key="lane2_upload_btn", help="Upload Lane 2 logo"):
                st.session_state['show_lane2_upload'] = not st.session_state['show_lane2_upload']
    
    if st.session_state['show_lane2_upload']:
        lane2_logo_file = st.file_uploader(
            "Upload Lane 2 logo", 
            type=["png", "jpg", "jpeg", "gif"], 
            key="lane2_logo_upload",
            help="Small logo for Lane 2 (saved per session)"
        )
        if lane2_logo_file:
            LANE2_LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LANE2_LOGO_PATH, "wb") as handle:
                handle.write(lane2_logo_file.getbuffer())
            st.session_state['lane2_logo_uploaded'] = True
            st.session_state['show_lane2_upload'] = False
            st.success("✅ Lane 2 logo saved")
            st.rerun()
    
    st.markdown(
        """
        <div class="lane-description">
        <strong>Best for:</strong> strategic KPIs, long trendlines, planning/forecasting, TAM/SAM/SOM, segment drilldowns.<br>
        <strong>Why:</strong> BI holds the "long memory" to train autopilot and keep the destination map accurate.<br>
        <strong>Examples:</strong> PowerBI REST, Tableau Extract, Looker, BigQuery/Snowflake/Redshift connectors, Databricks delta feeds.<br>
        <strong>Result:</strong> 📊 Gives the CEO map historical context and confidence intervals.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="feed-control-panel">', unsafe_allow_html=True)
    st.markdown("#### 🔧 Lane 2 Input Panel")
    bi_system = st.selectbox(
        "BI Platform",
        ["PowerBI", "Tableau", "Looker", "BigQuery", "Snowflake", "Redshift", "Databricks"],
        key="lane2_bi_platform",
    )
    bi_dataset = st.text_input("Dataset / View", value="executive_rollup.share", key="lane2_bi_dataset")
    refresh = st.slider("Refresh cadence (minutes)", 15, 720, 120, step=15, key="lane2_refresh")
    st.caption(f"Connector `{bi_system}` scheduled every {refresh} minutes for long-memory KPIs.")
    save_bi_btn = st.button("Save BI Connector Config", key="save_lane2_bi")
    if save_bi_btn:
        st.success(f"✅ Lane 2 BI connector configured — {bi_system} dataset will refresh every {refresh} minutes.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Lane 3 — File Uploads
with lane_col3:
    st.markdown('<div class="lane-wrapper">', unsafe_allow_html=True)
    st.markdown("#### 🛣️ Lane 3 — File Uploads")
    
    # Lane 3 Logo with upload icon button
    if 'show_lane3_upload' not in st.session_state:
        st.session_state['show_lane3_upload'] = False
    
    lane3_container = st.container()
    with lane3_container:
        lane3_col1, lane3_col2 = st.columns([20, 1])
        with lane3_col1:
            st.markdown('<div class="lane-image-container">', unsafe_allow_html=True)
            if LANE3_LOGO_PATH.exists():
                st.image(str(LANE3_LOGO_PATH), use_container_width=False, caption="Lane 3 logo")
            else:
                st.info("No logo")
            st.markdown('</div>', unsafe_allow_html=True)
        with lane3_col2:
            if st.button("📤", key="lane3_upload_btn", help="Upload Lane 3 logo"):
                st.session_state['show_lane3_upload'] = not st.session_state['show_lane3_upload']
    
    if st.session_state['show_lane3_upload']:
        lane3_logo_file = st.file_uploader(
            "Upload Lane 3 logo", 
            type=["png", "jpg", "jpeg", "gif"], 
            key="lane3_logo_upload",
            help="Small logo for Lane 3 (saved per session)"
        )
        if lane3_logo_file:
            LANE3_LOGO_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LANE3_LOGO_PATH, "wb") as handle:
                handle.write(lane3_logo_file.getbuffer())
            st.session_state['lane3_logo_uploaded'] = True
            st.session_state['show_lane3_upload'] = False
            st.success("✅ Lane 3 logo saved")
            st.rerun()
    
    st.markdown(
        """
        <div class="lane-description">
        <strong>Best for:</strong> new market CSVs, consultant decks, one-shot datasets, market research, investment memos, board packs.<br>
        <strong>Why:</strong> leaders constantly ingest external files before APIs exist; this lane keeps the cockpit flexible.<br>
        <strong>Formats:</strong> CSV/Excel, PDF (OCR), JSON, images (AI extraction).<br>
        <strong>Result:</strong> 🧳 Rapid ingestion channel until formal integrations land.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="feed-control-panel">', unsafe_allow_html=True)
    st.markdown("#### 🔧 Lane 3 Input Panel")
    feed_upload = st.file_uploader(
        "Upload supplemental data file",
        type=["csv", "xlsx", "xls", "json", "pdf"],
        key="lane3_file_upload",
        help="Drop market decks, consultant data, or emergency feeds.",
    )
    if feed_upload:
        st.success(f"✅ {feed_upload.name} staged for ingestion via Lane 3.")
    file_schema = st.text_area(
        "Column mapping (CSV/Excel)", 
        value="Quarter,Revenue,EBITDA,Region",
        key="lane3_file_schema",
    )
    apply_ocr = st.toggle("Apply OCR for PDF/Image uploads", value=True, key="lane3_apply_ocr")
    st.caption("Use this panel to align ad-hoc files with cockpit schema before ingestion.")
    if st.button("Process File", key="process_lane3_file"):
        if feed_upload:
            st.success(f"✅ File processed and mapped — ready for cockpit ingestion.")
        else:
            st.warning("⚠️ Please upload a file first.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
