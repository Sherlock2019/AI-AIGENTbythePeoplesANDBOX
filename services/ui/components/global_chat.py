"""Global control tower chat overlay that keeps a holistic view of all agents."""
from __future__ import annotations

from typing import Dict, List

import streamlit as st

from services.common.personas import get_persona, list_personas
from services.ui.components.chat_assistant import render_chat_assistant

_GLOBAL_FAQ = [
    "Summarize combined asset + credit + fraud posture.",
    "Which agent should run next for this borrower?",
    "Generate a meeting brief for all personas.",
    "Show blockers preventing credit approval.",
    "Draft a unified report for the regulator.",
]


def _collect_agent_snapshot() -> Dict[str, str]:
    ss = st.session_state
    snapshot = {
        "asset_stage": ss.get("asset_stage"),
        "credit_stage": ss.get("credit_stage") or ss.get("stage"),
        "fraud_stage": ss.get("afk_stage") or ss.get("afk_active_tab"),
        "scoring_status": ss.get("credit_scoring_status"),
        "compliance_status": ss.get("legal_compliance_status"),
        "pending_asset": ss.get("asset_pending_cases"),
        "pending_credit": ss.get("credit_apps_in_review"),
        "pending_fraud": ss.get("afk_pending"),
        "flags_credit": ss.get("credit_flagged_cases"),
        "flags_asset": ss.get("asset_flagged_cases"),
        "flags_fraud": ss.get("afk_flagged"),
        "last_credit_run": ss.get("credit_last_run_id"),
        "last_asset_run": ss.get("asset_last_run_id"),
        "last_scoring_run": ss.get("credit_scoring_last_run_ts"),
        "last_compliance_run": ss.get("legal_compliance_last_run_ts"),
    }
    return {k: v for k, v in snapshot.items() if v not in (None, "", [])}


def render_global_control_tower() -> None:
    """Inject the global chat assistant pinned to the top of the viewport."""
    persona = get_persona("control_tower")
    invited = list_personas(
        ["asset_appraisal", "credit_appraisal", "anti_fraud_kyc", "credit_scoring", "legal_compliance"]
    )
    context = _collect_agent_snapshot()
    render_chat_assistant(
        page_id="global_control_tower",
        context=context,
        title="🛰 Unified Control Tower",
        default_open=False,
        faq_questions=_GLOBAL_FAQ,
        persona=persona,
        invited_personas=invited,
        pin_to_top=True,
        global_view=True,
    )
