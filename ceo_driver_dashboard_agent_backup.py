#!/usr/bin/env python3
"""🚗 CEO Driver Seat — AI-powered business cockpit."""
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
    page_title="🚗 CEO Driver Seat",
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


def _compass_gauge(deviation_pct: float, title: str) -> go.Figure:
    deviation = max(-100.0, min(100.0, deviation_pct))
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=deviation,
            number={"suffix": "%", "font": {"color": "#f8fafc"}},
            delta={
                "reference": 0,
                "increasing": {"color": "#22c55e"},
                "decreasing": {"color": "#ef4444"},
            },
            title={"text": title, "font": {"color": "#f8fafc"}},
            gauge={
                "shape": "angular",
                "axis": {"range": [-50, 50], "tickcolor": "#94a3b8"},
                "bar": {"color": "#22d3ee"},
                "bgcolor": "#0f172a",
                "borderwidth": 2,
                "bordercolor": "#1f2937",
                "steps": [
                    {"range": [-50, -15], "color": "rgba(239,68,68,0.25)"},
                    {"range": [-15, 15], "color": "rgba(234,179,8,0.25)"},
                    {"range": [15, 50], "color": "rgba(34,197,94,0.25)"},
                ],
                "threshold": {"line": {"color": "#a855f7", "width": 4}, "value": 0},
            },
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
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
            CEO DRIVER SEAT
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    '<div style="text-align:center;">AI-powered command seat for CEOs — align revenue speed, cash fuel, ops heat, and market traffic in one cockpit.</div>',
    unsafe_allow_html=True,
)

st.warning("🚧 CEO DRIVER SEAT is flagged **Coming Soon**. Preview is disabled while we finalize verification.")
st.info("Thanks for your patience. Ping the platform team to request early access.")
st.stop()
LOGO_UPLOAD_PATH = Path(".cache/ceo_assets/driver_logo.png")
st.markdown("#### 🪪 Cockpit Logo")
logo_file = st.file_uploader(
    "Upload a dashboard logo", type=["png", "jpg", "jpeg", "gif"], key="logo_upload", help="Logo appears across sessions until you replace it."
)
if logo_file:
    LOGO_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOGO_UPLOAD_PATH, "wb") as handle:
        handle.write(logo_file.getbuffer())
    st.success("New logo saved.")
    st.image(logo_file, width=200)
elif LOGO_UPLOAD_PATH.exists():
    st.image(str(LOGO_UPLOAD_PATH), width=200, caption="Current cockpit logo")
else:
    st.info("Upload your company emblem to brand the CEO Driver Seat.")

company_choice = st.selectbox("Company cockpit", list(COMPANY_PRESETS.keys()))
use_live = st.toggle("Use live market scrape", value=False, help="Pulls Yahoo Finance snapshot when enabled.")
snapshot = get_company_snapshot(company_choice, prefer_live=use_live)
metrics: Dict[str, float] = snapshot["metrics"]
financials = snapshot["financials"]

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

st.markdown("#### 📈 Live Market Pulse")
_render_stock_widget(company_choice, snapshot.get("symbol"))

MAP_UPLOAD_PATH = Path(".cache/ceo_map_uploads/mock_map.png")

st.markdown("#### 🗺️ Upload Mock Road Map")
uploaded_map = st.file_uploader(
    "Upload a mock map image", type=["png", "jpg", "jpeg", "gif"], help="Use any image to represent the Road Map Map."
)
if uploaded_map:
    MAP_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MAP_UPLOAD_PATH, "wb") as handle:
        handle.write(uploaded_map.getbuffer())
    st.warning("Coming Soon — Mock map uploads will activate once the agent exits beta.")
elif MAP_UPLOAD_PATH.exists():
    st.warning("Coming Soon — saved mock maps are hidden until GA.")
else:
    st.info("This agent is marked **Coming Soon**. Map uploads will unlock after validation.")

st.markdown("#### 🕹️ Drive Mode & Gauges (Coming Soon)")
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
        go.Figure(),  # blank placeholder
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
st.info("This cockpit is currently in preview. Gauges will light up after QA sign-off.")

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

st.markdown("##### KPI Compass Gauges")
rev_deviation = ((metrics["rev_speed"] - target_rev) / target_rev) * 100
balance_deviation = (
    ((balance_gap or 0) - target_balance) / target_balance * 100 if target_balance else 0
)
ops_target = 80.0
ops_deviation = ((metrics["ops_heat"] - ops_target) / ops_target) * 100
compass_col1, compass_col2, compass_col3 = st.columns(3)
with compass_col1:
    st.plotly_chart(
        _compass_gauge(rev_deviation, "Revenue vs Target"),
        use_container_width=True,
    )
