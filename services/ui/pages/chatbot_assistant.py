import os
from typing import Dict, Any, List

import requests
import streamlit as st
from services.ui.theme_manager import apply_theme, render_theme_toggle

API_URL = os.getenv("API_URL", "http://localhost:8090")

ROLE_CONFIG: Dict[str, Dict[str, Any]] = {
    "credit": {
        "label": "💳 Credit Appraisal Agent",
        "page_id": "credit_appraisal",
        "context": {"agent_type": "credit", "stage": "credit_review"},
        "faqs": [
            "How does the Credit Appraisal agent work end-to-end?",
            "What are the step-by-step stages in this agent?",
            "Explain the lexical definitions for PD, DTI, LTV, and other credit terms.",
            "What inputs and outputs does the credit agent expect?",
            "What benefits do we get from using this AI credit agent?",
            "How do I explain an approve vs review decision?",
            "What credit score threshold are we using for SMEs?",
            "Summarize PD, LTV, and DTI for the current borrower.",
            "Which policy rules can trigger an automatic reject?",
            "How do I export the credit decision narrative?",
            "What inputs feed the probability of default model?",
            "How do I rerun the credit model after adjusting collateral?",
            "Where can I see recent manual overrides?",
            "How do I share credit results with the Unified agent?",
            "What datasets power the explainability section?",
        ],
    },
    "asset": {
        "label": "🏦 Asset Appraisal Agent",
        "page_id": "asset_appraisal",
        "context": {"agent_type": "asset", "stage": "valuation"},
        "faqs": [
            "How does the Asset Appraisal agent work from intake to report?",
            "What are the stage-by-stage steps in the asset workflow?",
            "Define the key terms (FMV, AI-adjusted, realizable, encumbrance).",
            "What inputs and outputs does the asset agent consume/produce?",
            "What benefits do we gain from automating asset valuation with AI?",
            "How are AI-adjusted FMVs derived?",
            "List comps used to price construction equipment.",
            "What encumbrance flags should I watch for?",
            "How do I upload new evidence (images/PDFs)?",
            "Where do I see anonymized vs raw intake data?",
            "How does the agent detect secondary liens?",
            "Can I export the appraisal report for auditors?",
            "What asset types have custom models?",
            "How do I sync FMV outputs with the Unified agent?",
            "How is valuation confidence calculated?",
        ],
    },
    "anti_fraud": {
        "label": "🛡️ Anti-Fraud & KYC Agent",
        "page_id": "anti_fraud_kyc",
        "context": {"agent_type": "fraud_kyc", "stage": "fraud_review"},
        "faqs": [
            "How does the Anti-Fraud/KYC agent work?",
            "What are the detailed steps (Intake → Privacy → Verification → Fraud → Review → Reporting)?",
            "Define the key lexical terms (sanction hits, fraud_score, kyc_passed).",
            "What inputs and outputs does this fraud agent use?",
            "What benefits does this AI fraud/KYC agent provide?",
            "Walk me through the fraud workflow A→H.",
            "Where do sanction hits appear for the borrower?",
            "How can I rerun the fraud rules for this application?",
            "What does the privacy scrub remove?",
            "How do I export the KYC audit packet?",
            "How is the fraud risk score calculated?",
            "Can the agent anonymize documents before sharing?",
            "Where do I see verification status by stage?",
            "How do I hand off a case to human review?",
            "How do I refresh watchlist data?",
        ],
    },
    "chatbot": {
        "label": "🤖 Chatbot Ops",
        "page_id": "chatbot_assistant",
        "context": {"agent_type": "chatbot", "stage": "testing"},
        "faqs": [
            "How does the chatbot assistant work behind the scenes?",
            "What are the steps from ingestion → retrieval → reply?",
            "Define lexical terms like retrieved snippet, agent_type, context_summary.",
            "What inputs and outputs does the chatbot endpoint expect?",
            "What are the benefits of using this AI chatbot with local RAG?",
            "What data sources are indexed in the chatbot?",
            "How do I refresh the local RAG store?",
            "Explain how the chatbot answers Unified Risk questions.",
            "How do I switch personas (credit, asset, fraud)?",
            "Where are chat logs stored?",
            "Can I push chatbot answers into a report?",
            "How do I update the FAQ entries?",
            "How do I reset the embeddings cache?",
            "How do I test from the command line?",
            "How can I add more CSV sources?",
        ],
    },
}

