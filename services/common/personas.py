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
    "troubleshooter": {
        "id": "troubleshooter",
        "name": "Quill",
        "title": "Troubleshooter Playbook Lead",
        "emoji": "🧩",
        "color": "#ec4899",
        "motto": "Turns incidents into clear remediation plans.",
        "focus": "Guides nine-step KT analysis from intake to deployment.",
    },
    "chatbot_rag": {
        "id": "chatbot_rag",
        "name": "Helix",
        "title": "Chatbot & RAG Chief",
        "emoji": "🧠",
        "color": "#0ea5e9",
        "motto": "Grounds every conversation in your uploaded knowledge.",
        "focus": "Manages ingestion, indexing, retrieval, personas, UI, and logging.",
    },
}

DEFAULT_FAQS: List[str] = [
    "Explain the lexical definitions for PD, DTI, LTV, and other credit terms.",
    "What is Probability of Default (PD) and how is it calculated?",
    "What is Debt-to-Income Ratio (DTI) and what are acceptable ranges?",
    "What is Loan-to-Value Ratio (LTV) and why does it matter?",
    "How does credit scoring work?",
    "What factors affect credit approval decisions?",
    "What is the difference between FMV and realizable value?",
    "How does fraud detection work in banking?",
    "What is KYC and why is it important?",
    "How are risk scores calculated?",
]

