# ~/credit-appraisal-agent-poc/services/ui/app.py
from __future__ import annotations
import os
import io
import re
import datetime
from typing import Dict, Any

import numpy as np
import pandas as pd
import requests
import streamlit as st

# ─────────────────────────────────────────────
# CONFIG
API_URL = os.getenv("API_URL", "http://localhost:8090")
RUNS_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/api/.runs")
os.makedirs(RUNS_DIR, exist_ok=True)

st.set_page_config(page_title="AI Credit Appraisal Platform", layout="wide")

# Realistic defaults
DEFAULT_TUNING: Dict[str, Any] = {
    "target_approval_rate": 0.50,
    "threshold": 0.45,
    "min_employment_years": 1,
    "max_debt_to_income": 0.40,
    "min_credit_history_length": 24,
    "max_num_delinquencies": 1,
    "max_current_loans": 3,
    "requested_amount_min": 2_000.0,
    "requested_amount_max": 150_000.0,
    "loan_term_months_allowed": [12, 24, 36, 48, 60],
}

# ─────────────────────────────────────────────
# HEADER — USER INFO + SECURITY
st.title("💳 AI Credit Appraisal Platform")
st.caption("Generate, sanitize, and appraise credit datasets securely — with tunable rules.")

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

st.session_state["user_info"] = {
    "name": user_name.strip(),
    "email": user_email.strip(),
    "flagged": flag_session,
    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
}

# ─────────────────────────────────────────────
# TABS
tab_gen, tab_clean, tab_run, tab_tune = st.tabs([
    "🏦 Synthetic Data Generator",
    "🧹 Anonymize & Sanitize Data",
    "📤 Run Credit Appraisal Agent",
    "🎛️ Credit Tuning"
])

# ─────────────────────────────────────────────
# UTILITIES
BANNED_NAMES = {"race", "gender", "religion", "ethnicity", "ssn", "national_id"}
PII_COLS = {"customer_name", "name", "email", "phone", "address", "ssn", "national_id", "dob"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{6,}\d")

def dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated(keep="last")]

def scrub_text_pii(s):
    if not isinstance(s, str): return s
    s = EMAIL_RE.sub("", s); s = PHONE_RE.sub("", s)
    return s.strip()

def drop_pii_columns(df: pd.DataFrame):
    original_cols = list(df.columns)
    keep_cols = [c for c in original_cols if all(k not in c.lower() for k in PII_COLS)]
    dropped = [c for c in original_cols if c not in keep_cols]
    out = df[keep_cols].copy()
    for c in out.select_dtypes(include="object"):
        out[c] = out[c].apply(scrub_text_pii)
    return dedupe_columns(out), dropped

def strip_policy_banned(df: pd.DataFrame) -> pd.DataFrame:
    return df[[c for c in df.columns if c.lower() not in BANNED_NAMES]]

def append_user_info(df: pd.DataFrame) -> pd.DataFrame:
    meta = st.session_state["user_info"]
    out = df.copy()
    out["session_user_name"] = meta["name"]
    out["session_user_email"] = meta["email"]
    out["session_flagged"] = meta["flagged"]
    out["created_at"] = meta["timestamp"]
    return dedupe_columns(out)

def save_to_runs(df: pd.DataFrame, prefix: str) -> str:
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    flag_suffix = "_FLAGGED" if st.session_state["user_info"]["flagged"] else ""
    fname = f"{prefix}_{ts}{flag_suffix}.csv"
    fpath = os.path.join(RUNS_DIR, fname)
    dedupe_columns(df).to_csv(fpath, index=False)
    return fpath

REQUIRED_FOR_AGENT = [
    "employment_years","debt_to_income","credit_history_length",
    "num_delinquencies","current_loans","requested_amount","loan_term_months",
]

