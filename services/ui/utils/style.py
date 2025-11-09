# services/ui/utils/style.py
from __future__ import annotations
from datetime import datetime, timezone
import streamlit as st

from services.ui.theme_manager import (
    apply_theme as apply_global_theme,
    ensure_theme,
    get_theme,
    render_theme_toggle,
    set_theme,
)


# -------------- Theme --------------
def apply_theme(theme: str = "dark"):
    """
    Compatibility wrapper around services.ui.theme_manager.apply_theme.

    Pages that still import this helper will automatically pick up the
    unified palette, while the legacy CSS snippet below remains available
    if you ever want to revert to the old styling.
    """
    return apply_global_theme(theme)

def ensure_keys():
    ss = st.session_state
    ensure_theme("dark")
    ss.setdefault("stage", "landing")
    ss.setdefault("credit_logged_in", False)
    ss.setdefault("credit_stage", "login")
    ss.setdefault(
        "user_info",
        {
            "name": "",
            "email": "",
            "flagged": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

def sync_theme(new_is_dark: bool):
    """Legacy hook that keeps shared theme state in sync with a boolean toggle."""
    desired = "dark" if new_is_dark else "light"
    if desired != get_theme():
        set_theme(desired)
        apply_global_theme(desired)
        return True
    return False

def render_nav_bar_app():
    """Home / Agents buttons + theme toggle identical across pages."""
    ss = st.session_state
    stage = ss.get("stage", "landing")
    show_home   = stage in ("agents", "credit_agent", "asset_agent")
    show_agents = stage not in ("landing", "agents")

    c1, c2, c3 = st.columns([1, 1, 2.5])
    with c1:
        if show_home and st.button("🏠 Back to Home", key=f"btn_home_{stage}"):
            ss["stage"] = "landing"
            try:
                st.switch_page("app.py")
            except Exception:
                st.rerun()

    with c2:
        if show_agents and st.button("🤖 Back to Agents", key=f"btn_agents_{stage}"):
            ss["stage"] = "agents"
            try:
                st.switch_page("app.py")
            except Exception:
                st.rerun()

    with c3:
        render_theme_toggle(
            label="🌗 Dark mode",
            key="utils_style_nav_toggle",
            help="Switch theme",
        )

    st.markdown("---")


# --- Legacy theme snippet (kept for optional reuse) --------------------------
LEGACY_STYLE_THEME_CSS = """
<style>
  .stApp { background:#0E1117!important; color:#f1f5f9!important; }
  .stCaption, .stMarkdown p, .stMarkdown li { color:#93a4b8!important; }
  .stButton>button {
    background-color:#3b82f6!important; color:#fff!important; border-radius:8px!important;
    font-weight:600!important; border:1px solid #334155!important;
  }
  .stButton>button:hover { filter:brightness(0.95); }
  .stTabs [data-baseweb="tab-list"] button {
    color:#f1f5f9!important; background:#111418!important; border-radius:10px!important;
    margin-right:4px!important; border:1px solid #334155!important;
  }
  .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    background-color:#3b82f6!important; color:#fff!important;
  }
  [data-testid="stDataFrame"] {
    background-color:#0f172a!important; color:#f1f5f9!important; border-radius:10px!important;
    border:1px solid #334155!important; box-shadow:0 4px 18px rgba(0,0,0,0.2)!important;
  }
  [data-testid="stDataFrame"] thead tr th {
    background:#1e293b!important; color:#93c5fd!important; font-weight:700!important;
    border-bottom:2px solid #3b82f6!important;
  }
</style>
"""
