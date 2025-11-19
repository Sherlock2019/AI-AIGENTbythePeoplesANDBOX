# agents/credit_score/runner.py
"""
Credit Score Agent Runner
Calculates credit scores (300-850 range) based on borrower financial data.
Output feeds directly into Credit Appraisal Agent.
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


def calculate_credit_score(df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Calculate credit scores (300-850 range) based on multiple factors.
    
    Scoring factors:
    - Payment History (35%): Delinquencies, late payments
    - Amounts Owed (30%): DTI, current loans, utilization
    - Length of Credit History (15%): Years of credit history
    - Credit Mix (10%): Types of credit accounts
    - New Credit (10%): Recent inquiries, new accounts
    
    Returns DataFrame with 'credit_score' column (300-850 range)
    """
    if params is None:
        params = {}
    
    df = df.copy()
    
    # Extract features with defaults
    income = _safe_num(df.get("income", 0.0))
    dti = _safe_num(df.get("DTI", df.get("debt_to_income", 0.0)))
    credit_history_years = _safe_num(df.get("credit_history_length", df.get("credit_history_years", 0)))
    num_delinquencies = _safe_num(df.get("num_delinquencies", df.get("delinquencies", 0)))
    current_loans = _safe_num(df.get("current_loans", 0))
    employment_years = _safe_num(df.get("employment_years", df.get("employment_length", 0)))
    existing_debt = _safe_num(df.get("existing_debt", 0))
    assets_owned = _safe_num(df.get("assets_owned", 0))
    
    # Payment History Score (0-100, weighted 35%)
    # Fewer delinquencies = higher score
    delinq_score = 100 - (num_delinquencies.clip(0, 10) * 10)
    delinq_score = delinq_score.clip(0, 100)
    
    # Amounts Owed Score (0-100, weighted 30%)
    # Lower DTI and fewer loans = higher score
    dti_score = 100 - (dti.clip(0, 1.0) * 100)
    loans_score = 100 - (current_loans.clip(0, 10) * 8)
    amounts_score = (dti_score * 0.6 + loans_score * 0.4).clip(0, 100)
    
    # Length of Credit History Score (0-100, weighted 15%)
    # More years = higher score (capped at 20 years)
    history_score = (credit_history_years.clip(0, 20) / 20.0 * 100).clip(0, 100)
    
    # Credit Mix Score (0-100, weighted 10%)
    # Diversified credit types = higher score
    # Simple heuristic: employment + assets indicate stability
    stability_score = (
        (employment_years.clip(0, 20) / 20.0 * 50) +
        ((assets_owned > 0).astype(int) * 50)
    ).clip(0, 100)
    
    # New Credit Score (0-100, weighted 10%)
    # Assume no recent inquiries for now (could be enhanced)
    new_credit_score = 85  # Default neutral score
    
    # Weighted combination
    base_score = (
        0.35 * delinq_score +
        0.30 * amounts_score +
        0.15 * history_score +
        0.10 * stability_score +
        0.10 * new_credit_score
    )
    
    # Scale to 300-850 range (FICO-like)
    credit_score = 300 + (base_score / 100.0) * 550
    credit_score = credit_score.clip(300, 850).round(0).astype(int)
    
    df["credit_score"] = credit_score
    
    # Add detailed breakdown for dashboard
    df["score_payment_history"] = delinq_score.round(1)
    df["score_amounts_owed"] = amounts_score.round(1)
    df["score_credit_history"] = history_score.round(1)
    df["score_credit_mix"] = stability_score.round(1)
    df["score_new_credit"] = new_credit_score
    
    # Add risk category
    df["risk_category"] = pd.cut(
        credit_score,
        bins=[0, 580, 670, 740, 850],
        labels=["Poor", "Fair", "Good", "Excellent"]
    )
    
    # Add score tier
    df["score_tier"] = pd.cut(
        credit_score,
        bins=[0, 300, 500, 600, 700, 750, 850],
        labels=["Very Poor", "Poor", "Fair", "Good", "Very Good", "Excellent"]
    )
    
    return df


def run(df: pd.DataFrame, params: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Main runner function for Credit Score Agent.
    
    Args:
        df: DataFrame with borrower data
        params: Optional parameters (currently unused but kept for API compatibility)
    
    Returns:
        DataFrame with credit_score column and breakdown metrics
    """
    return calculate_credit_score(df, params)