PERSONA_FAQS: Dict[str, List[str]] = {
    "control_tower": [
        "How do I use the control tower to coordinate asset, credit, fraud, scoring, and compliance agents end-to-end?",
        "What are the exact steps to broadcast a decision or alert to every downstream team?",
        "How do I review the top 10 readiness checks before a program goes live?",
        "Where can I see the current counts of loans approved, in review, or declined across all agents?",
        "How do I trigger a rerun of any agent stage (asset valuation, fraud check, credit scoring) from the tower?",
        "What glossary definitions (PD, LTV, FraudScore, FMV) does the tower enforce for consistency?",
        "How do I invite the Troubleshooter agent when multiple alerts collide?",
        "How do I download the latest unified audit packet (JSON/PDF) for regulators?",
        "How do I triage cross-agent data gaps or human-review bottlenecks?",
        "How do I monitor which personas are active and shift the chatbot between technical vs compliance tone?",
    ],
    "credit_appraisal": [
        "How do I run the A→H credit appraisal workflow end-to-end for a borrower?",
        "Which intake artifacts (profile, loan data, income, obligations) must be ready before stage A?",
        "How are PD, LGD, RiskScore, DTI, and LTV defined inside this agent?",
        "What are the top 10 policy checks I should complete before issuing a decision?",
        "Where can I view the running tally of approvals, reviews, and declines for this agent?",
        "How do I capture analyst overrides during the Human Review stage (E) and explain them?",
        "How do I export compliance-ready PDF/JSON packages from the Reporting stage (F)?",
        "How do I bundle and deploy the latest model + metrics during stage G?",
        "How do I deliver the four department handoffs (credit, risk, compliance, customer service) during stage H?",
        "How can I compare collateral strength from asset appraisal while reviewing PD tiers mid-process?",
    ],
    "asset_appraisal": [
        "How do I execute the full A0–F12 asset appraisal pipeline for a new collateral file?",
        "Which evidence (CSV, PDF, photos, GPS EXIF) should I gather before starting A0 Intake?",
        "How do I anonymize data and engineer features (privacy scrub, property age, geohash) during B2–B3?",
        "What definitions separate FMV, AI-adjusted FMV, and realizable value in this agent?",
        "What are the top 10 checks (condition, liens, comps, encumbrances, policy haircuts) before sign-off?",
        "How do I inspect the intermediate artifacts such as intake_table.csv or evidence_index.json?",
        "How do I trigger and review legal/ownership verification (C5) plus encumbrance alerts?",
        "How do I apply policy haircuts and compute realizable_value during D6?",
        "How do I prepare the reporting and credit_collateral_input handoffs in F10–F12?",
        "How can I monitor weekly counts of appraisals approved, routed to review, or rejected?",
    ],
    "anti_fraud_kyc": [
        "How do I run the Anti-Fraud & KYC agent through the A→F stages for a borrower?",
        "What intake data (IDs, selfies, device fingerprint, transactions) should I capture up front?",
        "How do I define and explain Fraud Score, Face Match %, Velocity Hits, and AML thresholds?",
        "What are the top 10 red-flag checks I must review before approving a customer?",
        "How do I interpret the current queue of approvals, denials, and escalations for this agent?",
        "How do I rerun the AI fraud evaluation (stage C) or policy rule engine (stage D)?",
        "How do I capture analyst override notes and suspicion levels in stage E?",
        "How do I package SAR-ready evidence or fraud dossiers for auditors?",
        "How can I whitelist recurring false positives without violating compliance guidance?",
        "How do I sync KYC/Fraud verdicts back into the credit or compliance agents?",
    ],
    "credit_scoring": [
        "How do I use the credit scoring agent’s A→H workflow from data intake to handoff?",
        "Which dataset columns (income, balance, payments, defaults) must be validated before training?",
        "How are Score, PD band, and feature importance defined inside this agent?",
        "What are the top 10 sanity checks (missing data, drift, bias) before promoting a scorecard?",
        "Where do I view the latest average score, approvals, and declines generated by this model?",
        "How do I run EDA/visualizations (heatmaps, distributions) during stage C?",
        "How do I package model.joblib, metrics.json, and notebooks for deployment (stages F–G)?",
        "How can I simulate the impact of policy or feature tweaks before shipping?",
        "How do I align scoring outputs with credit appraisal PD/DTI thresholds?",
        "How do I share scoring artifacts with the credit or control tower teams for transparency?",
    ],
    "legal_compliance": [
        "How do I walk through the legal/compliance workflow to validate a borrower or branch?",
        "What documents or evidence must I capture before launching license and consent checks?",
        "How are sanctions hits, PEP matches, licensing gaps, and adverse media flags defined here?",
        "What are the top 10 compliance checks I should review daily (licenses, SARs, disclosures, retention)?",
        "How do I inspect current counts of approvals, pending reviews, and escalations in compliance?",
        "How do I log analyst notes, overrides, or regulator communications for audit?",
        "How do I export examiner-ready packets (PDF/JSON) covering sanctions, consent, and privacy proofs?",
        "How do I synchronize findings with fraud/KYC, credit, and legal counsel?",
        "How can I detect when enhanced due diligence (EDD) is required versus standard review?",
        "How do I monitor retention policy timelines and ensure secure archiving?",
    ],
    "troubleshooter": [
        "How do I run the nine-step KT Troubleshooter process from Intake to Deployment?",
        "What information should I gather before creating an incident ticket or synthetic log?",
        "How do I define urgency, severity, and missing data during Situation Appraisal?",
        "How do I perform IS / IS NOT analysis to isolate root-cause hypotheses?",
        "What are the top 10 decision factors I should weigh during Decision Analysis?",
        "How do I conduct Potential Problem Analysis and document contingency plans?",
        "How do I draft the AI remediation plan with commands, config changes, and rollback steps?",
        "How do I capture human approvals or overrides before executing the fix?",
        "How do I export the remediation plan (PDF/JSON) for audit or DevOps tracking?",
        "How do I monitor how many incidents are resolved, pending, or escalated right now?",
    ],
    "chatbot_rag": [
        "How do I use the Chatbot + RAG agent to ingest data, index it, and answer questions end-to-end?",
        "What file types (CSV, PDF, TXT, PY) should I upload, and where are they stored in /rag_db?",
        "How does the indexing pipeline chunk text, embed vectors, and manage namespaces?",
        "How does RAG retrieval decide which snippets to cite, and when does it fall back to the model?",
        "How do personas influence tone (technical vs compliance vs customer) inside this chatbot?",
        "What are the top 10 operational checks for keeping RAG answers accurate and fresh?",
        "How can I inspect the live conversation log and retrieved context for each answer?",
        "How do I monitor current usage stats (messages answered, uploads processed, errors)?",
        "How do I refresh or rebuild the RAG store when new data arrives?",
        "How do I hand off chatbot summaries or transcripts to other agents or departments?",
    ],
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
    "troubleshooter": "troubleshooter",
    "troubleshooter_agent": "troubleshooter",
    "chatbot_rag": "chatbot_rag",
    "chatbot": "chatbot_rag",
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


def get_persona_faqs(persona_id: str | None, limit: int = 10) -> List[str]:
    """
    Return up to `limit` FAQ questions for the requested persona.
    Falls back to the global default list when persona-specific FAQs are unavailable.
    """
    if not persona_id:
        return DEFAULT_FAQS[:limit]
    faqs = PERSONA_FAQS.get(persona_id, DEFAULT_FAQS)
    return faqs[:limit] if limit else list(faqs)


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
