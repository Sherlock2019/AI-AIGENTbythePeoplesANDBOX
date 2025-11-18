"""Central persona registry shared by UI pages and chat backend."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional


PERSONA_REGISTRY: Dict[str, Dict[str, str]] = {
    "control_tower": {
        "id": "control_tower",
        "name": "Nova",
        "title": "Unified Control Tower",
        "emoji": "🛰️",
        "color": "#38bdf8",
        "motto": "Keeps every agent in sync and surfaces cross-domain intel.",
        "focus": "Orchestrates asset, credit, fraud/KYC, scoring, and compliance signals.",
    },
    "credit_appraisal": {
        "id": "credit_appraisal",
        "name": "Ariel",
        "title": "Credit Appraisal Lead",
        "emoji": "💳",
        "color": "#7c3aed",
        "motto": "Balances affordability, PD, and policy guardrails.",
        "focus": "Underwrites SME/retail borrowers with transparent reasoning.",
    },
    "asset_appraisal": {
        "id": "asset_appraisal",
        "name": "Atlas",
        "title": "Asset Intelligence Officer",
        "emoji": "🏛️",
        "color": "#f97316",
        "motto": "Turns messy evidence into explainable valuations.",
        "focus": "Triangulates FMV, comps, encumbrances, and human review.",
    },
    "anti_fraud_kyc": {
        "id": "anti_fraud_kyc",
        "name": "Sentinel",
        "title": "Fraud & KYC Guardian",
        "emoji": "🛡️",
        "color": "#10b981",
        "motto": "Detects anomalies before they hit the credit stack.",
        "focus": "Intake, privacy scrub, verification, fraud rules, audit-ready trails.",
    },
    "credit_scoring": {
        "id": "credit_scoring",
        "name": "Pulse",
        "title": "Credit Scoring Strategist",
        "emoji": "📊",
        "color": "#3b82f6",
        "motto": "Feeds Gemma risk signals into the appraisal core.",
        "focus": "Bridges Anti-Fraud insights with Gemma-based credit scoring.",
    },
    "legal_compliance": {
        "id": "legal_compliance",
        "name": "Lex",
        "title": "Legal & Compliance Counsel",
        "emoji": "⚖️",
        "color": "#facc15",
        "motto": "Keeps sanctions, PEP, and licensing spotless.",
        "focus": "Translates regulatory constraints into actionable guidance.",
    },
}

AGENT_TO_PERSONA = {
    "global": "control_tower",
    "credit_appraisal": "credit_appraisal",
    "credit_agent": "credit_appraisal",
    "credit_scoring": "credit_scoring",
    "credit_scoring_agent": "credit_scoring",
    "asset_appraisal": "asset_appraisal",
    "asset_agent": "asset_appraisal",
    "anti_fraud_kyc": "anti_fraud_kyc",
    "fraud_agent": "anti_fraud_kyc",
    "legal_compliance": "legal_compliance",
    "legal_compliance_agent": "legal_compliance",
}


def get_persona(persona_id: str | None) -> Optional[Dict[str, str]]:
    if not persona_id:
        return None
    return PERSONA_REGISTRY.get(persona_id)


def get_persona_for_agent(agent_key: str | None) -> Optional[Dict[str, str]]:
    if not agent_key:
        return None
    persona_id = AGENT_TO_PERSONA.get(agent_key.lower(), AGENT_TO_PERSONA.get(agent_key))
    return get_persona(persona_id)


def list_personas(ids: Optional[List[str]] = None) -> List[Dict[str, str]]:
    if ids:
        return [PERSONA_REGISTRY[p] for p in ids if p in PERSONA_REGISTRY]
    return list(PERSONA_REGISTRY.values())


def persona_summary(persona_ids: List[str]) -> str:
    personas = list_personas(persona_ids)
    return ", ".join(f"{p['emoji']} {p['name']}" for p in personas) if personas else ""


def _auto_register_personas() -> None:
    """Scan UI agent pages and /agents dir for new personas."""
    try:
        ui_root = Path(__file__).resolve().parents[2] / "services" / "ui" / "pages"
        agents_root = Path(__file__).resolve().parents[2] / "agents"
    except Exception:
        return

    discovered: set[str] = set()
    if ui_root.exists():
        for path in ui_root.glob("*.py"):
            if not path.is_file():
                continue
            agent_id = path.stem
            if agent_id.startswith("_") or agent_id in {"__init__"}:
                continue
            discovered.add(agent_id)
    if agents_root.exists():
        for path in agents_root.iterdir():
            if path.is_dir():
                discovered.add(path.name)

    existing = set(PERSONA_REGISTRY.keys())
    for agent_id in sorted(discovered):
        if agent_id not in existing:
            pretty = agent_id.replace("_", " ").strip().title()
            PERSONA_REGISTRY[agent_id] = {
                "id": agent_id,
                "name": pretty,
                "title": f"{pretty} Agent",
                "emoji": "🤖",
                "color": "#64748b",
                "motto": f"Auto-discovered persona for {pretty}.",
                "focus": f"Learned from {agent_id}.",
            }
            existing.add(agent_id)
        AGENT_TO_PERSONA.setdefault(agent_id, agent_id)


try:
    _auto_register_personas()
except Exception as exc:
    logging.getLogger(__name__).debug("Persona auto-load skipped: %s", exc)
