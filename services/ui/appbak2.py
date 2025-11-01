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

# ─────────────────────────────────────────────
# Utils

def dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate-named columns (keep last occurrence). pyarrow-safe for Streamlit."""
    if not isinstance(df, pd.DataFrame):
        return df
    return df.loc[:, ~df.columns.duplicated(keep="last")]

def append_user_info(df: pd.DataFrame) -> pd.DataFrame:
    """Set/overwrite session metadata columns without creating duplicates."""
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

# PII masking helpers
PII_KEYS = ["customer_name", "name", "email", "phone", "address", "ssn", "national_id", "dob"]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{6,}\d")

def scrub_text(s):
    if not isinstance(s, str): 
        return s
    s = EMAIL_RE.sub("***MASKED***", s)
    s = PHONE_RE.sub("***MASKED***", s)
    return s

def mask_pii(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # Column-name based masking
    for col in out.columns:
        if any(k in col.lower() for k in PII_KEYS):
            out[col] = "***MASKED***"
    # Content-level scrubbing for object columns
    for c in out.select_dtypes(include="object"):
        out[c] = out[c].apply(scrub_text)
    return dedupe_columns(out)

# Generators
def generate_raw_synthetic(n: int) -> pd.DataFrame:
    """Generate RAW synthetic data with PII columns."""
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
    """Generate ANON synthetic data WITHOUT PII columns (ready for agent)."""
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

    with st.expander("📊 Data Schema Helper & Template", expanded=False):
        st.markdown("""
**Template Columns (for reference):**

