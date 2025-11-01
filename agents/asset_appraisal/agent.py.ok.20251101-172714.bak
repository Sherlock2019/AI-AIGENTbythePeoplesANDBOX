# agents/asset_appraisal/agent.py
from __future__ import annotations

import time
from typing import Dict, Any

import numpy as np
import pandas as pd


def run(df: pd.DataFrame, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Minimal Asset Appraisal agent entry point.
    Contract: run(df, params) -> dict
      - df: input asset/collateral dataset
      - params: optional run-time controls from the form/body
    Returns:
      {
        "run_id": ...,
        "summary": {...},
        # optionally more keys like "merged_df", "preview", etc.
      }
    """
    params = params or {}

    # Base value: prefer provided collateral_value; else synthesize
    if "collateral_value" in df.columns:
        base = df["collateral_value"].astype(float)
    else:
        rng = np.random.default_rng(0)
        base = pd.Series(rng.integers(20_000, 200_000, len(df)), index=df.index)

    # Type bump
    bump_series = pd.Series(1.0, index=df.index, dtype="float64")
    for cand in ("asset_type", "collateral_type"):
        if cand in df.columns:
            bump_map = {
                "Apartment": 1.10, "House": 1.12, "Condo": 1.08, "Shop": 1.15, "Factory": 1.20,
                "Land Plot": 1.08, "Car": 0.95, "Deposit": 1.00,
                "real_estate": 1.12, "land": 1.08, "car": 0.95, "deposit": 1.00
            }
            bump_series = df[cand].map(bump_map).fillna(1.0).astype(float)
            break

    # Optional: adjust by quality_score if provided
    qual = df["quality_score"].astype(float) if "quality_score" in df.columns else 1.0
    est = (base * bump_series * qual).round(2)

    out = df.copy()
    out["estimated_collateral_value"] = est
    out["valuation_method"] = "heuristics_v1"

    summary = {
        "agent": "asset_appraisal",
        "rows": int(len(out)),
        "stats": {
            "min": float(out["estimated_collateral_value"].min()),
            "mean": float(out["estimated_collateral_value"].mean()),
            "max": float(out["estimated_collateral_value"].max()),
        },
    }

    return {
        "run_id": f"asset_{int(time.time())}",
        "summary": summary,
        # You can also return small previews or save artifacts here
        # "preview": out.head(10).to_dict(orient="records"),
        # "merged_df": out,
    }