def to_agent_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy(); n = len(out)
    if "employment_years" not in out.columns:
        out["employment_years"] = out["employment_length"] if "employment_length" in out.columns else 0
    if "debt_to_income" not in out.columns:
        if "DTI" in out.columns:
            out["debt_to_income"] = pd.to_numeric(out["DTI"], errors="coerce").fillna(0.0).clip(0, 10)
        elif "existing_debt" in out.columns and "income" in out.columns:
            denom = pd.to_numeric(out["income"], errors="coerce").replace(0, np.nan)
            out["debt_to_income"] = (pd.to_numeric(out["existing_debt"], errors="coerce") / denom).fillna(0.0).clip(0, 10)
        else:
            out["debt_to_income"] = 0.0
    rng = np.random.default_rng(12345)
    if "credit_history_length" not in out.columns: out["credit_history_length"] = rng.integers(0, 30, n)
    if "num_delinquencies" not in out.columns:    out["num_delinquencies"] = np.minimum(rng.poisson(0.2, n), 10)
    if "current_loans" not in out.columns:        out["current_loans"] = rng.integers(0, 5, n)
    if "requested_amount" not in out.columns:     out["requested_amount"] = out["loan_amount"] if "loan_amount" in out.columns else 0
    if "loan_term_months" not in out.columns:     out["loan_term_months"] = out["loan_duration_months"] if "loan_duration_months" in out.columns else 0
    return dedupe_columns(out)

def apply_tuning_filters(df_agent: pd.DataFrame, t: dict) -> pd.DataFrame:
    out = df_agent.copy()
    for col in REQUIRED_FOR_AGENT:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    m = pd.Series(True, index=out.index)
    if "min_employment_years" in t and "employment_years" in out: m &= (out["employment_years"] >= float(t["min_employment_years"]))
    if "max_debt_to_income" in t and "debt_to_income" in out:     m &= (out["debt_to_income"] <= float(t["max_debt_to_income"]))
    if "min_credit_history_length" in t and "credit_history_length" in out: m &= (out["credit_history_length"] >= float(t["min_credit_history_length"]))
    if "max_num_delinquencies" in t and "num_delinquencies" in out: m &= (out["num_delinquencies"] <= float(t["max_num_delinquencies"]))
    if "max_current_loans" in t and "current_loans" in out:       m &= (out["current_loans"] <= float(t["max_current_loans"]))
    if all(k in t for k in ("requested_amount_min","requested_amount_max")) and "requested_amount" in out:
        m &= out["requested_amount"].between(float(t["requested_amount_min"]), float(t["requested_amount_max"]))
    if "loan_term_months_allowed" in t and "loan_term_months" in out:
        allowed = set(map(int, t["loan_term_months_allowed"]))
        if allowed:
            m &= out["loan_term_months"].astype("Int64").isin(list(allowed))
    return out[m].copy()

