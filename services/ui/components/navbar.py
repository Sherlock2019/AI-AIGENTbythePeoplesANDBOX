import streamlit as st
import uuid
from services.ui.components.theme_manager import apply_theme

def render_nav_bar_app():
    """Universal macOS-style Navbar shared across agents."""
    ss = st.session_state
    unique_id = uuid.uuid4().hex[:6]

    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if st.button("🏠 Home", key=f"btn_home_{unique_id}"):
            ss["stage"] = "landing"; st.rerun()
    with c2:
        if st.button("🤖 Agents", key=f"btn_agents_{unique_id}"):
            ss["stage"] = "agents"; st.rerun()
    with c3:
        theme = ss.get("ui_theme", "dark")
        new_is_dark = st.toggle("🌙 Dark mode", value=(theme == "dark"), key=f"nav_toggle_{unique_id}")
        new_theme = "dark" if new_is_dark else "light"
        if new_theme != theme:
            ss["ui_theme"] = new_theme
            apply_theme(new_theme)
            st.rerun()

    st.markdown("---")
