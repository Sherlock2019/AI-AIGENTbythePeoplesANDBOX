# ─────────────────────────────────────────────
# 🧩 utils/components.py — Shared UI Components
# Provides reusable building blocks for Streamlit pages
# ─────────────────────────────────────────────
import streamlit as st

def header(title: str, subtitle: str = ""):
    """
    Render a standardized section header with optional subtitle.
    """
    st.markdown(f"""
    <div style='padding: 0.5rem 0;'>
        <h2 style='color:#60a5fa;margin-bottom:0.2rem;'>{title}</h2>
        <p style='color:#94a3b8;margin-top:0;margin-bottom:0.8rem;font-size:0.95rem;'>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)

def divider(label: str = ""):
    """
    Render a horizontal divider, optionally labeled.
    """
    if label:
        st.markdown(f"""
        <hr style='border: 0; height: 1px; background: linear-gradient(90deg,#1e40af,#3b82f6,#1e40af);
                    margin: 1.5rem 0;'>
        <h4 style='text-align:center; color:#60a5fa;'>{label}</h4>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<hr style='border:0;height:1px;background:#334155;margin:1.5rem 0;'>",
                    unsafe_allow_html=True)

def banner(title: str, emoji: str = "🧠"):
    """
    Render a banner-like title box for main pages.
    """
    st.markdown(f"""
    <div style='background:linear-gradient(90deg,#1e293b,#0f172a);
                border-radius:14px;padding:1.2rem 1.5rem;
                box-shadow:0 4px 8px rgba(0,0,0,0.2);margin-bottom:1rem;'>
        <h1 style='font-size:2rem;color:#f8fafc;'>{emoji} {title}</h1>
    </div>
    """, unsafe_allow_html=True)
