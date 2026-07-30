"""🚀 Deployment in Production — AI 4 the People.

Sends an agent from the AI 4 the People library straight to CloudJumper for
governed FLEX / OpenCenter / Palantir production. Renders the same stage as
YES AI CAN (integrations.cloudjumper.deploy_stage), so the two platforms cannot
drift apart in what they promise.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from integrations.cloudjumper import deploy_stage, is_enabled  # noqa: E402

st.set_page_config(page_title="Deployment in Production", page_icon="🚀", layout="wide")

if not is_enabled():
    st.warning("Disabled (CLOUDJUMPER_PRODUCTION_FACTORY_ENABLED=0).")
    st.stop()

# Agents from the AI 4 the People library. Source type AI4PEOPLE is what
# CloudJumper detects from the bundle manifest.
CANDIDATES = [
    {
        "global_ai_project_id": "AIPROJ-2026-000201",
        "title": "Anti-Fraud KYC Agent",
        "adoption_mode": "BROWNFIELD", "source_type": "AI4PEOPLE",
        "business_owner": "risk@acme.com", "technical_owner": "eng@acme.com",
        "data_owner": "dpo@acme.com", "production_owner": "ops@acme.com",
        "business_problem": "KYC review is manual and inconsistent across analysts.",
        "target_kpi": "60% faster KYC clearance", "agent_version": "2.1.0",
        "source_repository": "https://github.com/ai4people/anti-fraud-kyc-agent",
        "model_name": "llama3.1", "model_version": "8b", "model_license": "Llama 3.1 Community",
        "health_endpoint": "/health", "readiness_endpoint": "/ready",
        "data_sensitivity": "REGULATED", "data_location": "eu-west",
        "pii_present": True, "pii_reviewed": True, "external_transfer_allowed": False,
        "human_approval_required": True,
        "rollback_behaviour": "Disable the agent; analysts resume the manual checklist.",
        "target_environment": "FLEX + OpenCenter + Palantir", "palantir_required": True,
    },
    {
        "global_ai_project_id": "AIPROJ-2026-000202",
        "title": "Real Estate Evaluator Agent",
        "adoption_mode": "GREENFIELD", "source_type": "AI4PEOPLE",
        "business_owner": "lending@acme.com", "technical_owner": "eng@acme.com",
        "data_owner": "dpo@acme.com", "production_owner": "ops@acme.com",
        "business_problem": "Property valuation requires a manual surveyor visit.",
        "target_kpi": "same-day indicative valuation", "agent_version": "1.0.0",
        "source_repository": "https://github.com/ai4people/real-estate-evaluator",
        "model_name": "mistral", "model_version": "7b", "model_license": "Apache-2.0",
        "health_endpoint": "/health", "data_sensitivity": "MEDIUM", "data_location": "eu-west",
        "pii_reviewed": True, "external_transfer_allowed": False, "human_approval_required": True,
        "rollback_behaviour": "Disable the agent; surveyor workflow is unaffected.",
        "target_environment": "FLEX + OpenCenter",
    },
]

deploy_stage.render(st, CANDIDATES, platform="AI 4 the People")
