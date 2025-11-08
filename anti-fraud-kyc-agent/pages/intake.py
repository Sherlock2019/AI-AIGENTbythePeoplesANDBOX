"""Customer intake workflow for the Anti-Fraud & KYC agent."""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import streamlit as st

HF_DEFAULT_DATASET = "uciml/default-of-credit-card-clients"
KAGGLE_RESULTS_KEY = "afk_kaggle_results"
KAGGLE_MANIFEST_KEY = "afk_kaggle_last_manifest"
BASE_COLUMNS = [
    "applicant_id",
    "full_name",
    "email",
    "country",
    "gov_id",
    "occupation",
    "source_of_funds",
    "transaction_amount",
    "channel",
    "ip_country",
    "device_id",
    "risk_score",
]


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def _read_table(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raw = uploaded_file.read()
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            sample = "\n".join(text.splitlines()[:10])
            try:
                dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
                sep = dialect.delimiter
            except Exception:
                sep = ","
            return pd.read_csv(io.StringIO(text), sep=sep)
        except Exception:
            continue
    return pd.read_csv(io.BytesIO(raw), engine="python")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename_map = {
        "full_name": ["full_name", "name", "customer_name"],
        "email": ["email", "customer_email"],
        "country": ["country", "country_code", "nationality"],
        "gov_id": ["gov_id", "passport", "national_id", "ssn"],
        "occupation": ["occupation", "job_title", "employment"],
        "source_of_funds": ["source_of_funds", "funds_source", "income_source"],
        "transaction_amount": ["transaction_amount", "amount", "amt"],
        "channel": ["channel", "channel_type"],
        "ip_country": ["ip_country", "ip_location"],
        "device_id": ["device_id", "device"],
        "risk_score": ["risk_score", "fraud_score", "class"],
    }
    for target, candidates in rename_map.items():
        for cand in candidates:
            if cand in df.columns:
                df.rename(columns={cand: target}, inplace=True)
                break
    if "applicant_id" not in df.columns:
        df["applicant_id"] = [f"AFK-{_ts()}-{i:04d}" for i in range(len(df))]
    for col in BASE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    ordered = BASE_COLUMNS + [c for c in df.columns if c not in BASE_COLUMNS]
    return df[ordered]


def _generate_synthetic(rows: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    countries = ["US", "GB", "DE", "VN", "IN", "SG", "CA"]
    occupations = ["Engineer", "Trader", "Consultant", "Teacher", "Founder", "Doctor"]
    funds = ["Salary", "Business", "Investments", "Crypto"]
    channels = ["Web", "Mobile", "Branch", "API"]
    payload: List[Dict[str, Any]] = []
    for i in range(rows):
        country = rng.choice(countries)
        payload.append(
            {
                "applicant_id": f"AFK-SYN-{_ts()}-{i:04d}",
                "full_name": f"Applicant {i:04d}",
                "email": f"user{i:04d}@example.ai",
                "country": country,
                "gov_id": f"{country}{rng.integers(100000, 999999)}",
                "occupation": rng.choice(occupations),
                "source_of_funds": rng.choice(funds),
                "transaction_amount": round(max(50, rng.normal(3500, 1200)), 2),
                "channel": rng.choice(channels),
                "ip_country": rng.choice(countries),
                "device_id": f"DEV-{rng.integers(10000, 99999)}",
                "risk_score": round(np.clip(rng.normal(35, 20), 0, 100), 2),
            }
        )
    return pd.DataFrame(payload)


def _load_hf_dataset(repo_id: str, limit: int = 2000) -> pd.DataFrame:
    from datasets import load_dataset

    ds = load_dataset(repo_id)
    split = next(iter(ds.keys()))
    df = ds[split].to_pandas()
    if limit:
        df = df.head(limit)
    if df.empty:
        raise RuntimeError(f"{repo_id} returned no rows.")
    return df


def _ensure_kaggle_env() -> bool:
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    cfg = Path.home() / ".kaggle" / "kaggle.json"
    if not cfg.exists():
        return False
    try:
        cfg.chmod(0o600)
    except Exception:
        pass
    try:
        data = json.loads(cfg.read_text())
        os.environ.setdefault("KAGGLE_USERNAME", data.get("username", ""))
        os.environ.setdefault("KAGGLE_KEY", data.get("key", ""))
        return bool(os.environ["KAGGLE_USERNAME"] and os.environ["KAGGLE_KEY"])
    except Exception:
        return False


def _kaggle_cli() -> str:
    exe = shutil.which("kaggle")
    if not exe:
        raise FileNotFoundError(
            "Kaggle CLI is not installed. Run `pip install kaggle` and ensure it is on PATH."
        )
    return exe


def _run_kaggle(args: List[str]) -> subprocess.CompletedProcess:
    cmd = [_kaggle_cli(), *args]
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _download_kaggle_dataset(ref: str, limit: int, runs_dir: Path):
    """
    Download a Kaggle dataset (CSV) and return a normalized DataFrame plus manifest path.
    """
    if not _ensure_kaggle_env():
        raise RuntimeError("Kaggle credentials not configured. Upload ~/.kaggle/kaggle.json or export KAGGLE_USERNAME/KAGGLE_KEY.")

    slug = ref.replace("/", "__")
    ts = _ts()
    dest = runs_dir / "kaggle" / slug / ts
    dest.mkdir(parents=True, exist_ok=True)

    proc = _run_kaggle(["datasets", "download", "-d", ref, "-p", str(dest), "--unzip"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "Unknown Kaggle CLI error")

    csv_candidates = list(dest.rglob("*.csv"))
    if not csv_candidates:
        raise FileNotFoundError("No CSV file found in downloaded archive.")
    csv_candidates.sort()
    csv_path = csv_candidates[0]
    if len(csv_candidates) > 1:
        st.info(
            f"Multiple CSV files detected inside Kaggle archive; using `{csv_path.name}` by default."
        )

    df_kaggle = pd.read_csv(csv_path).head(limit)
    df_kaggle = _normalize_columns(df_kaggle)

    manifest = {
        "timestamp": ts,
        "ref": ref,
        "row_limit": limit,
        "rows_imported": len(df_kaggle),
        "target_csv": csv_path.name,
        "dest_dir": str(dest),
        "files": [str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file()],
    }
    manifest_path = dest / f"manifest_{ts}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    st.session_state[KAGGLE_MANIFEST_KEY] = manifest

    return df_kaggle, manifest_path


def _store_intake_df(ss, runs_dir: Path, df: pd.DataFrame, *, append: bool = False) -> None:
    existing = ss.get("afk_intake_df")
    if append and isinstance(existing, pd.DataFrame) and not existing.empty:
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df.reset_index(drop=True)
    ss["afk_intake_df"] = combined
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "stage_a_intake.csv").write_bytes(combined.to_csv(index=False).encode("utf-8"))


def _append_manual_record(ss, runs_dir: Path, record: Dict[str, Any]) -> None:
    df = _normalize_columns(pd.DataFrame([record]))
    _store_intake_df(ss, runs_dir, df, append=True)


def render_intake_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("A) Intake — Datasets, Synth Generation & Manual Capture")
    st.caption("Feed KYC by importing historical data, generating synthetic applicants, or capturing individuals manually.")

    # ---- Upload ----
    st.markdown("### 1. Upload CSV/XLSX datasets")
    col_up, col_mode = st.columns([2, 1])
    with col_up:
        uploads = st.file_uploader(
            "Upload one or more files",
            type=["csv", "tsv", "txt", "xlsx"],
            accept_multiple_files=True,
            key="afk_upload_files",
        )
    with col_mode:
        mode = st.radio("When new data arrives", ["Replace current", "Append to current"], key="afk_upload_mode")

    if uploads:
        frames: List[pd.DataFrame] = []
        for upl in uploads:
            try:
                frames.append(_normalize_columns(_read_table(upl)))
                st.success(f"Loaded `{upl.name}`.")
            except Exception as exc:
                st.error(f"Failed to read {upl.name}: {exc}")
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            _store_intake_df(ss, runs_dir, combined, append=(mode == "Append to current"))
            st.info(f"Dataset now tracks {len(ss['afk_intake_df']):,} applicants.")

    # ---- Hugging Face import ----
    st.markdown("### 2. Import from Hugging Face")
    hf_repo = st.text_input("Repo ID", HF_DEFAULT_DATASET)
    hf_limit = st.slider("Row limit", 100, 5000, 1500, 100)
    if st.button("⬇️ Load dataset from Hugging Face", key="afk_hf_import"):
        try:
            df_hf = _normalize_columns(_load_hf_dataset(hf_repo, limit=hf_limit))
            _store_intake_df(ss, runs_dir, df_hf, append=True)
            st.success(f"Imported {len(df_hf):,} rows from {hf_repo}.")
        except Exception as exc:
            st.error(f"Hugging Face import failed: {exc}")
            needs_fallback = (
                isinstance(exc, FileNotFoundError)
                or "doesn't exist" in str(exc).lower()
                or "not found" in str(exc).lower()
            )
            if needs_fallback and "/" in hf_repo:
                st.info("Attempting Kaggle fallback with the same dataset id…")
                try:
                    df_kaggle, manifest_path = _download_kaggle_dataset(hf_repo, hf_limit, runs_dir)
                    _store_intake_df(ss, runs_dir, df_kaggle, append=True)
                    st.success(f"Imported {len(df_kaggle):,} rows via Kaggle fallback.")
                    st.caption(f"Kaggle cache → `{manifest_path}`")
                except Exception as kaggle_exc:
                    st.error(f"Kaggle fallback failed: {kaggle_exc}")
                    st.info("Use the Kaggle importer below or upload your own file.")
            else:
                st.info("Try another repo ID or provide your own dataset. You can also use the Kaggle importer below.")

    st.markdown("### 3. Import from Kaggle (CLI)")
    kaggle_query = st.text_input("Search Kaggle datasets", "fraud detection", key="afk_kaggle_query")
    if st.button("🔎 Search Kaggle", key="afk_kaggle_search"):
        if not _ensure_kaggle_env():
            st.error("Kaggle credentials not found. Place kaggle.json under ~/.kaggle or set KAGGLE_USERNAME/KAGGLE_KEY.")
        else:
            try:
                result = _run_kaggle(["datasets", "list", "-s", kaggle_query, "-v"])
                if result.returncode != 0:
                    raise RuntimeError(result.stderr or result.stdout)
                ss[KAGGLE_RESULTS_KEY] = pd.read_csv(io.StringIO(result.stdout))
                st.success(f"Found {len(ss[KAGGLE_RESULTS_KEY]):,} Kaggle entries.")
            except FileNotFoundError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Kaggle search failed: {exc}")

    kaggle_results = ss.get(KAGGLE_RESULTS_KEY)
    if isinstance(kaggle_results, pd.DataFrame) and not kaggle_results.empty:
        st.dataframe(kaggle_results, use_container_width=True, hide_index=True)
        refs = kaggle_results["ref"].astype(str).tolist()
        selected_ref = st.selectbox("Choose dataset ref", refs, key="afk_kaggle_ref")
        kaggle_rows = st.slider("Row limit (post-import)", 100, 5000, 1500, 100, key="afk_kaggle_row_limit")
        if st.button("⬇️ Download Kaggle dataset", key="afk_kaggle_download"):
            try:
                df_kaggle, manifest_path = _download_kaggle_dataset(selected_ref, kaggle_rows, runs_dir)
                _store_intake_df(ss, runs_dir, df_kaggle, append=True)
                st.success(f"Imported {len(df_kaggle):,} rows from {selected_ref}.")
                st.caption(f"Kaggle cache → `{manifest_path}`")
            except Exception as exc:
                st.error(f"Kaggle download failed: {exc}")

    # ---- Synthetic data ----
    st.markdown("### 4. Generate synthetic applicants")
    synth_rows = st.slider("Rows to synthesize", 50, 2000, 300, 50)
    if st.button("🎲 Generate synthetic dataset", key="afk_synth_generate"):
        df_synth = _normalize_columns(_generate_synthetic(synth_rows))
        _store_intake_df(ss, runs_dir, df_synth, append=True)
        st.success(f"Synthetic dataset generated ({len(df_synth):,} rows).")

    # ---- Manual capture ----
    st.markdown("### 5. Quick manual capture")
    with st.form("afk_intake_form"):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full name", value=ss.get("afk_name", ""))
            email = st.text_input("Email", value=ss.get("afk_email", ""))
            country = st.selectbox("Country", ["US", "CA", "UK", "VN", "IN", "DE", "SG"], index=0)
        with col2:
            gov_id = st.text_input("Gov ID / Passport")
            occupation = st.text_input("Occupation / Role")
            source_of_funds = st.selectbox("Source of funds", ["Salary", "Business", "Investments", "Crypto", "Other"])
        notes = st.text_area("Notes", placeholder="Context, onboarding channel, product selected")
        saved = st.form_submit_button("💾 Save applicant")

    if saved:
        if not full_name.strip():
            st.error("Full name is required.")
        else:
            record = {
                "applicant_id": f"AFK-MAN-{_ts()}",
                "full_name": full_name.strip(),
                "email": email.strip(),
                "country": country,
                "gov_id": gov_id.strip(),
                "occupation": occupation.strip(),
                "source_of_funds": source_of_funds,
                "notes": notes.strip(),
                "transaction_amount": 0,
                "channel": "Manual",
                "ip_country": country,
                "device_id": "MANUAL",
                "risk_score": 25,
                "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
            }
            _append_manual_record(ss, runs_dir, record)
            ss["afk_name"] = record["full_name"]
            ss["afk_email"] = record["email"]
            st.success("Applicant captured and ready for Stage B.")

    active_df = ss.get("afk_intake_df")
    if isinstance(active_df, pd.DataFrame) and not active_df.empty:
        st.markdown("### ✅ Active intake dataset")
        st.caption(f"Rows: {len(active_df):,} • Columns: {len(active_df.columns)}")
        st.dataframe(active_df.head(200), use_container_width=True)
        st.download_button(
            "⬇️ Download intake CSV",
            data=active_df.to_csv(index=False).encode("utf-8"),
            file_name="afk_intake_dataset.csv",
            mime="text/csv",
        )
    else:
        st.info("Load or generate data to continue to Stage B.")