st.set_page_config(
    page_title="Chatbot Assistant — Preview",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_theme()

st.markdown(
    """
    <style>
    [data-testid="stSidebar"], section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="stAppViewContainer"] { margin-left: 0 !important; padding-left: 0 !important; }
    .chatbot-nav {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-bottom: 1rem;
    }
    .chatbot-nav button {
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _launch_page(target: str):
    mapping = {
        "asset": "pages/asset_appraisal.py",
        "credit": "pages/credit_appraisal.py",
        "anti_fraud": "pages/anti_fraud_kyc.py",
        "unified": "pages/unified_risk.py",
        "agents": "app.py",
    }
    path = mapping.get(target)
    if not path:
        return
    try:
        st.switch_page(path)
    except Exception:
        pass


nav_cols = st.columns([1, 1, 1, 1, 1])
with nav_cols[0]:
    if st.button("🏠 Home", use_container_width=True):
        _launch_page("agents")
with nav_cols[1]:
    if st.button("🧩 Unified", use_container_width=True):
        _launch_page("unified")
with nav_cols[2]:
    if st.button("💳 Credit", use_container_width=True):
        _launch_page("credit")
with nav_cols[3]:
    if st.button("🏦 Asset", use_container_width=True):
        _launch_page("asset")
with nav_cols[4]:
    if st.button("🛡️ Anti-Fraud", use_container_width=True):
        _launch_page("anti_fraud")

_, theme_col = st.columns([5, 1])
with theme_col:
    render_theme_toggle(key="chatbot_theme_toggle")

st.title("💬 Chatbot Assistant (Preview)")
st.caption("Context-aware copilot that stays in sync with local RAG + agent blueprints.")

st.markdown(
    """
    ### 🧠 What it does today
    - Answers FAQs about every agent blueprint (credit, asset, anti-fraud, unified risk).
    - Surfaces ingestion status and signals if the local vector store is stale.
    - Streams reasoning steps so operators can audit every suggestion.

    ### 🛣️ Roadmap
    1. Multi-turn workflows so the chatbot can kick off asset/credit decisions directly.
    2. Inline analytics cards powered by the same sentence-transformer embeddings.
    3. Agent-to-agent orchestration so this copilot can dispatch work to the others.

    ### ✅ Try it out
    - Seed the local RAG store with `seed_local_rag_agent_docs.py`.
    - Ask *“How does the asset appraisal agent price farm equipment?”*
    - Run `/refresh_rag` from the chat sidebar to pull the latest code comments into memory.
    """
)

st.success("Preview ready — wire this page into the nav once the full chat stack ships.")

st.markdown("---")
st.subheader("Chatbot Test Bench")

left_col, right_col = st.columns([1, 1])

st.session_state.setdefault("chatbot_test_runs", [])
st.session_state.setdefault("chatbot_selected_role", "credit")

with left_col:
    st.subheader("Role & Shortcuts")
    role_options = list(ROLE_CONFIG.keys())
    default_role = st.session_state.get("chatbot_selected_role", "credit")
    role_key = ROLE_CONFIG.get(default_role, ROLE_CONFIG[role_options[0]])
    selected_role = st.selectbox(
        "Choose assistant persona",
        role_options,
        index=role_options.index(default_role) if default_role in role_options else 0,
        format_func=lambda key: ROLE_CONFIG[key]["label"],
    )
    st.session_state["chatbot_selected_role"] = selected_role
    role_key = ROLE_CONFIG[selected_role]

    st.markdown(
        """
        **How to test**
        - Paste FAQs or operator questions.
        - Reference agent files (`credit_appraisal.py`, `asset_appraisal.py`, etc.).
        - Ask follow ups like *"Show me the fraud workflow"*.
        - Responses on the right come directly from the local `/v1/chat` endpoint.
        """
    )
    st.info("⚙️ Uses local embeddings + CSV fallback. Ensure the API server is running on port 8090.")

    st.markdown("**Starter FAQs**")
    faqs: List[str] = role_key.get("faqs", [])
    for idx, question in enumerate(faqs):
        if st.button(question, key=f"faq_{selected_role}_{idx}"):
            st.session_state["chatbot_test_prompt"] = question
            st.rerun()

with right_col:
    with st.form("chatbot_test_form"):
        prompt = st.text_area(
            "Prompt",
            height=320,
            placeholder="e.g. Explain how the Unified Risk agent combines fraud + credit",
            key="chatbot_test_prompt",
        )
        submitted = st.form_submit_button("Send", use_container_width=True)

    reply_box = st.empty()
    if submitted:
        trimmed = prompt.strip()
        if not trimmed:
            st.warning("Enter a prompt before sending.")
        else:
            try:
                resp = requests.post(
                    f"{API_URL}/v1/chat",
                    json={
                        "message": trimmed,
                        "page_id": role_key["page_id"],
                        "context": role_key.get("context", {}),
                        "history": [
                            {"role": "user", "content": run["prompt"]}
                            for run in st.session_state["chatbot_test_runs"][-3:]
                        ],
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data: Dict[str, Any] = resp.json()
                st.session_state["chatbot_test_runs"].append(
                    {
                        "prompt": trimmed,
                        "reply": data.get("reply", "(No reply)"),
                        "retrieved": data.get("retrieved", []),
                        "timestamp": data.get("timestamp"),
                    }
                )
            except requests.RequestException as exc:
                st.error(f"Chat API error: {exc}")

    if st.session_state["chatbot_test_runs"]:
        last = st.session_state["chatbot_test_runs"][-1]
        reply_box.text_area(
            "Assistant Response",
            value=last["reply"],
            height=320,
        )
        with st.expander("Retrieved context", expanded=False):
            for idx, doc in enumerate(last.get("retrieved", []), start=1):
                st.markdown(f"**Match {idx}: {doc.get('title')}** (score={doc.get('score')})")
                st.write(doc.get("snippet"))
    else:
        reply_box.text_area(
            "Assistant Response",
            value="Awaiting first prompt…",
            height=320,
        )
