import os
import io
import re
import json
import datetime
import argparse
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional

import pandas as pd
import numpy as np
import requests

# ─────────────────────────────────────────────
# OPTIONAL UI: Streamlit if available, else CLI fallback
try:  # don't crash when Streamlit isn't installed
    import streamlit as st  # type: ignore
    STREAMLIT_AVAILABLE = True
except Exception:  # ModuleNotFoundError or others
    STREAMLIT_AVAILABLE = False
    st = None  # sentinel

# ─────────────────────────────────────────────
# CONFIG (shared)
DEFAULT_API_URL = os.getenv("API_URL", "http://localhost:8090")
RUNS_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/api/.runs")
os.makedirs(RUNS_DIR, exist_ok=True)

# Base policies
BANNED_NAMES_BASE = {"race", "gender", "religion", "ethnicity", "ssn", "national_id"}
PII_COLS_BASE = {"customer_name", "name", "email", "phone", "address", "ssn", "national_id", "dob"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{6,}\d")

@dataclass
class UserInfo:
    name: str
    email: str
    flagged: bool = False
    timestamp: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name.strip(),
            "email": self.email.strip(),
            "flagged": bool(self.flagged),
            "timestamp": self.timestamp
            or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

# ─────────────────────────────────────────────
# CORE UTILITIES (UI-independent)

def dedupe_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated(keep="last")]


def scrub_text_pii(s):
    if not isinstance(s, str):
        return s
    s = EMAIL_RE.sub("", s)
    s = PHONE_RE.sub("", s)
    return s.strip()


def drop_pii_columns(df: pd.DataFrame, extra_pii: Optional[set] = None) -> Tuple[pd.DataFrame, list]:
    pii = PII_COLS_BASE.union({c.strip().lower() for c in (extra_pii or set()) if c})
    original_cols = list(df.columns)
    keep_cols = [c for c in original_cols if all(k not in c.lower() for k in pii)]
    dropped = [c for c in original_cols if c not in keep_cols]
    out = df[keep_cols].copy()
    for c in out.select_dtypes(include="object"):
        out[c] = out[c].apply(scrub_text_pii)
    return dedupe_columns(out), dropped


def strip_policy_banned(df: pd.DataFrame, extra_banned: Optional[set] = None) -> pd.DataFrame:
    banned = BANNED_NAMES_BASE.union({c.strip().lower() for c in (extra_banned or set()) if c})
    keep = [c for c in df.columns if c.lower() not in banned]
    return df[keep]


def apply_column_mapping(df: pd.DataFrame, colmap: Optional[Dict[str, str]] = None) -> pd.DataFrame:
    if not colmap:
        return df
    rename_map = {your: expected for your, expected in colmap.items() if your in df.columns}
    return df.rename(columns=rename_map)


def append_user_info(df: pd.DataFrame, user_info: UserInfo) -> pd.DataFrame:
    meta = user_info.as_dict()
    out = df.copy()
    out["session_user_name"] = meta["name"]
    out["session_user_email"] = meta["email"]
    out["session_flagged"] = meta["flagged"]
    out["created_at"] = meta["timestamp"]
    return dedupe_columns(out)


def save_to_runs(df: pd.DataFrame, prefix: str, flagged: bool = False) -> str:
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    flag_suffix = "_FLAGGED" if flagged else ""
    fname = f"{prefix}_{ts}{flag_suffix}.csv"
    fpath = os.path.join(RUNS_DIR, fname)
    dedupe_columns(df).to_csv(fpath, index=False)
    return fpath

# Agent schema
REQUIRED_FOR_AGENT = [
    "employment_years",
    "debt_to_income",
    "credit_history_length",
    "num_delinquencies",
    "current_loans",
    "requested_amount",
    "loan_term_months",
]


