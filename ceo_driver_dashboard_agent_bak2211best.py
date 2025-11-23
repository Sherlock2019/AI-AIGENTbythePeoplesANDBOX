#!/usr/bin/env python3
"""🚗 CEO driver DASHBOARD — AI-powered business cockpit."""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from pathlib import Path
import json
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
        height=400,  # Increased height to show whole gauge
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
        y=0.02,
        text=f"<b>{direction_text}</b>",
        showarrow=False,
        font=dict(size=18, color=direction_color, family="Arial"),
        xref="paper",
        yref="paper",
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
        margin=dict(l=60, r=60, t=120, b=120),
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
        f"Continue on {destination['name']} route for {int(metrics['eta_days'])} days.",
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

# Preview mode enabled - Coming Soon check removed
# st.warning("🚧 CEO DRIVER SEAT is flagged **Coming Soon**. Preview is disabled while we finalize verification.")
# st.info("Thanks for your patience. Ping the platform team to request early access.")
# st.stop()
LOGO_UPLOAD_PATH = Path(".cache/ceo_assets/driver_logo.png")
logo_file = st.file_uploader(
    "Upload a dashboard logo", type=["png", "jpg", "jpeg", "gif"], key="logo_upload", help="Logo appears across sessions until you replace it."
)
if logo_file:
    LOGO_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOGO_UPLOAD_PATH, "wb") as handle:
        handle.write(logo_file.getbuffer())
    st.success("New logo saved.")

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

# SECTION 1: Logo full width (second)
st.markdown("#### 🪪 Cockpit Logo")
if LOGO_UPLOAD_PATH.exists():
    st.image(str(LOGO_UPLOAD_PATH), use_container_width=True, caption="Current cockpit logo")
else:
    st.info("Upload your company emblem to brand the CEO driver DASHBOARD.")

# SECTION 6: KPI Gauges and Drive Mode section (moved to be right after logo)
st.markdown("#### 🕹️ Drive Mode & KPI Gauges")
gear_col, gauge_col = st.columns([0.35, 1.65])
with gear_col:
    st.markdown(
        """
        <style>
        .gearbox-stack {
            background: linear-gradient(160deg,#020617,#0b1220 60%,#020617);
            border: 1px solid #1e293b;
            border-radius: 20px;
            padding: 1.4rem;
            box-shadow: inset 0 0 25px rgba(15,23,42,0.85), 0 12px 35px rgba(2,6,23,0.85);
        }
        .gearbox-stack h4 {
            margin: 0 0 1rem 0;
            font-size: 1.2rem;
            letter-spacing: 0.25rem;
            text-transform: uppercase;
            color: #67e8f9;
            text-align:center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="gearbox-stack"><h4>AUTO GEAR</h4></div>', unsafe_allow_html=True)
    mode = st.radio(
        "Drive mode",
        ["Eco", "Sport", "Autopilot", "Storm", "Exploration", "Pit-Stop"],
        index=2,
        key="gear_mode",
        label_visibility="collapsed",
    )

with gauge_col:
    g_left, g_center, g_right = st.columns(3)
    with g_left:
        st.plotly_chart(
            _plot_gauge(metrics["rev_speed"], "Revenue Speed", 0, 150, " mph"),
            use_container_width=True,
        )
    with g_center:
        st.plotly_chart(
            _plot_gauge(metrics["cash_months"], "Cash Fuel (Flow $M)", 0, 50, " $M"),
            use_container_width=True,
        )
    with g_right:
        st.plotly_chart(
            _plot_gauge(metrics["ops_heat"], "Engine Status (Ops)", 0, 120, " score"),
            use_container_width=True,
        )

mode_bio = {
    "Eco": "Cash preservation: efficiency first, gentle acceleration.",
    "Sport": "Growth push: aggressive GTM, bold spend.",
    "Autopilot": "Routine AI control: decisions optimized automatically.",
    "Storm": "Crisis response: risks and cash overrides take precedence.",
    "Exploration": "Market expansion: scenario labs + sandbox budgets.",
    "Pit-Stop": "Maintenance focus: ops cooldown, team recharge.",
}

# KPI Compass Gauge right after logo
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
        min(100, (metrics["rev_speed"] / 150) * 100),
        min(100, (metrics["cash_months"] / 50) * 100),
        min(100, (metrics["traffic"] / 100) * 100),
        min(100, (metrics["nps"] / 10) * 100),
        min(100, (100 - metrics["ops_heat"])),
        min(100, (metrics["rev_speed"] * 0.6)),
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

# KPI Compass Gauges section (moved here to be under Revenue Target Compass)
st.markdown("#### 🧭 KPI Compass Gauges")
target_rev = 150.0  # $M run-rate goal over last 3 quarters
target_balance = 1.8e9  # Desired cash-minus-debt cushion
balance_gap = (financials.get("cash") or 0) - (financials.get("debt") or 0)
ops_target = 80.0

rev_deviation = ((metrics["rev_speed"] - target_rev) / target_rev) * 100
balance_deviation = (
    ((balance_gap or 0) - target_balance) / target_balance * 100 if target_balance else 0
)
ops_deviation = ((metrics["ops_heat"] - ops_target) / ops_target) * 100
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

# Customer Acquisition vs Churn Table
st.markdown("#### 👥 Customer Acquisition & Churn Analysis")
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

customer_data = pd.DataFrame([
    {
        "Metric": "🟢 New Customers",
        "Count": f"{new_customers_count:,}",
        "Revenue Value": format_currency(new_customer_revenue * 1000),  # Convert to actual dollars
        "Status": "Growth"
    },
    {
        "Metric": "🔴 Lost Customers",
        "Count": f"{lost_customers_count:,}",
        "Revenue Value": format_currency(lost_customer_revenue * 1000),
        "Status": "Churn"
    },
    {
        "Metric": "📊 Net Change",
        "Count": f"{net_customers:+,}",
        "Revenue Value": format_currency(net_revenue * 1000),
        "Status": "Net" if net_customers > 0 else "Decline"
    }
])

# Style the dataframe with custom CSS
st.markdown(
    """
    <style>
    .customer-table {
        background: linear-gradient(160deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.9));
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.dataframe(
    customer_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Metric": st.column_config.TextColumn("Metric", width="medium"),
        "Count": st.column_config.TextColumn("Count", width="small"),
        "Revenue Value": st.column_config.TextColumn("Revenue Value", width="medium"),
        "Status": st.column_config.TextColumn("Status", width="small"),
    }
)

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

