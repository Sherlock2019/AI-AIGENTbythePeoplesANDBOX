# agents/credit_appraisal/model_utils.py
from __future__ import annotations

import json
import os
import re
import time
import shutil
from typing import Dict, Any, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score

# ───────────────────────────────────────────────────────────────
# Paths & constants
# ───────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(__file__)
MODELS_DIR = os.path.join(BASE_DIR, "models")
TRAINED_DIR = os.path.join(MODELS_DIR, "trained")
PRODUCTION_DIR = os.path.join(MODELS_DIR, "production")

os.makedirs(TRAINED_DIR, exist_ok=True)
os.makedirs(PRODUCTION_DIR, exist_ok=True)

PRODUCTION_MODEL_FILENAME = "credit_model.joblib"
PRODUCTION_META_FILENAME = "meta.json"

PRODUCTION_MODEL_PATH = os.path.join(PRODUCTION_DIR, PRODUCTION_MODEL_FILENAME)
PRODUCTION_META_PATH = os.path.join(PRODUCTION_DIR, PRODUCTION_META_FILENAME)

# Common numeric feature candidates we try to keep if present
PREFERRED_NUMERIC_FEATURES = [
    # core raw
    "age", "income", "employment_length", "loan_amount", "loan_duration_months",
    "collateral_value", "co_loaners", "credit_score", "existing_debt", "assets_owned",
    "current_loans",
    # engineered
    "DTI", "LTV", "CCR", "ITI", "CWI",
    # harmonized
    "employment_years", "debt_to_income", "loan_term_months", "requested_amount",
]

# Columns to always drop from feature set
DROP_FEATURE_LIKE = {
    "application_id", "app_id", "id",
    "ai_decision", "human_decision", "decision",
    "rule_reasons", "explanation",
    "proposed_consolidation_loan", "proposed_loan_option",
    "customer_type", "currency_code", "created_at",
    "session_user_name", "session_user_email", "session_flagged",
    "decision_at",
}

# ───────────────────────────────────────────────────────────────
# Utilities
# ───────────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:40] or "user"

def _now_ts() -> str:
    return time.strftime("%Y%m%d-%H%M%S")

def _sidecar_json_path(joblib_path: str) -> str:
    base, _ = os.path.splitext(joblib_path)
    return base + ".json"

def _read_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _coerce_label_series(df: pd.DataFrame) -> pd.Series:
    """
    Expect a label column derived from human review. We support:
      - 'human_decision' with values 'approved'/'denied' (preferred)
      - OR 'label' already numeric {0,1}
      - OR 'target' {0,1}
      - OR fallback from 'decision' (approved/denied) if present
    """
    if "human_decision" in df.columns:
        y = df["human_decision"].astype(str).str.lower().map({"approved": 1, "denied": 0})
        if y.isna().any():
            raise ValueError("human_decision must contain only 'approved' or 'denied'.")
        return y.astype(int)

    for c in ("label", "target"):
        if c in df.columns:
            y = df[c]
            if not set(pd.unique(y)).issubset({0, 1}):
                raise ValueError(f"{c} must be binary 0/1.")
            return y.astype(int)

    if "decision" in df.columns:
        y = df["decision"].astype(str).str.lower().map({"approved": 1, "denied": 0})
        if y.isna().any():
            raise ValueError("decision must be only 'approved' or 'denied' to be used as label.")
        return y.astype(int)

    raise ValueError(
        "Feedback CSV must contain 'human_decision' (approved/denied), "
        "or a binary 'label'/'target', or a 'decision' column."
    )

# Numeric coercion helper: turns "$12,345.67", "10,000", "45%" into numbers.
_CLEAN_NUM_RE = re.compile(r"[^\d\.\-]+")
def _to_number(s) -> float:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return np.nan
    try:
        if isinstance(s, (int, float, np.number)):
            return float(s)
        st = str(s).strip()
        if st == "":
            return np.nan
        # percentages: keep as fraction if endswith %
        if st.endswith("%"):
            st = st[:-1]
            st = _CLEAN_NUM_RE.sub("", st)
            val = float(st)
            return val / 100.0
        st = st.replace(",", "")
        st = st.replace(" ", "")
        st = st.replace("₫", "").replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
        st = st.replace("\u00a0", "")  # non-breaking space
        return float(st)
    except Exception:
        return np.nan

def _coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].apply(_to_number)
            out[c] = pd.to_numeric(out[c], errors="ignore")
    return out

