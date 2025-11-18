from __future__ import annotations

from typing import Dict

import streamlit as st

from data.llm_profiles import model_full


def render_llm_selector(context: str = "narratives") -> Dict[str, str]:
    """Shared LLM selector with consistent heading + multiline entries.

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
    saved_value = st.session_state.get(session_value_key, model_full[0]["value"])
    default_index = next(
        (idx for idx, entry in enumerate(model_full) if entry["value"] == saved_value),
        0,
    )
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
