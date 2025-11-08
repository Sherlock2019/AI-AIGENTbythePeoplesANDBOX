# ─────────────────────────────────────────────
# 🌗 UNIVERSAL THEME MANAGER — macOS style
# Shared across all agents
# ─────────────────────────────────────────────
import streamlit as st

# Initialize global theme once
if "ui_theme" not in st.session_state:
    st.session_state["ui_theme"] = "dark"

# ─────────────────────────────────────────────
# 🎨 MAC-INSPIRED COLOR PALETTES
# ─────────────────────────────────────────────
PALETTE = {
    "light": {
        "bg": "#f5f7fa",
        "text": "#0f172a",
        "subtext": "#334155",
        "card": "#ffffff",
        "border": "#d1d5db",
        "accent": "#007aff",
        "accent2": "#34c759",
        "tab_bg": "#f1f5f9",
        "table_bg": "#ffffff",
        "table_head_bg": "#e5e7eb",
        "table_head_tx": "#111827",
        "shadow": "0 2px 12px rgba(0,0,0,0.1)",
    },
    "dark": {
        "bg": "#0b1220",
        "text": "#f8fafc",
        "subtext": "#9ca3af",
        "card": "#0f172a",
        "border": "#1e3a8a",
        "accent": "#0a84ff",
        "accent2": "#30d158",
        "tab_bg": "#111827",
        "table_bg": "#0f172a",
        "table_head_bg": "#1e3a8a",
        "table_head_tx": "#e5e7eb",
        "shadow": "0 2px 14px rgba(0,0,0,0.6)",
    },
}


# ─────────────────────────────────────────────
# 💄 APPLY THEME (injects CSS)
# ─────────────────────────────────────────────
def apply_theme(theme: str = "dark"):
    pal = PALETTE.get(theme, PALETTE["dark"])

    st.markdown(
        f"""
        <style>
        html, body, [class*="stAppViewContainer"], .stApp {{
            background: {pal['bg']} !important;
            color: {pal['text']} !important;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif;
        }}

        h1,h2,h3,h4,h5,h6 {{
            color: {pal['text']} !important;
            font-weight: 700 !important;
            letter-spacing: -0.5px;
        }}

        /* Card sections */
        .stCard, .stContainer {{
            background: {pal['card']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 14px !important;
            box-shadow: {pal['shadow']} !important;
            padding: 0.8rem 1rem !important;
        }}

        /* Buttons */
        .stButton>button {{
            background: {pal['accent']} !important;
            color: #fff !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            border: none !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
            transition: all 0.2s ease-in-out;
        }}
        .stButton>button:hover {{
            filter: brightness(1.1);
            transform: translateY(-1px);
        }}

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] button {{
            background: {pal['tab_bg']} !important;
            color: {pal['text']} !important;
            border-radius: 8px !important;
            border: 1px solid {pal['border']} !important;
            margin-right: 6px !important;
        }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
            background: {pal['accent']} !important;
            color: #fff !important;
        }}

        /* DataFrame tables */
        [data-testid="stDataFrame"] {{
            background: {pal['table_bg']} !important;
            border: 1px solid {pal['border']} !important;
            border-radius: 10px !important;
            box-shadow: {pal['shadow']} inset !important;
        }}
        [data-testid="stDataFrame"] thead tr th {{
            background: {pal['table_head_bg']} !important;
            color: {pal['table_head_tx']} !important;
            font-weight: 600 !important;
            border-bottom: 2px solid {pal['accent']} !important;
        }}
        [data-testid="stDataFrame"] tbody td {{
            color: {pal['text']} !important;
            border-top: 1px solid {pal['border']} !important;
        }}

        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background: {pal['card']} !important;
            border-right: 1px solid {pal['border']} !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: {pal['text']} !important;
        }}

        hr {{
            border-color: {pal['border']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# 🚀 INIT THEME — shared toggle for all agents
# ─────────────────────────────────────────────
def init_theme():
    theme = st.session_state.get("ui_theme", "dark")
    apply_theme(theme)

    # Sidebar switch shared across all agents
    with st.sidebar:
        st.markdown("### 🌗 Theme Mode")
        toggle = st.toggle(
            "☀️ Day / 🌙 Night Mode",
            value=(theme == "dark"),
            key="global_theme_toggle",
        )

    new_theme = "dark" if toggle else "light"
    if new_theme != theme:
        st.session_state["ui_theme"] = new_theme
        apply_theme(new_theme)
        st.rerun()
