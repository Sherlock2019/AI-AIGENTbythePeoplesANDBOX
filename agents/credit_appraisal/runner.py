# agents/credit_appraisal/runner.py
from __future__ import annotations
from typing import Dict, Any
import numpy as np
import pandas as pd

def _to_float(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default

def _to_bool(x, default=False):
    if isinstance(x, bool):
        return x
    if x is None:
        return default
    s = str(x).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default

def _safe_num(series, default=0.0):
    try:
        return pd.to_numeric(series, errors="coerce").fillna(default)
    except Exception:
        return pd.Series([default] * len(series))

def _score_classic(df: pd.DataFrame) -> pd.Series:
    """
    Simple, explainable score using common credit features.
    Range ~[0,1]; higher is better.
    """
    dti = _safe_num(df.get("DTI", 0.0))
    ltv = _safe_num(df.get("LTV", 0.0))
    credit_score = _safe_num(df.get("credit_score", 600))
    emp_years = _safe_num(df.get("employment_years", df.get("employment_length", 0)))
    hist_years = _safe_num(df.get("credit_history_length", 0))
    delinq = _safe_num(df.get("num_delinquencies", 0))
    current_loans = _safe_num(df.get("current_loans", 0))

    # Normalize
    dti_n = 1.0 - dti.clip(0, 1.5) / 1.5            # lower DTI better
    ltv_n = 1.0 - ltv.clip(0, 1.5) / 1.5            # lower LTV better
    cs_n  = (credit_score.clip(300, 850) - 300) / 550.0
    emp_n = (emp_years.clip(0, 30)) / 30.0
    hist_n= (hist_years.clip(0, 30)) / 30.0
    delq_n= 1.0 - (delinq.clip(0, 10) / 10.0)       # fewer delinq better
    loans_n=1.0 - (current_loans.clip(0, 10) / 10.0)# fewer loans better

    score = (
        0.22 * dti_n +
        0.18 * ltv_n +
        0.28 * cs_n  +
        0.10 * emp_n +
        0.08 * hist_n+
        0.07 * delq_n+
        0.07 * loans_n
    ).clip(0, 1)
    return score

def _score_ndi(df: pd.DataFrame, ndi_value_min: float, ndi_ratio_min: float) -> pd.Series:
    """
    NDI = income - monthly obligations (approx from DTI and income)
    We'll derive a heuristic NDI signal and map to [0,1].
    """
    income = _safe_num(df.get("income", 0.0))
    dti    = _safe_num(df.get("DTI", 0.0))
    # approximate monthly obligations as income * dti
    ndi = income - (income * dti)
    # two terms: absolute NDI and relative ratio
    ndi_abs_n = (ndi / max(ndi_value_min, 1e-6)).clip(0, 2.0) / 2.0
    ndi_ratio = 1.0 - dti
    ndi_ratio_n = (ndi_ratio / max(ndi_ratio_min, 1e-6)).clip(0, 2.0) / 2.0
    score = (0.6 * ndi_abs_n + 0.4 * ndi_ratio_n).clip(0, 1)
    return score

def _apply_strict_rules(df: pd.DataFrame, params: Dict[str, Any]) -> pd.Series:
    """
    Hard disqualifiers from classic knobs. Returns boolean mask of rows that PASS strict checks.
    If a knob is missing, we don't enforce it.
    """
    emp_min   = _to_float(params.get("min_employment_years"))      # classic
    hist_min  = _to_float(params.get("min_credit_history_length"))
    max_del   = _to_float(params.get("max_num_delinquencies"))
    max_loans = _to_float(params.get("max_current_loans"))
    salary_fl = _to_float(params.get("salary_floor"))

    ok = pd.Series(True, index=df.index)

    if emp_min is not None:
        emp = _safe_num(df.get("employment_years", df.get("employment_length", 0)))
        ok &= (emp >= emp_min)

    if hist_min is not None:
        hist = _safe_num(df.get("credit_history_length", 0))
        ok &= (hist >= hist_min)

    if max_del is not None:
        delq = _safe_num(df.get("num_delinquencies", 0))
        ok &= (delq <= max_del)

    if max_loans is not None:
        loans = _safe_num(df.get("current_loans", 0))
        ok &= (loans <= max_loans)

    if salary_fl is not None:
        income = _safe_num(df.get("income", 0.0))
        ok &= (income >= salary_fl)

    # requested amount range (optional)
    req_min = _to_float(params.get("requested_amount_min"))
    req_max = _to_float(params.get("requested_amount_max"))
    if req_min is not None or req_max is not None:
        amt = _safe_num(df.get("requested_amount", df.get("loan_amount", 0)))
        if req_min is not None:
            ok &= (amt >= req_min)
        if req_max is not None:
            ok &= (amt <= req_max)

    # explicit DTI cap if provided
    max_dti = _to_float(params.get("max_debt_to_income"))
    if max_dti is not None:
        dti = _safe_num(df.get("DTI", 0.0))
        ok &= (dti <= max_dti)

    return ok

def run(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """
    Main credit runner used by the API. Produces 'score' and 'decision'.
    Honors:
      - rule_mode: 'classic' or 'ndi'
      - threshold: numeric [0,1]
      - target_approval_rate: 0.05..0.95
      - random_band: true/false (only used if neither threshold nor target provided)
    """
    out = df.copy()
    rng = np.random.default_rng(123)  # deterministic unless you want per-run randomness

    rule_mode = str(params.get("rule_mode") or "classic").lower()

    # Compute score
    if rule_mode == "ndi":
        ndi_val = _to_float(params.get("ndi_value"), 800.0)
        ndi_rat = _to_float(params.get("ndi_ratio"), 0.5)
        score = _score_ndi(out, ndi_val, ndi_rat)
    else:
        score = _score_classic(out)

    out["score"] = score.round(4)

    # Strict rules act as hard gates (classic only, if knobs provided)
    strict_ok = _apply_strict_rules(out, params) if rule_mode == "classic" else pd.Series(True, index=out.index)

    # Decision policy
    threshold = _to_float(params.get("threshold"), None)
    target    = _to_float(params.get("target_approval_rate"), None)
    rand_band = _to_bool(params.get("random_band"), False)

    decision = pd.Series(False, index=out.index)

    if threshold is not None:
        decision = (score >= threshold) & strict_ok

    elif target is not None:
        # approve top-K by score subject to strict_ok
        k = int(round(len(out) * float(target)))
        k = min(max(k, 0), len(out))
        # rank only among rows that pass strict checks
        candidates = out[strict_ok].copy()
        if k > 0 and len(candidates) > 0:
            topk_idx = candidates["score"].sort_values(ascending=False).head(k).index
            decision.loc[topk_idx] = True

    else:
        # If neither provided, optionally randomize an approval band (20–60%)
        if rand_band:
            rate = rng.uniform(0.20, 0.60)
        else:
            rate = 0.40
        k = int(round(len(out) * rate))
        candidates = out[strict_ok].copy()
        # sample from higher scores with probability ∝ score
        if len(candidates) > 0 and k > 0:
            probs = candidates["score"].values.astype(float)
            probs = probs - probs.min() + 1e-6
            probs = probs / probs.sum()
            choose = rng.choice(candidates.index.to_numpy(), size=min(k, len(candidates)), replace=False, p=probs)
            decision.loc[choose] = True

    out["decision"] = np.where(decision, "approved", "denied")
    # Confidence ~ score with small noise
    out["confidence"] = np.clip(score + rng.normal(0, 0.03, size=len(out)), 0, 1).round(4)

    # Optional explanation sketch
    out["top_feature"] = np.where(
        rule_mode == "ndi",
        "NDI_ratio" ,
        np.where(score >= score.median(), "DTI", "credit_score")
    )
    out["explanation"] = np.where(
        out["decision"].eq("approved"),
        "Meets policy thresholds given DTI/LTV/score.",
        "Fails one or more policy thresholds (DTI/LTV/history/amount)."
    )

    return out
