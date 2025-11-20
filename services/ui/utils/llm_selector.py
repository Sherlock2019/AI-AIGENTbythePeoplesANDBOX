from __future__ import annotations

import sys
import yaml
from pathlib import Path
from typing import Dict, Optional

import streamlit as st

from services.common.llm_profiles_loader import get_llm_profiles

# Ensure project root is in Python path for data module imports
try:
    _PROJECT_ROOT = Path(__file__).resolve().parents[3]  # services/ui/utils -> project root
except NameError:
    # Fallback if __file__ is not available (shouldn't happen in normal execution)
    _PROJECT_ROOT = Path.cwd()
_PROJECT_ROOT_STR = str(_PROJECT_ROOT.resolve())
if _PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_STR)

model_full = get_llm_profiles()


def _load_agent_presets() -> Optional[Dict]:
    """Load agent model presets from config file."""
    try:
        config_path = _PROJECT_ROOT / "config" / "agent_model_presets.yaml"
        if config_path.exists():
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
    except Exception:
        pass
    return None


def _get_recommended_llm_for_context(context: str) -> Optional[str]:
    """Get recommended LLM model value for a given agent context."""
    presets = _load_agent_presets()
    if not presets or "llm_models" not in presets:
        return None
    
    llm_config = presets.get("llm_models", {})
    agent_config = llm_config.get(context)
    
    if not agent_config:
        return None
    
    # Return primary model, or fallback if primary not available
    primary = agent_config.get("primary")
    if primary:
        # Check if primary model exists in model_full
        if any(entry["value"] == primary for entry in model_full):
            return primary
    
    # Try fallback
    fallback = agent_config.get("fallback")
    if fallback:
        if any(entry["value"] == fallback for entry in model_full):
            return fallback
    
    return None


def render_llm_selector(context: str = "narratives") -> Dict[str, str]:
    """Shared LLM selector with consistent heading + multiline entries.
    
    Automatically preselects recommended model based on agent context.
    
    Returns the selected entry dict (model, type, gpu, notes, value).
    """
    st.markdown(
        "<h1 style='font-size:2.2rem;font-weight:700;'>🔥 Local/HF LLM (used for narratives/explanations)</h1>",
        unsafe_allow_html=True,
    )

    options = [
        f"{entry['model']} — {entry['type']} — GPU: {entry['gpu']}\nNotes: {entry['notes']}"
        for entry in model_full
    ]
    session_value_key = f"llm_{context}_value"
    session_label_key = f"llm_{context}_label"
    
    # Get recommended model for this context
    recommended_value = _get_recommended_llm_for_context(context)
    
    # Priority: saved value > recommended > first model
    saved_value = st.session_state.get(session_value_key)
    if not saved_value and recommended_value:
        saved_value = recommended_value
        st.session_state[session_value_key] = recommended_value
        # Find and set label too
        for entry in model_full:
            if entry["value"] == recommended_value:
                st.session_state[session_label_key] = entry["model"]
                break
    
    if not saved_value:
        saved_value = model_full[0]["value"]
    
    default_index = next(
        (idx for idx, entry in enumerate(model_full) if entry["value"] == saved_value),
        0,
    )
    
    # Show recommendation badge if using recommended model
    if recommended_value and saved_value == recommended_value:
        st.info(f"✅ **Recommended for {context.replace('_', ' ')}**: {recommended_value} (auto-selected)", icon="⭐")
    
    selection = st.selectbox(
        "Local LLM",
        options,
        index=default_index,
        key=f"{session_value_key}_select",
        label_visibility="collapsed",
    )
    selected_index = options.index(selection)
    selected_entry = model_full[selected_index]
    st.session_state[session_value_key] = selected_entry["value"]
    st.session_state[session_label_key] = selected_entry["model"]
    return selected_entry
