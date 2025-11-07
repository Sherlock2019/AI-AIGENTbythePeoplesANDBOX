import streamlit as st

THEMES = {
    "Neon Blue": {
        "header": "linear-gradient(90deg, #00b4ff, #0077ff)",
        "accent": "#00ffff",
        "glow": "rgba(0,200,255,0.8)",
        "hover": "rgba(0,200,255,0.2)"
    },
    "Neon Pink": {
        "header": "linear-gradient(90deg, #ff66cc, #ff1a8c)",
        "accent": "#ff80d5",
        "glow": "rgba(255,105,180,0.8)",
        "hover": "rgba(255,105,180,0.25)"
    },
    "Neon Green": {
        "header": "linear-gradient(90deg, #00ff9d, #00cc66)",
        "accent": "#00ffb4",
        "glow": "rgba(0,255,180,0.8)",
        "hover": "rgba(0,255,180,0.25)"
    },
    "Classic White": {
        "header": "linear-gradient(90deg, #f9fafb, #e5e7eb)",
        "accent": "#111827",
        "glow": "rgba(180,180,180,0.4)",
        "hover": "rgba(220,220,220,0.25)"
    },
    "Neon Orange": {
        "header": "linear-gradient(90deg, #ff9966, #ff5e00)",
        "accent": "#ffb347",
        "glow": "rgba(255,150,80,0.8)",
        "hover": "rgba(255,180,120,0.25)"
    },
}

def apply_theme():
    theme_name = st.session_state.get("theme_choice", "Neon Blue")
    t = THEMES.get(theme_name, THEMES["Neon Blue"])

    st.markdown(f"""
    <style>
    @keyframes pulseAccent {{
        0% {{ box-shadow: 0 0 10px {t['glow']}, inset 0 0 10px {t['glow']}; }}
        50% {{ box-shadow: 0 0 40px {t['glow']}, inset 0 0 20px {t['glow']}; }}
        100% {{ box-shadow: 0 0 10px {t['glow']}, inset 0 0 10px {t['glow']}; }}
    }}

    .neon-frame {{
        border: 2px solid {t['accent']};
        border-radius: 20px;
        padding: 1.5rem;
        background: linear-gradient(180deg, #08111e 0%, #0f2035 100%);
        animation: pulseAccent 4s infinite ease-in-out;
        width: 85%;
        margin: 2rem auto;
        color: #e6f7ff;
        box-shadow: 0 0 40px {t['glow']}, inset 0 0 15px rgba(0,0,0,0.3);
    }}

    .neon-frame table {{
        width: 100%;
        border-collapse: collapse;
        border-radius: 10px;
        color: #fff !important;
        background-color: rgba(5,20,40,0.9);
        overflow: hidden;
    }}

    thead th {{
        background: {t['header']};
        color: #fff !important;
        font-size: 1.1rem;
        font-weight: 700;
        padding: 14px 18px;
        text-shadow: 0 0 10px {t['accent']};
        border-bottom: 2px solid {t['accent']};
    }}

    tbody td {{
        padding: 12px 18px;
        font-size: 1rem;
        border: 1px solid rgba(255,255,255,0.1);
    }}
    tbody tr:hover {{
        background-color: {t['hover']};
        transform: scale(1.002);
    }}
    a.launchbtn {{
        display: inline-block;
        text-decoration: none;
        color: #fff !important;
        font-weight: 700;
        padding: 8px 20px;
        border-radius: 8px;
        border: 1px solid {t['accent']};
        box-shadow: 0 0 12px {t['glow']}, inset 0 0 6px {t['glow']};
        transition: all 0.2s ease-in-out;
    }}
    a.launchbtn:hover {{
        box-shadow: 0 0 25px {t['accent']}, inset 0 0 10px {t['accent']};
        transform: translateY(-1px) scale(1.04);
    }}
    footer {{
        text-align:center;
        margin-top:2rem;
        color:{t['accent']};
        font-size:0.95rem;
        text-shadow:0 0 6px {t['glow']};
    }}
    </style>
    """, unsafe_allow_html=True)
