# agents/real_estate_evaluator/agent.py
from __future__ import annotations

import time
from typing import Dict, Any

import numpy as np
import pandas as pd

from .runner import run as runner_run


def run(df: pd.DataFrame, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Real Estate Evaluator agent entry point.
    Contract: run(df, params) -> dict
      - df: input real estate asset dataset
      - params: optional run-time controls from the form/body
    Returns:
      {
        "run_id": ...,
        "summary": {...},
        "evaluated_df": ...,
        "map_data": ...,
      }
    """
    params = params or {}
    
    # Run the evaluation
    evaluated_df = runner_run(df, params)
    
    # Prepare map data
    map_data = []
    for _, row in evaluated_df.iterrows():
        if pd.notna(row.get("lat")) and pd.notna(row.get("lon")):
                map_data.append({
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "name": str(row.get("address", row.get("district", "Unknown"))),
                    "city": str(row.get("city", "Unknown")),
                    "district": str(row.get("district", "")),
                    "property_type": str(row.get("property_type", "Apartment")),
                    "market_price": float(row.get("market_price_per_sqm", 0)),
                    "customer_price": float(row.get("customer_price_per_sqm", 0)),
                    "price_delta": float(row.get("price_delta", 0)),
                    "color": str(row.get("color", "#808080")),
                    "price_range": str(row.get("price_range_category", "medium")),
                    "status": str(row.get("evaluation_status", "at_market")),
                    "area_sqm": float(row.get("area_sqm", 0)),
                    "confidence": float(row.get("confidence", 0)),
                })
    
    # Generate zone data (polygons) for price zones
    from .runner import generate_zone_data
    zone_data = generate_zone_data(evaluated_df)
    
    # Summary statistics
    summary = {
        "agent": "real_estate_evaluator",
        "total_assets": int(len(evaluated_df)),
        "assets_on_map": len(map_data),
        "avg_market_price": float(evaluated_df["market_price_per_sqm"].mean()) if len(evaluated_df) > 0 else 0.0,
        "avg_customer_price": float(evaluated_df["customer_price_per_sqm"].mean()) if len(evaluated_df) > 0 else 0.0,
        "avg_price_delta": float(evaluated_df["price_delta"].mean()) if len(evaluated_df) > 0 else 0.0,
        "above_market_count": int((evaluated_df["evaluation_status"] == "above_market").sum()),
        "below_market_count": int((evaluated_df["evaluation_status"] == "below_market").sum()),
        "at_market_count": int((evaluated_df["evaluation_status"] == "at_market").sum()),
        "avg_confidence": float(evaluated_df["confidence"].mean()) if len(evaluated_df) > 0 else 0.0,
    }
    
    return {
        "run_id": f"real_estate_{int(time.time())}",
        "summary": summary,
        "evaluated_df": evaluated_df,
        "map_data": map_data,
        "zone_data": zone_data,  # Add zone data for polygon layers
    }