| Column | Description | Example |
|--------|--------------|---------|
| customer_name | PII: Person's name | Alice Nguyen |
| email | PII: Email address | alice@example.com |
| phone | PII: Phone number | +1-202-555-0123 |
| address | PII: Address | 23 Elm St, Boston, MA |
| national_id | PII: ID number | 85739201 |
| age | Applicant age | 35 |
| income | Annual income | 75000 |
| employment_length | Years employed | 8 |
| loan_amount | Requested loan | 20000 |
| loan_duration_months | Loan term | 60 |
| collateral_value | Asset value | 30000 |
| collateral_type | Asset type | house/car |
| co_loaners | Co-signers | 1 |
| credit_score | Bureau score | 720 |
| existing_debt | Current debt | 10000 |
| assets_owned | Declared assets | 80000 |
| DTI | Debt-to-Income | 0.13 |
| LTV | Loan-to-Value | 0.66 |
| CCR | Collateral Coverage | 1.5 |
| ITI | Installment-to-Income | 0.05 |
| CWI | Creditworthiness Index | 0.85 |
""")
        csv_template = pd.DataFrame({
            "customer_name": ["Alice Nguyen"],
            "email": ["alice@example.com"],
            "phone": ["+1-202-555-0123"],
            "address": ["23 Elm St, Boston, MA"],
            "national_id": [85739201],
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
        st.download_button(
            "📥 Download Template CSV (with PII)",
            csv_template.to_csv(index=False).encode("utf-8"),
            "credit_data_template_with_pii.csv",
            "text/csv"
        )

    rows = st.slider("Number of rows to generate", 50, 1000, 200, step=50)
    colA, colB = st.columns(2)

    # Button A: Generate RAW (with PII)
    with colA:
        if st.button("🔴 Generate RAW Synthetic Data (with PII)", use_container_width=True):
            raw_df = generate_raw_synthetic(rows)
            raw_df = append_user_info(raw_df)
            st.session_state.synthetic_raw_df = dedupe_columns(raw_df)
            raw_path = save_to_runs(st.session_state.synthetic_raw_df, "synthetic_raw")
            st.success(f"Generated RAW (PII) dataset with {rows} rows. Saved to {raw_path}")
            st.dataframe(dedupe_columns(st.session_state.synthetic_raw_df.head(10)), use_container_width=True)

    # Button B: Generate ANON (ready for agent)
    with colB:
        if st.button("🟢 Generate ANON Synthetic Data (ready for agent)", use_container_width=True):
            if "synthetic_raw_df" in st.session_state:
                # Start from a copy and mask PII
                base = st.session_state.synthetic_raw_df.copy()
                masked = mask_pii(base)

                # Columns to absolutely drop (PII surface), using name matching
                drop_pii_cols = [c for c in masked.columns if any(k in c.lower() for k in PII_KEYS)]

                # Keep only non-PII + key columns we need downstream
                keep_core = [
                    "application_id","age","income","employment_length","loan_amount","loan_duration_months",
                    "collateral_value","collateral_type","co_loaners","credit_score","existing_debt",
                    "assets_owned","DTI","LTV","CCR","ITI","CWI"
                ]
                keep_meta_present = [c for c in ["session_user_name","session_user_email","session_flagged","created_at"] if c in masked.columns]

                # Build the keep list in order, avoiding duplicates
                keep = []
                for col in masked.columns:
                    if col in keep_core and col not in keep:
                        keep.append(col)

                # Ensure required cores exist (pull from base if missing)
                for col in keep_core:
                    if col not in masked.columns and col in base.columns:
                        masked[col] = base[col]
                        if col not in keep:
                            keep.append(col)

                # Include existing meta columns if present
                for m in keep_meta_present:
                    if m not in keep:
                        keep.append(m)

                # Remove explicit PII columns
                keep = [c for c in keep if c not in drop_pii_cols]

                anon_df = masked[keep].copy()
            else:
                anon_df = generate_anon_synthetic(rows)

            anon_df = append_user_info(anon_df)
            anon_df = dedupe_columns(anon_df)

            st.session_state.synthetic_df = anon_df
            anon_path = save_to_runs(st.session_state.synthetic_df, "synthetic_anon")
            st.success(f"Generated ANON dataset with {len(anon_df)} rows. Saved to {anon_path}")
            st.dataframe(dedupe_columns(anon_df.head(10)), use_container_width=True)

    # Quick visuals for latest ANON set
    if "synthetic_df" in st.session_state:
        with st.expander("📈 Quick Visuals (Latest ANON Data)", expanded=False):
            dfv = st.session_state.synthetic_df
            num_cols = [c for c in ["income","loan_amount","collateral_value","credit_score","DTI","LTV","CCR","ITI","CWI"] if c in dfv.columns]
            if num_cols:
                c1, c2, c3 = st.columns(3)
                cols = [c1, c2, c3]
                for i, c in enumerate(num_cols[:9]):
                    with cols[i % 3]:
                        st.bar_chart(dfv[c].sample(min(200, len(dfv))))
            if "collateral_type" in dfv.columns:
                st.write("Collateral type distribution")
                st.bar_chart(dfv["collateral_type"].value_counts())

# ─────────────────────────────────────────────
# 🧹 TAB 2 — Anonymize & Sanitize Data
with tab_clean:
    st.subheader("🧹 Upload & Anonymize Customer Data")
    st.markdown("Upload your real dataset; we’ll detect and mask PII before you use it.")

    uploaded = st.file_uploader("Upload CSV file", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.write("📊 Original Data Preview:")
        st.dataframe(dedupe_columns(df.head(5)), use_container_width=True)

        df_clean = mask_pii(df)
        df_clean = append_user_info(df_clean)
        df_clean = dedupe_columns(df_clean)
        st.session_state.anonymized_df = df_clean

        st.write("✅ Sanitized Data Preview:")
        st.dataframe(dedupe_columns(df_clean.head(5)), use_container_width=True)

        fpath = save_to_runs(df_clean, "anonymized")
        st.success(f"Saved anonymized file: {fpath}")
        st.download_button("⬇️ Download Clean Data", dedupe_columns(df_clean).to_csv(index=False).encode("utf-8"),
                           os.path.basename(fpath), "text/csv")

# ─────────────────────────────────────────────
# 📤 TAB 3 — Run Credit Appraisal Agent
with tab_run:
    st.subheader("📤 Run Credit Appraisal Agent")

    # keep state for manual upload (so it persists across reruns)
    if "manual_upload" not in st.session_state:
        st.session_state.manual_upload = None

    data_choice = st.selectbox(
        "Select Data Source",
        [
            "Use sample dataset",
            "Use synthetic (ANON)",
            "Use synthetic (RAW – auto-mask)",
            "Use anonymized dataset",
            "Upload manually"
        ]
    )
    use_llm = st.checkbox("Use LLM narrative", value=True)
    agent = "credit_appraisal"

    # Show uploader BEFORE clicking the button (and persist in session)
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
            data = {"use_sample": "false", "use_llm_narrative": str(use_llm).lower()}

            if data_choice == "Use sample dataset":
                data["use_sample"] = "true"

            elif data_choice == "Use synthetic (ANON)":
                if "synthetic_df" not in st.session_state:
                    st.warning("No ANON synthetic dataset found. Generate it in the first tab.")
                    st.stop()
                buf = io.StringIO()
                dedupe_columns(st.session_state.synthetic_df).to_csv(buf, index=False)
                files = {"file": ("synthetic_anon.csv", buf.getvalue().encode("utf-8"), "text/csv")}

            elif data_choice == "Use synthetic (RAW – auto-mask)":
                if "synthetic_raw_df" not in st.session_state:
                    st.warning("No RAW synthetic dataset found. Generate it in the first tab.")
                    st.stop()
                safe_df = mask_pii(st.session_state.synthetic_raw_df)
                # Drop PII columns entirely
                safe_df = safe_df[[c for c in safe_df.columns if not any(k in c.lower() for k in PII_KEYS)] +
                                  [c for c in safe_df.columns if c.startswith("session_") or c in ("created_at","application_id")]]
                safe_df = dedupe_columns(safe_df)
                buf = io.StringIO()
                safe_df.to_csv(buf, index=False)
                files = {"file": ("synthetic_raw_masked.csv", buf.getvalue().encode("utf-8"), "text/csv")}

            elif data_choice == "Use anonymized dataset":
                if "anonymized_df" not in st.session_state:
                    st.warning("No anonymized dataset found. Create it in the second tab.")
                    st.stop()
                buf = io.StringIO()
                dedupe_columns(st.session_state.anonymized_df).to_csv(buf, index=False)
                files = {"file": ("anonymized.csv", buf.getvalue().encode("utf-8"), "text/csv")}

            elif data_choice == "Upload manually":
                up = st.session_state.manual_upload
                if up is None:
                    st.warning("Please upload a CSV first.")
                    st.stop()
                # Auto-mask PII on uploaded data before sending (safety net)
                try:
                    tmp_df = pd.read_csv(io.BytesIO(up["bytes"]))
                    tmp_df = mask_pii(tmp_df)
                    tmp_df = dedupe_columns(tmp_df)
                    buf = io.StringIO()
                    tmp_df.to_csv(buf, index=False)
                    files = {"file": (up["name"], buf.getvalue().encode("utf-8"), "text/csv")}
                except Exception:
                    # If reading failed, just send raw bytes
                    files = {"file": (up["name"], up["bytes"], "text/csv")}

            r = requests.post(f"{API_URL}/v1/agents/{agent}/run", data=data, files=files)
            if r.status_code != 200:
                st.error(f"Run failed ({r.status_code}): {r.text}")
                st.stop()

            res = r.json()
            st.session_state.last_run_id = res.get("run_id")
            st.success(f"✅ Run succeeded! Run ID: {st.session_state.last_run_id}")

            # Inline display: summary + sample scores
            result = res.get("result", {})
            summary = result.get("summary", {})
            scores = result.get("scores", [])

            st.markdown("### ✅ Run Summary")
            if summary:
                st.metric("Total", summary.get("count", 0))
                c1, c2 = st.columns(2)
                c1.metric("Approved", summary.get("approved", 0))
                c2.metric("Denied", summary.get("denied", 0))

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
