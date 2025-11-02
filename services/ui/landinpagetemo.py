# services/ui/app.py
# ─────────────────────────────────────────────
# 🌐 OpenSource AI Agent Library + Credit Appraisal PoC by Dzoan
# ─────────────────────────────────────────────
from __future__ import annotations
import os, re, io, json, random, datetime
from typing import Optional, Dict, List, Any
import pandas as pd, numpy as np, streamlit as st, requests, plotly.express as px, plotly.graph_objects as go

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://localhost:8090")
RUNS_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/api/.runs")
TMP_FEEDBACK_DIR = os.path.join(RUNS_DIR, "tmp_feedback")
LANDING_IMG_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/ui/landing_images")

os.makedirs(RUNS_DIR, exist_ok=True)
os.makedirs(TMP_FEEDBACK_DIR, exist_ok=True)
os.makedirs(LANDING_IMG_DIR, exist_ok=True)
st.set_page_config(page_title="OpenSource AI Agent Library", layout="wide")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def load_image(base: str) -> Optional[str]:
    for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]:
        path = os.path.join(LANDING_IMG_DIR, f"{base}{ext}")
        if os.path.exists(path): return path
    return None

def save_uploaded_image(uploaded_file, base: str) -> Optional[str]:
    if not uploaded_file: return None
    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".png"
    dest = os.path.join(LANDING_IMG_DIR, f"{base}{ext}")
    with open(dest, "wb") as f: f.write(uploaded_file.getvalue())
    return dest

def render_image_tag(agent_id: str, industry: str, emoji_fallback: str) -> str:
    base = agent_id.lower().replace(" ", "_")
    img_path = load_image(base) or load_image(industry.replace(" ", "_"))
    if img_path:
        return f'<img src="file://{img_path}" style="width:40px;height:40px;border-radius:8px;object-fit:cover;">'
    else:
        return f'<div style="font-size:28px;">{emoji_fallback}</div>'

# ─────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────
AGENTS = [
    ("🏦 Banking & Finance", "💰 Retail Banking", "💳 Credit Appraisal Agent", "Explainable AI for loan decisioning", "Available", "💳"),
    ("🏦 Banking & Finance", "💰 Retail Banking", "🏦 Asset Appraisal Agent", "Market-driven collateral valuation", "Available", "🏦"),
    ("🏦 Banking & Finance", "🩺 Insurance", "🩺 Claims Triage Agent", "Automated claims prioritization", "Coming Soon", "🩺"),
    ("⚡ Energy & Sustainability", "🔋 EV & Charging", "⚡ EV Charger Optimizer", "Optimize charger deployment via AI", "Coming Soon", "⚡"),
    ("⚡ Energy & Sustainability", "☀️ Solar", "☀️ Solar Yield Estimator", "Estimate solar ROI and efficiency", "Coming Soon", "☀️"),
    ("🚗 Automobile & Transport", "🚙 Automobile", "🚗 Predictive Maintenance", "Prevent downtime via sensor analytics", "Coming Soon", "🚗"),
    ("🚗 Automobile & Transport", "🔋 EV", "🔋 EV Battery Health Agent", "Monitor EV battery health cycles", "Coming Soon", "🔋"),
    ("🚗 Automobile & Transport", "🚚 Ride-hailing / Logistics", "🛻 Fleet Route Optimizer", "Dynamic route optimization for fleets", "Coming Soon", "🛻"),
    ("💻 Information Technology", "🧰 Support & Security", "🧩 IT Ticket Triage", "Auto-prioritize support tickets", "Coming Soon", "🧩"),
    ("💻 Information Technology", "🛡️ Security", "🔐 SecOps Log Triage", "Detect anomalies & summarize alerts", "Coming Soon", "🔐"),
    ("⚖️ Legal & Government", "⚖️ Law Firms", "⚖️ Contract Analyzer", "Extract clauses and compliance risks", "Coming Soon", "⚖️"),
    ("⚖️ Legal & Government", "🏛️ Public Services", "🏛️ Citizen Service Agent", "Smart assistant for citizen services", "Coming Soon", "🏛️"),
    ("🛍️ Retail / SMB / Creative", "🏬 Retail & eCommerce", "📈 Sales Forecast Agent", "Predict demand & inventory trends", "Coming Soon", "📈"),
    ("🎬 Retail / SMB / Creative", "🎨 Media & Film", "🎬 Budget Cost Assistant", "Estimate, optimize, and track film & production costs using AI", "Coming Soon", "🎬"),
]

