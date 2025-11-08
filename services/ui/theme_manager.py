#
# add this top of your  page 
#from services.ui.theme_manager import apply_theme
#apply_theme(st.session_state.get("ui_theme", "dark"))


import streamlit as st

def apply_theme(theme: str = "dark"):
    """Apply unified macOS-inspired dark/light theme across all agents."""

    # Define palette
    if theme == "dark":
        bg = "#0b0f16"
        text = "#f8fafc"
        subtext = "#e2e8f0"
        card = "#0f172a"
        accent = "#007aff"
        table_bg = "#0b1220"
        json_bg = "#0f172a"
        json_text = "#f8fafc"
    else:
        bg = "#f8fafc"
        text = "#0f172a"
        subtext = "#334155"
        card = "#ffffff"
        accent = "#007aff"
        table_bg = "#ffffff"
        json_bg = "#ffffff"
        json_text = "#000000"

    st.markdown(f"""
    <style>
    /* ===============================================
       🌙 / ☀️ GLOBAL THEME BASE
    =============================================== */
    html, body, [data-testid="stAppViewContainer"] {{
        background: radial-gradient(circle at 20% 20%, {bg}, {bg}) !important;
        color: {text} !important;
        font-family: "Inter","SF Pro Display","Segoe UI",system-ui,sans-serif !important;
    }}
    h1,h2,h3,h4,h5,h6 {{
        color: {text} !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }}
    p, li, label, span, div {{ color: {subtext} !important; }}
    small, .stCaption {{ color: #94a3b8 !important; }}
    a, a:link, a:visited {{ color: {accent} !important; }}
    a:hover {{ color: #60a5fa !important; text-decoration: underline; }}
    hr {{ border: none !important; height: 1px !important;
         background: linear-gradient(90deg,transparent,{accent},transparent) !important; }}

    /* ===============================================
       🧱 CONTAINERS
    =============================================== */
    .stMarkdown, .stContainer, .stAlert, [class*="stCard"], [class*="block-container"] {{
        background: {card} !important;
        border: 1px solid #1e3a8a33 !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4) !important;
    }}

    /* ===============================================
       🔘 BUTTONS
    =============================================== */
    button[kind="primary"], .stButton>button, .stDownloadButton>button {{
        background: linear-gradient(180deg,#007aff,#005ecb) !important;
        color: #ffffff !important;
        border: 1px solid #0051b8 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.25s ease-in-out !important;
    }}
    button[kind="primary"]:hover, .stButton>button:hover {{
        background: linear-gradient(180deg,#339dff,#006ae6) !important;
        transform: translateY(-1px) !important;
    }}

    /* ===============================================
       🧠 INPUTS / SELECTS
    =============================================== */
    .stTextInput>div>div>input,
    .stSelectbox>div>div>div,
    .stNumberInput input {{
        background: #111827 !important;
        color: {text} !important;
        border: 1px solid #1e3a8a !important;
        border-radius: 8px !important;
        padding: 6px 10px !important;
    }}
    ::placeholder {{ color: #9ca3af !important; }}

    /* ===============================================
       📊 TABLES
    =============================================== */
    [data-testid="stDataFrame"] {{
        background: {table_bg} !important;
        border: 1px solid #1e3a8a !important;
        border-radius: 12px !important;
        box-shadow: 0 0 12px rgba(0,0,0,0.6) inset;
    }}
    [data-testid="stDataFrame"] tbody tr:hover {{
        background: rgba(0,122,255,0.15) !important;
    }}

    /* ===============================================
       🧭 SIDEBAR
    =============================================== */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg,#0d1320,#060a12) !important;
        border-right: 1px solid #1e3a8a !important;
        color: {text} !important;
    }}

    /* ===============================================
       🧩 JSON / CODE BLOCK FIX — adaptive contrast
    =============================================== */
    [data-testid="stJson"], [data-testid="stCodeBlock"], pre, code {{
        background: {json_bg} !important;
        color: {json_text} !important;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        font-family: "SF Mono","Menlo","Consolas",monospace !important;
        font-size: 0.9rem !important;
        line-height: 1.45 !important;
    }}
    [data-testid="stJson"] .key     {{ color: {json_text} !important; font-weight: 600 !important; }}
    [data-testid="stJson"] .string  {{ color: #007aff !important; }}
    [data-testid="stJson"] .number  {{ color: #2563eb !important; }}
    [data-testid="stJson"] .boolean {{ color: #047857 !important; }}
    [data-testid="stJson"] .null    {{ color: #9f1239 !important; }}
    pre code, code {{
        color: {json_text} !important;
        background: {json_bg} !important;
        border-radius: 6px !important;
        padding: 0.6rem !important;
    }}
    </style>
    """, unsafe_allow_html=True)
