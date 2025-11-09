"""Standalone Streamlit page for the Anti-Fraud & KYC agent."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
st.set_page_config(page_title="Anti-Fraud & KYC Agent", layout="wide")
from services.ui.components.operator_banner import render_operator_banner
from services.ui.components.telemetry_dashboard import render_telemetry_dashboard
from services.ui.components.feedback import render_feedback_tab
from services.ui.theme_manager import (
    apply_theme as apply_global_theme,
    get_palette,
    get_theme,
    render_theme_toggle,
)

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
ss.setdefault("stage", "agents")
ss.setdefault("afk_logged_in", True)
ss.setdefault("afk_user", {"name": "Operator", "email": "operator@demo.local"})
ss.setdefault("afk_pending", 12)
ss.setdefault("afk_flagged", 4)
ss.setdefault("afk_avg_time", "14 min")
ss.setdefault("afk_ai_performance", 0.91)
ss["afk_logged_in"] = True
if not ss["afk_user"].get("name"):
    ss["afk_user"]["name"] = "Operator"


def _coerce_minutes(value, fallback: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch == ".")
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            pass
    return float(fallback)


def _go_stage(target_stage: str) -> None:
    """Navigate back to the shared app router if available."""
    ss["stage"] = target_stage
    try:
        st.switch_page("app.py")
        return
    except Exception:
        pass
    try:
        st.query_params["stage"] = target_stage
    except Exception:
        pass


def _theme_css(theme: str) -> str:
    pal = get_palette(theme)
    bg = pal["bg"]
    text = pal["text"]
    panel = pal["card"]
    accent = pal["accent"]
    accent_alt = pal.get("accent_alt", pal["accent"])
    border = pal["border"]
    input_bg = pal.get("input_bg", panel)
    shadow = pal["shadow"]
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
      background: linear-gradient(95deg,{accent},{accent_alt}) !important;
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
    apply_global_theme(theme)
    st.markdown(_theme_css(theme), unsafe_allow_html=True)


_apply_theme(get_theme())

nav_cols = st.columns([1, 1, 4])
with nav_cols[0]:
    if st.button("🏠 Back to Home", key="afk_back_home"):
        _go_stage("landing")
with nav_cols[1]:
    if st.button("🤖 Back to Agents", key="afk_back_agents"):
        _go_stage("agents")

if not ss["afk_logged_in"]:
    st.title("🔐 Anti-Fraud & KYC Agent Login")
    render_theme_toggle("🌗 Dark mode", key="afk_theme_toggle_login")
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
    render_theme_toggle("🌗 Dark mode", key="afk_theme_toggle_main")

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

afk_ai_minutes = _coerce_minutes(ss.get("afk_avg_time"), 14.0)

render_operator_banner(
    operator_name=ss.get("afk_user", {}).get("name", "Guest"),
    title="Anti-Fraud & KYC Command",
    summary="Manage digital onboarding with live KYC, privacy, policy attestation, and fraud scoring.",
    bullets=[
        "Collect minimal viable data → anonymize before sharing.",
        "Run IDV + watchlist scans, then route risky cases.",
        "Capture manual overrides to feed training + reports.",
    ],
    metrics=[
        {
            "label": "Pending Applicants",
            "value": ss.get("afk_pending"),
            "delta": "+3 vs yesterday",
            "delta_color": "#34d399",
            "color": "#34d399",
            "percent": 0.72,
            "context": "Human avg queue: 26",
        },
        {
            "label": "Flagged Cases",
            "value": ss.get("afk_flagged"),
            "delta": "-1 cleared",
            "delta_color": "#f87171",
            "color": "#f87171",
            "percent": 0.35,
            "context": "Manual review avg: 7",
        },
        {
            "label": "Avg Verification Time",
            "value": ss.get("afk_avg_time") or f"{afk_ai_minutes:.0f} min",
            "delta": "-2 min vs last week",
            "delta_color": "#60a5fa",
            "color": "#60a5fa",
            "percent": min(1.0, afk_ai_minutes / 40.0),
            "context": "AI verification cycle",
        },
    ],
    icon="🛡️",
)
# Replace sidebar radio with tabbed workflow like asset_appraisal
tab_guide, tab_intake, tab_privacy, tab_kyc, tab_fraud, tab_policy, tab_review, tab_train, tab_report, tab_feedback = st.tabs([
    "🧭 Guide",
    "A) Intake",
    "B) Privacy",
    "C) KYC Verification",
    "D) Fraud Detection",
    "E) Policy & Controls",
    "F) Human Review",
    "G) Train",
    "H) Reports",
    "🗣️ Feedback",
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

with tab_feedback:
    render_feedback_tab("🛡️ Anti-Fraud & KYC Agent")
