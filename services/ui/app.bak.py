import os
import io
import re
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

# ─────────────────────────────────────────────
# UTILITIES

BANNED_NAMES = {"race", "gender", "religion", "ethnicity", "ssn", "national_id"}

PII_COLS = {
    "customer_name", "name", "email", "phone", "address", "ssn", "national_id", "dob"
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{6,}\d")

def dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated(keep="last")]

def scrub_text_pii(s):
    if not isinstance(s, str):
        return s
    s = EMAIL_RE.sub("", s)
    s = PHONE_RE.sub("", s)
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
    keep = []
    for c in df.columns:
        cl = c.lower()
        if cl in BANNED_NAMES:
            continue
        keep.append(c)
    return df[keep]

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
    "employment_years",
    "debt_to_income",
    "credit_history_length",
    "num_delinquencies",
    "current_loans",
    "requested_amount",
    "loan_term_months",
]

def to_agent_schema(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    n = len(out)

    if "employment_years" not in out.columns:
        if "employment_length" in out.columns:
            out["employment_years"] = out["employment_length"]
        else:
            out["employment_years"] = 0

    if "debt_to_income" not in out.columns:
        if "DTI" in out.columns:
            out["debt_to_income"] = out["DTI"].astype(float)
        elif "existing_debt" in out.columns and "income" in out.columns:
            denom = out["income"].replace(0, np.nan)
            dti = (out["existing_debt"] / denom).fillna(0.0)
            out["debt_to_income"] = dti.clip(0, 10)
        else:
            out["debt_to_income"] = 0.0

    rng = np.random.default_rng(12345)

    if "credit_history_length" not in out.columns:
        out["credit_history_length"] = rng.integers(0, 30, n)

    if "num_delinquencies" not in out.columns:
        out["num_delinquencies"] = np.minimum(rng.poisson(0.2, n), 10)

    if "current_loans" not in out.columns:
        out["current_loans"] = rng.integers(0, 5, n)

    if "requested_amount" not in out.columns:
        out["requested_amount"] = out["loan_amount"] if "loan_amount" in out.columns else 0

    if "loan_term_months" not in out.columns:
        out["loan_term_months"] = out["loan_duration_months"] if "loan_duration_months" in out.columns else 0

    return dedupe_columns(out)

# ─────────────────────────────────────────────
# DATA GENERATORS
def generate_raw_synthetic(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    names = ["Alice Nguyen","Bao Tran","Chris Do","Duy Le","Emma Tran",
             "Felix Nguyen","Giang Ho","Hanh Vo","Ivan Pham","Julia Ngo"]
    emails = [f"{n.split()[0].lower()}.{n.split()[1].lower()}@gmail.com" for n in names]
    addrs = [
        "23 Elm St, Boston, MA","19 Pine Ave, San Jose, CA","14 High St, London, UK",
        "55 Nguyen Hue, Ho Chi Minh","78 Oak St, Chicago, IL","10 Broadway, New York, NY",
        "8 Rue Lafayette, Paris, FR","21 Königstr, Berlin, DE","44 Maple Dr, Los Angeles, CA","22 Bay St, Toronto, CA"
    ]
    df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, n + 1)],
        "customer_name": np.random.choice(names, n),
        "email": np.random.choice(emails, n),
        "phone": [f"+1-202-555-{1000+i:04d}" for i in range(n)],
        "address": np.random.choice(addrs, n),
        "national_id": rng.integers(10_000_000, 99_999_999, n),
        "age": rng.integers(21, 65, n),
        "income": rng.integers(25_000, 150_000, n),
        "employment_length": rng.integers(0, 30, n),
        "loan_amount": rng.integers(5_000, 100_000, n),
        "loan_duration_months": rng.choice([12, 24, 36, 48, 60, 72], n),
        "collateral_value": rng.integers(8_000, 200_000, n),
        "collateral_type": rng.choice(["house","car","land","deposit"], n),
        "co_loaners": rng.choice([0,1,2], n, p=[0.7,0.25,0.05]),
        "credit_score": rng.integers(300, 850, n),
        "existing_debt": rng.integers(0, 50_000, n),
        "assets_owned": rng.integers(10_000, 300_000, n),
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
        "application_id": [f"APP_{i:04d}" for i in range(1, n + 1)],
        "age": rng.integers(21, 65, n),
        "income": rng.integers(25_000, 150_000, n),
        "employment_length": rng.integers(0, 30, n),
        "loan_amount": rng.integers(5_000, 100_000, n),
        "loan_duration_months": rng.choice([12, 24, 36, 48, 60, 72], n),
        "collateral_value": rng.integers(8_000, 200_000, n),
        "collateral_type": rng.choice(["house","car","land","deposit"], n),
        "co_loaners": rng.choice([0,1,2], n, p=[0.7,0.25,0.05]),
        "credit_score": rng.integers(300, 850, n),
        "existing_debt": rng.integers(0, 50_000, n),
        "assets_owned": rng.integers(10_000, 300_000, n),
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
# 🧹 TAB 2 — Anonymize & Sanitize Data (DROP PII)
with tab_clean:
    st.subheader("🧹 Upload & Anonymize Customer Data (PII columns will be DROPPED)")
    st.markdown("Upload your **real CSV**. We will drop PII columns (not mask) and scrub emails/phones from text fields.")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            st.stop()

        st.write("📊 Original Data Preview:")
        st.dataframe(dedupe_columns(df.head(5)), use_container_width=True)

        sanitized, dropped_cols = drop_pii_columns(df)
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

    # 💡 Decision controls: target acceptance (20–60%) and optional explicit threshold
    with st.expander("⚙️ Decision Controls (Approvals)"):
        target_rate = st.slider("Target acceptance rate", 0.20, 0.60, 0.40, 0.01,
                                help="Agent converts this to a percentile threshold; if omitted, agent will pick a random rate in 20–60%.")
        use_explicit_thr = st.checkbox("Use explicit model score threshold (overrides target rate)", value=False)
        thr_val = None
        if use_explicit_thr:
            thr_val = st.slider("Model score threshold", 0.0, 1.0, 0.50, 0.01)

    use_llm = st.checkbox("Use LLM narrative", value=True)
    agent = "credit_appraisal"

    if data_choice == "Upload manually":
        up = st.file_uploader("Upload your CSV", type=["csv"], key="manual_upload_widget")
        if up is not None:
            st.session_state.manual_upload = {"name": up.name, "bytes": up.getvalue()}
            st.success(f"File staged: {up.name} ({len(st.session_state.manual_upload['bytes'])} bytes)")
        elif st.session_state.manual_upload is not None:
            st.info(f"Using previously staged file: {st.session_state.manual_upload['name']}")

    if st.button("🚀 Run Agent", use_container_width=True):
        try:
            files = None
            data = {
                "use_sample": "false",
                "use_llm_narrative": str(use_llm).lower(),
                # send target acceptance and optional threshold
                "target_approval_rate": f"{target_rate:.3f}",
            }
            if use_explicit_thr and thr_val is not None:
                data["threshold"] = f"{thr_val:.3f}"

            def prep_and_pack(df: pd.DataFrame, filename: str):
                """
                Preparation pipeline for agent submission:
                  1) Drop PII columns (defense in depth)
                  2) Remove policy-banned columns by name
                  3) Harmonize schema to agent-required fields
                  4) CSV pack for multipart/form-data
                """
                safe = dedupe_columns(df)
                safe, _ = drop_pii_columns(safe)
                safe = strip_policy_banned(safe)
                safe = to_agent_schema(safe)
                buf = io.StringIO()
                safe.to_csv(buf, index=False)
                return {"file": (filename, buf.getvalue().encode("utf-8"), "text/csv")}

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

            # Inline display
            result = res.get("result", {})
            summary = result.get("summary", {})
            scores = result.get("scores", [])

            st.markdown("### ✅ Run Summary")
            if summary:
                # show totals and tuning used if present
                c0, c1, c2, c3 = st.columns([1,1,1,1])
                c0.metric("Total", summary.get("count", 0))
                c1.metric("Approved", summary.get("approved", 0))
                c2.metric("Denied", summary.get("denied", 0))
                if "target_accept_rate" in summary:
                    c3.metric("Target accept", summary.get("target_accept_rate"))
                elif "used_threshold" in summary:
                    c3.metric("Threshold", summary.get("used_threshold"))

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
