"""
HF Agent Inspector — Streamlit UI for Testing Agent Manager
-----------------------------------------------------------

Interactive interface for testing all agent tasks:
    - Generate
    - Summarize
    - QA
    - Embedding
    - Translate
    - Caption
    - Classify
"""

import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Optional

# Import theme and navigation
from services.ui.theme_manager import init_theme, render_theme_toggle
from services.ui.utils.style import render_nav_bar_app

# Initialize theme
init_theme()

# Page config
st.set_page_config(
    page_title="HF Agent Inspector",
    page_icon="🤖",
    layout="wide",
)

# Navigation bar and theme toggle
render_nav_bar_app()

# API endpoint
try:
    API_BASE_URL = st.secrets.get("API_URL", "http://localhost:8090")
except (AttributeError, FileNotFoundError, Exception):
    # Fallback to environment variable or default
    import os
    API_BASE_URL = os.getenv("API_URL", "http://localhost:8090")


def call_agent_api(task: str, payload: Dict[str, Any], engine: Optional[str] = None) -> Dict[str, Any]:
    """Call the agent manager API."""
    url = f"{API_BASE_URL}/agent/run"
    request_data = {
        "task": task,
        "payload": payload,
    }
    if engine:
        request_data["engine"] = engine

    try:
        response = requests.post(url, json=request_data, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e), "result": None, "source": "error"}


def get_health_status() -> Dict[str, Any]:
    """Get agent manager health status."""
    try:
        url = f"{API_BASE_URL}/agent/health"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Sidebar
st.sidebar.title("🤖 Agent Manager Inspector")
st.sidebar.markdown("---")

# Health status
with st.sidebar:
    st.subheader("📊 Status")
    health = get_health_status()
    if health.get("status") == "ok":
        st.success("✅ API Connected")
        st.json(health.get("models_loaded", {}))
    else:
        st.error(f"❌ API Error: {health.get('error', 'Unknown')}")

# Model selector
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Engine Selection")
engine = st.sidebar.selectbox(
    "Engine",
    ["auto", "local", "ollama", "hf_api"],
    help="Auto: Let system decide, Local: Use local model, Ollama: Use Ollama, HF API: Use HuggingFace API"
)

# Main content
st.title("🤖 HF Agent Inspector")
st.markdown("Test all agent tasks through the unified Agent Manager interface.")

# Task selector
task = st.selectbox(
    "Select Task",
    ["generate", "summarize", "qa", "embedding", "translate", "caption", "classify"],
    help="Choose the task you want to test"
)

st.markdown("---")

# Task-specific UI
if task == "generate":
    st.subheader("📝 Text Generation")
    prompt = st.text_area("Prompt", height=100, placeholder="Enter your prompt here...")
    max_tokens = st.slider("Max Tokens", 50, 2000, 200)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
    
    if st.button("Generate", type="primary"):
        if prompt:
            with st.spinner("Generating..."):
                start_time = time.time()
                result = call_agent_api(
                    "generate",
                    {
                        "prompt": prompt,
                        "max_new_tokens": max_tokens,
                        "temperature": temperature,
                    },
                    engine=None if engine == "auto" else engine
                )
                elapsed = time.time() - start_time
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
            else:
                st.success(f"✅ Generated in {result.get('latency', elapsed):.2f}s using {result.get('source', 'unknown')}")
                st.text_area("Result", result.get("result", ""), height=200)
                with st.expander("📊 Response Details"):
                    st.json(result)

elif task == "summarize":
    st.subheader("📄 Summarization")
    text = st.text_area("Text to Summarize", height=200, placeholder="Enter long text to summarize...")
    max_length = st.slider("Max Length", 50, 300, 150)
    min_length = st.slider("Min Length", 10, 100, 30)
    
    if st.button("Summarize", type="primary"):
        if text:
            with st.spinner("Summarizing..."):
                result = call_agent_api(
                    "summarize",
                    {
                        "text": text,
                        "max_length": max_length,
                        "min_length": min_length,
                    },
                    engine=None if engine == "auto" else engine
                )
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
            else:
                st.success(f"✅ Summarized in {result.get('latency', 0):.2f}s using {result.get('source', 'unknown')}")
                st.text_area("Summary", result.get("result", ""), height=150)
                with st.expander("📊 Response Details"):
                    st.json(result)

elif task == "qa":
    st.subheader("❓ Question Answering")
    question = st.text_input("Question", placeholder="What is your question?")
    context = st.text_area("Context", height=200, placeholder="Enter the context/document text...")
    
    if st.button("Answer", type="primary"):
        if question and context:
            with st.spinner("Answering..."):
                result = call_agent_api(
                    "qa",
                    {
                        "question": question,
                        "context": context,
                    },
                    engine=None if engine == "auto" else engine
                )
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
            else:
                st.success(f"✅ Answered in {result.get('latency', 0):.2f}s using {result.get('source', 'unknown')}")
                qa_result = result.get("result", {})
                if isinstance(qa_result, dict):
                    st.markdown(f"**Answer:** {qa_result.get('answer', 'N/A')}")
                    st.markdown(f"**Score:** {qa_result.get('score', 0):.3f}")
                else:
                    st.text_area("Answer", str(qa_result), height=100)
                with st.expander("📊 Response Details"):
                    st.json(result)