def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    # harmonize schema
    if "employment_years" not in out.columns:
        out["employment_years"] = out.get("employment_length", 0)
    if "loan_term_months" not in out.columns:
        out["loan_term_months"] = out.get("loan_duration_months", 0)
    if "requested_amount" not in out.columns:
        out["requested_amount"] = out.get("loan_amount", 0)

    # engineered metrics
    eps = 1e-9
    if "DTI" not in out.columns and {"existing_debt","income"}.issubset(out.columns):
        out["DTI"] = out["existing_debt"] / (out["income"] + eps)
    if "LTV" not in out.columns and {"loan_amount","collateral_value"}.issubset(out.columns):
        out["LTV"] = out["loan_amount"] / (out["collateral_value"] + eps)
    if "CCR" not in out.columns and {"collateral_value","loan_amount"}.issubset(out.columns):
        out["CCR"] = out["collateral_value"] / (out["loan_amount"] + eps)
    if "ITI" not in out.columns and {"loan_amount","loan_term_months","income"}.issubset(out.columns):
        out["ITI"] = (out["loan_amount"] / (out["loan_term_months"] + eps)) / (out["income"] + eps)
    if "CWI" not in out.columns:
        dti = out.get("DTI", 0.0)
        ltv = out.get("LTV", 0.0)
        ccr = out.get("CCR", 0.0)
        try:
            out["CWI"] = ((1 - dti).clip(0, 1)) * ((1 - ltv).clip(0, 1)) * (ccr.clip(0, 3))
        except Exception:
            out["CWI"] = 0.0

    if "debt_to_income" not in out.columns:
        if "DTI" in out.columns:
            out["debt_to_income"] = out["DTI"]
        elif {"existing_debt","income"}.issubset(out.columns):
            out["debt_to_income"] = out["existing_debt"] / (out["income"] + eps)
        else:
            out["debt_to_income"] = 0.0

    return out

def _select_feature_columns(df: pd.DataFrame) -> List[str]:
    """
    Conservative numeric feature selection:
    - Prefer PREFERRED_NUMERIC_FEATURES in that order if present
    - Else: all numeric columns minus DROP_FEATURE_LIKE
    """
    present = [c for c in PREFERRED_NUMERIC_FEATURES if c in df.columns]
    present = [c for c in present if pd.api.types.is_numeric_dtype(df[c])]
    if present:
        return present

    num_df = df.select_dtypes(include=[np.number]).copy()
    feat_cols = [c for c in num_df.columns if c not in DROP_FEATURE_LIKE]
    feat_cols = sorted(feat_cols)
    if not feat_cols:
        raise ValueError(
            "No numeric features available after coercion. "
            "Ensure your feedback CSV contains numeric fields like income, loan_amount, DTI, etc."
        )
    return feat_cols

def _load_feedback_csvs(paths: List[str]) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for p in paths:
        frames.append(pd.read_csv(p))
    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(axis=1, how="all")
    return df

def _preprocess_feedback_for_training(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """
    Full preprocessing pipeline for training from feedback CSVs:
      1) coerce numeric-like strings to numbers
      2) engineer features (DTI/LTV/CCR/ITI/CWI + harmonized fields)
      3) select numeric features
      4) extract label series
    Returns (X_df, y_series, feature_cols)
    """
    y = _coerce_label_series(df_raw)
    df_num = _coerce_numeric_columns(df_raw)
    df_eng = _engineer_features(df_num)
    feat_cols = _select_feature_columns(df_eng)

    X = df_eng.reindex(columns=feat_cols, fill_value=0.0)
    for c in feat_cols:
        if not pd.api.types.is_numeric_dtype(X[c]):
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0.0)

    return X, y.astype(int), feat_cols

# ───────────────────────────────────────────────────────────────
# Public API used by FastAPI router & agent
# ───────────────────────────────────────────────────────────────

