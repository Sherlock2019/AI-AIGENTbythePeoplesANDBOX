# services/api/routers/asset_appraisal.py
from __future__ import annotations
import os, json, datetime, random
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse

router = APIRouter(prefix="/v1/agents/asset_appraisal", tags=["asset_appraisal"])

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
RUNS_DIR = Path("services/api/.runs/asset_appraisal")
RUNS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# SYNTHETIC DATA GENERATOR
# ─────────────────────────────────────────────
def generate_synthetic_assets(n: int = 400) -> pd.DataFrame:
    """Generate synthetic asset appraisal data for testing."""
    rng = np.random.default_rng(42)
    app_ids = [f"APP_{i:06d}" for i in range(1, n + 1)]
    asset_types = ["Apartment", "House", "Condo", "Land Plot", "Car"]
    countries = ["US", "UK", "FR", "DE", "VN", "JP"]
    cities = ["New York", "London", "Paris", "Berlin", "Hanoi", "Tokyo"]
    data = []

    for app_id in app_ids:
        asset_type = random.choice(asset_types)
        declared_value = rng.integers(20_000, 1_000_000)
        estimated_value = declared_value * rng.uniform(0.8, 1.1)
        condition = random.choice(list("ABCD"))
        country = random.choice(countries)
        city = random.choice(cities)
        legal_verified = bool(rng.random() > 0.1)
        field_verified = bool(rng.random() > 0.2)
        fraud_flag = not (legal_verified and field_verified) and rng.random() < 0.05
        status = (
            "validated" if legal_verified and field_verified and not fraud_flag
            else "pending_validation"
        )
        data.append({
            "application_id": app_id,
            "asset_type": asset_type,
            "country": country,
            "city": city,
            "declared_value": round(float(declared_value), 2),
            "estimated_value": round(float(estimated_value), 2),
            "condition_grade": condition,
            "valuation_confidence": round(float(rng.uniform(0.6, 0.95)), 3),
            "legal_verified": legal_verified,
            "field_verified": field_verified,
            "fraud_flag": fraud_flag,
            "status": status,
            "updated_at": datetime.datetime.now().isoformat(),
        })
    return pd.DataFrame(data)


# ─────────────────────────────────────────────
# MAIN ROUTE — Unified Run
# ─────────────────────────────────────────────
@router.post("/run")
def run_asset_appraisal(file: Optional[UploadFile] = None):
    """
    Run the Asset Appraisal Agent.
    If a CSV is provided, use it; otherwise generate synthetic dataset.
    Returns a run_id and summary, and saves merged.csv for dashboard.
    """
    run_id = f"asset_{int(datetime.datetime.now().timestamp())}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Load or generate data
    if file:
        df = pd.read_csv(file.file)
        msg = f"Loaded user-supplied dataset ({len(df)} rows)"
    else:
        df = generate_synthetic_assets()
        msg = f"No input file — generated synthetic dataset ({len(df)} rows)"

    # Basic stats
    stats = {
        "min": float(df["estimated_value"].min()),
        "mean": float(df["estimated_value"].mean()),
        "max": float(df["estimated_value"].max()),
    }
    summary = {"agent": "asset_appraisal", "rows": len(df), "stats": stats}

    # Save merged file and summary for dashboard
    merged_path = run_dir / "merged.csv"
    df.to_csv(merged_path, index=False)
    with open(run_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return JSONResponse({
        "run_id": run_id,
        "summary": summary,
        "message": msg
    })


# ─────────────────────────────────────────────
# REPORT ROUTE (used by Streamlit dashboard)
# ─────────────────────────────────────────────
@router.get("/../../runs/asset_appraisal/{run_id}/report")
def get_asset_report(run_id: str, format: str = "csv"):
    """
    Serve stored merged.csv or summary.json for a given run_id.
    Streamlit calls this endpoint to render dashboard data.
    """
    run_dir = RUNS_DIR / run_id
    merged_path = run_dir / "merged.csv"
    summary_path = run_dir / "summary.json"

    if not run_dir.exists():
        return JSONResponse({"error": f"Run ID {run_id} not found."}, status_code=404)

    if format == "csv" and merged_path.exists():
        return FileResponse(merged_path, media_type="text/csv", filename=f"{run_id}.csv")

    if format == "json" and summary_path.exists():
        with open(summary_path) as f:
            return JSONResponse(json.load(f))

    return PlainTextResponse("Report not found", status_code=404)
