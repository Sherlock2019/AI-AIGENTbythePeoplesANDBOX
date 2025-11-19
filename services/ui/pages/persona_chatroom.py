#!/usr/bin/env python3
"""Virtual meeting room to invite multiple agent personas into the same discussion."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List

import requests
import streamlit as st

from services.common.personas import get_persona, list_personas
from services.ui.theme_manager import apply_theme as apply_global_theme, get_theme, render_theme_toggle
from services.ui.components.operator_banner import render_operator_banner

API_URL = os.getenv("API_URL", "http://localhost:8090")

st.set_page_config(page_title="Persona Strategy Room", layout="wide")
apply_global_theme(get_theme())

ss = st.session_state
ss.setdefault("stage", "persona_chatroom")
ss.setdefault("persona_chat_history", [])
ss.setdefault("persona_case_summary", "")

all_personas = list_personas()
persona_lookup: Dict[str, Dict[str, str]] = {p["id"]: p for p in all_personas}

render_operator_banner(
    operator_name=ss.get("user_info", {}).get("name", "Operator"),
    title="Persona Strategy Room",
    summary="Spin up an ad-hoc meeting between the domain personas (asset, credit, fraud/KYC, scoring, compliance).",
    bullets=[
        "Invite any combination of personas for a live discussion.",
        "Share a case summary so everyone has the same context.",
        "Log the transcript and export it for audits.",
    ],
    metrics=[
        {"label": "Personas available", "value": len(all_personas)},
        {"label": "Active meeting lines", "value": len(ss["persona_chat_history"])},
    ],
    icon="🧑‍🚀",
)

st.markdown("### Invite personas")

default_invite = ["asset_appraisal", "credit_appraisal", "anti_fraud_kyc"]
selected_ids = st.multiselect(
    "Choose which personas to invite",
    options=[p["id"] for p in all_personas],
    format_func=lambda pid: f"{persona_lookup[pid]['emoji']} {persona_lookup[pid]['name']} — {persona_lookup[pid]['title']}",
    default=[pid for pid in default_invite if pid in persona_lookup],
)
selected_personas: List[Dict[str, str]] = [persona_lookup[pid] for pid in selected_ids]

col_case, col_settings = st.columns([2.5, 1])
with col_case:
    ss["persona_case_summary"] = st.text_area(
        "Case brief",
        value=ss.get("persona_case_summary", ""),
        placeholder="Example: SME borrower #4481 requesting 1.8M USD. Asset FMV 2.1M. Fraud cleared. Waiting on compliance.",
    )
with col_settings:
    render_theme_toggle("🌗 Theme", key="persona_room_theme")
    if st.button("🧹 Clear transcript", use_container_width=True):
        ss["persona_chat_history"] = []
        st.success("Cleared meeting transcript.")

st.markdown("### Drive the conversation")
meeting_prompt = st.text_area(
    "Ask a question or set the agenda",
    placeholder="e.g. 'Should we approve SME-4481 today? Highlight blockers from each agent.'",
    key="persona_room_prompt",
)

def _record_message(role: str, speaker: str, content: str) -> None:
    history = ss.setdefault("persona_chat_history", [])
    history.append(
        {
            "role": role,
            "speaker": speaker,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def _serialize_history() -> List[Dict[str, str]]:
    return [
        {
            "role": item.get("role", "user"),
            "content": f"{item.get('speaker', 'Operator')}: {item.get('content')}",
            "timestamp": item.get("timestamp"),
        }
        for item in ss.get("persona_chat_history", [])
    ][-40:]


send_disabled = not meeting_prompt.strip() or not selected_personas

if st.button("🚀 Ask the room", use_container_width=True, disabled=send_disabled):
    if not selected_personas:
        st.warning("Invite at least one persona.")
    elif not meeting_prompt.strip():
        st.warning("Add a prompt for the meeting.")
    else:
        _record_message("user", "Operator", meeting_prompt.strip())
        payload = {
            "message": meeting_prompt.strip(),
            "page_id": "persona_chatroom",
            "context": {
                "stage": "persona_roundtable",
                "case_summary": ss.get("persona_case_summary"),
                "invited": [p["name"] for p in selected_personas],
            },
            "history": _serialize_history(),
            "persona_id": selected_personas[0]["id"] if selected_personas else None,
            "invited_personas": [p["id"] for p in selected_personas],
            "global_room": True,
        }
        try:
            resp = requests.post(f"{API_URL}/v1/chat", json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("reply") or "No reply."
            speaker = get_persona("control_tower") or {"name": "Control Tower"}
            _record_message("assistant", speaker.get("name", "Control Tower"), reply)
            st.success("Control Tower shared the group intelligence.")
        except Exception as exc:
            st.error(f"Meeting call failed: {exc}")

st.markdown("### Transcript")
chat_history = ss.get("persona_chat_history", [])
if not chat_history:
    st.info("No messages yet. Invite personas and start the discussion.")
else:
    for item in chat_history:
        role = item.get("role", "user")
        speaker = item.get("speaker") or ("Operator" if role == "user" else "Control Tower")
        with st.chat_message("assistant" if role != "user" else "user"):
            st.markdown(f"**{speaker}:** {item.get('content')}")
