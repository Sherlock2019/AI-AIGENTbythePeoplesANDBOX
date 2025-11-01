# agents/asset_appraisal/runner.py
"""
Asset Appraisal runner
Contract: run(df: pd.DataFrame, form_fields: Dict[str, Any]) -> pd.DataFrame

Outputs (at minimum):
- ai_adjusted: float
- confidence: float (0–100)
- market_delta: float  (percentage) = ((ai_adjusted - market_value)/market_value)*100
- decision: "approved" | "denied"
- rule_reasons: dict[str,bool] explaining each rule satisfied/failed
- ltv_ai: optional, computed if loan_amount is present
"""

from typing import Dict, Any, Tuple
import math
import numpy as np
import pandas as pd


def _fnum(v, default=None):
    """
    Robust float caster:
    - treats '', 'nan', None, 'null' as default
    - strips strings
    - returns default if conversion fails or if NaN/Inf detected
    """
    if v is None:
        return default
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("", "nan", "none", "null"):
            return default
        try:
            return float(s)
        except Exception:
            return default
    try:
        # covers ints, floats, numpy types
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
        return float(v)
    except Exception:
        return default


def _ai_adjust_value(row: pd.Series) -> float:
    """
    Lightweight AVM heuristic, safe on partial inputs.
    Adjusts market value by condition, legal penalty, age depreciation, and small city/type bumps.
    """
    mv    = _fnum(row.get("market_value"), 0.0) or 0.0
    cond  = _fnum(row.get("condition_score"), 0.88) or 0.88     # 0..1
    legal = _fnum(row.get("legal_penalty"), 0.98) or 0.98       # 0..1
    age   = _fnum(row.get("age_years"), 10.0) or 10.0

    # Light depreciation w/ age (cap at 40 years)
    dep = max(0.85, 1.0 - min(age, 40.0) * 0.005)

    # Small micro-adjustments by type/city to add variance
    bump = 1.0
    at = str(row.get("asset_type", "")).lower()
    city = str(row.get("city", "")).lower()
    if at in ("house", "apartment"):
        bump += 0.03
    if "hcm" in city or "hochiminh" in city or "hồ chí minh" in city:
        bump += 0.02

    return float(mv * cond * legal * dep * bump)


def _rule_eval(row: pd.Series, rule_mode: str, th: Dict[str, float]) -> Tuple[str, Dict[str, bool]]:
    """
    Evaluate approval rules. Coerces all inputs to float before comparing.
    """
    emp   = float(_fnum(row.get("employment_years"), 0.0) or 0.0)
    hist  = float(_fnum(row.get("credit_history_years"), 0.0) or 0.0)
    delin = float(_fnum(row.get("delinquencies"), 0.0) or 0.0)  # default 0.0
    amt   = float(_fnum(row.get("loan_amount"), 0.0) or 0.0)
    dti   = float(_fnum(row.get("DTI"), 1.0) or 1.0)

    reasons = {
        "min_emp_years":      emp   >= float(th["min_emp"]),
        "min_credit_hist":    hist  >= float(th["min_hist"]),
        "max_delinquencies":  delin <= float(th["max_delin"]),
        "amount_min":         amt   >= float(th["req_min"]),
        "amount_max":         amt   <= float(th["req_max"]),
    }

    if rule_mode == "classic":
        reasons["max_dti"] = dti <= float(th["max_dti"])
    else:
        income = float(_fnum(row.get("income"), amt * 1.25) or (amt * 1.25))
        compounded = amt * (1.0 + float(th["monthly_relief"]))
        ndi_ratio = (income / compounded) if compounded else 0.0
        reasons["min_ndi_ratio"] = ndi_ratio >= float(th["min_ndi_ratio"])

    decision = "approved" if all(reasons.values()) else "denied"
    return decision, reasons


def run(df: pd.DataFrame, form_fields: Dict[str, Any]) -> pd.DataFrame:
    df = df.copy()

    # Ensure core columns exist with sane defaults
    for col, default in [
        ("market_value", np.nan),
        ("condition_score", 0.9),
        ("legal_penalty", 0.98),
        ("age_years", 10),
    ]:
        if col not in df.columns:
            df[col] = default

    # Compute ai_adjusted if missing
    if "ai_adjusted" not in df.columns:
        df["ai_adjusted"] = df.apply(_ai_adjust_value, axis=1)

    # Confidence proxy from condition & legal; clamp to 55..97
    conf = 60.0 \
        + 20.0 * (df["condition_score"].fillna(0.88) - 0.5) \
        + 15.0 * (df["legal_penalty"].fillna(0.98) - 0.9)
    df["confidence"] = conf.clip(55.0, 97.0).round(1)

    # market_delta (%)
    with np.errstate(divide="ignore", invalid="ignore"):
        df["market_delta"] = ((df["ai_adjusted"] - df["market_value"]) / df["market_value"]) * 100.0
    df["market_delta"] = df["market_delta"].replace([np.inf, -np.inf], np.nan).fillna(0.0).round(2)

    # Sanity defaults for rule columns (so comparisons always see numeric floats)
    for col, dv in [
        ("employment_years", 0.0),
        ("credit_history_years", 0.0),
        ("delinquencies", 0.0),
        ("loan_amount", 0.0),
        ("DTI", 1.0),
    ]:
        if col not in df.columns:
            df[col] = dv

    # Thresholds from UI (with robust defaults)
    rule_mode = (form_fields.get("rule_mode") or "classic").strip().lower()
    thresholds = {
        "min_emp":        _fnum(form_fields.get("min_emp"), 2.0) or 2.0,
        "min_hist":       _fnum(form_fields.get("min_hist"), 3.0) or 3.0,
        "max_delin":      _fnum(form_fields.get("max_delin"), 2.0) or 2.0,
        "req_min":        _fnum(form_fields.get("req_min"), 1000.0) or 1000.0,
        "req_max":        _fnum(form_fields.get("req_max"), 200000.0) or 200000.0,
        "max_dti":        _fnum(form_fields.get("max_dti"), 0.45) or 0.45,
        "min_ndi_ratio":  _fnum(form_fields.get("min_ndi_ratio"), 0.35) or 0.35,
        "monthly_relief": _fnum(form_fields.get("monthly_relief"), 0.50) or 0.50,
    }

    # Apply rules only if not already produced by an external model
    if "decision" not in df.columns or "rule_reasons" not in df.columns:
        decisions, reasons_list = [], []
        for _, r in df.iterrows():
            d, reasons = _rule_eval(r, "classic" if rule_mode.startswith("classic") else "ndi", thresholds)
            decisions.append(d)
            reasons_list.append(reasons)
        if "decision" not in df.columns:
            df["decision"] = decisions
        df["rule_reasons"] = reasons_list

    # Optional: compute LTV using AI value
    if {"loan_amount", "ai_adjusted"}.issubset(df.columns):
        with np.errstate(divide="ignore", invalid="ignore"):
            df["ltv_ai"] = (df["loan_amount"] / df["ai_adjusted"]).replace([np.inf, -np.inf], np.nan)

    return df