def to_agent_schema(df: pd.DataFrame, overrides: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    out = df.copy()
    n = len(out)

    if "employment_years" not in out.columns:
        out["employment_years"] = out.get("employment_length", 0)

    if "debt_to_income" not in out.columns:
        if "DTI" in out.columns:
            out["debt_to_income"] = pd.to_numeric(out["DTI"], errors="coerce").fillna(0.0)
        elif "existing_debt" in out.columns and "income" in out.columns:
            denom = out["income"].replace(0, np.nan)
            out["debt_to_income"] = (out["existing_debt"] / denom).fillna(0.0).clip(0, 10)
        else:
            out["debt_to_income"] = 0.0

    rng = np.random.default_rng(12345)
    out.setdefault("credit_history_length", rng.integers(0, 30, n))
    out.setdefault("num_delinquencies", np.minimum(rng.poisson(0.2, n), 10))
    out.setdefault("current_loans", rng.integers(0, 5, n))
    out.setdefault("requested_amount", out.get("loan_amount", 0))
    out.setdefault("loan_term_months", out.get("loan_duration_months", 0))

    overrides = overrides or {}
    for k, v in overrides.items():
        out[k] = v

    return dedupe_columns(out)

# Generators
DEFAULTS = dict(
    rows_default=200,
    age_min=21,
    age_max=65,
    income_min=25000,
    income_max=150000,
    emp_min=0,
    emp_max=30,
    loan_min=5000,
    loan_max=100000,
    term_options=[12, 24, 36, 48, 60, 72],
    collateral_types=["house", "car", "land", "deposit"],
    credit_min=300,
    credit_max=850,
    debt_max=50000,
    assets_min=10000,
    assets_max=300000,
)


def _rng():
    return np.random.default_rng(42)


def generate_raw_synthetic(n: int, cfg: Dict[str, Any]) -> pd.DataFrame:
    rng = _rng()
    names = [
        "Alice Nguyen","Bao Tran","Chris Do","Duy Le","Emma Tran",
        "Felix Nguyen","Giang Ho","Hanh Vo","Ivan Pham","Julia Ngo",
    ]
    emails = [f"{nm.split()[0].lower()}.{nm.split()[1].lower()}@gmail.com" for nm in names]
    addrs = [
        "23 Elm St, Boston, MA","19 Pine Ave, San Jose, CA","14 High St, London, UK",
        "55 Nguyen Hue, Ho Chi Minh","78 Oak St, Chicago, IL","10 Broadway, New York, NY",
        "8 Rue Lafayette, Paris, FR","21 Königstr, Berlin, DE","44 Maple Dr, Los Angeles, CA","22 Bay St, Toronto, CA",
    ]
    df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, n + 1)],
        "customer_name": np.random.choice(names, n),
        "email": np.random.choice(emails, n),
        "phone": [f"+1-202-555-{1000+i:04d}" for i in range(n)],
        "address": np.random.choice(addrs, n),
        "national_id": rng.integers(10_000_000, 99_999_999, n),
        "age": rng.integers(cfg["age_min"], cfg["age_max"] + 1, n),
        "income": rng.integers(cfg["income_min"], cfg["income_max"] + 1, n),
        "employment_length": rng.integers(cfg["emp_min"], cfg["emp_max"] + 1, n),
        "loan_amount": rng.integers(cfg["loan_min"], cfg["loan_max"] + 1, n),
        "loan_duration_months": rng.choice(cfg["term_options"], n),
        "collateral_value": rng.integers(max(8000, cfg["loan_min"]//2), max(200000, cfg["loan_max"]*2), n),
        "collateral_type": rng.choice(cfg["collateral_types"], n),
        "co_loaners": rng.choice([0,1,2], n, p=[0.7,0.25,0.05]),
        "credit_score": rng.integers(cfg["credit_min"], cfg["credit_max"] + 1, n),
        "existing_debt": rng.integers(0, cfg["debt_max"] + 1, n),
        "assets_owned": rng.integers(cfg["assets_min"], cfg["assets_max"] + 1, n),
    })
    eps = 1e-9
    df["DTI"] = df["existing_debt"] / (df["income"] + eps)
    df["LTV"] = df["loan_amount"] / (df["collateral_value"] + eps)
    df["CCR"] = df["collateral_value"] / (df["loan_amount"] + eps)
    df["ITI"] = (df["loan_amount"] / (df["loan_duration_months"] + eps)) / (df["income"] + eps)
    df["CWI"] = ((1 - df["DTI"]).clip(0, 1)) * ((1 - df["LTV"]).clip(0, 1)) * (df["CCR"].clip(0, 3))
    return dedupe_columns(df)


