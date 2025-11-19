import os
<<<<<<< HEAD
from typing import Dict, Any, List, Tuple
=======
from typing import Dict, Any, List
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2

import requests
import streamlit as st
from services.ui.theme_manager import apply_theme, render_theme_toggle

API_URL = os.getenv("API_URL", "http://localhost:8090")

<<<<<<< HEAD

def check_api_health(api_url: str) -> Tuple[bool, str]:
    """Check if the API server is reachable and healthy."""
    try:
        # Try health endpoint first
        health_url = f"{api_url.rstrip('/')}/health"
        resp = requests.get(health_url, timeout=3)
        if resp.status_code == 200:
            return True, "API is healthy"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to {api_url}. Make sure the API server is running."
    except requests.exceptions.Timeout:
        return False, f"API at {api_url} is not responding (timeout)."
    except Exception as e:
        return False, f"Error checking API: {str(e)}"
    return False, "API health check failed"

=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
ROLE_CONFIG: Dict[str, Dict[str, Any]] = {
    "credit": {
        "label": "💳 Credit Appraisal Agent",
        "page_id": "credit_appraisal",
        "context": {"agent_type": "credit", "stage": "credit_review"},
        "faqs": [
<<<<<<< HEAD
            "Explain the lexical definitions for PD, DTI, LTV, and other credit terms.",
            "How does the Credit Appraisal agent work end-to-end?",
            "What are the step-by-step stages in this agent?",
            "What inputs and outputs does the credit agent expect?",
            "How do I explain an approve vs review decision?",
            "What is probability of default (PD) and how is it calculated?",
            "How does the credit agent handle rule-based vs model-based decisions?",
            "What are the key metrics used in credit scoring (NDI, DTI, LTV)?",
            "How can I rerun Stage C - Credit AI Evaluation?",
            "What is the difference between classic rules and NDI-based rules?",
        ],
    },
    "credit_score": {
        "label": "💳 Credit Score Agent",
        "page_id": "credit_score",
        "context": {"agent_type": "credit_score", "stage": "scoring"},
        "faqs": [
            "How does the Credit Score agent calculate scores?",
            "What factors are used in credit score calculation?",
            "What is the scoring range (300-850)?",
            "How do I export credit scores to Credit Appraisal Agent?",
            "What data inputs does the Credit Score agent need?",
            "What is the difference between credit score and credit rating?",
            "How are payment history and credit utilization weighted?",
            "What credit score ranges indicate poor, fair, good, and excellent credit?",
            "How does credit history length affect the score?",
            "Can I see a breakdown of score components for a borrower?",
        ],
    },
    "legal_compliance": {
        "label": "⚖️ Legal & Compliance Agent",
        "page_id": "legal_compliance",
        "context": {"agent_type": "legal_compliance", "stage": "compliance_check"},
        "faqs": [
            "How does the Legal Compliance agent check sanctions?",
            "What is PEP (Politically Exposed Person) detection?",
            "How are licensing requirements verified?",
            "What compliance scores indicate approval readiness?",
            "How do compliance verdicts feed into Credit Appraisal?",
            "What sanctions lists does the agent check against?",
            "How does KYC risk scoring work in the compliance agent?",
            "What are the different compliance statuses (approved, review, rejected)?",
            "How are policy flags generated and what do they mean?",
            "What happens when a borrower fails compliance checks?",
=======
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
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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
<<<<<<< HEAD
            "How are AI-adjusted FMVs derived?",
            "What is the difference between FMV and realizable value?",
            "How does the agent handle different asset types (residential, commercial, industrial)?",
            "What factors affect the condition score and legal penalty?",
            "How are comparable properties (comps) used in valuation?",
            "What happens when an asset has encumbrances or liens?",
=======
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
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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
<<<<<<< HEAD
            "How can I rerun the fraud rules for this application?",
            "What is the fraud risk score range and what do the tiers mean?",
            "How does the agent detect identity fraud and document verification?",
            "What happens when a borrower fails KYC checks?",
            "How are sanction list hits processed and reported?",
            "What is the difference between low, medium, and high fraud risk tiers?",
        ],
    },
    "unified_risk": {
        "label": "🧩 Unified Risk Orchestration Agent",
        "page_id": "unified_risk",
        "context": {"agent_type": "unified_risk", "stage": "orchestration"},
        "faqs": [
            "How does the Unified Risk Orchestration agent work?",
            "What are the stages in unified risk decisioning?",
            "How does it combine asset, credit, and fraud signals?",
            "What is the final decision workflow?",
            "How do I export unified risk reports?",
            "What is the aggregated risk score and how is it calculated?",
            "How does the agent weight different risk factors (asset, credit, fraud)?",
            "What are the three risk tiers (low, medium, high) and their thresholds?",
            "How does the unified agent handle conflicting signals from different agents?",
            "What is the difference between approve, review, and reject recommendations?",
=======
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
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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
<<<<<<< HEAD
            "How do I upload files to enhance the RAG knowledge base?",
            "What file types are supported for RAG ingestion?",
            "How does the chatbot prioritize RAG data vs general knowledge?",
            "What is the difference between banking and non-banking question handling?",
            "How can I test the chatbot with different agent personas?",
=======
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
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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

<<<<<<< HEAD
st.success("✅ Preview available! Test the chatbot assistant below. You can select different agent personas and models to see how it responds.")
=======
st.success("Preview ready — wire this page into the nav once the full chat stack ships.")
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2

st.markdown("---")
st.subheader("Chatbot Test Bench")

left_col, right_col = st.columns([1, 1])

st.session_state.setdefault("chatbot_test_runs", [])
st.session_state.setdefault("chatbot_selected_role", "credit")
<<<<<<< HEAD
st.session_state.setdefault("chatbot_selected_model", None)
=======
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2

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
<<<<<<< HEAD
    
    # Model selection dropdown
    st.markdown("---")
    st.subheader("Model Selection")
    try:
        models_resp = requests.get(f"{API_URL}/v1/chat/models", timeout=5)
        if models_resp.status_code == 200:
            models_data = models_resp.json()
            available_models = models_data.get("models", [])
            recommended_models = models_data.get("recommended", ["phi3", "mistral", "gemma2:2b", "gemma2:9b"])
            default_model = models_data.get("default", "phi3")
            
            if available_models:
                # Get current selection or default
                current_model = st.session_state.get("chatbot_selected_model") or default_model
                if current_model not in available_models:
                    current_model = default_model
                
                # Show recommended models info
                recommended_available = [m for m in recommended_models if m in available_models]
                if recommended_available:
                    st.caption(f"💡 Recommended: {', '.join(recommended_available)}")
                
                selected_model = st.selectbox(
                    "Choose LLM model",
                    available_models,
                    index=available_models.index(current_model) if current_model in available_models else 0,
                    help="Select the Ollama model to use for generating responses. RAG DB is prioritized first, then model generic data. Recommended: phi3, mistral, gemma2:2b, gemma2:9b",
                )
                st.session_state["chatbot_selected_model"] = selected_model
                
                # Show model status
                if selected_model in recommended_models:
                    st.caption(f"✅ Using: {selected_model} (Recommended)")
                else:
                    st.caption(f"Using: {selected_model}")
                    
                # Show note if recommended models are missing
                missing_recommended = [m for m in recommended_models if m not in available_models]
                if missing_recommended:
                    st.info(f"💡 To use recommended models, pull them with: ollama pull {' '.join(missing_recommended)}")
            else:
                st.info("No models available. Using default.")
                st.session_state["chatbot_selected_model"] = default_model
        else:
            st.warning("Could not fetch available models. Using default.")
            st.session_state["chatbot_selected_model"] = None
    except Exception as exc:
        st.warning(f"Error fetching models: {exc}. Using default.")
        st.session_state["chatbot_selected_model"] = None

    # File upload for RAG database
    st.markdown("---")
    st.subheader("📤 Upload Files to RAG Database")
    st.caption("Upload files to enhance the chatbot's knowledge base. Supported: TXT, CSV, PDF, PY, HTML, MD, JSON, XML")
    
    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=["txt", "csv", "pdf", "py", "html", "md", "json", "xml"],
        help="Upload files to add to the RAG database. The chatbot will be able to answer questions based on these files.",
    )
    
    if uploaded_file is not None:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📄 Selected: **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")
        with col2:
            if st.button("Upload", key="upload_rag_file", use_container_width=True):
                try:
                    with st.spinner(f"Uploading and processing {uploaded_file.name}..."):
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        resp = requests.post(
                            f"{API_URL}/v1/chat/upload",
                            files=files,
                            data={"max_rows": 500},
                            timeout=300,  # 5 minutes for large files
                        )
                        resp.raise_for_status()
                        result = resp.json()
                        st.success(f"✅ {result.get('message', 'File uploaded successfully')}")
                        st.balloons()
                except requests.exceptions.Timeout:
                    st.error("⏱️ Upload timeout. File may be too large. Try a smaller file.")
                except requests.exceptions.HTTPError as exc:
                    error_detail = exc.response.json().get("detail", str(exc)) if hasattr(exc.response, 'json') else str(exc)
                    st.error(f"❌ Upload failed: {error_detail}")
                except Exception as exc:
                    st.error(f"❌ Upload error: {str(exc)}")
    
=======

>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
    st.markdown(
        """
        **How to test**
        - Paste FAQs or operator questions.
        - Reference agent files (`credit_appraisal.py`, `asset_appraisal.py`, etc.).
        - Ask follow ups like *"Show me the fraud workflow"*.
        - Responses on the right come directly from the local `/v1/chat` endpoint.
<<<<<<< HEAD
        - Upload files above to add them to the RAG database.
        """
    )
    # Check API health
    api_healthy, health_msg = check_api_health(API_URL)
    if api_healthy:
        st.success(f"✅ {health_msg}")
    else:
        st.error(f"❌ {health_msg}")
        st.info(f"💡 To start the API server, run: `./start.sh` or `uvicorn services.api.main:app --host 0.0.0.0 --port 8090`")
    
    st.info("⚙️ Uses local embeddings + CSV fallback. Ensure the API server is running on port 8090.")

=======
        """
    )
    st.info("⚙️ Uses local embeddings + CSV fallback. Ensure the API server is running on port 8090.")

    uploaded = st.file_uploader(
        "Upload file into RAG (csv/txt/md/html/pdf/json/py)",
        type=["csv", "txt", "md", "html", "htm", "json", "pdf", "py", "log", "doc", "docx"],
        key="chatbot_lab_upload",
        help="Any file will be chunked and embedded into the selected persona namespace.",
    )
    if uploaded is not None and st.button("Embed file", key="chatbot_lab_embed"):
        try:
            resp = requests.post(
                f"{API_URL}/chatbot/ingest/file",
                files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")},
                params={"agent_id": selected_role},
                timeout=120,
            )
            resp.raise_for_status()
            meta = resp.json()
            st.success(
                f"Embedded {meta.get('rows_indexed', 0)} chunks from {uploaded.name} "
                f"into `{selected_role}` namespace."
            )
        except requests.RequestException as exc:
            st.error(f"Upload failed: {exc}")

>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
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
<<<<<<< HEAD
            # Check API health before making request
            api_healthy, health_msg = check_api_health(API_URL)
            if not api_healthy:
                st.error(f"❌ Cannot send message: {health_msg}")
                st.info(f"💡 Please ensure the API server is running at {API_URL}")
            else:
                try:
                    # Include selected model in request
                    request_payload = {
=======
            try:
                resp = requests.post(
                    f"{API_URL}/v1/chat",
                    json={
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
                        "message": trimmed,
                        "page_id": role_key["page_id"],
                        "context": role_key.get("context", {}),
                        "history": [
                            {"role": "user", "content": run["prompt"]}
                            for run in st.session_state["chatbot_test_runs"][-3:]
                        ],
<<<<<<< HEAD
                    }
                    # Add model if selected
                    selected_model = st.session_state.get("chatbot_selected_model")
                    if selected_model:
                        request_payload["model"] = selected_model
                    
                    resp = requests.post(
                        f"{API_URL}/v1/chat",
                        json=request_payload,
                        timeout=60,  # Reduced - API now returns fast with fallback
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
                except requests.exceptions.ConnectionError as exc:
                    st.error(f"❌ Connection refused: Cannot connect to {API_URL}/v1/chat")
                    st.info(f"💡 The API server may not be running. Try: `./start.sh` or check if port 8090 is accessible.")
                    st.code(f"Error details: {str(exc)}", language="text")
                except requests.exceptions.Timeout:
                    st.error(f"⏱️ Request timeout: The API at {API_URL} took too long to respond.")
                except requests.exceptions.HTTPError as exc:
                    st.error(f"❌ HTTP error: {exc.response.status_code} - {exc.response.text[:200]}")
                except requests.RequestException as exc:
                    st.error(f"❌ Chat API error: {exc}")
                    st.info(f"💡 Check that the API server is running and accessible at {API_URL}")
=======
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
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2

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