# ─────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────
st.markdown("""
<style>
.block-container {padding: 0rem; max-width: 100%;}
.banner {width:100%;height:320px;border-radius:12px;overflow:hidden;margin-bottom:1.5rem;box-shadow:0 4px 10px rgba(0,0,0,0.15);}
.banner img {width:100%;height:320px;object-fit:cover;border-radius:12px;}
.status-Available {color:#16a34a;font-weight:600;}
.status-ComingSoon {color:#f59e0b;font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HERO BANNER
# ─────────────────────────────────────────────
banner_key = "agent_library_banner"
banner_path = load_image(banner_key)
st.markdown("<div class='banner'>", unsafe_allow_html=True)
if banner_path and os.path.exists(banner_path):
    st.image(banner_path, use_container_width=True)
else:
    st.markdown(
        "<div style='height:320px;background:#1e293b;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:20px;border-radius:12px;'>🖼️ Upload your AI Agent Library banner</div>",
        unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

banner_upload = st.file_uploader("Upload new top banner (JPG/PNG/WebP)", type=["jpg", "png", "webp"], key="upload_banner")
if banner_upload:
    new_path = save_uploaded_image(banner_upload, banner_key)
    if new_path:
        st.success(f"✅ New top banner saved to {new_path}")
        st.rerun()

# ─────────────────────────────────────────────
# TABLE — AI AGENT LIBRARY
# ─────────────────────────────────────────────
st.title("📊 Global AI Agent Library")
st.caption("Explore sectors, industries, and ready-to-use AI agents across domains.")

rows = []
for sector, industry, agent, desc, status, emoji in AGENTS:
    rating = round(random.uniform(3.5, 5.0), 1)
    users = random.randint(800, 9000)
    comments = random.randint(5, 120)
    image_html = render_image_tag(agent, industry, emoji)
    rows.append({
        "🖼️": image_html,
        "🏭 Sector": sector,
        "🧩 Industry": industry,
        "🤖 Agent": agent,
        "🧠 Description": desc,
        "📶 Status": f'<span class="status-{status.replace(" ", "")}">{status}</span>',
        "⭐ Rating": "⭐" * int(rating) + "☆" * (5 - int(rating)),
        "👥 Users": users,
        "💬 Comments": comments
    })
df = pd.DataFrame(rows)
st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 🚀 LANDING + PIPELINE SECTION (inserted)
# ─────────────────────────────────────────────
st.markdown("""
<hr style='margin:3rem 0;border:0;height:1px;background:#334155;'>
<div style='text-align:center;margin-bottom:2rem;'>
  <h1 style='font-size:2.8rem;color:#60a5fa;font-weight:800;'>🚀 Start Building Now</h1>
  <p style='font-size:1.2rem;color:#cbd5e1;max-width:800px;margin:auto;'>
     Deploy ready-to-use AI agents – from Credit Appraisal to Asset Valuation – in minutes.  
     Connect, analyze, and optimize your entire workflow with explainable AI and human feedback loops.
  </p>
</div>

<div style='text-align:center;margin-top:2rem;'>
  <a href='credit_appraisal.py'>
     <button style='background:linear-gradient(90deg,#2563eb,#1d4ed8);
                    border:none;border-radius:14px;
                    color:white;padding:18px 40px;
                    font-size:22px;font-weight:700;
                    cursor:pointer;'>
       🚀 Start Building Now
     </button>
  </a>
</div>

<hr style='margin:3rem 0;border:0;height:1px;background:#334155;'>
<div style='text-align:center;margin-bottom:2rem;'>
  <h1 style='font-size:2.4rem;color:#f8fafc;'>AI Appraisal Workflow</h1>
</div>

<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:2rem;text-align:center;'>
  <div style='background:#1e293b;border-radius:14px;padding:1.2rem;'>
    <h2>🧩 Step 1</h2><h3>Synthetic Data Generator</h3>
    <p>Generate realistic loan and asset samples for training.</p>
  </div>
  <div style='background:#1e293b;border-radius:14px;padding:1.2rem;'>
    <h2>🧹 Step 2</h2><h3>Anonymize & Sanitize Data</h3>
    <p>Remove PII and prepare datasets for compliant AI processing.</p>
  </div>
  <div style='background:#1e293b;border-radius:14px;padding:1.2rem;'>
    <h2>🤖 Step 3</h2><h3>Credit Appraisal by AI Assistant</h3>
    <p>Score borrowers with explainable AI logic and transparency.</p>
  </div>
  <div style='background:#1e293b;border-radius:14px;padding:1.2rem;'>
    <h2>🧑‍⚖️ Step 4</h2><h3>Human Review</h3>
    <p>Enable credit officers to validate AI decisions with reasoning.</p>
  </div>
  <div style='background:#1e293b;border-radius:14px;padding:1.2rem;'>
    <h2>🔁 Step 5</h2><h3>Training (Feedback → Retrain)</h3>
    <p>Continuously improve models based on human feedback.</p>
  </div>
  <div style='background:#1e293b;border-radius:14px;padding:1.2rem;'>
    <h2>🔄 Step 6</h2><h3>Loop Back to Step 3</h3>
    <p>Deploy retrained models and restart evaluation cycles.</p>
  </div>
</div>
<hr style='margin:3rem 0;border:0;height:1px;background:#334155;'>
<p style='text-align:center;color:#94a3b8;'>© 2025 Rackspace FAIR • AI Agent Library v1.0</p>
""", unsafe_allow_html=True)
