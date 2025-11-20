#!/usr/bin/env python3
"""Chatbot Assistant - Simple, clean implementation using model knowledge base only."""
from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import requests
import streamlit as st

from services.common.personas import list_personas, get_persona_faqs
from services.ui.theme_manager import apply_theme, render_theme_toggle
from services.ui.components.feedback import render_feedback_tab

API_URL = os.getenv("API_URL", "http://localhost:8090")

st.set_page_config(
    page_title="💬 Chatbot Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_theme()

ss = st.session_state
ss.setdefault("chatbot_history", [])
ss.setdefault("chatbot_selected_model", "phi3:latest")

CHATBOT_PERSONA_IDS = [
    "control_tower",
    "credit_appraisal",
    "asset_appraisal",
    "anti_fraud_kyc",
    "credit_scoring",
    "legal_compliance",
    "troubleshooter",
    "chatbot_rag",
]
CHATBOT_PERSONAS = list_personas(CHATBOT_PERSONA_IDS) or list_personas()
PERSONA_LOOKUP = {p["id"]: p for p in CHATBOT_PERSONAS}
DEFAULT_PERSONA_ID = CHATBOT_PERSONAS[0]["id"] if CHATBOT_PERSONAS else None
ss.setdefault("chatbot_persona_id", DEFAULT_PERSONA_ID)

# ─────────────────────────────────────────────
# NAVIGATION BAR
# ─────────────────────────────────────────────
def _go_stage(target: str):
    """Navigate to a stage/page."""
    ss["stage"] = target
    try:
        st.switch_page("app.py")
    except Exception:
        try:
            st.query_params["stage"] = target
        except Exception:
            pass
        st.rerun()

def render_nav_bar():
    """Top navigation bar with Home, Agents, and Theme switch."""
    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if st.button("🏠 Back to Home", key="btn_home_chatbot", use_container_width=True):
            _go_stage("landing")
            st.stop()
    with c2:
        if st.button("🤖 Back to Agents", key="btn_agents_chatbot", use_container_width=True):
            _go_stage("agents")
            st.stop()
    with c3:
        render_theme_toggle(
            label="🌗 Dark mode",
            key="chatbot_nav_theme",
            help="Switch theme",
        )
    st.markdown("---")

render_nav_bar()

st.title("💬 Chatbot Assistant")
st.caption("AI-powered assistant using model knowledge base - Pick a persona to focus the answers")

# ─────────────────────────────────────────────
# PERSONA SELECTION
# ─────────────────────────────────────────────
persona_ids = list(PERSONA_LOOKUP.keys())
selected_persona = None
if persona_ids:
    current_persona_id = ss.get("chatbot_persona_id") or DEFAULT_PERSONA_ID or persona_ids[0]
    if current_persona_id not in persona_ids:
        current_persona_id = persona_ids[0]
    persona_labels = {
        pid: f"{PERSONA_LOOKUP[pid]['emoji']} {PERSONA_LOOKUP[pid]['title']}"
        for pid in persona_ids
    }
    selected_id = st.selectbox(
        "🎭 Choose assistant persona",
        options=persona_ids,
        index=persona_ids.index(current_persona_id),
        format_func=lambda pid: persona_labels.get(pid, pid),
        key="chatbot_persona_select",
    )
    selected_persona = PERSONA_LOOKUP.get(selected_id)
    ss["chatbot_persona_id"] = selected_id
else:
    st.warning("No personas registered. Using default assistant behavior.")

if not selected_persona:
    selected_persona = {
        "id": "chatbot",
        "name": "Chatbot",
        "title": "Unified Assistant",
        "emoji": "💬",
        "focus": "Answers general banking and credit automation questions.",
    }

info_col1, info_col2 = st.columns([3, 2])
with info_col1:
    st.subheader(f"{selected_persona['emoji']} {selected_persona['name']} — {selected_persona['title']}")
    if selected_persona.get("motto"):
        st.write(selected_persona["motto"])
    st.caption(selected_persona.get("focus", ""))
with info_col2:
    st.metric("Focus Agent", selected_persona.get("id", "chatbot"))
    st.metric("Theme Color", selected_persona.get("color", "#2563eb"))

# Spacer before model selection
st.markdown("---")

# ─────────────────────────────────────────────
# MODEL SELECTION
# ─────────────────────────────────────────────
def get_available_models() -> List[str]:
    """Fetch available models from API."""
    try:
        resp = requests.get(f"{API_URL}/v1/chat/models", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("models", [])
    except Exception:
        pass
    return ["phi3:latest", "mistral:latest", "gemma2:2b", "gemma2:9b"]

col1, col2 = st.columns([2, 1])
with col1:
    available_models = get_available_models()
    selected_model = st.selectbox(
        "🤖 Select LLM Model",
        options=available_models,
        index=0 if "phi3:latest" in available_models else 0,
        key="chatbot_model_select",
    )
    ss["chatbot_selected_model"] = selected_model

with col2:
    if st.button("🔄 Refresh Models", use_container_width=True):
        ss.pop("chatbot_cached_models", None)
        st.rerun()

# ─────────────────────────────────────────────
# RAG FILE UPLOAD
# ─────────────────────────────────────────────
st.markdown("#### 📤 Upload Documents to the Chat Knowledge Base")
st.caption("Add PDFs, CSVs, or notes so the chatbot can reference them first. Supported: txt, csv, pdf, py, html, md, json, xml.")
uploaded_rag_file = st.file_uploader(
    "Upload file to RAG (max 50 MB)",
    type=["txt", "csv", "pdf", "py", "html", "md", "json", "xml", "log"],
    key="chatbot_rag_file",
)
if uploaded_rag_file is not None:
    filename = uploaded_rag_file.name
    filesize = len(uploaded_rag_file.getvalue() or b"")
    col_info, col_upload = st.columns([3, 1])
    with col_info:
        st.info(f"Selected **{filename}** ({filesize/1024:.1f} KB)")
    with col_upload:
        if st.button("Upload to RAG", key="chatbot_rag_upload_btn", use_container_width=True):
            try:
                with st.spinner(f"Uploading {filename}..."):
                    files = {"file": (filename, uploaded_rag_file.getvalue(), uploaded_rag_file.type or "application/octet-stream")}
                    resp = requests.post(
                        f"{API_URL}/v1/chat/upload",
                        files=files,
                        data={"max_rows": 500},
                        timeout=300,
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    st.success(result.get("message", "File ingested successfully."))
            except requests.exceptions.Timeout:
                st.error("⏱️ Upload timed out. Try a smaller file or check API connectivity.")
            except requests.exceptions.HTTPError as exc:
                detail = exc.response.json().get("detail", str(exc)) if getattr(exc, "response", None) else str(exc)
                st.error(f"❌ Upload failed: {detail}")
            except Exception as exc:
                st.error(f"❌ Unexpected error: {exc}")

st.markdown("---")

# ─────────────────────────────────────────────
# FAQ QUESTIONS (persona-aware)
# ─────────────────────────────────────────────
active_faqs = get_persona_faqs(selected_persona.get("id"))

with st.expander(
    f"💡 Quick Start FAQs for {selected_persona.get('name', 'Chatbot')} ({len(active_faqs)} prompts)",
    expanded=True,
):
    if not active_faqs:
        st.info("No quick-start questions found for this persona yet.")
    else:
        st.caption("Click a question to use it (it will be sent automatically)")
        faq_cols = st.columns(2)
        for idx, faq in enumerate(active_faqs):
            col_idx = idx % 2
            with faq_cols[col_idx]:
                if st.button(faq, key=f"faq_{idx}", use_container_width=True):
                    ss["chatbot_question"] = faq
                    ss["chatbot_question_input"] = faq
                    st.rerun()

st.markdown("---")

# ─────────────────────────────────────────────
# CHAT INTERFACE
# ─────────────────────────────────────────────
tab_chat, tab_feedback = st.tabs(["💬 Chat", "🗣️ Feedback & Reviews"])

with tab_chat:
    # Question input
    question = st.text_area(
        "Your Question",
        value=ss.get("chatbot_question", ""),
        placeholder=f"Ask {selected_persona.get('name', 'the assistant')} anything...",
        height=150,
        key="chatbot_question_input",
    )
    
    col_send, col_clear = st.columns([3, 1])
    with col_send:
        send_button = st.button("💬 Send Message", use_container_width=True, type="primary")
    with col_clear:
        if st.button("🧹 Clear", use_container_width=True):
            ss["chatbot_history"] = []
            ss["chatbot_question"] = ""
            st.rerun()
    
    # Determine when to send (manual only)
    should_send = send_button and question.strip()
    
    # Send message
    if should_send and question.strip():
        with st.spinner("🤔 Thinking..."):
            try:
                context_payload = {
                    "agent_type": selected_persona.get("id", "chatbot"),
                    "persona_id": selected_persona.get("id"),
                    "persona_name": selected_persona.get("name"),
                    "persona_title": selected_persona.get("title"),
                    "persona_focus": selected_persona.get("focus"),
                    "persona_color": selected_persona.get("color"),
                }
                payload = {
                    "message": question.strip(),
                    "page_id": "chatbot_assistant",
                    "context": context_payload,
                    "model": ss["chatbot_selected_model"],
                    "agent_id": "chatbot",
                    "history": [
                        {"role": h.get("role"), "content": h.get("content")}
                        for h in ss["chatbot_history"][-5:]
                    ],
                }
                
                resp = requests.post(
                    f"{API_URL}/v1/chat",
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                
                # Store in history
                ss["chatbot_history"].append({
                    "role": "user",
                    "content": question.strip(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                ss["chatbot_history"].append({
                    "role": "assistant",
                    "content": data.get("reply", "No reply."),
                    "timestamp": data.get("timestamp"),
                    "model": ss["chatbot_selected_model"],
                    "confidence": data.get("confidence"),
                })
                ss["chatbot_question"] = ""
                st.rerun()
                
            except requests.exceptions.Timeout:
                st.error("⏱️ Request timeout. The API took too long to respond.")
            except requests.exceptions.ConnectionError:
                st.error(f"❌ Cannot connect to {API_URL}. Make sure the API server is running.")
            except Exception as exc:
                st.error(f"❌ Error: {exc}")
    
    # Display chat history
    st.markdown("### 💬 Conversation History")
    if not ss["chatbot_history"]:
        st.info("👋 Ask a question above to get started!")
    else:
        for msg in ss["chatbot_history"]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            model = msg.get("model", "")
            confidence = msg.get("confidence", "")
            
            with st.chat_message(role):
                st.markdown(content)
                if role == "assistant" and model:
                    st.caption(f"Model: {model} | Confidence: {confidence}")
        
        # Export button
        st.markdown("---")
        if st.button("📥 Export Chat History", use_container_width=True):
            chat_json = json.dumps(ss["chatbot_history"], indent=2, ensure_ascii=False)
            st.download_button(
                label="⬇️ Download Chat History (JSON)",
                data=chat_json.encode("utf-8"),
                file_name=f"chatbot_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

with tab_feedback:
    render_feedback_tab("💬 Chatbot Assistant")
