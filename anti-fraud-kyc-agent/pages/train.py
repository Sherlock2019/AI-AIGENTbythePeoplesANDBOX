"""Training tab for Anti-Fraud agent."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BASE_DIR / "models"
TRAINED_DIR = MODEL_DIR / "trained"
PRODUCTION_DIR = MODEL_DIR / "production"
for _dir in (MODEL_DIR, TRAINED_DIR, PRODUCTION_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = ["transaction_amount", "risk_score", "pep_flag", "sanctions_hit"]
FEEDBACK_FILENAME = "stage_f_feedback.csv"

MODEL_TABLE = [
    {"Model": "Logistic Regression", "Type": "Baseline", "GPU": "CPU", "Notes": "Fast + explainable"},
    {"Model": "Random Forest", "Type": "Ensemble", "GPU": "CPU/GPU", "Notes": "Handles nonlinearities"},
    {"Model": "Gradient Boost", "Type": "Tree Boost", "GPU": "CPU/GPU", "Notes": "Accurate with tabular"},
]

GPU_PROFILES = ["CPU", "GPU: 1×A10", "GPU: 1×L40", "GPU: 1×A100"]


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def _feedback_path(runs_dir: Path) -> Path:
    return Path(runs_dir) / FEEDBACK_FILENAME


def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame(index=df.index)
    feats["transaction_amount"] = pd.to_numeric(df.get("transaction_amount"), errors="coerce").fillna(0)
    feats["risk_score"] = pd.to_numeric(df.get("risk_score"), errors="coerce").fillna(0)
    feats["pep_flag"] = df.get("pep_flag", pd.Series(False, index=df.index)).astype(int)
    feats["sanctions_hit"] = df.get("sanctions_hit", pd.Series(False, index=df.index)).astype(int)
    return feats[FEATURE_COLS]


def _build_labels(df: pd.DataFrame, threshold: float) -> pd.Series:
    if "human_decision" in df.columns:
        return df["human_decision"].astype(str).str.lower().isin(
            ["review", "reject", "request info"]
        ).astype(int)
    return (pd.to_numeric(df.get("fraud_score"), errors="coerce").fillna(0) >= threshold).astype(int)


def render_train_tab(ss, runs_dir: Path) -> None:
    runs_dir = Path(runs_dir)
    st.header("G) Train & Evaluate")
    st.caption("Use human feedback to retrain classifiers, compare against baselines, and manage promotion.")

    feedback_col, upload_col = st.columns([1, 1])
    feedback_path = _feedback_path(runs_dir)
    with feedback_col:
        if feedback_path.exists():
            if st.button("⬅️ Load latest Stage F feedback", use_container_width=True):
                try:
                    ss["afk_feedback_df"] = pd.read_csv(feedback_path)
                    st.success(f"Loaded `{feedback_path.name}`.")
                except Exception as exc:
                    st.error(f"Could not read feedback CSV: {exc}")
        else:
            st.caption("Save feedback in Stage F to auto-load it here.")
    uploaded_file = upload_col.file_uploader("Upload CSV dataset", type=["csv"])

    dataset = None
    data_source = "Not available"

    if uploaded_file is not None:
        try:
            dataset = pd.read_csv(uploaded_file)
            data_source = f"Uploaded file ({uploaded_file.name})"
        except Exception as exc:
            st.error(f"Upload failed: {exc}")
            return
    elif isinstance(ss.get("afk_feedback_df"), pd.DataFrame) and not ss["afk_feedback_df"].empty:
        dataset = ss["afk_feedback_df"].copy()
        data_source = "Stage F human feedback"
    elif feedback_path.exists():
        dataset = pd.read_csv(feedback_path)
        data_source = f"Saved feedback ({feedback_path.name})"
    elif isinstance(ss.get("afk_fraud_df"), pd.DataFrame) and not ss["afk_fraud_df"].empty:
        dataset = ss["afk_fraud_df"].copy()
        data_source = "Stage D fraud scoring"

    if dataset is None or dataset.empty:
        st.info("No dataset available yet. Provide feedback in Stage F or upload a CSV.")
        return

    st.markdown("### 1. Dataset preview")
    st.caption(f"Source: **{data_source}** — Rows: {len(dataset):,}")
    st.dataframe(dataset.head(200), use_container_width=True)
    st.download_button(
        "⬇️ Download current dataset",
        data=dataset.to_csv(index=False).encode("utf-8"),
        file_name="afk_training_dataset.csv",
        mime="text/csv",
    )

    st.markdown("### 2. Select model & runtime")
    st.dataframe(pd.DataFrame(MODEL_TABLE), use_container_width=True)
    dataset_rows = len(dataset)
    fraud_series = pd.to_numeric(dataset.get("fraud_score"), errors="coerce")
    fraud_series = fraud_series if isinstance(fraud_series, pd.Series) else pd.Series(dtype=float)
    high_risk_rate = float((fraud_series >= 70).mean()) if not fraud_series.empty else None

    st.markdown("#### ⭐ Recommended models (EQACh signal)")
    hint = f"{dataset_rows:,} rows analysed"
    if high_risk_rate is not None and not np.isnan(high_risk_rate):
        hint += f" · {high_risk_rate*100:.1f}% high-risk cases"
    st.caption(hint)

    def score_afk_model(name: str) -> tuple[int, str]:
        """Simple heuristic so operators see why a classifier is suggested."""
        reason = ""
        score = 0

        if name == "Logistic Regression":
            score = 3 if dataset_rows <= 5_000 else 1
            reason = "Fast, explainable baseline for smaller review queues."
        elif name == "Random Forest":
            score = 4 if 5_000 < dataset_rows <= 25_000 else 2
            reason = "Great when feedback mixes numeric+binary features and you want robustness."
        elif name == "Gradient Boost":
            score = 5 if dataset_rows > 15_000 else 3
            reason = "Top accuracy on imbalanced fraud labels, especially with >15k rows."

        if high_risk_rate is not None:
            if high_risk_rate < 0.2 and name != "Logistic Regression":
                score += 1
                reason += " Handles rare-fraud imbalance."
            elif high_risk_rate > 0.5 and name == "Logistic Regression":
                score += 1
                reason += " Balanced labels keep coefficients stable."

        return score, reason

    model_profiles = []
    model_options = [m["Model"] for m in MODEL_TABLE]
    for candidate in model_options:
        score, reason = score_afk_model(candidate)
        model_profiles.append(
            {
                "name": candidate,
                "score": score,
                "tagline": {
                    "Logistic Regression": "Audit-friendly baseline",
                    "Random Forest": "Ensemble stability",
                    "Gradient Boost": "Enterprise default",
                }[candidate],
                "reason": reason,
            }
        )

    model_profiles.sort(key=lambda x: x["score"], reverse=True)
    rec_cols = st.columns(len(model_profiles))
    for col, profile in zip(rec_cols, model_profiles):
        with col:
            st.markdown(f"**{profile['name']}**")
            st.caption(profile["tagline"])
            st.write(profile["reason"])
            if st.button(f"Use {profile['name']}", key=f"use_afk_{profile['name']}"):
                ss["afk_train_model"] = profile["name"]

    default_choice = ss.get("afk_train_model", model_profiles[0]["name"])
    if default_choice not in model_options:
        default_choice = model_options[0]

    model_label = st.selectbox(
        "Model",
        model_options,
        index=model_options.index(default_choice),
        key="afk_train_model"
    )
    gpu_profile = st.selectbox("GPU profile", GPU_PROFILES, index=0, key="afk_train_gpu")
    st.caption(f"Running {model_label} on {gpu_profile} (UI placeholder).")

    st.markdown("### 3. Train & compare")
    threshold = st.slider("Label threshold (fraud_score ≥ X → 1)", 40, 95, 70, 1)
    features = _prepare_features(dataset)
    labels = _build_labels(dataset, threshold)

    class_counts = labels.value_counts()
    if labels.nunique() <= 1:
        st.warning("Need at least two classes (Review vs Auto-Clear) to train a model.")
        return

    if class_counts.min() < 2:
        st.info("Only one sample exists for one of the classes; using the full dataset for training/eval.")
        X_train = X_test = features.copy()
        y_train = y_test = labels.copy()
    else:
        from sklearn.model_selection import StratifiedShuffleSplit

        splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.3, random_state=42)
        train_idx, test_idx = next(splitter.split(features, labels))
        X_train, X_test = features.iloc[train_idx], features.iloc[test_idx]
        y_train, y_test = labels.iloc[train_idx], labels.iloc[test_idx]

    if model_label == "Random Forest":
        clf = RandomForestClassifier(n_estimators=250, random_state=42)
    elif model_label == "Gradient Boost":
        clf = GradientBoostingClassifier(random_state=42)
    else:
        clf = LogisticRegression(max_iter=1000)

    try:
        clf.fit(X_train, y_train)
    except ValueError as exc:
        st.error(f"Training failed: {exc}")
        st.info("Try lowering the fraud-score threshold or collecting more feedback so both classes are present.")
        return
    preds = clf.predict(X_test)
    proba = clf.predict_proba(X_test)[:, 1] if hasattr(clf, "predict_proba") else preds.astype(float)

    metrics = {
        "Accuracy": accuracy_score(y_test, preds),
        "Precision": precision_score(y_test, preds, zero_division=0),
        "Recall": recall_score(y_test, preds, zero_division=0),
        "F1": f1_score(y_test, preds, zero_division=0),
    }
    try:
        metrics["ROC-AUC"] = roc_auc_score(y_test, proba)
    except Exception:
        metrics["ROC-AUC"] = float("nan")

    kpi_cols = st.columns(len(metrics))
    for (name, value), col in zip(metrics.items(), kpi_cols):
        col.metric(name, f"{value:.3f}")

    report = classification_report(y_test, preds, output_dict=True, zero_division=0)
    st.json(report)

    cm = confusion_matrix(y_test, preds)
    fig_cm = px.imshow(
        cm,
        text_auto=True,
        color_continuous_scale="Blues",
        labels=dict(x="Predicted", y="Actual", color="Count"),
    )
    fig_cm.update_layout(title="Confusion Matrix")
    st.plotly_chart(fig_cm, use_container_width=True)

    fig_roc = go.Figure(
        go.Histogram(
            x=proba,
            nbinsx=40,
            marker_color="#6366f1",
            opacity=0.7,
        )
    )
    fig_roc.update_layout(title="Prediction score distribution", xaxis_title="Positive probability", yaxis_title="Frequency")
    st.plotly_chart(fig_roc, use_container_width=True)

    ts = _ts()
    trained_dir = TRAINED_DIR
    model_path = trained_dir / f"{model_label.replace(' ', '_').lower()}_{ts}.joblib"
    joblib.dump(clf, model_path)

    preds_df = pd.DataFrame({"actual": y_test, "predicted": preds, "score": proba})
    preds_path = runs_dir / f"training_predictions_{ts}.csv"
    preds_df.to_csv(preds_path, index=False)

    report_payload = {
        "timestamp": ts,
        "model": model_label,
        "gpu_profile": gpu_profile,
        "source": data_source,
        "rows": int(len(dataset)),
        "metrics": metrics,
    }
    report_path = runs_dir / f"training_report_{ts}.json"
    with open(report_path, "w", encoding="utf-8") as fp:
        json.dump(report_payload, fp, indent=2)

    ss["afk_latest_trained_model"] = str(model_path)
    ss["afk_latest_training_report"] = report_payload
    st.success(f"Model saved → `{model_path.name}`")

    art_col1, art_col2 = st.columns(2)
    with art_col1:
        st.download_button(
            "⬇️ Download holdout predictions",
            data=preds_df.to_csv(index=False).encode("utf-8"),
            file_name="afk_training_predictions.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with art_col2:
        st.download_button(
            "⬇️ Download training report",
            data=json.dumps(report_payload, indent=2).encode("utf-8"),
            file_name="afk_training_report.json",
            mime="application/json",
            use_container_width=True,
        )

    promote_path = Path(ss.get("afk_latest_trained_model", ""))
    report_meta = ss.get("afk_latest_training_report", {})
    if promote_path.exists():
        st.markdown("### Promotion")
        if st.button("🚀 Promote last trained model to Production", use_container_width=True):
            dest = PRODUCTION_DIR / "model.joblib"
            shutil.copy2(promote_path, dest)
            meta_path = PRODUCTION_DIR / "production_meta.json"
            meta = {
                "model_path": promote_path.name,
                "promoted_at": datetime.utcnow().isoformat(),
                "report": report_meta,
            }
            meta_path.write_text(json.dumps(meta, indent=2))
            st.success(f"Production model updated → `{dest.name}`")
