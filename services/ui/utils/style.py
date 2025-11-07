# services/ui/utils/style.py
from __future__ import annotations
from datetime import datetime, timezone
import streamlit as st

# -------------- Theme --------------
def apply_theme(theme: str = "dark"):
    if theme == "light":
        bg      = "#ffffff"; text    = "#0f172a"; subtext = "#334155"
        card    = "#f8fafc"; border  = "#e2e8f0"; accent  = "#2563eb"; accent2 = "#22c55e"
        tab_bg  = "#eef2ff"; table_bg= "#ffffff"; table_head_bg = "#e2e8f0"; table_head_tx = "#0f172a"
    else:
        bg      = "#0E1117"; text    = "#f1f5f9"; subtext = "#93a4b8"
        card    = "#0f172a"; border  = "#334155"; accent  = "#3b82f6"; accent2 = "#22c55e"
        tab_bg  = "#111418"; table_bg= "#0f172a"; table_head_bg = "#1e293b"; table_head_tx = "#93c5fd"

    st.markdown(f"""
    <style>
      .stApp {{ background:{bg}!important; color:{text}!important; }}
      .stCaption, .stMarkdown p, .stMarkdown li {{ color:{subtext}!important; }}
      .stButton>button {{
        background-color:{accent}!important; color:#fff!important; border-radius:8px!important;
        font-weight:600!important; border:1px solid {border}!important;
      }}
      .stButton>button:hover {{ filter:brightness(0.95); }}
      .stTabs [data-baseweb="tab-list"] button {{
        color:{text}!important; background:{tab_bg}!important; border-radius:10px!important;
        margin-right:4px!important; border:1px solid {border}!important;
      }}
      .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
        background-color:{accent}!important; color:#fff!important;
      }}
      [data-testid="stDataFrame"] {{
        background-color:{table_bg}!important; color:{text}!important; border-radius:10px!important;
        border:1px solid {border}!important; box-shadow:0 4px 18px rgba(0,0,0,0.2)!important;
      }}
      [data-testid="stDataFrame"] thead tr th {{
        background:{table_head_bg}!important; color:{table_head_tx}!important; font-weight:700!important;
        border-bottom:2px solid {accent}!important;
      }}
    </style>
    """, unsafe_allow_html=True)

def ensure_keys():
    ss = st.session_state
    ss.setdefault("stage", "landing")
    ss.setdefault("theme", "dark")
    ss.setdefault("ui_theme", ss["theme"])  # keep legacy key in sync
    ss.setdefault("credit_logged_in", False)
    ss.setdefault("credit_stage", "login")
    ss.setdefault("user_info", {"name": "", "email": "", "flagged": False,
                                "timestamp": datetime.now(timezone.utc).isoformat()})

def sync_theme(new_is_dark: bool):
    new_theme = "dark" if new_is_dark else "light"
    if new_theme != st.session_state.get("theme"):
        st.session_state["theme"] = new_theme
        st.session_state["ui_theme"] = new_theme
        apply_theme(new_theme)

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
        is_dark = (ss.get("theme", "dark") == "dark")
        new_is_dark = st.toggle("🌙 Dark mode", value=is_dark, key="ui_theme_toggle", help="Switch theme")
        sync_theme(new_is_dark)

    st.markdown("---")