# ─────────────────────────────────────────────
# DATA GENERATORS
def generate_raw_synthetic(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    names = ["Alice Nguyen","Bao Tran","Chris Do","Duy Le","Emma Tran","Felix Nguyen","Giang Ho","Hanh Vo","Ivan Pham","Julia Ngo"]
    emails = [f"{n.split()[0].lower()}.{n.split()[1].lower()}@gmail.com" for n in names]
    addrs = ["23 Elm St, Boston, MA","19 Pine Ave, San Jose, CA","14 High St, London, UK","55 Nguyen Hue, Ho Chi Minh",
             "78 Oak St, Chicago, IL","10 Broadway, New York, NY","8 Rue Lafayette, Paris, FR","21 Königstr, Berlin, DE",
             "44 Maple Dr, Los Angeles, CA","22 Bay St, Toronto, CA"]
    df = pd.DataFrame({
        "application_id":[f"APP_{i:04d}" for i in range(1, n+1)],
        "customer_name":np.random.choice(names, n),
        "email":np.random.choice(emails, n),
        "phone":[f"+1-202-555-{1000+i:04d}" for i in range(n)],
        "address":np.random.choice(addrs, n),
        "national_id":rng.integers(10_000_000, 99_999_999, n),
        "age":rng.integers(21, 65, n),
        "income":rng.integers(25_000, 150_000, n),
        "employment_length":rng.integers(0, 30, n),
        "loan_amount":rng.integers(5_000, 100_000, n),
        "loan_duration_months":rng.choice([12,24,36,48,60,72], n),
        "collateral_value":rng.integers(8_000, 200_000, n),
        "collateral_type":rng.choice(["house","car","land","deposit"], n),
        "co_loaners":rng.choice([0,1,2], n, p=[0.7,0.25,0.05]),
        "credit_score":rng.integers(300, 850, n),
        "existing_debt":rng.integers(0, 50_000, n),
        "assets_owned":rng.integers(10_000, 300_000, n),
    })
    eps = 1e-9
    df["DTI"] = df["existing_debt"] / (df["income"] + eps)
    df["LTV"] = df["loan_amount"] / (df["collateral_value"] + eps)
    df["CCR"] = df["collateral_value"] / (df["loan_amount"] + eps)
    df["ITI"] = (df["loan_amount"] / (df["loan_duration_months"] + eps)) / (df["income"] + eps)
    df["CWI"] = ((1 - df["DTI"]).clip(0, 1)) * ((1 - df["LTV"]).clip(0, 1)) * (df["CCR"].clip(0, 3))
    return dedupe_columns(df)

def generate_anon_synthetic(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "application_id":[f"APP_{i:04d}" for i in range(1, n+1)],
        "age":rng.integers(21, 65, n),
        "income":rng.integers(25_000, 150_000, n),
        "employment_length":rng.integers(0, 30, n),
        "loan_amount":rng.integers(5_000, 100_000, n),
        "loan_duration_months":rng.choice([12,24,36,48,60,72], n),
        "collateral_value":rng.integers(8_000, 200_000, n),
        "collateral_type":rng.choice(["house","car","land","deposit"], n),
        "co_loaners":rng.choice([0,1,2], n, p=[0.7,0.25,0.05]),
        "credit_score":rng.integers(300, 850, n),
        "existing_debt":rng.integers(0, 50_000, n),
        "assets_owned":rng.integers(10_000, 300_000, n),
    })
    eps = 1e-9
    df["DTI"] = df["existing_debt"] / (df["income"] + eps)
    df["LTV"] = df["loan_amount"] / (df["collateral_value"] + eps)
    df["CCR"] = df["collateral_value"] / (df["loan_amount"] + eps)
    df["ITI"] = (df["loan_amount"] / (df["loan_duration_months"] + eps)) / (df["income"] + eps)
    df["CWI"] = ((1 - df["DTI"]).clip(0, 1)) * ((1 - df["LTV"]).clip(0, 1)) * (df["CCR"].clip(0, 3))
    return dedupe_columns(df)

# ─────────────────────────────────────────────
# 🏦 TAB 1 — Synthetic Data Generator
with tab_gen:
    st.subheader("🏦 Synthetic Credit Data Generator")

    rows = st.slider("Number of rows to generate", 50, 1000, 200, step=50)
    colA, colB = st.columns(2)

    with colA:
        if st.button("🔴 Generate RAW Synthetic Data (with PII)", use_container_width=True):
            raw_df = append_user_info(generate_raw_synthetic(rows))
            st.session_state.synthetic_raw_df = raw_df
            raw_path = save_to_runs(raw_df, "synthetic_raw")
            st.success(f"Generated RAW (PII) dataset with {rows} rows. Saved to {raw_path}")
            st.dataframe(raw_df.head(10), use_container_width=True)
            st.download_button("⬇️ Download RAW CSV",
                               raw_df.to_csv(index=False).encode("utf-8"),
                               os.path.basename(raw_path), "text/csv")

    with colB:
        if st.button("🟢 Generate ANON Synthetic Data (ready for agent)", use_container_width=True):
            anon_df = append_user_info(generate_anon_synthetic(rows))
            st.session_state.synthetic_df = anon_df
            anon_path = save_to_runs(anon_df, "synthetic_anon")
            st.success(f"Generated ANON dataset with {rows} rows. Saved to {anon_path}")
            st.dataframe(anon_df.head(10), use_container_width=True)
            st.download_button("⬇️ Download ANON CSV",
                               anon_df.to_csv(index=False).encode("utf-8"),
                               os.path.basename(anon_path), "text/csv")