def fit_candidate_on_feedback(
    feedback_csvs: List[str],
    user_name: str,
    agent_name: str = "credit_appraisal",
    algo_name: str = "credit_lr",
) -> Dict[str, Any]:
    """
    Train a candidate model from one or more feedback CSVs.
    Returns dict with model/meta info that FastAPI serializes as TrainResponse.
    """
    if not feedback_csvs:
        raise ValueError("feedback_csvs is empty.")

    df_raw = _load_feedback_csvs(feedback_csvs)
    X, y, feat_cols = _preprocess_feedback_for_training(df_raw)

    if y.nunique() < 2:
        raise ValueError("Need at least 2 classes in feedback to train (both approved and denied).")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipe = Pipeline(
        steps=[
            ("scaler", StandardScaler(with_mean=False)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    pipe.fit(X_train, y_train)

    # Metrics
    y_pred = pipe.predict(X_test) if len(X_test) else np.array([])
    acc = float(accuracy_score(y_test, y_pred)) if len(X_test) else None
    try:
        y_proba = pipe.predict_proba(X_test)[:, 1] if len(X_test) else np.array([])
        auc = float(roc_auc_score(y_test, y_proba)) if len(X_test) else None
    except Exception:
        auc = None

    # Persist
    ts = _now_ts()
    model_name = f"{algo_name}-{_slug(user_name)}-{_slug(agent_name)}-{ts}.joblib"
    model_path = os.path.join(TRAINED_DIR, model_name)
    meta_path = _sidecar_json_path(model_path)

    blob = {"pipeline": pipe, "features": feat_cols}
    joblib.dump(blob, model_path)

    meta = {
        "version": "1.0",
        "created_at": ts,
        "created_by": user_name,
        "agent_name": agent_name,
        "algo_name": algo_name,
        "model_name": model_name,
        "feature_names": feat_cols,
        "metrics": {
            "accuracy": acc,
            "roc_auc": auc,
            "n_rows": int(len(df_raw)),
            "n_features": int(len(feat_cols)),
        },
        "source": {"feedback_csvs": feedback_csvs},
    }
    _write_json(meta_path, meta)

    return {
        "job_id": ts,
        "model_name": model_name,
        "model_path": model_path,
        "meta_path": meta_path,
        "metrics": meta["metrics"],
        "feature_names": feat_cols,
    }

def list_available_models(kind: str = "trained") -> List[str]:
    """
    Return list of available model filenames for a registry kind.
    kind ∈ {"trained","production"}
    """
    if kind == "trained":
        if not os.path.isdir(TRAINED_DIR):
            return []
        return sorted([f for f in os.listdir(TRAINED_DIR) if f.endswith(".joblib")])

    if kind == "production":
        return [PRODUCTION_MODEL_FILENAME] if os.path.exists(PRODUCTION_MODEL_PATH) else []

    raise ValueError("kind must be 'trained' or 'production'")

def promote_to_production(model_name: str) -> Dict[str, Any]:
    """
    Copy a trained .joblib to production/credit_model.joblib and write production meta.json.
    """
    src_model_path = os.path.join(TRAINED_DIR, model_name)
    src_meta_path = _sidecar_json_path(src_model_path)
    if not os.path.exists(src_model_path):
        raise FileNotFoundError(f"Trained model not found: {model_name}")

    os.makedirs(PRODUCTION_DIR, exist_ok=True)
    shutil.copyfile(src_model_path, PRODUCTION_MODEL_PATH)

    prod_meta = {"version": "1.0", "promoted_at": _now_ts(), "source": model_name}
    if os.path.exists(src_meta_path):
        src_meta = _read_json(src_meta_path, {})
        prod_meta["trained_meta"] = {
            k: src_meta.get(k)
            for k in ("created_at", "created_by", "agent_name", "algo_name", "metrics", "feature_names")
        }

    _write_json(PRODUCTION_META_PATH, prod_meta)
    return {"model_path": PRODUCTION_MODEL_PATH, "meta_path": PRODUCTION_META_PATH}

def get_production_meta() -> Dict[str, Any]:
    """
    Return {"has_production": bool, "meta": {...}}.
    """
    if not os.path.exists(PRODUCTION_MODEL_PATH) or not os.path.exists(PRODUCTION_META_PATH):
        return {"has_production": False, "meta": None}
    return {"has_production": True, "meta": _read_json(PRODUCTION_META_PATH, {})}

def _load_model_from_path(path: str) -> Dict[str, Any]:
    blob = joblib.load(path)
    # If legacy: wrap raw estimator
    if not isinstance(blob, dict) or "pipeline" not in blob:
        blob = {"pipeline": blob, "features": []}
    blob.setdefault("features", [])
    return blob

def load_model_by_name(name: str, kind: str = "trained") -> Dict[str, Any]:
    if kind == "production":
        path = PRODUCTION_MODEL_PATH
        if not os.path.exists(path):
            raise FileNotFoundError("No production model.")
        return _load_model_from_path(path)

    if kind == "trained":
        path = os.path.join(TRAINED_DIR, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Trained model not found: {name}")
        return _load_model_from_path(path)

    raise ValueError("kind must be 'trained' or 'production'")

def load_latest_trained_model() -> Optional[Dict[str, Any]]:
    if not os.path.isdir(TRAINED_DIR):
        return None
    candidates = [
        os.path.join(TRAINED_DIR, f)
        for f in os.listdir(TRAINED_DIR)
        if f.endswith(".joblib")
    ]
    if not candidates:
        return None
    latest = max(candidates, key=os.path.getmtime)
    return _load_model_from_path(latest)

# Back-compat shim — legacy code may call this with varying signatures
def ensure_model(
    df: Optional[pd.DataFrame] = None,
    selected_model_name: Optional[str] = None,
    registry: str = "auto",
    **_: Any,
) -> Tuple[Any, List[str]]:
    """
    Returns (pipeline, feature_cols).
    Selection order:
      1. selected_model_name from TRAINED
      2. PRODUCTION default
      3. Latest TRAINED
      4. Bootstrap from df (heuristic labels) if nothing available
    """
    # 1) Explicit selection (trained)
    if selected_model_name:
        blob = load_model_by_name(selected_model_name, kind="trained")
        pipe = blob["pipeline"]
        feat_cols = blob.get("features") or []
        return pipe, feat_cols

    # 2) Production
    if os.path.exists(PRODUCTION_MODEL_PATH):
        blob = _load_model_from_path(PRODUCTION_MODEL_PATH)
        return blob["pipeline"], (blob.get("features") or [])

    # 3) Latest trained
    latest = load_latest_trained_model()
    if latest:
        return latest["pipeline"], (latest.get("features") or [])

    # 4) Bootstrap: train a tiny baseline if df provided
    if df is None or df.empty:
        raise RuntimeError("No available model found to load.")

    work = df.copy()
    work = _coerce_numeric_columns(work)
    work = _engineer_features(work)

    # Pseudo label: approve if (DTI ≤ 0.45 and credit_score ≥ 600) else deny
    dti = work.get("DTI", pd.Series([0]*len(work), index=work.index)).fillna(0)
    score = work.get("credit_score", pd.Series([650]*len(work), index=work.index)).fillna(650)
    y = ((dti <= 0.45) & (score >= 600)).astype(int)

    feat_cols = _select_feature_columns(work)
    X = work.reindex(columns=feat_cols, fill_value=0.0)
    for c in feat_cols:
        if not pd.api.types.is_numeric_dtype(X[c]):
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0.0)

    pipe = Pipeline(
        steps=[
            ("scaler", StandardScaler(with_mean=False)),
            ("clf", LogisticRegression(max_iter=500, class_weight="balanced")),
        ]
    )
    try:
        pipe.fit(X, y)
    except Exception:
        fallback = [c for c in ["DTI","credit_score","income","loan_amount"] if c in X.columns] or [X.columns[0]]
        pipe.fit(X[fallback], y)
        feat_cols = fallback

    return pipe, feat_cols

# ───────────────────────────────────────────────────────────────
# Promotion Utility — latest trained → production
# ───────────────────────────────────────────────────────────────

def promote_last_trained_to_production() -> Dict[str, Any]:
    """
    Promote the latest trained model from /models/trained to /models/production.
    Copies both .joblib and .json, ensures compatibility with UI and API.
    """
    os.makedirs(PRODUCTION_DIR, exist_ok=True)

    trained_models = sorted(
        [f for f in os.listdir(TRAINED_DIR) if f.endswith(".joblib")],
        key=lambda f: os.path.getmtime(os.path.join(TRAINED_DIR, f)),
        reverse=True,
    )
    if not trained_models:
        raise FileNotFoundError("No trained models found in /models/trained")

    last_model = trained_models[0]
    src_model = os.path.join(TRAINED_DIR, last_model)
    src_meta = _sidecar_json_path(src_model)
    if not os.path.exists(src_meta):
        raise FileNotFoundError(f"Missing metadata for model: {src_meta}")

    dest_model = PRODUCTION_MODEL_PATH
    dest_meta = PRODUCTION_META_PATH

    shutil.copy2(src_model, dest_model)
    shutil.copy2(src_meta, dest_meta)

    prod_meta = _read_json(dest_meta, {}) or {}
    prod_meta.update({
        "promoted_at": _now_ts(),
        "source_model": last_model,
    })
    _write_json(dest_meta, prod_meta)

    return {"ok": True, "promoted_model": last_model, "model_path": dest_model, "meta_path": dest_meta}
