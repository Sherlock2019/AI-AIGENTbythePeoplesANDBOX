from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests

__all__ = ["call_local_llm", "llm_generate_summary"]

_LOGGER = logging.getLogger(__name__)


def _default_endpoint() -> str:
    base = os.getenv("OLLAMA_URL") or f"http://localhost:{os.getenv('GEMMA_PORT', '7001')}"
    return base.rstrip("/")


def call_local_llm(prompt: str, timeout: int = 45) -> str:
    """Best-effort call to the local Gemma/FastAPI wrapper. Falls back silently."""
    prompt = (prompt or "").strip()
    if not prompt:
        return ""

    endpoint = _default_endpoint()
    url = f"{endpoint}/chat"
    payload = {"prompt": prompt}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            for key in ("response", "text", "message"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    except Exception as exc:  # pragma: no cover - network best-effort
        _LOGGER.warning("Local LLM summary call failed: %s", exc)
    return ""


def _fallback_summary(metrics: Dict[str, Any]) -> str:
    agreement = float(metrics.get("agreement", 0.0) or 0.0)
    fraud_hits = int(metrics.get("fraud_hits", 0) or 0)
    kyc_feeds = int(metrics.get("kyc_feeds", 0) or 0)
    freshness = float(metrics.get("refresh_age", 0.0) or 0.0)

    if agreement >= 90:
        posture = "Alignment between AI and analysts remains high."
    elif agreement >= 70:
        posture = "Alignment is acceptable but should be spot-checked."
    else:
        posture = "Alignment has slipped; trigger a calibration huddle."

    freshness_note = (
        "Signals are fresh (<24h) so downstream scoring can trust the feed."
        if freshness < 24
        else "Telemetry is getting stale; refresh Anti-Fraud/KYC sync soon."
    )
    action = (
        "Keep the current cadence but document notable fraud edge-cases."
        if fraud_hits <= 2
        else "Prioritise fraud investigations before pushing applicants forward."
    )
    workload = (
        f"{kyc_feeds} dossiers are ready for review; balance staffing accordingly."
        if kyc_feeds
        else "No staged dossiers detected; run Stage 1 intake."
    )

    return f"{posture} {freshness_note} {workload} {action}"


def llm_generate_summary(metrics_dict: Dict[str, Any]) -> str:
    """
    LLM CALL: Summarize health of scoring system in human language.
    Output: 2–3 sentences, plain English.
    """
    prompt = f"""You are a risk-operations expert.
Summarize the current Credit Risk Telemetry:
LLM-Human agreement: {metrics_dict.get('agreement')}
Fraud hits: {metrics_dict.get('fraud_hits')}
KYC feeds: {metrics_dict.get('kyc_feeds')}
Data freshness (hours): {metrics_dict.get('refresh_age')}

Provide: 1) health status, 2) operational insight,
3) recommended immediate action if any."""

    llm_text = call_local_llm(prompt)
    if llm_text:
        return llm_text
    return _fallback_summary(metrics_dict)
