#!/usr/bin/env bash
# ============================================================
# 🧩 Anti-Fraud & KYC Agent — Full Auto-Installer (Clean Final)
# ============================================================
set -euo pipefail

ROOT="${HOME}/AI-AIGENTbythePeoplesANDBOX/HUGKAG"
AGENT_NAME="anti-fraud-kyc-agent"
VENV="${ROOT}/${AGENT_NAME}/.venv"

echo "🚀 Setting up Anti-Fraud & KYC Agent at: ${ROOT}/${AGENT_NAME}"

sudocmd() {
  if command -v sudo >/dev/null; then
    if sudo -n true 2>/dev/null; then
      return 0
    fi
    echo "ℹ️  sudo available but passwordless execution not permitted; skipping apt install." >&2
  else
    echo "ℹ️  sudo not found; skipping apt install." >&2
  fi
  return 1
}

if sudocmd; then
  sudo apt update -y
  sudo apt install -y python3 python3-venv python3-pip git unzip zip wget curl jq
fi

mkdir -p "${ROOT}/${AGENT_NAME}"/{services/ui/pages,services/agents,pages,utils,models,tests,.tmp_runs}
cd "${ROOT}/${AGENT_NAME}"

# ------------------------------------------------------------
# 🧱 1. Virtual environment & dependencies
# ------------------------------------------------------------
python3 -m venv "$VENV"
source "$VENV/bin/activate"

cat > requirements.txt <<"REQ"
streamlit>=1.20
pandas
numpy
scikit-learn
lightgbm
datasets
huggingface_hub
kaggle
geopy
pydeck
plotly
python-multipart
pillow
pyyaml
requests
python-dotenv
pytest
shap
REQ

if ! pip install -r requirements.txt; then
  echo "⚠️  pip install failed (likely due to restricted network). Install dependencies manually later." >&2
fi

# ------------------------------------------------------------
# 🐳 2. Dockerfile (updated for your folder)
# ------------------------------------------------------------
cat > Dockerfile <<"DOCK"
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8501
CMD ["streamlit","run","services/ui/pages/anti-fraud-kyc-agent.py","--server.port=8501","--server.address=0.0.0.0"]
DOCK

# ------------------------------------------------------------
# 🖥️ 3. Main Streamlit app (correct path)
# ------------------------------------------------------------
cat > services/ui/pages/anti-fraud-kyc-agent.py <<"PY"
#!/usr/bin/env python3
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import pandas as pd
import streamlit as st
from utils.data_loaders import load_hf_dataset_as_df, download_kaggle_dataset
from pages.intake import render_intake_tab
from pages.anonymize import render_anonymize_tab
from pages.kyc_verification import render_kyc_tab
from pages.fraud_detection import render_fraud_tab
from pages.policy import render_policy_tab
from pages.review import render_review_tab
from pages.train import render_train_tab
from pages.report import render_report_tab

st.set_page_config(page_title="Anti-Fraud & KYC Agent", layout="wide")
ss = st.session_state
ss.setdefault("afk_logged_in", False)
ss.setdefault("afk_user", {"name": "Guest"})
RUNS_DIR = os.path.abspath("./.tmp_runs"); os.makedirs(RUNS_DIR, exist_ok=True)

if not ss["afk_logged_in"]:
    st.title("🔐 Login")
    u = st.text_input("Username")
    e = st.text_input("Email")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u.strip():
            ss["afk_logged_in"] = True
            ss["afk_user"] = {"name": u, "email": e}
            st.rerun()  # ✅ new API (was st.experimental_rerun)
        else:
            st.error("Enter username")
            st.stop()
    st.stop()

st.title("🔒 Anti-Fraud & KYC Agent")
nav = st.sidebar.radio(
    "Navigation",
    ["A) Intake", "B) Privacy", "C) KYC Verify", "D) Fraud", "E) Policy", "F) Train", "G) Report"]
)

if nav.startswith("A"): render_intake_tab(ss, RUNS_DIR)
elif nav.startswith("B"): render_anonymize_tab(ss, RUNS_DIR)
elif nav.startswith("C"): render_kyc_tab(ss, RUNS_DIR)
elif nav.startswith("D"): render_fraud_tab(ss, RUNS_DIR)
elif nav.startswith("E"): render_policy_tab(ss, RUNS_DIR)
elif nav.startswith("F"): render_train_tab(ss, RUNS_DIR)
elif nav.startswith("G"): render_report_tab(ss, RUNS_DIR)
PY

# ------------------------------------------------------------
# ⚙️ 4. Utils
# ------------------------------------------------------------
cat > utils/data_loaders.py <<"PY"
import pandas as pd, os, subprocess
from datasets import load_dataset

def load_hf_dataset_as_df(repo_id):
    ds = load_dataset(repo_id)
    split = next(iter(ds.keys()))
    return ds[split].to_pandas()

def download_kaggle_dataset(ref, dest):
    os.makedirs(dest, exist_ok=True)
    cmd = ["kaggle", "datasets", "download", "-d", ref, "-p", dest, "--unzip"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    for f in os.listdir(dest):
        if f.endswith(".csv"):
            return os.path.join(dest, f)
    raise FileNotFoundError("No CSV found")
PY

# ------------------------------------------------------------
# 📘 5. README (properly closed heredoc)
# ------------------------------------------------------------
cat > README.md <<"MD"
# Anti-Fraud & KYC Agent
Run locally:
```bash
pip install -r requirements.txt
streamlit run services/ui/pages/anti-fraud-kyc-agent.py
```
MD
echo "✅ All files created."
echo "To launch:"
echo " source ${VENV}/bin/activate"
echo " cd ${ROOT}/${AGENT_NAME}"
echo " streamlit run services/ui/pages/anti-fraud-kyc-agent.py"
