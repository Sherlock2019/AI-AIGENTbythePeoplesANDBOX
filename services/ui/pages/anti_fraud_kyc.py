"""Standalone Streamlit page for the Anti-Fraud & KYC agent."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
st.set_page_config(page_title="Anti-Fraud & KYC Agent", layout="wide")

BASE_DIR = Path(__file__).resolve().parents[3]
AFK_ROOT = BASE_DIR / "anti-fraud-kyc-agent"

if not AFK_ROOT.exists():
    st.error("Anti-Fraud agent assets are missing. Run fraudinst.sh first.")
    st.stop()

if str(AFK_ROOT) not in sys.path:
    sys.path.insert(0, str(AFK_ROOT))

try:
    from pages import (
        render_anonymize_tab,
        render_fraud_tab,
        render_intake_tab,
        render_kyc_tab,
        render_policy_tab,
        render_report_tab,
        render_review_tab,
        render_train_tab,
    )
except Exception as exc:  # pragma: no cover - guard for partial installs
    st.error(f"Could not load Anti-Fraud tabs: {exc}")
    st.stop()

RUNS_DIR = AFK_ROOT / ".tmp_runs"
RUNS_DIR.mkdir(exist_ok=True)
ss = st.session_state
ss.setdefault("afk_theme", "light")
ss.setdefault("afk_logged_in", False)
ss.setdefault("afk_user", {"name": "Guest"})
ss.setdefault("afk_pending", 12)
ss.setdefault("afk_flagged", 4)
ss.setdefault("afk_avg_time", "14 min")


def _theme_css(theme: str) -> str:
    if theme == "dark":
        bg = "#05070d"
        text = "#f8fafc"
        panel = "#0f172a"
        accent = "#60a5fa"
        border = "rgba(99,102,241,0.4)"
        input_bg = "#0f172a"
        shadow = "0 20px 60px rgba(15,23,42,0.4)"
    else:
        bg = "#f4f6fb"
        text = "#0f172a"
        panel = "#ffffff"
        accent = "#2563eb"
        border = "rgba(59,130,246,0.25)"
        input_bg = "#ffffff"
        shadow = "0 20px 60px rgba(148,163,184,0.25)"
    return f"""
    <style>
    .stApp {{
      background: {bg} !important;
      color: {text} !important;
      font-family: "Inter","SF Pro Display","Segoe UI",sans-serif;
    }}
    .afk-hero,
    .afk-status-card,
    .afk-right-panel,
    .stButton>button,
    button[kind="primary"] {{
      background: {panel} !important;
      color: {text} !important;
      border: 1px solid {border} !important;
      border-radius: 14px !important;
      box-shadow: {shadow} !important;
    }}
    .stButton>button {{
      background: linear-gradient(95deg,{accent},{border}) !important;
      color: #fff !important;
      border: none !important;
    }}
    .stTabs [data-baseweb="tab-list"] button {{
      background: rgba(148,163,184,0.1) !important;
      color: {text} !important;
      border-radius: 14px !important;
      border: 1px solid rgba(148,163,184,0.3) !important;
      padding: 0.9rem 1.2rem !important;
      font-size: 1rem !important;
    }}
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {{
      background: linear-gradient(120deg,{accent},#0f172a) !important;
      color: #fff !important;
      box-shadow: 0 10px 25px rgba(15,23,42,0.35) !important;
    }}
    .stTextInput>div>div>input,
    .stNumberInput input,
    .stSelectbox>div>div>div {{
      background: {input_bg} !important;
      color: {text} !important;
      border-radius: 10px !important;
      border: 1px solid rgba(148,163,184,0.4) !important;
    }}
    [data-testid="stDataFrame"] {{
      border-radius: 14px !important;
      border: 1px solid rgba(148,163,184,0.4) !important;
      background: {panel} !important;
      color: {text} !important;
    }}
    </style>
    """


def _apply_theme(theme: str):
    st.markdown(_theme_css(theme), unsafe_allow_html=True)


def _render_theme_toggle(label: str, key: str):
    current = ss["afk_theme"] == "dark"
    preference = st.checkbox(label, value=current, key=key, help="Switch between light and dark themes.")
    selected = "dark" if preference else "light"
    if selected != ss["afk_theme"]:
        ss["afk_theme"] = selected
        st.rerun()


_apply_theme(ss["afk_theme"])

if not ss["afk_logged_in"]:
    st.title("🔐 Anti-Fraud & KYC Agent Login")
    _render_theme_toggle("🌗 Dark mode", "afk_theme_toggle_login")
    st.caption("Authenticate to orchestrate intake → KYC → fraud triage in one cockpit.")

    with st.form("afk_login_form"):
        u = st.text_input("Username", placeholder="e.g. analyst01")
        e = st.text_input("Email", placeholder="name@domain.com")
        pwd = st.text_input("Passphrase", type="password", placeholder="•••••••")
        remember = st.checkbox("Remember session", value=True)
        submitted = st.form_submit_button("🚀 Enter Command Center", use_container_width=True)

        if submitted:
            if u.strip():
                ss["afk_logged_in"] = True
                ss["afk_user"] = {"name": u.strip(), "email": e.strip(), "remember": remember}
                st.success("Welcome back — initializing agent workspace…")
                st.rerun()
            else:
                st.error("Enter username to continue")
    st.stop()

st.title("🔒 Anti-Fraud & KYC Agent")
st.caption("Unified onboarding → privacy → verification → fraud response → reporting workflow.")

_, theme_col = st.columns([5, 1])
with theme_col:
    _render_theme_toggle("🌗 Dark mode", "afk_theme_toggle_main")

st.markdown(
    """
    <style>
    .afk-hero {
        background: radial-gradient(circle at top left, #0f172a, #111827);
        border: 1px solid rgba(59,130,246,0.3);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 25px 60px rgba(15,23,42,0.45);
        color: #f8fafc;
    }
    .afk-hero h3 { margin-bottom: 0.2rem; }
    .afk-hero p { color: #cbd5f5; }
    .afk-status-card {
        background: rgba(15,23,42,0.8);
        border-radius: 16px;
        padding: 1rem 1.3rem;
        border: 1px solid rgba(148,163,184,0.2);
        box-shadow: inset 0 0 20px rgba(15,23,42,0.5);
    }
    .afk-status-card h4 {
        margin: 0;
        font-size: 0.95rem;
        text-transform: uppercase;
        color: #94a3b8;
    }
    .afk-status-card span.value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .afk-right-panel {
        background: rgba(15,23,42,0.6);
        border-radius: 16px;
        padding: 1rem 1.2rem;
        border: 1px dashed rgba(148,163,184,0.4);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([1.4, 1], gap="large")
with left_col:
    user_name = ss.get("afk_user", {}).get("name", "Guest")
    st.markdown(
        f"""
        <div class='afk-hero'>
            <h3>👤 Operator: {user_name}</h3>
            <p>Manage digital onboarding with live KYC, privacy, policy attestation, and fraud scoring.</p>
            <ul style='color:#a5b4fc;'>
              <li>Collect minimal viable data → anonymize before sharing.</li>
              <li>Run IDV + watchlist scans, then route risky cases.</li>
              <li>Capture manual overrides to feed training + reports.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right_col:
    st.markdown("<div class='afk-right-panel'>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
            <div class='afk-status-card'>
                <h4>Pending Applicants</h4>
                <span class='value'>{ss.get('afk_pending')}</span>
                <p style='color:#34d399;margin:0;'>+3 vs yesterday</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class='afk-status-card'>
                <h4>Flagged Cases</h4>
                <span class='value'>{ss.get('afk_flagged')}</span>
                <p style='color:#f87171;margin:0;'>-1 cleared</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        f"""
        <div class='afk-status-card' style='margin-top:0.8rem;'>
            <h4>Avg Verification Time</h4>
            <span class='value'>{ss.get('afk_avg_time')}</span>
            <p style='color:#60a5fa;margin:0;'>-2 min vs last week</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# Replace sidebar radio with tabbed workflow like asset_appraisal
tab_guide, tab_intake, tab_privacy, tab_kyc, tab_fraud, tab_policy, tab_review, tab_train, tab_report = st.tabs([
    "🧭 Guide",
    "A) Intake",
    "B) Privacy",
    "C) KYC Verification",
    "D) Fraud Detection",
    "E) Policy & Controls",
    "F) Human Review",
    "G) Train",
    "H) Reports",
])

with tab_guide:
    st.markdown(
        """
        ### What
        An AI and rules-based agent that detects fraudulent behavior and verifies customer identities automatically.

        ### Goal
        To prevent financial losses, strengthen AML/KYC compliance, and ensure trustworthy customer onboarding.

        ### How
        1. Upload transaction or customer datasets, or import data from Kaggle or Hugging Face.
        2. The agent anonymizes PII, validates IDs and emails, and runs AI-driven fraud scoring.
        3. Combines heuristic rules and ML models to flag anomalies, fake identities, or high-risk transactions.
        4. Provides fraud scores, reasoning, and compliance reports.

        ### So What (Benefits)
        - Instantly flags suspicious behavior in real-time.
        - Reduces manual fraud review by over 80%.
        - Learns from feedback to adapt to new fraud patterns.
        - Ensures audit-ready, compliant identity checks.

        ### What Next
        Try it with your transaction or KYC data.
        Contact our team to integrate government ID APIs, risk scoring modules, or AML data sources.
        Once customized, deploy the agent to your production environment to continuously monitor and prevent fraudulent activity.
        """
    )

with tab_intake:
    render_intake_tab(ss, RUNS_DIR)

with tab_privacy:
    render_anonymize_tab(ss, RUNS_DIR)

with tab_kyc:
    render_kyc_tab(ss, RUNS_DIR)

with tab_fraud:
    render_fraud_tab(ss, RUNS_DIR)

with tab_policy:
    render_policy_tab(ss, RUNS_DIR)

with tab_review:
    render_review_tab(ss, RUNS_DIR)

with tab_train:
    render_train_tab(ss, RUNS_DIR)

with tab_report:
    render_report_tab(ss, RUNS_DIR)