with compass_col2:
    st.plotly_chart(
        _compass_gauge(balance_deviation, "Balance Cushion vs Target"),
        use_container_width=True,
    )
with compass_col3:
    st.plotly_chart(
        _compass_gauge(ops_deviation, "Ops Heat vs Target"),
        use_container_width=True,
    )

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

st.caption("© 2025 CEO Driver AI Seat — Built for adaptive leadership.")

st.markdown("### 🔌 Data Feed Lanes")
st.markdown(
    """
    #### 🛣️ Lane 1 — Direct API Feeds (Optimal Real-Time Source)
    **Best for:** cash flow, sales pipelines, customer KPIs, product usage, market/competitor scans, AI-inferred KPIs, route/traffic analogs.  
    **Why:** real-time (< minutes), zero human touch, enables true autopilot correlations.  
    **Examples:** ERP (SAP/Netsuite) `/finance`, CRM (Salesforce/HubSpot) `/customers`, Jira/Linear `/product`, HR `/people`, Stripe/Adyen `/billing`, internal ops `/ops`, competitor scrapers `/market`.  
    **Result:** 🚀 Primary fuel line powering the cockpit.

    #### 🛣️ Lane 2 — BI System Connectors (Deep Historical Feed)
    **Best for:** strategic KPIs, long trendlines, planning/forecasting, TAM/SAM/SOM, segment drilldowns.  
    **Why:** BI holds the “long memory” to train autopilot and keep the destination map accurate.  
    **Examples:** PowerBI REST, Tableau Extract, Looker, BigQuery/Snowflake/Redshift connectors, Databricks delta feeds.  
    **Result:** 📊 Gives the CEO map historical context and confidence intervals.

    #### 🛣️ Lane 3 — File Uploads (Emergency / Ad-hoc)
    **Best for:** new market CSVs, consultant decks, one-shot datasets, market research, investment memos, board packs.  
    **Why:** leaders constantly ingest external files before APIs exist; this lane keeps the cockpit flexible.  
    **Formats:** CSV/Excel, PDF (OCR), JSON, images (AI extraction).  
    **Result:** 🧳 Rapid ingestion channel until formal integrations land.
    """,
    unsafe_allow_html=True,
)

st.markdown("#### 🔧 Data Feed Control Center")
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
    </style>
    """,
    unsafe_allow_html=True,
)

feed_panel = st.container()
with feed_panel:
    st.markdown('<div class="feed-control-panel">', unsafe_allow_html=True)
    lane_options = [
        "Lane 1 — Direct API",
        "Lane 2 — BI Connector",
        "Lane 3 — Manual Upload",
    ]
    selected_lane = st.selectbox("Choose data feed lane", lane_options, index=0, key="lane_selectbox")
    feed_upload = st.file_uploader(
        "Upload supplemental data file",
        type=["csv", "xlsx", "xls", "json", "pdf"],
        key="feed_lane_upload",
        help="Drop market decks, consultant data, or emergency feeds.",
    )
    if feed_upload:
        st.success(f"{feed_upload.name} staged for ingestion via {selected_lane}.")

    with st.expander("Lane 1 — API Configuration", expanded=True):
        api_url = st.text_input(
            "API Endpoint URL",
            value=st.session_state.get("lane_api_url", "https://api.internal/cockpit"),
        )
        api_token = st.text_input("Bearer / API Token", type="password", key="lane_api_token")
        api_payload = st.text_area(
            "Sample Payload / Query", value='{"company":"Amazon","metric":"cash_flow"}'
        )
        if st.button("Save API Config", key="save_api_lane"):
            st.session_state["lane_api_url"] = api_url
            st.success("API lane saved — ready for live autopilot feeds.")

    with st.expander("Lane 2 — BI Connector Setup", expanded=True):
        bi_system = st.selectbox(
            "BI Platform",
            ["PowerBI", "Tableau", "Looker", "BigQuery", "Snowflake", "Redshift", "Databricks"],
            key="bi_platform",
        )
        bi_dataset = st.text_input("Dataset / View", value="executive_rollup.share")
        refresh = st.slider("Refresh cadence (minutes)", 15, 720, 120, step=15)
        st.caption(f"Connector `{bi_system}` scheduled every {refresh} minutes for long-memory KPIs.")

    with st.expander("Lane 3 — File Mapping Panel", expanded=True):
        file_schema = st.text_area("Column mapping (CSV/Excel)", value="Quarter,Revenue,EBITDA,Region")
        apply_ocr = st.toggle("Apply OCR for PDF/Image uploads", value=True)
        st.caption("Use this panel to align ad-hoc files with cockpit schema before ingestion.")

    st.markdown("</div>", unsafe_allow_html=True)
