import os
import io
import re
import hashlib
import datetime
import pandas as pd
import numpy as np
import requests
import streamlit as st

# ─────────────────────────────────────────────
# CONFIG
API_URL = os.getenv("API_URL", "http://localhost:8090")
RUNS_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/api/.runs")
os.makedirs(RUNS_DIR, exist_ok=True)

st.set_page_config(page_title="AI Credit Appraisal Platform", layout="wide")

# ─────────────────────────────────────────────
# HEADER — USER INFO + SECURITY
st.title("💳 AI Credit Appraisal Platform")
st.caption("Generate, sanitize, or appraise credit datasets securely — all in one place.")

with st.container():
    st.markdown("### 🧑 User Identity & Security Info")
    col1, col2, col3 = st.columns([1.5, 1.5, 1])
    with col1:
        user_name = st.text_input("Your Name (required)", value="", placeholder="e.g. Alice Nguyen")
    with col2:
        user_email = st.text_input("Email (required)", value="", placeholder="e.g. alice@bank.com")
    with col3:
        flag_session = st.checkbox("⚠️ Flag for Security Review", value=False)

    if not user_name or not user_email:
        st.warning("Please enter your name and email before proceeding.")
        st.stop()

# Session info storage
st.session_state["user_info"] = {
    "name": user_name.strip(),
    "email": user_email.strip(),
    "flagged": flag_session,
    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

# ─────────────────────────────────────────────
# TABS
tab_gen, tab_clean, tab_run = st.tabs([
    "🏦 Synthetic Data Generator",
    "🧹 Anonymize & Sanitize Data",
    "📤 Run Credit Appraisal Agent"
])

# Utility: save file persistently
def save_to_runs(df: pd.DataFrame, prefix: str) -> str:
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    flag_suffix = "_FLAGGED" if st.session_state["user_info"]["flagged"] else ""
    fname = f"{prefix}_{ts}{flag_suffix}.csv"
    fpath = os.path.join(RUNS_DIR, fname)
    df.to_csv(fpath, index=False)
    return fpath

# Utility: append user metadata
def append_user_info(df: pd.DataFrame) -> pd.DataFrame:
    meta = st.session_state["user_info"]
    df["session_user_name"] = meta["name"]
    df["session_user_email"] = meta["email"]
    df["session_flagged"] = meta["flagged"]
    df["created_at"] = meta["timestamp"]
    return df

# ─────────────────────────────────────────────
# 🏦 TAB 1 — Synthetic Data Generator
with tab_gen:
    st.subheader("🏦 Synthetic Credit Data Generator")

    with st.expander("📊 Data Schema Helper & Template", expanded=False):
        st.markdown("""
        **Template Columns (for reference):**

        | Column | Description | Example |
        |--------|--------------|----------|
        | age | Applicant's age | 35 |
        | income | Annual income | 75000 |
        | employment_length | Years employed | 8 |
        | loan_amount | Requested loan amount | 20000 |
        | loan_duration_months | Loan term | 60 |
        | collateral_value | Value of pledged assets | 30000 |
        | collateral_type | Type of collateral | house / car |
        | co_loaners | Number of co-signers | 1 |
        | credit_score | Bureau score | 720 |
        | existing_debt | Current total debt | 10000 |
        | assets_owned | Declared assets | 80000 |
        | DTI | Debt-to-Income ratio | 0.13 |
        | LTV | Loan-to-Value ratio | 0.66 |
        | CCR | Collateral Coverage ratio | 1.5 |
        | ITI | Installment-to-Income ratio | 0.05 |
        | CWI | Creditworthiness Index | 0.85 |

        Download a ready-to-use CSV template below.
        """)
        csv_template = pd.DataFrame({
            "age": [35],
            "income": [75000],
            "employment_length": [8],
            "loan_amount": [20000],
            "loan_duration_months": [60],
            "collateral_value": [30000],
            "collateral_type": ["house"],
            "co_loaners": [1],
            "credit_score": [720],
            "existing_debt": [10000],
            "assets_owned": [80000],
            "DTI": [0.13],
            "LTV": [0.66],
            "CCR": [1.5],
            "ITI": [0.05],
            "CWI": [0.85],
        })
        st.download_button("📥 Download Template CSV",
                           csv_template.to_csv(index=False).encode("utf-8"),
                           "credit_data_template.csv", "text/csv")

    rows = st.slider("Number of rows to generate", 50, 1000, 100, step=50)
    if st.button("⚙️ Generate Synthetic Data"):
        rng = np.random.default_rng(42)
        df = pd.DataFrame({
            "application_id": [f"APP_{i:04d}" for i in range(1, rows + 1)],
            "age": rng.integers(21, 65, rows),
            "income": rng.integers(25000, 150000, rows),
            "employment_length": rng.integers(0, 30, rows),
            "loan_amount": rng.integers(5000, 100000, rows),
            "loan_duration_months": rng.choice([12, 24, 36, 48, 60, 72], rows),
            "collateral_value": rng.integers(8000, 200000, rows),
            "collateral_type": rng.choice(["house", "car", "land", "deposit"], rows),
            "co_loaners": rng.choice([0, 1, 2], rows, p=[0.7, 0.25, 0.05]),
            "credit_score": rng.integers(300, 850, rows),
            "existing_debt": rng.integers(0, 50000, rows),
            "assets_owned": rng.integers(10000, 300000, rows)
        })
        # Derived metrics
        eps = 1e-9
        df["DTI"] = df["existing_debt"] / (df["income"] + eps)
        df["LTV"] = df["loan_amount"] / (df["collateral_value"] + eps)
        df["CCR"] = df["collateral_value"] / (df["loan_amount"] + eps)
        df["ITI"] = (df["loan_amount"] / (df["loan_duration_months"] + eps)) / (df["income"] + eps)
        df["CWI"] = ((1 - df["DTI"]).clip(0, 1)) * ((1 - df["LTV"]).clip(0, 1)) * (df["CCR"].clip(0, 3))
        df = append_user_info(df)

        st.session_state.synthetic_df = df
        fpath = save_to_runs(df, "synthetic")
        st.success(f"✅ Generated {rows} rows. Saved to {fpath}")
        st.dataframe(df.head(10), use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download Synthetic CSV", csv, os.path.basename(fpath), "text/csv")

# ─────────────────────────────────────────────
# 🧹 TAB 2 — Anonymize & Sanitize Data
with tab_clean:
    st.subheader("🧹 Upload & Anonymize Customer Data")
    st.markdown("Upload your real dataset; we’ll detect and mask PII before you use it.")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.write("📊 Original Data Preview:")
        st.dataframe(df.head(5))

        PII_KEYS = ["name", "email", "phone", "address", "ssn", "national_id", "dob"]
        df_clean = df.copy()
        for col in df.columns:
            if any(k in col.lower() for k in PII_KEYS):
                df_clean[col] = "***MASKED***"

        df_clean = append_user_info(df_clean)
        st.session_state.anonymized_df = df_clean

        st.write("✅ Sanitized Data Preview:")
        st.dataframe(df_clean.head(5), use_container_width=True)

        fpath = save_to_runs(df_clean, "anonymized")
        st.success(f"Saved anonymized file: {fpath}")
        st.download_button("⬇️ Download Clean Data", df_clean.to_csv(index=False).encode("utf-8"),
                           os.path.basename(fpath), "text/csv")

# ─────────────────────────────────────────────
# 📤 TAB 3 — Run Credit Appraisal Agent
with tab_run:
    st.subheader("📤 Run Credit Appraisal Agent")

    data_choice = st.selectbox("Select Data Source", [
        "Use sample dataset", "Use synthetic dataset", "Use anonymized dataset", "Upload manually"
    ])

    use_llm = st.checkbox("Use LLM narrative", value=True)
    agent = "credit_appraisal"

    if st.button("🚀 Run Agent"):
        try:
            files, data = None, {"use_sample": "false", "use_llm_narrative": str(use_llm).lower()}
            if data_choice == "Use sample dataset":
                data["use_sample"] = "true"
            elif data_choice == "Use synthetic dataset" and "synthetic_df" in st.session_state:
                buf = io.StringIO()
                st.session_state.synthetic_df.to_csv(buf, index=False)
                files = {"file": ("synthetic.csv", buf.getvalue().encode("utf-8"), "text/csv")}
            elif data_choice == "Use anonymized dataset" and "anonymized_df" in st.session_state:
                buf = io.StringIO()
                st.session_state.anonymized_df.to_csv(buf, index=False)
                files = {"file": ("anonymized.csv", buf.getvalue().encode("utf-8"), "text/csv")}
            elif data_choice == "Upload manually":
                up = st.file_uploader("Upload your CSV", type=["csv"])
                if up:
                    files = {"file": (up.name, up.getvalue(), "text/csv")}
                else:
                    st.warning("Please upload a CSV to continue.")
                    st.stop()

            r = requests.post(f"{API_URL}/v1/agents/{agent}/run", data=data, files=files)
            if r.status_code != 200:
                st.error(f"Run failed ({r.status_code}): {r.text}")
            else:
                res = r.json()
                st.session_state.last_run_id = res.get("run_id")
                st.success(f"✅ Run succeeded! Run ID: {res.get('run_id')}")
                with st.expander("Result JSON"):
                    st.json(res)
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")
    st.subheader("📥 Download Reports")
    fmt = st.selectbox("Output Format", ["pdf", "scores_csv", "explanations_csv", "json"])
    if st.button("⬇️ Download Latest Report"):
        if "last_run_id" not in st.session_state or not st.session_state.last_run_id:
            st.warning("No completed run yet.")
        else:
            run_id = st.session_state.last_run_id
            url = f"{API_URL}/v1/runs/{run_id}/report?format={fmt}"
            res = requests.get(url)
            if res.status_code == 200:
                filename = f"credit_report_{run_id}.{fmt}"
                st.download_button(f"Save {fmt.upper()} File", res.content, filename)
            else:
                st.error(f"Download failed: {res.status_code}")