# SECTION 7: AI Suggest Direction section with mockup data (fifth)
st.markdown("#### 🤖 AI Suggest Direction")
ai_suggest_col1, ai_suggest_col2 = st.columns([0.6, 0.4])

# Mockup data with sources and dates (current_date already defined above)
mockup_data = [
    {
        "metric": "Revenue Growth Rate",
        "value": f"{revenue_deviation_pct:.1f}%",
        "target": "0.0%",
        "status": "Below Target" if revenue_deviation_pct < 0 else "Above Target",
        "source": "Internal Finance Dashboard",
        "date": (current_date - timedelta(days=1)).strftime("%Y-%m-%d"),
        "trend": "↓" if revenue_deviation_pct < 0 else "↑",
    },
    {
        "metric": "Sales Pipeline Value",
        "value": "$12.4M",
        "target": "$15.0M",
        "status": "Below Target",
        "source": "Salesforce CRM",
        "date": (current_date - timedelta(days=0)).strftime("%Y-%m-%d"),
        "trend": "↓",
    },
    {
        "metric": "Customer Acquisition Cost",
        "value": "$2,450",
        "target": "$2,000",
        "status": "Above Target",
        "source": "Marketing Analytics",
        "date": (current_date - timedelta(days=2)).strftime("%Y-%m-%d"),
        "trend": "↑",
    },
    {
        "metric": "Monthly Recurring Revenue",
        "value": "$8.2M",
        "target": "$9.0M",
        "status": "Below Target",
        "source": "Stripe Billing",
        "date": (current_date - timedelta(days=1)).strftime("%Y-%m-%d"),
        "trend": "↓",
    },
]

