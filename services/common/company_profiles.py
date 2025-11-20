"""Company persona generator + lightweight financial scraper."""
from __future__ import annotations

import logging
import random
from functools import lru_cache
from typing import Dict, List

import numpy as np
import requests

LOGGER = logging.getLogger(__name__)

COMPANY_PRESETS: Dict[str, Dict] = {
    "Amazon": {
        "symbol": "AMZN",
        "sector": "Commerce & Cloud",
        "hq": (47.6062, -122.3321),
        "base_metrics": {
            "rev_speed": 130,
            "cash_months": 6,
            "ops_heat": 72,
            "traffic": 68,
            "nps": 8.2,
            "eta_days": 65,
        },
    },
    "Palantir": {
        "symbol": "PLTR",
        "sector": "AI / Defense",
        "hq": (39.7392, -104.9903),
        "base_metrics": {
            "rev_speed": 95,
            "cash_months": 9,
            "ops_heat": 58,
            "traffic": 57,
            "nps": 7.8,
            "eta_days": 75,
        },
    },
    "Rackspace": {
        "symbol": "RXT",
        "sector": "Cloud Services",
        "hq": (29.4252, -98.4946),
        "base_metrics": {
            "rev_speed": 82,
            "cash_months": 4,
            "ops_heat": 66,
            "traffic": 49,
            "nps": 7.1,
            "eta_days": 92,
        },
    },
}


def _jitter(value: float, pct: float = 0.08) -> float:
    return max(0.0, value * (1 + np.random.uniform(-pct, pct)))


def generate_company_metrics(company: str) -> Dict[str, float]:
    preset = COMPANY_PRESETS.get(company) or COMPANY_PRESETS["Amazon"]
    base = preset["base_metrics"]
    np.random.seed()
    return {
        "rev_speed": _jitter(base["rev_speed"], 0.12),
        "cash_months": _jitter(base["cash_months"], 0.25),
        "ops_heat": min(120, _jitter(base["ops_heat"], 0.2)),
        "traffic": min(100, _jitter(base["traffic"], 0.2)),
        "nps": min(10, max(4.5, _jitter(base["nps"], 0.1))),
        "eta_days": max(15, _jitter(base["eta_days"], 0.15)),
    }


@lru_cache(maxsize=16)
def _scrape_from_yahoo(symbol: str) -> Dict:
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    params = {"modules": "financialData,defaultKeyStatistics"}
    try:
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        payload = resp.json()
        result = payload["quoteSummary"]["result"][0]
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Yahoo scrape failed for %s: %s", symbol, exc)
        return {}

    def _num(block: Dict, key: str):
        value = block.get(key)
        if isinstance(value, dict):
            return value.get("raw")
        return None

    financial = result.get("financialData") or {}
    stats = result.get("defaultKeyStatistics") or {}
    return {
        "revenue": _num(financial, "totalRevenue"),
        "ebitda": _num(financial, "ebitda"),
        "profit_margin": _num(financial, "profitMargins"),
        "cash": _num(financial, "totalCash"),
        "debt": _num(financial, "totalDebt"),
        "beta": _num(stats, "beta"),
        "market_cap": _num(stats, "marketCap"),
        "pe_ratio": _num(stats, "forwardPE") or _num(stats, "trailingPE"),
    }


def format_currency(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1e12:
        return f"${value/1e12:.1f}T"
    if abs(value) >= 1e9:
        return f"${value/1e9:.1f}B"
    if abs(value) >= 1e6:
        return f"${value/1e6:.1f}M"
    return f"${value:,.0f}"


def build_insights(company: str, metrics: Dict[str, float], financials: Dict[str, float]) -> List[str]:
    insights = []
    cash = financials.get("cash")
    debt = financials.get("debt")
    margin = financials.get("profit_margin")
    if cash and debt and cash < debt * 0.6:
        insights.append("Refuel alert — debt pressure exceeding cash reserves.")
    if margin and margin < 0.05:
        insights.append("Margins thin — Eco mode recommended for cost discipline.")
    if metrics["ops_heat"] > 80:
        insights.append("Engine temp critical — initiate Pit-Stop maintenance.")
    if metrics["traffic"] > 70:
        insights.append("Traffic jam detected — reroute go-to-market plan.")
    if not insights:
        insights.append("Systems nominal — maintain current mode and monitor radar.")
    return insights


def get_company_snapshot(company: str, prefer_live: bool = False) -> Dict:
    preset = COMPANY_PRESETS.get(company) or COMPANY_PRESETS["Amazon"]
    symbol = preset["symbol"]
    metrics = generate_company_metrics(company)
    financials: Dict[str, float] = {}
    if prefer_live:
        financials = _scrape_from_yahoo(symbol)
    if not financials:
        financials = {
            "revenue": preset["base_metrics"]["rev_speed"] * 1e7,
            "profit_margin": random.uniform(0.06, 0.18),
            "cash": preset["base_metrics"]["cash_months"] * 1.5e9,
            "debt": random.uniform(0.5, 3.5) * 1e9,
            "beta": random.uniform(0.9, 1.6),
            "market_cap": random.uniform(5, 45) * 1e9,
            "pe_ratio": random.uniform(15, 65),
        }
    if financials.get("profit_margin"):
        metrics["rev_speed"] *= 1 + float(financials["profit_margin"]) * 0.4
    if financials.get("cash") and financials.get("debt"):
        ratio = max(0.5, min(2.5, financials["cash"] / max(1.0, financials["debt"])))
        metrics["cash_months"] *= ratio
    insights = build_insights(company, metrics, financials)
    return {
        "company": company,
        "symbol": symbol,
        "sector": preset["sector"],
        "metrics": metrics,
        "financials": financials,
        "insights": insights,
        "hq": preset["hq"],
    }


__all__ = ["COMPANY_PRESETS", "get_company_snapshot", "format_currency"]
