from __future__ import annotations

import os
import requests
import streamlit as st

from services.ui.theme_manager import apply_theme, render_theme_toggle
from services.common.personas import list_personas
from services.ui.data.chatbot_faqs import get_agent_faqs

API_URL = os.getenv("AGENT_API_URL", "http://localhost:8090")

st.set_page_config(page_title="🤖 Phi-3 Chatbot", layout="wide")
apply_theme()

st.title("🤖 Phi-3 Control Tower")
st.caption("External Phi-3 (Ollama) + Chroma RAG powered by recent agent CSV outputs.")
render_theme_toggle()

if "chatbot_history" not in st.session_state:
    st.session_state["chatbot_history"] = []
if "chatbot_sources" not in st.session_state:
    st.session_state["chatbot_sources"] = []
st.session_state.setdefault("chatbot_pending_prompt", None)
st.session_state.setdefault("chatbot_pending_agent", None)


def _post_json(path: str, payload: dict, *, params: dict | None = None, timeout: int = 120):
    resp = requests.post(
        f"{API_URL.rstrip('/')}{path}",
        json=payload,
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _post_file(path: str, file_name: str, data: bytes, *, params: dict | None = None):
    files = {"file": (file_name, data, "application/octet-stream")}
    resp = requests.post(
        f"{API_URL.rstrip('/')}{path}",
        files=files,
        params=params,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


personas = list_personas()
persona_options = ["auto"] + [p["id"] for p in personas]
persona_lookup = {p["id"]: p for p in personas}

with st.sidebar:
    st.subheader("RAG Controls")
    selected_persona = st.selectbox(
        "Tag uploaded content to an agent persona",
        persona_options,
        format_func=lambda pid: "Auto-detect" if pid == "auto" else f"{pid}",
    )
    agent_param = None if selected_persona == "auto" else {"agent_id": selected_persona}

    uploaded = st.file_uploader("Upload CSV to ingest", type=["csv"])
    if uploaded is not None and st.button("Ingest uploaded CSV"):
        try:
            meta = _post_file(
                "/chatbot/ingest",
                uploaded.name,
                uploaded.getvalue(),
                params=agent_param,
            )
            st.success(f"Ingested {meta.get('rows_indexed', 0)} rows.")
        except requests.RequestException as exc:
            st.error(f"Upload failed: {exc}")

    upload_any = st.file_uploader(
        "Upload document (csv/txt/md/html/pdf/json/py)",
        type=["csv", "txt", "md", "html", "htm", "json", "pdf", "py", "log", "doc", "docx"],
        accept_multiple_files=False,
        help="Any file will be chunked into text and embedded for the selected persona.",
    )
    if upload_any is not None and st.button("Embed & ingest file"):
        try:
            meta = _post_file(
                "/chatbot/ingest/file",
                upload_any.name,
                upload_any.getvalue(),
                params=agent_param,
            )
            st.success(
                f"Ingested {meta.get('rows_indexed', 0)} chunks from {upload_any.name} "
                f"under persona '{agent_param.get('agent_id', 'auto') if agent_param else 'auto'}'."
            )
        except requests.RequestException as exc:
            st.error(f"Document upload failed: {exc}")

    if st.button("🔄 Refresh RAG DB"):
        try:
            meta = _post_json("/chatbot/refresh", {}, params=None)
            st.success(
                "CSV rows: "
                f"{meta['csv'].get('rows_indexed', 0)} | Agent chunks: {meta['agent_ui'].get('rows_indexed', 0)} | "
                f"Doc chunks: {meta['docs'].get('rows_indexed', 0)} | Pruned runs: {meta['pruned_runs'].get('entries_removed', 0)}"
            )
        except requests.RequestException as exc:
            st.error(f"Refresh failed: {exc}")

    if st.button("♻️ Hard Reset & Rebuild RAG"):
        try:
            meta = _post_json("/chatbot/refresh", {}, params={"reset": "true"})
            st.success(
                "Recreated store. CSV rows: "
                f"{meta['csv'].get('rows_indexed', 0)}, agent chunks: {meta['agent_ui'].get('rows_indexed', 0)}, "
                f"doc chunks: {meta['docs'].get('rows_indexed', 0)}, pruned runs: {meta['pruned_runs'].get('entries_removed', 0)}"
            )
        except requests.RequestException as exc:
            st.error(f"Rebuild failed: {exc}")

    st.markdown("**Current Model:** `Phi-3 (Ollama)`")
    st.caption("Ensure `ollama run phi3:latest` (or similar) is active locally.")

    if personas:
        st.divider()
        st.subheader("Agent FAQs")
        default_persona_id = personas[0]["id"]
        faq_persona = st.selectbox(
            "Choose persona",
            [p["id"] for p in personas],
            format_func=lambda pid: f"{persona_lookup[pid]['emoji']} {persona_lookup[pid]['name']}",
            key="chatbot_faq_persona",
        )
        faqs = get_agent_faqs(faq_persona) or get_agent_faqs(default_persona_id)
        for idx, question in enumerate(faqs[:10]):
            if st.button(
                question,
                key=f"chatbot_faq_{faq_persona}_{idx}",
                help="Ask this FAQ using the selected persona namespace",
            ):
                st.session_state["chatbot_pending_prompt"] = question
                st.session_state["chatbot_pending_agent"] = faq_persona


def _handle_prompt(prompt_text: str, agent_override: str | None = None):
    """Send prompt to chatbot and stream response within the chat UI."""
    if not prompt_text:
        return
    target_agent = agent_override or (None if selected_persona == "auto" else selected_persona)
    agent_params = {"agent_id": target_agent} if target_agent else None
    st.session_state["chatbot_history"].append({"role": "user", "content": prompt_text})
    with st.chat_message("user"):
        st.markdown(prompt_text)
        if target_agent:
            persona = persona_lookup.get(target_agent)
            label = persona["name"] if persona else target_agent
            st.caption(f"Persona: {label}")
    try:
        response = _post_json("/chatbot/chat", {"question": prompt_text}, params=agent_params)
    except requests.RequestException as exc:
        st.error(f"Chat backend error: {exc}")
        return

    answer = response.get("answer", "No answer returned.")
    sources = response.get("sources", [])
    st.session_state["chatbot_history"].append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
    st.session_state["chatbot_sources"] = sources
    with st.chat_message("assistant"):
        st.markdown(answer)
        if sources:
            st.caption("Sources:")
            for src in sources:
                st.write(f"- `{src['file']}` (score={src['score']})")


for message in st.session_state["chatbot_history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            st.caption("Sources:")
            for src in message["sources"]:
                st.write(f"- `{src['file']}` (score={src['score']})")


pending_prompt = st.session_state.pop("chatbot_pending_prompt", None)
pending_agent = st.session_state.pop("chatbot_pending_agent", None)
prompt = st.chat_input("Ask about any agent pipeline…")
if prompt:
    _handle_prompt(prompt)
elif pending_prompt:
    _handle_prompt(pending_prompt, agent_override=pending_agent)


if st.session_state.get("chatbot_sources"):
    with st.expander("Sources used in last answer", expanded=True):
        for src in st.session_state["chatbot_sources"]:
            st.write(f"- `{src['file']}` · score {src['score']}")