# ─────────────────────────────────────────────
# 🧹 TAB 2 — Anonymize & Sanitize Data
with tab_clean:
    st.subheader("🧹 Upload & Anonymize Customer Data (PII columns will be DROPPED)")
    st.markdown("Upload your **real CSV**. We will drop PII columns and scrub emails/phones from text fields.")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            st.stop()

        st.write("📊 Original Data Preview:")
        st.dataframe(dedupe_columns(df_up.head(5)), use_container_width=True)

        sanitized, dropped_cols = drop_pii_columns(df_up)
        sanitized = append_user_info(sanitized)
        sanitized = dedupe_columns(sanitized)
        st.session_state.anonymized_df = sanitized

        st.success(f"Dropped PII columns: {sorted(dropped_cols) if dropped_cols else 'None'}")
        st.write("✅ Sanitized Data Preview:")
        st.dataframe(sanitized.head(5), use_container_width=True)

        fpath = save_to_runs(sanitized, "anonymized")
        st.success(f"Saved anonymized file: {fpath}")
        st.download_button("⬇️ Download Clean Data",
                           sanitized.to_csv(index=False).encode("utf-8"),
                           os.path.basename(fpath),
                           "text/csv")
    else:
        st.info("Choose a CSV to see the sanitize flow.", icon="ℹ️")

# ─────────────────────────────────────────────
# 🎛️ TAB 4 — Credit Tuning
with tab_tune:
    st.subheader("🎛️ Credit Tuning — Thresholds & Business Filters")
    tuning = st.session_state.get("tuning", DEFAULT_TUNING.copy())

    c1, c2 = st.columns(2)
    with c1:
        tuning["target_approval_rate"] = st.slider("🎯 Target approval ratio", 0.0, 1.0,
                                                   float(tuning["target_approval_rate"]), 0.01)
    with c2:
        tuning["threshold"] = st.slider("📈 Manual approval threshold (used if target=0)", 0.0, 1.0,
                                        float(tuning["threshold"]), 0.01)

    st.markdown("##### Business Filters (applied before scoring)")
    cA, cB, cC = st.columns(3)
    with cA:
        tuning["min_employment_years"] = st.number_input("Min employment years", value=int(tuning["min_employment_years"]), min_value=0, step=1)
        tuning["min_credit_history_length"] = st.number_input("Min credit history (months)", value=int(tuning["min_credit_history_length"]), min_value=0, step=1)
    with cB:
        tuning["max_debt_to_income"] = st.number_input("Max Debt-to-Income (DTI)", value=float(tuning["max_debt_to_income"]), min_value=0.0, step=0.01, format="%.2f")
        tuning["max_num_delinquencies"] = st.number_input("Max recent delinquencies", value=int(tuning["max_num_delinquencies"]), min_value=0, step=1)
    with cC:
        tuning["max_current_loans"] = st.number_input("Max current loans", value=int(tuning["max_current_loans"]), min_value=0, step=1)
        ra = st.slider("Requested amount range", 0.0, 200000.0,
                       (float(tuning["requested_amount_min"]), min(200000.0, float(tuning["requested_amount_max"]))), step=1000.0)
        tuning["requested_amount_min"], tuning["requested_amount_max"] = float(ra[0]), float(ra[1])

    tuning["loan_term_months_allowed"] = st.multiselect(
        "Allowed loan terms (months)", [12,24,36,48,60,72],
        default=tuning["loan_term_months_allowed"]
    )
    st.session_state["tuning"] = tuning

    with st.expander("👁️ View current default metrics & your selections"):
        st.markdown("**Default metrics (factory settings):**")
        st.json(DEFAULT_TUNING)
        st.markdown("**Your current selections (overrides):**")
        st.json(tuning)

    st.info("Filters apply client-side before upload; threshold/target are sent to the backend agent.")