with ai_suggest_col1:
    st.markdown("**AI Analysis of Current Metrics:**")
    st.markdown(f"*Last updated: {current_date.strftime('%B %d, %Y at %I:%M %p')}*")
    for item in mockup_data:
        status_color = "#ef4444" if item["status"] == "Below Target" else "#22c55e"
        st.markdown(
            f"""
            <div style="background: rgba(30, 41, 59, 0.5); padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid {status_color};">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                    <strong style="color: #f8fafc;">{item['metric']}</strong>
                    <span style="color: {status_color}; font-weight: bold;">{item['status']}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <span style="color: #cbd5e1;">Value: <strong>{item['value']}</strong></span>
                    <span style="color: #94a3b8;">Target: {item['target']}</span>
                </div>
                <div style="display: flex; justify-content: space-between; color: #64748b; font-size: 0.85em;">
                    <span>📊 {item['source']}</span>
                    <span>📅 {item['date']} {item['trend']}</span>
                </div>
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

with ai_suggest_col2:
    st.markdown("**Recommended Actions to Meet Revenue Target:**")
    st.markdown(f"*Generated: {current_date.strftime('%B %d, %Y')}*")
    actions_data = [
        {
            "action": "Accelerate Enterprise Sales",
            "priority": "High",
            "impact": "Revenue +$3.2M",
            "timeline": "30 days",
            "source": "Sales Strategy Team",
        },
        {
            "action": "Launch Referral Program",
            "priority": "Medium",
            "impact": "Pipeline +$1.8M",
            "timeline": "45 days",
            "source": "Marketing Department",
        },
        {
            "action": "Optimize Pricing Tiers",
            "priority": "High",
            "impact": "MRR +$1.5M",
            "timeline": "60 days",
            "source": "Product & Finance",
        },
        {
            "action": "Reduce Customer Churn",
            "priority": "Medium",
            "impact": "Retention +8%",
            "timeline": "90 days",
            "source": "Customer Success",
        },
    ]
    for action in actions_data:
        priority_color = "#ef4444" if action["priority"] == "High" else "#f59e0b"
        st.markdown(
            f"""
            <div style="background: rgba(30, 41, 59, 0.4); padding: 10px; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid {priority_color};">
                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                    <strong style="color: #f8fafc;">{action['action']}</strong>
                    <span style="color: {priority_color}; font-size: 0.85em;">{action['priority']}</span>
                </div>
                <div style="color: #cbd5e1; margin-bottom: 4px;">{action['impact']} | ⏱️ {action['timeline']}</div>
                <div style="color: #64748b; font-size: 0.85em;">📋 {action['source']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Product Portfolio Analysis Table
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

st.markdown(
    """
    <style>
    .product-portfolio-table {
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

# SECTION 3: RSS Feed box for market news (Twitter/X and market feeds) (sixth)
st.markdown("#### 📰 Market News & Social Feed")
rss_col1, rss_col2 = st.columns([0.6, 0.4])

with rss_col1:
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

with rss_col2:
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
    st.markdown("")
    
    actions_data = [
        {
            "action": "📈 Accelerate Sales Pipeline",
            "priority": "High",
            "impact": "Expected +$2.6M pipeline value",
            "timeline": "30 days",
            "source": "Sales Operations Analysis",
        },
        {
            "action": "🎯 Focus on High-Value Deals",
            "priority": "High",
            "impact": "Improve win rate by 15%",
            "timeline": "45 days",
            "source": "Sales Performance Dashboard",
        },
        {
            "action": "🤝 Expand Partner Channels",
            "priority": "Medium",
            "impact": "Add $800K pipeline via partners",
            "timeline": "60 days",
            "source": "Partner Program Metrics",
        },
        {
            "action": "💡 Launch New Product Features",
            "priority": "Medium",
            "impact": "Increase upsell conversion 20%",
            "timeline": "90 days",
            "source": "Product Analytics",
        },
        {
            "action": "📢 Optimize Marketing Spend",
            "priority": "High",
            "impact": "Reduce CAC by $140 to target",
            "timeline": "21 days",
            "source": "Marketing Attribution Report",
        },
        {
            "action": "🔄 Customer Retention Program",
            "priority": "Critical",
            "impact": "Reduce churn to <2.5% target",
            "timeline": "45 days",
            "source": "Customer Success Platform",
        },
    ]
    
    for action_data in actions_data:
        priority_color = "#ef4444" if action_data["priority"] == "Critical" else "#f59e0b" if action_data["priority"] == "High" else "#3b82f6"
        st.markdown(
            f"""
            <div style="background: rgba(30, 41, 59, 0.4); padding: 10px; border-radius: 6px; margin-bottom: 8px;">
                <strong>{action_data['action']}</strong><br>
                <span style="color: {priority_color}; font-size: 0.85em;">Priority: {action_data['priority']}</span> | 
                <span style="color: #94a3b8; font-size: 0.85em;">Timeline: {action_data['timeline']}</span><br>
                <span style="color: #cbd5e1; font-size: 0.9em;">{action_data['impact']}</span><br>
                <span style="color: #64748b; font-size: 0.8em;">📊 {action_data['source']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# Rest of the content
st.markdown("#### 📈 Live Market Pulse")
_render_stock_widget(company_choice, snapshot.get("symbol"))

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

st.markdown("#### 🧭 KPI Compass")
target_rev = 150.0  # $M run-rate goal over last 3 quarters
target_balance = 1.8e9  # Desired cash-minus-debt cushion
balance_gap = (financials.get("cash") or 0) - (financials.get("debt") or 0)

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
        "Actual": f"${metrics['rev_speed']:.1f}M",
        "Target": f"${target_rev:.0f}M",
        "Status": _direction_label(metrics["rev_speed"] / target_rev),
    },
    {
        "Axis": "Balance Sheet",
        "Actual": format_currency(balance_gap),
        "Target": format_currency(target_balance),
        "Status": _direction_label(balance_gap / target_balance if target_balance else 0),
    },
]
st.dataframe(pd.DataFrame(compass_rows), use_container_width=True, hide_index=True)

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
st.dataframe(_mock_reviews(company_choice), use_container_width=True, hide_index=True)

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

st.caption("© 2025 CEO driver DASHBOARD — Built for adaptive leadership.")

st.markdown("### 🔌 Data Feed Lanes")


st.markdown(
    """
    <style>
    .feed-control-panel {
        background: radial-gradient(circle at top, #050b1a, #020617 55%, #01040b);
        border: 1px solid #1f2937;
        border-radius: 22px;
        padding: 28px;
        box-shadow: 0 20px 55px rgba(1, 8, 20, 0.85);
        margin-bottom: 2rem;
    }
    .feed-control-panel h4 {
        color: #67e8f9;
        letter-spacing: 0.2rem;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }
    .feed-control-panel label, .feed-control-panel p, .feed-control-panel span {
        color: #cbd5f5 !important;
    }
    .feed-control-panel div[data-baseweb="select"] > div {
        background: #0f172a !important;
        color: #e2e8f0 !important;
        border-radius: 10px !important;
        border: 1px solid #1e293b !important;
    }
    .feed-control-panel textarea, .feed-control-panel input {
        background: rgba(15, 23, 42, 0.8) !important;
        color: #e2e8f0 !important;
        border-radius: 10px !important;
        border: 1px solid #1e293b !important;
    }
    .feed-control-panel .stFileUploader label {
        border: 1px dashed #334155 !important;
        background: rgba(15,23,42,0.4) !important;
    }
    .lane-description {
        background: rgba(15, 23, 42, 0.3);
        border-left: 4px solid #3b82f6;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Lane 1 — Direct API Feeds
st.markdown("#### 🛣️ Lane 1 — Direct API Feeds (Optimal Real-Time Source)")
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

feed_panel_lane1 = st.container()
with feed_panel_lane1:
    st.markdown('<div class="feed-control-panel">', unsafe_allow_html=True)
    st.markdown("#### 🔧 Lane 1 Input Panel")
    api_url = st.text_input(
        "API Endpoint URL",
        value=st.session_state.get("lane_api_url", "https://api.internal/cockpit"),
        key="lane1_api_url",
    )
    api_token = st.text_input("Bearer / API Token", type="password", key="lane1_api_token")
    api_payload = st.text_area(
        "Sample Payload / Query", 
        value='{"company":"Amazon","metric":"cash_flow"}',
        key="lane1_api_payload",
    )
    if st.button("Save API Config", key="save_lane1_api"):
        st.session_state["lane_api_url"] = api_url
        st.success("✅ Lane 1 API configuration saved — ready for live autopilot feeds.")
    st.markdown("</div>", unsafe_allow_html=True)

# Lane 2 — BI System Connectors
st.markdown("#### 🛣️ Lane 2 — BI System Connectors (Deep Historical Feed)")
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

feed_panel_lane2 = st.container()
with feed_panel_lane2:
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
    if st.button("Save BI Connector Config", key="save_lane2_bi"):
        st.success(f"✅ Lane 2 BI connector configured — {bi_system} dataset will refresh every {refresh} minutes.")
    st.markdown("</div>", unsafe_allow_html=True)

# Lane 3 — File Uploads
st.markdown("#### 🛣️ Lane 3 — File Uploads (Emergency / Ad-hoc)")
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

feed_panel_lane3 = st.container()
with feed_panel_lane3:
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
