"""Fraud detection tab."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
import joblib

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BASE_DIR / "models"
TRAINED_DIR = MODEL_DIR / "trained"
PRODUCTION_DIR = MODEL_DIR / "production"
for _dir in (MODEL_DIR, TRAINED_DIR, PRODUCTION_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

MODEL_FAMILIES = [
    {"Model": "Logistic Regression", "Type": "Local baseline", "GPU": "CPU", "Notes": "Fast + explainable"},
    {"Model": "Random Forest", "Type": "Tabular ensemble", "GPU": "CPU / GPU", "Notes": "Handles mixed features"},
    {"Model": "Gradient Boost", "Type": "TAB GBDT", "GPU": "CPU / GPU", "Notes": "Strong accuracy"},
    {"Model": "mistralai/Mistral-7B", "Type": "HF LLM (narratives)", "GPU": ">= 8 GB", "Notes": "Text reasoning for alerts"},
    {"Model": "meta-llama/Meta-Llama-3-8B", "Type": "HF LLM", "GPU": ">= 12 GB", "Notes": "Multilingual risk notes"},
]

GPU_PROFILES = [
    "CPU (slow)",
    "GPU: 1×A10",
    "GPU: 1×L40",
    "GPU: 1×A100",
]

FEATURE_COLS = ["transaction_amount", "risk_score", "pep_flag", "sanctions_hit"]


def _base_dataframe(ss) -> pd.DataFrame:
    for key in ("afk_kyc_df", "afk_anonymized_df", "afk_intake_df"):
        df = ss.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df.copy()
    return pd.DataFrame()


def _score_transactions(df: pd.DataFrame, pep_weight: float, sanctions_weight: float) -> pd.DataFrame:
    if df.empty:
        return df
    sample = df.copy()
    amount = pd.to_numeric(sample.get("transaction_amount", pd.Series(5000, index=sample.index)), errors="coerce").fillna(2500)
    risk = pd.to_numeric(sample.get("risk_score", pd.Series(35, index=sample.index)), errors="coerce").fillna(35)
    pep = sample.get("pep_flag", pd.Series(False, index=sample.index)).astype(bool)
    sanctions = sample.get("sanctions_hit", pd.Series(False, index=sample.index)).astype(bool)

    score = (
        0.4 * np.clip(risk, 0, 100)
        + 0.3 * np.clip(amount / (amount.max() or 1) * 100, 0, 100)
        + pep_weight * pep.astype(float) * 100
        + sanctions_weight * sanctions.astype(float) * 100
    )

    sample["fraud_score"] = np.clip(score, 0, 100).round(2)
    return sample


def _ensure_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame(index=df.index)
    feats["transaction_amount"] = pd.to_numeric(df.get("transaction_amount"), errors="coerce").fillna(0)
    feats["risk_score"] = pd.to_numeric(df.get("risk_score"), errors="coerce").fillna(0)
    feats["pep_flag"] = df.get("pep_flag", pd.Series(False, index=df.index)).astype(int)
    feats["sanctions_hit"] = df.get("sanctions_hit", pd.Series(False, index=df.index)).astype(int)
    return feats[FEATURE_COLS]


def _list_models(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.joblib"), key=lambda p: p.stat().st_mtime, reverse=True)


def render_fraud_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("D) Fraud Detection")
    st.caption("Prioritize investigators by combining heuristic signals, sanctions hits, and KYC results.")

    import_col, export_col = st.columns(2)
    with import_col:
        if st.button("⬅️ Load Stage C anonymized data", use_container_width=True):
            st.success("Stage C dataset loaded into this view.")
    with export_col:
        if st.button("➡️ Send results to Stage F (Human Review)", use_container_width=True):
            st.success("Outputs will appear automatically in Stage F once scoring completes.")

    st.markdown("### 🧠 Model & Hardware selection")
    st.dataframe(pd.DataFrame(MODEL_FAMILIES), use_container_width=True)
    model_names = [m["Model"] for m in MODEL_FAMILIES]
    default_model = ss.get("afk_fraud_model_choice", model_names[0])
    if default_model not in model_names:
        default_model = model_names[0]
    model_choice = st.selectbox(
        "Fraud model",
        model_names,
        index=model_names.index(default_model),
        key="afk_fraud_model_choice_widget",
    )
    ss["afk_fraud_model_choice"] = model_choice

    default_gpu = ss.get("afk_fraud_gpu_choice", GPU_PROFILES[1])
    if default_gpu not in GPU_PROFILES:
        default_gpu = GPU_PROFILES[1]
    gpu_choice = st.selectbox(
        "GPU profile",
        GPU_PROFILES,
        index=GPU_PROFILES.index(default_gpu),
        key="afk_fraud_gpu_choice_widget",
    )
    ss["afk_fraud_gpu_choice"] = gpu_choice

    st.caption(f"Using `{model_choice}` with `{gpu_choice}` profile (UI-only placeholder).")

    base_df = _base_dataframe(ss)
    if base_df.empty:
        st.info("Run Stages A–C first so there is data to score.")
        return

    st.markdown("### 🔁 Registry choice")
    col_mod, col_alt = st.columns([1.2, 1])
    with col_mod:
        registry_choice = st.radio(
            "Model registry",
            ["Production", "Trained"],
            horizontal=True,
            key="afk_registry_choice",
        )
    if registry_choice == "Production":
        available = _list_models(PRODUCTION_DIR)
        label = "Production model"
    else:
        available = _list_models(TRAINED_DIR)
        label = "Trained model"

    selected_model_path = None
    if available:
        options = {f"{p.name} ({datetime.fromtimestamp(p.stat().st_mtime).strftime('%b %d %H:%M')})": p for p in available}
        display = st.selectbox(label, list(options.keys()), key=f"{registry_choice}_model_select")
        selected_model_path = options[display]
        st.caption(f"Selected file: `{selected_model_path.name}`")
    else:
        st.caption(f"No {registry_choice.lower()} models found yet.")

    pep_weight = st.slider("PEP weight", 0.0, 1.0, 0.4, 0.05)
    sanctions_weight = st.slider("Sanctions weight", 0.0, 1.0, 0.6, 0.05)
    threshold = st.slider("Escalation threshold", 40, 95, 70, 1)

    run_scoring = st.button("🚀 Run Fraud Detection", use_container_width=True)

    if not run_scoring and "afk_fraud_df" not in ss:
        st.info("Configure the sliders above and click **Run Fraud Detection**.")
        return

    if run_scoring:
        scored = _score_transactions(base_df, pep_weight, sanctions_weight)
        if scored.empty:
            st.warning("No rows available to score.")
            return

        if selected_model_path:
            try:
                clf = joblib.load(selected_model_path)
                features = _ensure_feature_frame(scored)
                if hasattr(clf, "predict_proba"):
                    model_prob = clf.predict_proba(features)[:, 1]
                else:
                    model_prob = clf.predict(features)
                scored["model_score"] = (np.asarray(model_prob, dtype=float) * 100).round(2)
                scored["model_action"] = np.where(scored["model_score"] >= threshold, "Review", "Auto-Clear")
                scored["fraud_score"] = (
                    (pd.to_numeric(scored["fraud_score"], errors="coerce") + scored["model_score"]) / 2.0
                ).round(2)
                st.success("Applied selected model on top of heuristic signals.")
            except Exception as exc:
                st.warning(f"Could not apply ML model: {exc}")
        scored["fraud_action"] = np.where(scored["fraud_score"] >= threshold, "Review", "Auto-Clear")
        ss["afk_fraud_df"] = scored
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / "stage_d_fraud.csv").write_bytes(scored.to_csv(index=False).encode("utf-8"))
        st.session_state["afk_fraud_last_run"] = datetime.utcnow().isoformat()
    else:
        scored = ss.get("afk_fraud_df")
        if scored is None or scored.empty:
            st.info("Run the detector at least once to view results.")
            return
        st.info(f"Showing previously computed results ({st.session_state.get('afk_fraud_last_run','n/a')}).")

    col1, col2, col3 = st.columns(3)
    col1.metric("Transactions scored", len(scored))
    col2.metric("Escalations", int((scored["fraud_action"] == "Review").sum()))
    col3.metric("Auto-clears", int((scored["fraud_action"] == "Auto-Clear").sum()))

    st.dataframe(
        scored[
            [
                "applicant_id",
                "transaction_amount",
                "risk_score",
                "pep_flag",
                "sanctions_hit",
                "fraud_score",
                "fraud_action",
            ]
        ].head(200),
        use_container_width=True,
    )
    st.bar_chart(scored[["fraud_score"]].head(100))

    st.download_button(
        "⬇️ Download fraud scoring CSV",
        data=scored.to_csv(index=False).encode("utf-8"),
        file_name="afk_fraud_scoring.csv",
        mime="text/csv",
    )
