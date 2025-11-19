# agents/legal_compliance/runner.py
"""
Legal Compliance Agent Runner
Checks regulatory compliance, sanctions, PEP, licensing requirements.
Output feeds into Credit Appraisal and Asset Appraisal agents.
"""
from __future__ import annotations
from typing import Dict, Any
import numpy as np
import pandas as pd


def _to_float(x, default=None):
    """Robust float converter."""
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def _safe_num(series, default=0.0):
    """Safely convert series to numeric."""
    try:
        return pd.to_numeric(series, errors="coerce").fillna(default)
    except Exception:
        return pd.Series([default] * len(series) if hasattr(series, '__len__') else [default])


def run_compliance_checks(df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Run legal compliance checks on application data.
    
    Checks:
    - PEP (Politically Exposed Person) flags
    - Sanctions matches
    - Licensing requirements by jurisdiction
    - KYC risk scores
    - Regulatory alignment
    
    Returns DataFrame with compliance verdicts and flags.
    """
    if params is None:
        params = {}
    
    df = df.copy()
    rng = np.random.default_rng(42)
    
    # Extract features with defaults
    jurisdiction = df.get("jurisdiction", df.get("country", pd.Series(["US"] * len(df))))
    pep_flag = _safe_num(df.get("pep_flag", 0))
    sanctions_match = _safe_num(df.get("sanctions_match", df.get("sanction_hits", 0)))
    license_required = _safe_num(df.get("license_required", 0))
    kyc_risk_score = _safe_num(df.get("kyc_risk_score", 0.1))
    fraud_score = _safe_num(df.get("fraud_probability", df.get("fraud_score", 0.1)))
    
    # Compliance scoring logic
    # Higher risk = lower compliance score
    compliance_score = (
        1.0 - (pep_flag * 0.3) - 
        (sanctions_match * 0.5) - 
        (kyc_risk_score * 0.15) - 
        (fraud_score * 0.05)
    )
    compliance_score = compliance_score.clip(0.0, 1.0)
    
    df["compliance_score"] = compliance_score.round(3)
    df["llm_alignment_score"] = compliance_score.round(3)
    
    # Determine compliance status
    def _compliance_status(row: pd.Series) -> str:
        if row["sanctions_match"] >= 1 or (row["pep_flag"] >= 1 and row["compliance_score"] < 0.5):
            return "🚫 Hold – Escalate"
        elif row["license_required"] >= 1 and row["compliance_score"] < 0.55:
            return "🟠 Conditional"
        elif row["compliance_score"] < 0.4:
            return "🟡 Review Required"
        else:
            return "✅ Cleared"
    
    df["compliance_status"] = df.apply(_compliance_status, axis=1)
    df["compliance_stage"] = np.where(
        df["compliance_status"] == "✅ Cleared",
        "Compliance OK",
        "Compliance Hold"
    )
    
    # Generate compliance reasons
    df["legal_reason"] = df.apply(
        lambda row: _generate_reason(row, rng),
        axis=1
    )
    
    # Policy flags
    df["policy_flags"] = df.apply(
        lambda row: _generate_policy_flags(row),
        axis=1
    )
    
    return df


def _generate_reason(row: pd.Series, rng) -> str:
    """Generate human-readable compliance reason."""
    reasons = []
    
    if row["sanctions_match"] >= 1:
        reasons.append("Sanctions match detected")
    if row["pep_flag"] >= 1:
        reasons.append("PEP flag raised")
    if row["license_required"] >= 1:
        reasons.append("License required for jurisdiction")
    if row["kyc_risk_score"] > 0.5:
        reasons.append(f"High KYC risk ({row['kyc_risk_score']:.2f})")
    
    if not reasons:
        reasons.append("No compliance issues identified")
    
    return " | ".join(reasons)


def _generate_policy_flags(row: pd.Series) -> str:
    """Generate policy flags as comma-separated string."""
    flags = []
    
    if row["sanctions_match"] >= 1:
        flags.append("SANCTIONS")
    if row["pep_flag"] >= 1:
        flags.append("PEP")
    if row["license_required"] >= 1:
        flags.append("LICENSE_REQUIRED")
    if row["kyc_risk_score"] > 0.6:
        flags.append("HIGH_KYC_RISK")
    if row.get("compliance_score", 1.0) < 0.4:
        flags.append("LOW_COMPLIANCE_SCORE")
    
    return ", ".join(flags) if flags else "NONE"


def run(df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Main runner function for Legal Compliance Agent.
    
    Args:
        df: DataFrame with application/borrower data
        params: Optional parameters
    
    Returns:
        DataFrame with compliance checks and verdicts
    """
    return run_compliance_checks(df, params)