# ─────────────────────────────────────────────
# 📤 TAB 3 — Run Credit Appraisal Agent
with tab_run:
    st.subheader("📤 Run Credit Appraisal Agent")

    if "manual_upload" not in st.session_state:
        st.session_state.manual_upload = None

    data_choice = st.selectbox(
        "Select Data Source",
        [
            "Use sample dataset",
            "Use synthetic (ANON)",
            "Use synthetic (RAW – auto-sanitize)",
            "Use anonymized dataset",
            "Upload manually"
        ]
    )
    use_llm = st.checkbox("Use LLM narrative", value=True)
    agent = "credit_appraisal"

    # Show the tuning that WILL be applied
    tuning = st.session_state.get("tuning", DEFAULT_TUNING.copy())
    with st.expander("🧭 Current credit tuning to be applied (read-only)"):
        st.json({
            "threshold (used if target=0)": tuning.get("threshold", DEFAULT_TUNING["threshold"]),
            "target_approval_rate": tuning.get("target_approval_rate", DEFAULT_TUNING["target_approval_rate"]),
            "filters": {
                "min_employment_years": tuning.get("min_employment_years", DEFAULT_TUNING["min_employment_years"]),
                "max_debt_to_income": tuning.get("max_debt_to_income", DEFAULT_TUNING["max_debt_to_income"]),
                "min_credit_history_length": tuning.get("min_credit_history_length", DEFAULT_TUNING["min_credit_history_length"]),
                "max_num_delinquencies": tuning.get("max_num_delinquencies", DEFAULT_TUNING["max_num_delinquencies"]),
                "max_current_loans": tuning.get("max_current_loans", DEFAULT_TUNING["max_current_loans"]),
                "requested_amount_min": tuning.get("requested_amount_min", DEFAULT_TUNING["requested_amount_min"]),
                "requested_amount_max": tuning.get("requested_amount_max", DEFAULT_TUNING["requested_amount_max"]),
                "loan_term_months_allowed": tuning.get("loan_term_months_allowed", DEFAULT_TUNING["loan_term_months_allowed"]),
            }
        })

    if data_choice == "Upload manually":
        up = st.file_uploader("Upload your CSV", type=["csv"], key="manual_upload_widget")
        if up is not None:
            st.session_state.manual_upload = {"name": up.name, "bytes": up.getvalue()}
            st.success(f"File staged: {up.name} ({len(st.session_state.manual_upload['bytes'])} bytes)")
        elif st.session_state.manual_upload is not None:
            st.info(f"Using previously staged file: {st.session_state.manual_upload['name']}")

    def prep_and_pack(df: pd.DataFrame, filename: str):
        safe = dedupe_columns(df)
        safe, _ = drop_pii_columns(safe)
        safe = strip_policy_banned(safe)
        safe = to_agent_schema(safe)
        safe = apply_tuning_filters(safe, tuning)
        buf = io.StringIO()
        safe.to_csv(buf, index=False)
        return {"file": (filename, buf.getvalue().encode("utf-8"), "text/csv")}

    if st.button("🚀 Run Agent", use_container_width=True):
        try:
            files = None
            data = {
                "use_sample": "false",
                "use_llm_narrative": str(use_llm).lower(),
                "threshold": str(tuning.get("threshold", DEFAULT_TUNING["threshold"])),
                "target_approval_rate": str(tuning.get("target_approval_rate", DEFAULT_TUNING["target_approval_rate"])),
                # also send filters (server uses these when use_sample=true)
                "min_employment_years": str(tuning.get("min_employment_years", DEFAULT_TUNING["min_employment_years"])),
                "max_debt_to_income": str(tuning.get("max_debt_to_income", DEFAULT_TUNING["max_debt_to_income"])),
                "min_credit_history_length": str(tuning.get("min_credit_history_length", DEFAULT_TUNING["min_credit_history_length"])),
                "max_num_delinquencies": str(tuning.get("max_num_delinquencies", DEFAULT_TUNING["max_num_delinquencies"])),
                "max_current_loans": str(tuning.get("max_current_loans", DEFAULT_TUNING["max_current_loans"])),
                "requested_amount_min": str(tuning.get("requested_amount_min", DEFAULT_TUNING["requested_amount_min"])),
                "requested_amount_max": str(tuning.get("requested_amount_max", DEFAULT_TUNING["requested_amount_max"])),
                "loan_term_months_allowed": ",".join(map(str, tuning.get("loan_term_months_allowed", DEFAULT_TUNING["loan_term_months_allowed"]))),
            }

            if data_choice == "Use sample dataset":
                data["use_sample"] = "true"

            elif data_choice == "Use synthetic (ANON)":
                if "synthetic_df" not in st.session_state:
                    st.warning("No ANON synthetic dataset found. Generate it in the first tab.")
                    st.stop()
                files = prep_and_pack(st.session_state.synthetic_df, "synthetic_anon.csv")

            elif data_choice == "Use synthetic (RAW – auto-sanitize)":
                if "synthetic_raw_df" not in st.session_state:
                    st.warning("No RAW synthetic dataset found. Generate it in the first tab.")
                    st.stop()
                files = prep_and_pack(st.session_state.synthetic_raw_df, "synthetic_raw_sanitized.csv")

            elif data_choice == "Use anonymized dataset":
                if "anonymized_df" not in st.session_state:
                    st.warning("No anonymized dataset found. Create it in the second tab.")
                    st.stop()
                files = prep_and_pack(st.session_state.anonymized_df, "anonymized.csv")

            elif data_choice == "Upload manually":
                up = st.session_state.manual_upload
                if up is None:
                    st.warning("Please upload a CSV first.")
                    st.stop()
                try:
                    tmp_df = pd.read_csv(io.BytesIO(up["bytes"]))
                    files = prep_and_pack(tmp_df, up["name"])
                except Exception:
                    files = {"file": (up["name"], up["bytes"], "text/csv")}

            r = requests.post(f"{API_URL}/v1/agents/{agent}/run", data=data, files=files)
            if r.status_code != 200:
                st.error(f"Run failed ({r.status_code}): {r.text}")
                st.stop()

            res = r.json()
            st.session_state.last_run_id = res.get("run_id")
            st.success(f"✅ Run succeeded! Run ID: {st.session_state.last_run_id}")

            result = res.get("result", {})
            summary = result.get("summary", {})
            scores = result.get("scores", [])

            st.markdown("### ✅ Run Summary")
            if summary:
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total", summary.get("count", 0))
                k2.metric("Approved", summary.get("approved", 0))
                k3.metric("Denied", summary.get("denied", 0))
                k4.metric("Threshold used", f"{summary.get('threshold_used', tuning.get('threshold', 0.45)):.3f}")

            if scores:
                st.markdown("#### Sample scores")
                st.dataframe(pd.DataFrame(scores).head(10), use_container_width=True)

        except Exception as e:
            st.exception(e)

    st.markdown("---")
    st.subheader("📥 Download Latest Outputs")

    if not st.session_state.get("last_run_id"):
        st.info("Run the agent to enable downloads.")
    else:
        rid = st.session_state.last_run_id
        col1, col2, col3, col4, col5 = st.columns(5)

        def fetch_and_button(fmt: str, label: str):
            url = f"{API_URL}/v1/runs/{rid}/report?format={fmt}"
            res = requests.get(url)
            if res.status_code == 200:
                ext = "json" if fmt == "json" else ("csv" if "csv" in fmt else "pdf")
                fname = f"{fmt}_{rid}.{ext}"
                st.download_button(label, res.content, fname, res.headers.get("content-type", "application/octet-stream"))
            else:
                st.warning(f"{label} not available ({res.status_code})")

        with col1: fetch_and_button("pdf", "⬇️ PDF")
        with col2: fetch_and_button("scores_csv", "⬇️ Scores CSV")
        with col3: fetch_and_button("explanations_csv", "⬇️ Explanations CSV")
        with col4: fetch_and_button("csv", "⬇️ Merged CSV")
        with col5: fetch_and_button("json", "⬇️ JSON")
