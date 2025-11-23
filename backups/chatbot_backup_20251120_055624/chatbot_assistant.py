import os
from datetime import datetime
from typing import Dict, Any, List, Tuple

import requests
import streamlit as st
from services.ui.theme_manager import apply_theme, render_theme_toggle
from services.ui.components.feedback import render_feedback_tab

API_URL = os.getenv("API_URL", "http://localhost:8090")


def check_api_health(api_url: str, timeout: int = 10) -> Tuple[bool, str]:
    """Check if the API server is reachable and healthy."""
    try:
        # Try health endpoint first
        health_url = f"{api_url.rstrip('/')}/health"
        resp = requests.get(health_url, timeout=timeout)
        if resp.status_code == 200:
            return True, "API is healthy"
    except requests.exceptions.ConnectionError:
        return False, f"Cannot connect to {api_url}. Make sure the API server is running."
    except requests.exceptions.Timeout:
        return False, f"API at {api_url} is not responding (timeout after {timeout}s). The server may be starting up or overloaded."
    except Exception as e:
        return False, f"Error checking API: {str(e)}"
    return False, "API health check failed"


ROLE_CONFIG: Dict[str, Dict[str, Any]] = {
    "credit": {
        "label": "💳 Credit Appraisal Agent",
        "page_id": "credit_appraisal",
        "context": {"agent_type": "credit", "stage": "credit_review"},
        "faqs": [
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
            "How are AI-adjusted FMVs derived?",
            "What is the difference between FMV and realizable value?",
            "How does the agent handle different asset types (residential, commercial, industrial)?",
            "What factors affect the condition score and legal penalty?",
            "How are comparable properties (comps) used in valuation?",
            "What happens when an asset has encumbrances or liens?",
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
            "How do I upload files to enhance the RAG knowledge base?",
            "What file types are supported for RAG ingestion?",
            "How does the chatbot prioritize RAG data vs general knowledge?",
            "What is the difference between banking and non-banking question handling?",
            "How can I test the chatbot with different agent personas?",
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
    .chat-response {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .chat-response pre {
        background: rgba(255,255,255,0.1);
        padding: 0.5rem;
        border-radius: 6px;
        overflow-x: auto;
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

st.title("💬 Chatbot Assistant")
st.caption("AI-powered assistant with RAG + LLM integration for beautiful, context-aware responses")

st.markdown(
    """
    ### 🧠 Features
    - **RAG-First**: Answers from your local knowledge base with semantic search
    - **LLM-Enhanced**: Beautiful, natural language responses powered by Ollama models
    - **Multi-Persona**: Switch between different agent contexts (credit, asset, fraud, etc.)
    - **File Upload**: Enhance knowledge base by uploading documents
    - **Real-time**: Fast responses with fallback mechanisms
    """
)

st.success("✅ Chatbot ready! Select a persona and model below, then start chatting.")

st.markdown("---")
st.subheader("Chatbot Test Bench")

left_col, right_col = st.columns([1, 1])

# Initialize session state
ss = st.session_state
ss.setdefault("chatbot_test_runs", [])
ss.setdefault("chatbot_selected_role", "credit")
ss.setdefault("chatbot_selected_model", None)

with left_col:
    st.subheader("Configuration")
    
    # Role selection
    role_options = list(ROLE_CONFIG.keys())
    default_role = ss.get("chatbot_selected_role", "credit")
    role_key = ROLE_CONFIG.get(default_role, ROLE_CONFIG[role_options[0]])
    selected_role = st.selectbox(
        "Choose assistant persona",
        role_options,
        index=role_options.index(default_role) if default_role in role_options else 0,
        format_func=lambda key: ROLE_CONFIG[key]["label"],
    )
    ss["chatbot_selected_role"] = selected_role
    role_key = ROLE_CONFIG[selected_role]
    
    # Model selection dropdown
    st.markdown("---")
    st.subheader("🤖 LLM Model Selection")
    
    # Use cached models if available and API is slow/unavailable
    cached_models = ss.get("chatbot_cached_models")
    cached_models_timestamp = ss.get("chatbot_cached_models_timestamp", 0)
    use_cache = cached_models and (datetime.now().timestamp() - cached_models_timestamp < 300)  # Cache for 5 minutes
    
    if use_cache:
        models_data = cached_models
        st.caption("ℹ️ Using cached model list. Click refresh to update.")
    else:
        try:
            with st.spinner("Fetching available models..."):
                models_resp = requests.get(f"{API_URL}/v1/chat/models", timeout=30)  # Increased timeout to 30s
                if models_resp.status_code == 200:
                    models_data = models_resp.json()
                    # Cache the models
                    ss["chatbot_cached_models"] = models_data
                    ss["chatbot_cached_models_timestamp"] = datetime.now().timestamp()
                else:
                    st.warning("Could not fetch available models. Using cached or default.")
                    models_data = cached_models if cached_models else None
        except requests.exceptions.Timeout:
            st.warning("⏱️ Model fetch timed out. Using cached models or default.")
            models_data = cached_models if cached_models else None
        except requests.exceptions.ConnectionError:
            st.warning("❌ Cannot connect to API. Using cached models or default.")
            models_data = cached_models if cached_models else None
        except Exception as exc:
            st.warning(f"Error fetching models: {exc}. Using cached or default.")
            models_data = cached_models if cached_models else None
    
    # Refresh button
    if st.button("🔄 Refresh Model List", use_container_width=True, help="Refresh the list of available models from the API"):
        if "chatbot_cached_models" in ss:
            del ss["chatbot_cached_models"]
        if "chatbot_cached_models_timestamp" in ss:
            del ss["chatbot_cached_models_timestamp"]
        st.rerun()
    
    if models_data:
        available_models = models_data.get("models", [])
        recommended_models = models_data.get("recommended", ["phi3", "mistral", "gemma2:2b", "gemma2:9b"])
        default_model = models_data.get("default", "phi3")
        
        if available_models:
            # Get current selection or default
            current_model = ss.get("chatbot_selected_model") or default_model
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
                help="Select the Ollama model for generating responses. RAG data is prioritized, then model knowledge.",
            )
            ss["chatbot_selected_model"] = selected_model
            
            # Show model status
            if selected_model in recommended_models:
                st.success(f"✅ Using: {selected_model} (Recommended)")
            else:
                st.info(f"Using: {selected_model}")
                
            # Show note if recommended models are missing
            missing_recommended = [m for m in recommended_models if m not in available_models]
            if missing_recommended:
                st.info(f"💡 To use recommended models: `ollama pull {' '.join(missing_recommended)}`")
        else:
            st.info("No models available. Using default.")
            ss["chatbot_selected_model"] = default_model
    else:
        # Fallback to default model
        default_model = "phi3"
        st.warning("⚠️ Could not fetch models. Using default model: phi3")
        st.info("💡 Ensure the API server is running: `./start.sh` or `uvicorn services.api.main:app --host 0.0.0.0 --port 8090`")
        ss["chatbot_selected_model"] = default_model

    # File upload for RAG database
    st.markdown("---")
    st.subheader("📤 Upload Files to RAG Database")
    st.caption("Enhance the chatbot's knowledge base with your documents")
    
    uploaded_file = st.file_uploader(
        "Choose a file to upload",
        type=["txt", "csv", "pdf", "py", "html", "md", "json", "xml"],
        help="Upload files to add to the RAG database. The chatbot will answer questions based on these files.",
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
                            timeout=300,
                        )
                        resp.raise_for_status()
                        result = resp.json()
                        st.success(f"✅ {result.get('message', 'File uploaded successfully')}")
                        st.balloons()
                except requests.exceptions.Timeout:
                    st.error("⏱️ Upload timeout. File may be too large.")
                except requests.exceptions.HTTPError as exc:
                    error_detail = exc.response.json().get("detail", str(exc)) if hasattr(exc.response, 'json') else str(exc)
                    st.error(f"❌ Upload failed: {error_detail}")
                except Exception as exc:
                    st.error(f"❌ Upload error: {str(exc)}")
    
    st.markdown("---")
    st.markdown(
        """
        **How to test**
        - Select a persona and LLM model above
        - Paste questions or use FAQs below
        - Responses combine RAG data + LLM knowledge
        - Upload files to enhance the knowledge base
        """
    )
    
    # Check API health with increased timeout
    api_healthy, health_msg = check_api_health(API_URL, timeout=15)
    if api_healthy:
        st.success(f"✅ {health_msg}")
    else:
        st.warning(f"⚠️ {health_msg}")
        with st.expander("💡 How to start the API server", expanded=False):
            st.code("""
# Option 1: Use the startup script
./start.sh

# Option 2: Start manually
cd Hugmesandbox
source .venv/bin/activate
uvicorn services.api.main:app --host 0.0.0.0 --port 8090 --reload

# Option 3: Check if API is running on a different port
# Check environment variable: echo $API_URL
            """, language="bash")
    
    st.info("⚙️ Uses local embeddings + CSV fallback. The chatbot will work with cached models if the API is temporarily unavailable.")

    st.markdown("---")
    st.markdown("**Starter FAQs**")
    faqs: List[str] = role_key.get("faqs", [])
    for idx, question in enumerate(faqs):
        if st.button(question, key=f"faq_{selected_role}_{idx}", use_container_width=True):
            ss["chatbot_test_prompt"] = question
            st.rerun()

with right_col:
    with st.form("chatbot_test_form"):
        prompt = st.text_area(
            "Your Question",
            height=200,
            placeholder="e.g. Explain how the Unified Risk agent combines fraud + credit signals",
            key="chatbot_test_prompt",
        )
        submitted = st.form_submit_button("💬 Send Message", use_container_width=True)

    reply_box = st.empty()
    if submitted:
        trimmed = prompt.strip()
        if not trimmed:
            st.warning("Enter a prompt before sending.")
        else:
            # Check API health before making request (with longer timeout)
            api_healthy, health_msg = check_api_health(API_URL, timeout=15)
            if not api_healthy:
                st.warning(f"⚠️ API may be slow or unavailable: {health_msg}")
                st.info("💡 The request will still be attempted. If it fails, check the API server status above.")
            
            # Try to send anyway (API might be slow but still working)
            try:
                with st.spinner("🤔 Thinking..."):
                    # Include selected model in request
                    request_payload = {
                        "message": trimmed,
                        "page_id": role_key["page_id"],
                        "context": role_key.get("context", {}),
                        "history": [
                            {"role": "user", "content": run["prompt"]}
                            for run in ss["chatbot_test_runs"][-3:]
                        ],
                    }
                    # Add model if selected
                    selected_model = ss.get("chatbot_selected_model")
                    if selected_model:
                        request_payload["model"] = selected_model
                    
                    resp = requests.post(
                        f"{API_URL}/v1/chat",
                        json=request_payload,
                        timeout=120,  # Increased timeout to 120s for slow responses
                    )
                    resp.raise_for_status()
                    data: Dict[str, Any] = resp.json()
                    
                    # Store the response
                    ss["chatbot_test_runs"].append(
                        {
                            "prompt": trimmed,
                            "reply": data.get("reply", "(No reply)"),
                            "retrieved": data.get("retrieved", []),
                            "timestamp": data.get("timestamp"),
                            "model": selected_model or "default",
                        }
                    )
            except requests.exceptions.ConnectionError as exc:
                st.error(f"❌ Connection refused: Cannot connect to {API_URL}/v1/chat")
                st.info(f"💡 The API server may not be running. Try: `./start.sh`")
            except requests.exceptions.Timeout:
                st.error(f"⏱️ Request timeout: The API took too long to respond (120s). The server may be overloaded or processing a large request.")
                st.info("💡 Try again in a moment, or check if the API server is running properly.")
            except requests.exceptions.HTTPError as exc:
                st.error(f"❌ HTTP error: {exc.response.status_code} - {exc.response.text[:200]}")
            except requests.RequestException as exc:
                st.error(f"❌ Chat API error: {exc}")
                st.info(f"💡 Check that the API server is running at {API_URL}")
    
    # Display response (outside form, but in right column)
    if ss["chatbot_test_runs"]:
        last = ss["chatbot_test_runs"][-1]
        
        # Display response with beautiful formatting
        reply_text = last["reply"]
        model_used = last.get("model", "default")
        
        st.markdown("### 💬 Assistant Response")
        st.markdown(f"**Model:** {model_used}")
        st.markdown(f"**Response:**")
        st.markdown(f'<div class="chat-response">{reply_text}</div>', unsafe_allow_html=True)
        
        # Show retrieved context
        retrieved = last.get("retrieved", [])
        if retrieved:
            with st.expander(f"📚 Retrieved Context ({len(retrieved)} sources)", expanded=False):
                for idx, doc in enumerate(retrieved, start=1):
                    score = doc.get("score", 0)
                    title = doc.get("title", "Unknown")
                    snippet = doc.get("snippet", "")
                    
                    st.markdown(f"**Source {idx}: {title}** (relevance: {score:.2f})")
                    st.markdown(f"```\n{snippet[:300]}...\n```")
                    st.markdown("---")
    else:
        st.markdown("### 💬 Assistant Response")
        st.info("👋 Ask a question to get started! Select a persona and model, then type your question above.")

st.markdown("---")
st.markdown("## 🗣️ Feedback & Feature Requests")
render_feedback_tab("💬 Chatbot Assistant")
