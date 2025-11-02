# ─────────────────────────────────────────────
# 🎨 utils/theme.py — Global Dark Theme Styling
# Shared by all Streamlit UIs (Landing, Credit, Asset)
# ─────────────────────────────────────────────
import streamlit as st

def apply_dark_theme():
    """
    Apply Rackspace FAIR-style dark theme for consistency across all agents.
    This CSS overrides Streamlit defaults with modern typography and layout.
    """
    st.markdown("""
    <style>
    /* Global Layout */
    .block-container {padding: 1.5rem 3rem; max-width: 1600px;}
    body {background-color: #0e1117; color: #e6edf3;}

    /* Headings */
    h1, h2, h3, h4 {color: #e6edf3 !important; font-weight: 700;}
    h1 {font-size: 2.4rem;}
    h2 {font-size: 1.9rem;}
    h3 {font-size: 1.4rem;}

    /* Buttons */
    div[data-testid="stButton"] > button {
        background: linear-gradient(90deg, #2563eb, #1d4ed8);
        border: none;
        color: white;
        border-radius: 12px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        transition: 0.25s all ease-in-out;
    }
    div[data-testid="stButton"] > button:hover {
        background: linear-gradient(90deg, #1e40af, #1d4ed8);
        transform: translateY(-1px);
    }

    /* Tables & DataFrames */
    .stDataFrame, .dataframe {background: #111827 !important; color: #f1f5f9 !important;}
    .stMarkdown, .stText {color: #e6edf3;}
    th {background: #1f2937 !important; color: #f8fafc !important;}
    td {color: #e5e7eb !important;}

    /* Inputs */
    input, textarea, select {
        background-color: #1f2937 !important;
        color: #f8fafc !important;
        border-radius: 8px !important;
    }

    /* Tabs */
    [data-baseweb="tab-list"] {border-bottom: 2px solid #334155;}
    [data-baseweb="tab"] {
        font-weight: 700 !important;
        color: #cbd5e1 !important;
        font-size: 18px !important;
    }
    [aria-selected="true"][data-baseweb="tab"] {
        color: #3b82f6 !important;
        border-bottom: 3px solid #3b82f6 !important;
    }

    /* Metrics */
    [data-testid="stMetricLabel"] {color: #94a3b8 !important;}
    [data-testid="stMetricValue"] {color: #f8fafc !important; font-weight: 700;}
    </style>
    """, unsafe_allow_html=True)