def generate_anon_synthetic(n: int, cfg: Dict[str, Any]) -> pd.DataFrame:
    rng = _rng()
    df = pd.DataFrame({
        "application_id": [f"APP_{i:04d}" for i in range(1, n + 1)],
        "age": rng.integers(cfg["age_min"], cfg["age_max"] + 1, n),
        "income": rng.integers(cfg["income_min"], cfg["income_max"] + 1, n),
        "employment_length": rng.integers(cfg["emp_min"], cfg["emp_max"] + 1, n),
        "loan_amount": rng.integers(cfg["loan_min"], cfg["loan_max"] + 1, n),
        "loan_duration_months": rng.choice(cfg["term_options"], n),
        "collateral_value": rng.integers(max(8000, cfg["loan_min"]//2), max(200000, cfg["loan_max"]*2), n),
        "collateral_type": rng.choice(cfg["collateral_types"], n),
        "co_loaners": rng.choice([0,1,2], n, p=[0.7,0.25,0.05]),
        "credit_score": rng.integers(cfg["credit_min"], cfg["credit_max"] + 1, n),
        "existing_debt": rng.integers(0, cfg["debt_max"] + 1, n),
        "assets_owned": rng.integers(cfg["assets_min"], cfg["assets_max"] + 1, n),
    })
    eps = 1e-9
    df["DTI"] = df["existing_debt"] / (df["income"] + eps)
    df["LTV"] = df["loan_amount"] / (df["collateral_value"] + eps)
    df["CCR"] = df["collateral_value"] / (df["loan_amount"] + eps)
    df["ITI"] = (df["loan_amount"] / (df["loan_duration_months"] + eps)) / (df["income"] + eps)
    df["CWI"] = ((1 - df["DTI"]).clip(0, 1)) * ((1 - df["LTV"]).clip(0, 1)) * (df["CCR"].clip(0, 3))
    return dedupe_columns(df)

# ─────────────────────────────────────────────
# STREAMLIT APP (when available)

def _streamlit_app():
    st.set_page_config(page_title="AI Credit Appraisal Platform — Customizable", layout="wide")

    # Sidebar
    st.sidebar.title("⚙️ Global Settings")
    api_url = st.sidebar.text_input("API URL", value=DEFAULT_API_URL)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔒 PII & Policy Columns")
    extra_pii_cols_csv = st.sidebar.text_area(
        "Additional PII-like column names (comma-separated)", value="", placeholder="passport, mother_maiden_name, iban"
    )
    extra_banned_cols_csv = st.sidebar.text_area(
        "Additional policy-banned column names (comma-separated)", value="", placeholder="religion_detail, union_membership"
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔁 Column Mapping (optional)")
    colmap_json = st.sidebar.text_area(
        "Map your columns to standard names (JSON)", value="", placeholder='{"years_at_job": "employment_length", "debt_income_ratio": "DTI"}'
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🏦 Generator Defaults")
    rows_default = st.sidebar.slider("Default rows", 50, 5000, DEFAULTS["rows_default"], step=50)
    age_min, age_max = st.sidebar.slider("Age range", 18, 85, (DEFAULTS["age_min"], DEFAULTS["age_max"]))
    income_min, income_max = st.sidebar.slider(
        "Income range", 5000, 500000, (DEFAULTS["income_min"], DEFAULTS["income_max"]), step=5000
    )
    emp_min, emp_max = st.sidebar.slider("Employment length (years)", 0, 50, (DEFAULTS["emp_min"], DEFAULTS["emp_max"]))
    loan_min, loan_max = st.sidebar.slider(
        "Loan amount range", 1000, 2000000, (DEFAULTS["loan_min"], DEFAULTS["loan_max"]), step=1000
    )
    term_options_default = DEFAULTS["term_options"]
    term_multiselect = st.sidebar.multiselect("Loan term options (months)", term_options_default, default=term_options_default)
    collateral_types_default = DEFAULTS["collateral_types"]
    collateral_types = st.sidebar.multiselect("Collateral types", collateral_types_default, default=collateral_types_default)
    credit_min, credit_max = st.sidebar.slider("Credit score range", 300, 900, (DEFAULTS["credit_min"], DEFAULTS["credit_max"]))
    debt_max = st.sidebar.slider("Existing debt max", 0, 1000000, DEFAULTS["debt_max"], step=1000)
    assets_min, assets_max = st.sidebar.slider(
        "Assets owned range", 0, 3000000, (DEFAULTS["assets_min"], DEFAULTS["assets_max"]), step=1000
    )

    # Header + user
    st.title("💳 AI Credit Appraisal Platform (Customizable)")
    st.caption("Generate, sanitize, or appraise credit datasets securely — with your own parameters.")

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

    user_info = UserInfo(user_name, user_email, flag_session)

    # Shared config
    custom_cfg = dict(
        rows_default=rows_default,
        age_min=age_min,
        age_max=age_max,
        income_min=income_min,
        income_max=income_max,
        emp_min=emp_min,
        emp_max=emp_max,
        loan_min=loan_min,
        loan_max=loan_max,
        term_options=term_multiselect or term_options_default,
        collateral_types=collateral_types or collateral_types_default,
        credit_min=credit_min,
        credit_max=credit_max,
        debt_max=debt_max,
        assets_min=assets_min,
        assets_max=assets_max,
    )

    extra_pii = {c.strip().lower() for c in (extra_pii_cols_csv.split(",") if extra_pii_cols_csv else []) if c.strip()}
    extra_banned = {c.strip().lower() for c in (extra_banned_cols_csv.split(",") if extra_banned_cols_csv else []) if c.strip()}

    USER_COLMAP: Dict[str, str] = {}
    if colmap_json.strip():
        try:
            parsed = json.loads(colmap_json)
            if isinstance(parsed, dict):
                USER_COLMAP = {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            st.sidebar.warning("Invalid JSON in Column Mapping — ignoring.")

    # Tabs
    tab_gen, tab_clean, tab_run, tab_over = st.tabs([
        "🏦 Synthetic Data Generator",
        "🧹 Anonymize & Sanitize Data",
        "📤 Run Credit Appraisal Agent",
        "🧰 Per-Run Overrides",
    ])

    # Per-run overrides storage
    if "per_run_overrides" not in st.session_state:
        st.session_state.per_run_overrides = {}

    with tab_gen:
        st.subheader("🏦 Synthetic Credit Data Generator")
        rows = st.slider("Number of rows to generate", 50, 10000, custom_cfg["rows_default"], step=50)
        colA, colB = st.columns(2)
        with colA:
            if st.button("🔴 Generate RAW Synthetic Data (with PII)", use_container_width=True):
                raw_df = generate_raw_synthetic(rows, custom_cfg)
                raw_df = apply_column_mapping(raw_df, USER_COLMAP)
                raw_df = append_user_info(raw_df, user_info)
                st.session_state.synthetic_raw_df = raw_df
                raw_path = save_to_runs(raw_df, "synthetic_raw", flagged=user_info.flagged)
                st.success(f"Generated RAW (PII) dataset with {rows} rows. Saved to {raw_path}")
                st.dataframe(raw_df.head(10), use_container_width=True)
                st.download_button("⬇️ Download RAW CSV", raw_df.to_csv(index=False).encode("utf-8"), os.path.basename(raw_path), "text/csv")
        with colB:
            if st.button("🟢 Generate ANON Synthetic Data (ready for agent)", use_container_width=True):
                anon_df = generate_anon_synthetic(rows, custom_cfg)
                anon_df = apply_column_mapping(anon_df, USER_COLMAP)
                anon_df = append_user_info(anon_df, user_info)
                st.session_state.synthetic_df = anon_df
                anon_path = save_to_runs(anon_df, "synthetic_anon", flagged=user_info.flagged)
                st.success(f"Generated ANON dataset with {rows} rows. Saved to {anon_path}")
                st.dataframe(anon_df.head(10), use_container_width=True)
                st.download_button("⬇️ Download ANON CSV", anon_df.to_csv(index=False).encode("utf-8"), os.path.basename(anon_path), "text/csv")

    with tab_clean:
        st.subheader("🧹 Upload & Anonymize Customer Data (PII columns will be DROPPED)")
        st.markdown("Upload your **real CSV**. We will drop PII columns (not mask), scrub emails/phones, and apply your optional column mapping.")
        uploaded = st.file_uploader("Upload CSV file", type=["csv"], key="clean_uploader")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
            except Exception as e:
                st.error(f"Could not read CSV: {e}")
                st.stop()
            st.write("📊 Original Data Preview:")
            st.dataframe(dedupe_columns(df.head(5)), use_container_width=True)
            df = apply_column_mapping(df, USER_COLMAP)
            sanitized, dropped_cols = drop_pii_columns(df, extra_pii)
            sanitized = strip_policy_banned(sanitized, extra_banned)
            sanitized = append_user_info(sanitized, user_info)
            sanitized = dedupe_columns(sanitized)
            st.session_state.anonymized_df = sanitized
            st.success(f"Dropped PII columns: {sorted(dropped_cols) if dropped_cols else 'None'}")
            st.write("✅ Sanitized Data Preview:")
            st.dataframe(sanitized.head(5), use_container_width=True)
            fpath = save_to_runs(sanitized, "anonymized", flagged=user_info.flagged)
            st.success(f"Saved anonymized file: {fpath}")
            st.download_button("⬇️ Download Clean Data", sanitized.to_csv(index=False).encode("utf-8"), os.path.basename(fpath), "text/csv")
        else:
            st.info("Choose a CSV to see the sanitize flow.", icon="ℹ️")

    with tab_over:
        st.subheader("🧰 Per-Run Numeric Overrides")
        st.markdown("These values, if set, will **override or create** columns before sending to the agent.")
        o_employment_years = st.number_input("employment_years (override all rows)", value=None, placeholder="leave blank to skip")
        o_debt_to_income = st.number_input("debt_to_income (0-10)", min_value=0.0, max_value=10.0, value=None, step=0.01, placeholder="leave blank to skip")
        o_credit_history_length = st.number_input("credit_history_length (years)", min_value=0, value=None, placeholder="leave blank to skip")
        o_num_delinquencies = st.number_input("num_delinquencies", min_value=0, value=None, placeholder="leave blank to skip")
        o_current_loans = st.number_input("current_loans", min_value=0, value=None, placeholder="leave blank to skip")
        o_requested_amount = st.number_input("requested_amount", min_value=0, value=None, placeholder="leave blank to skip")
        o_loan_term_months = st.number_input("loan_term_months", min_value=0, value=None, placeholder="leave blank to skip")
        st.markdown("**Custom overrides (JSON)** — e.g. `{\"branch_code\": \"HCM-01\", \"risk_tier\": 2}`")
        o_json = st.text_area("Additional column overrides JSON", value="")
        overrides: Dict[str, Any] = {}
        for name, val in [
            ("employment_years", o_employment_years),
            ("debt_to_income", o_debt_to_income),
            ("credit_history_length", o_credit_history_length),
            ("num_delinquencies", o_num_delinquencies),
            ("current_loans", o_current_loans),
            ("requested_amount", o_requested_amount),
            ("loan_term_months", o_loan_term_months),
        ]:
            if val is not None:
                overrides[name] = val
        if o_json.strip():
            try:
                extra = json.loads(o_json)
                if isinstance(extra, dict):
                    overrides.update(extra)
            except Exception:
                st.warning("Invalid JSON in Additional overrides — ignoring.")
        st.session_state["per_run_overrides"] = overrides
        if overrides:
            st.success(f"Overrides prepared: {list(overrides.keys())}")
        else:
            st.info("No overrides set.")

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
                "Upload manually",
            ],
        )
        use_llm = st.checkbox("Use LLM narrative", value=True)
        agent = "credit_appraisal"
        if data_choice == "Upload manually":
            up = st.file_uploader("Upload your CSV", type=["csv"], key="manual_upload_widget")
            if up is not None:
                st.session_state.manual_upload = {"name": up.name, "bytes": up.getvalue()}
                st.success(f"File staged: {up.name} ({len(st.session_state.manual_upload['bytes'])} bytes)")
            elif st.session_state.manual_upload is not None:
                st.info(f"Using previously staged file: {st.session_state.manual_upload['name']}")

        def prep_and_pack(df: pd.DataFrame, filename: str):
            safe = dedupe_columns(df)
            safe = apply_column_mapping(safe, USER_COLMAP)
            safe, _ = drop_pii_columns(safe, extra_pii)
            safe = strip_policy_banned(safe, extra_banned)
            safe = to_agent_schema(safe, overrides=st.session_state.get("per_run_overrides", {}))
            buf = io.StringIO()
            safe.to_csv(buf, index=False)
            return {"file": (filename, buf.getvalue().encode("utf-8"), "text/csv")}

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
                r = requests.post(f"{api_url}/v1/agents/{agent}/run", data=data, files=files)
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
                url = f"{api_url}/v1/runs/{rid}/report?format={fmt}"
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

# ─────────────────────────────────────────────
# CLI FALLBACK (no Streamlit)

def _parse_colmap(colmap_json: Optional[str]) -> Dict[str, str]:
    if not colmap_json:
        return {}
    try:
        parsed = json.loads(colmap_json)
        return {str(k): str(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _cli_main():
    parser = argparse.ArgumentParser(description="AI Credit Appraisal Platform — CLI mode (Streamlit not installed)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # common user args
    def add_user_args(p):
        p.add_argument("--user-name", required=True)
        p.add_argument("--user-email", required=True)
        p.add_argument("--flag", action="store_true")

    # generate
    p_gen = sub.add_parser("generate", help="Generate synthetic data")
    add_user_args(p_gen)
    p_gen.add_argument("--rows", type=int, default=DEFAULTS["rows_default"])
    p_gen.add_argument("--anon", action="store_true", help="Generate ANON instead of RAW")
    p_gen.add_argument("--out", required=True)
    p_gen.add_argument("--colmap-json", default="")

    # clean
    p_clean = sub.add_parser("clean", help="Anonymize & sanitize a CSV")
    add_user_args(p_clean)
    p_clean.add_argument("--inp", required=True)
    p_clean.add_argument("--out", required=True)
    p_clean.add_argument("--extra-pii", default="")
    p_clean.add_argument("--extra-banned", default="")
    p_clean.add_argument("--colmap-json", default="")

    # run agent
    p_run = sub.add_parser("run-agent", help="Run credit appraisal agent with a CSV")
    add_user_args(p_run)
    p_run.add_argument("--api-url", default=DEFAULT_API_URL)
    p_run.add_argument("--csv", required=True)
    p_run.add_argument("--use-llm", action="store_true")
    p_run.add_argument("--overrides-json", default="")

    # tests
    sub.add_parser("run-tests", help="Run built-in unit tests")

    args = parser.parse_args()

    if args.cmd == "run-tests":
        _run_tests()
        return

    user = UserInfo(args.user_name, args.user_email, args.flag)
    colmap = _parse_colmap(getattr(args, "colmap_json", ""))

    if args.cmd == "generate":
        cfg = DEFAULTS.copy()
        df = generate_anon_synthetic(args.rows, cfg) if args.anon else generate_raw_synthetic(args.rows, cfg)
        df = apply_column_mapping(df, colmap)
        df = append_user_info(df, user)
        df.to_csv(args.out, index=False)
        print(f"Wrote {len(df)} rows → {args.out}")

    elif args.cmd == "clean":
        extra_pii = {c.strip().lower() for c in args.extra_pii.split(",") if c.strip()}
        extra_banned = {c.strip().lower() for c in args.extra_banned.split(",") if c.strip()}
        df = pd.read_csv(args.inp)
        df = apply_column_mapping(df, colmap)
        sanitized, dropped_cols = drop_pii_columns(df, extra_pii)
        sanitized = strip_policy_banned(sanitized, extra_banned)
        sanitized = append_user_info(sanitized, user)
        sanitized.to_csv(args.out, index=False)
        print(f"Dropped: {sorted(dropped_cols) if dropped_cols else 'None'}")
        print(f"Wrote {len(sanitized)} rows → {args.out}")

    elif args.cmd == "run-agent":
        df = pd.read_csv(args.csv)
        df, _ = drop_pii_columns(df)
        df = strip_policy_banned(df)
        overrides = _parse_colmap(args.overrides_json)
        df = to_agent_schema(df, overrides=overrides)
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        files = {"file": (os.path.basename(args.csv), buf.getvalue().encode("utf-8"), "text/csv")}
        data = {"use_sample": "false", "use_llm_narrative": str(bool(args.use_llm)).lower()}
        r = requests.post(f"{args.api_url}/v1/agents/credit_appraisal/run", data=data, files=files)
        print(f"HTTP {r.status_code}")
        try:
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)

# ─────────────────────────────────────────────
# TESTS

def _run_tests():
    import unittest

    class CoreTests(unittest.TestCase):
        def setUp(self):
            self.cfg = DEFAULTS.copy()
            self.df_raw = generate_raw_synthetic(10, self.cfg)
            self.df_anon = generate_anon_synthetic(10, self.cfg)

        def test_dedupe_columns(self):
            df = self.df_raw.copy()
            df["dup"] = 1
            df = df.rename(columns={"dup": "age"})  # force duplicate name
            out = dedupe_columns(df)
            self.assertEqual(len(out.columns), len(set(out.columns)))

        def test_drop_pii_columns(self):
            df = self.df_raw.copy()
            clean, dropped = drop_pii_columns(df)
            self.assertTrue("customer_name" not in clean.columns)
            self.assertTrue("email" not in clean.columns)
            self.assertTrue(any(x in dropped for x in ["customer_name", "email"]))

        def test_policy_strip(self):
            df = self.df_raw.copy()
            df["religion"] = "x"
            out = strip_policy_banned(df)
            self.assertTrue("religion" not in out.columns)

        def test_to_agent_schema_creates_required(self):
            df = self.df_anon.copy()[["income", "existing_debt"]]  # minimal
            out = to_agent_schema(df)
            for col in REQUIRED_FOR_AGENT:
                self.assertIn(col, out.columns)

        def test_overrides(self):
            df = self.df_anon.copy()
            out = to_agent_schema(df, overrides={"debt_to_income": 0.5, "loan_term_months": 36})
            self.assertTrue((out["debt_to_income"] == 0.5).all())
            self.assertTrue((out["loan_term_months"] == 36).all())

        def test_append_user_info(self):
            user = UserInfo("Tester", "t@example.com", True)
            out = append_user_info(self.df_anon, user)
            self.assertIn("session_user_name", out.columns)
            self.assertIn("session_user_email", out.columns)
            self.assertIn("session_flagged", out.columns)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CoreTests)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    if not res.wasSuccessful():
        raise SystemExit(1)

# ─────────────────────────────────────────────
# ENTRYPOINT
if __name__ == "__main__":
    if STREAMLIT_AVAILABLE:
        _streamlit_app()
    else:
        _cli_main()