elif task == "embedding":
    st.subheader("🔢 Embeddings")
    text = st.text_area("Text to Embed", height=150, placeholder="Enter text to generate embeddings...")
    show_vector = st.checkbox("Show Full Vector", value=False)
    
    if st.button("Generate Embedding", type="primary"):
        if text:
            with st.spinner("Generating embedding..."):
                result = call_agent_api(
                    "embedding",
                    {"text": text},
                    engine=None if engine == "auto" else engine
                )
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
            else:
                embedding = result.get("result", [])
                st.success(f"✅ Generated embedding in {result.get('latency', 0):.2f}s using {result.get('source', 'unknown')}")
                st.metric("Vector Dimension", len(embedding) if isinstance(embedding, list) else "N/A")
                if show_vector:
                    st.code(json.dumps(embedding[:10] if len(embedding) > 10 else embedding, indent=2))
                else:
                    st.info(f"Vector preview (first 10 dims): {embedding[:10] if isinstance(embedding, list) and len(embedding) > 10 else embedding}")
                with st.expander("📊 Response Details"):
                    st.json(result)

elif task == "translate":
    st.subheader("🌐 Translation")
    text = st.text_area("Text to Translate", height=150, placeholder="Enter text to translate...")
    src_lang = st.selectbox("Source Language", ["en", "fr", "de", "es"], index=0)
    tgt_lang = st.selectbox("Target Language", ["fr", "en", "de", "es"], index=0)
    
    if st.button("Translate", type="primary"):
        if text:
            with st.spinner("Translating..."):
                result = call_agent_api(
                    "translate",
                    {
                        "text": text,
                        "src_lang": src_lang,
                        "tgt_lang": tgt_lang,
                    },
                    engine=None if engine == "auto" else engine
                )
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
            else:
                st.success(f"✅ Translated in {result.get('latency', 0):.2f}s using {result.get('source', 'unknown')}")
                st.text_area("Translation", result.get("result", ""), height=150)
                with st.expander("📊 Response Details"):
                    st.json(result)

elif task == "caption":
    st.subheader("🖼️ Image Captioning")
    st.info("Image captioning requires image upload. This feature needs image file handling.")
    image_url = st.text_input("Image URL", placeholder="Enter image URL or upload file...")
    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    
    if st.button("Generate Caption", type="primary"):
        if image_url or uploaded_file:
            with st.spinner("Generating caption..."):
                # Note: This is a simplified version. Full implementation would handle file uploads properly
                image_input = image_url or (uploaded_file.name if uploaded_file else None)
                if image_input:
                    result = call_agent_api(
                        "caption",
                        {"image": image_input},
                        engine=None if engine == "auto" else engine
                    )
                    
                    if result.get("error"):
                        st.error(f"Error: {result['error']}")
                    else:
                        st.success(f"✅ Caption generated in {result.get('latency', 0):.2f}s using {result.get('source', 'unknown')}")
                        st.text_area("Caption", result.get("result", ""), height=100)
                        with st.expander("📊 Response Details"):
                            st.json(result)
        else:
            st.warning("Please provide an image URL or upload a file")

elif task == "classify":
    st.subheader("🏷️ Classification (Sentiment Analysis)")
    text = st.text_area("Text to Classify", height=150, placeholder="Enter text to classify...")
    return_all = st.checkbox("Return All Scores", value=False)
    
    if st.button("Classify", type="primary"):
        if text:
            with st.spinner("Classifying..."):
                result = call_agent_api(
                    "classify",
                    {
                        "text": text,
                        "return_all_scores": return_all,
                    },
                    engine=None if engine == "auto" else engine
                )
            
            if result.get("error"):
                st.error(f"Error: {result['error']}")
            else:
                classification = result.get("result", {})
                st.success(f"✅ Classified in {result.get('latency', 0):.2f}s using {result.get('source', 'unknown')}")
                if isinstance(classification, dict):
                    st.markdown(f"**Label:** {classification.get('label', 'N/A')}")
                    st.markdown(f"**Score:** {classification.get('score', 0):.3f}")
                else:
                    st.json(classification)
                with st.expander("📊 Response Details"):
                    st.json(result)

# Footer
st.markdown("---")
st.markdown("### 📚 API Documentation")
st.code(f"""
POST {API_BASE_URL}/agent/run
{{
    "task": "generate",
    "engine": "auto",
    "payload": {{
        "prompt": "Hello world",
        "max_new_tokens": 200
    }}
}}
""", language="json")

st.markdown("### 🔗 Quick Links")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"[API Docs]({API_BASE_URL}/docs)")
with col2:
    st.markdown(f"[Health Check]({API_BASE_URL}/agent/health)")
with col3:
    st.markdown(f"[Models Status]({API_BASE_URL}/agent/models)")
