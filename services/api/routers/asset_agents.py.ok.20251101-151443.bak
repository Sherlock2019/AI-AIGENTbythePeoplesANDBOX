# services/api/routers/asset_agents.py
from __future__ import annotations
import io, os, json, time
from typing import Any, Dict, List
import numpy as np, pandas as pd
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

router = APIRouter(prefix="/v1/agents/asset_appraisal", tags=["asset_agent"])

AGENT_NAME = "asset_appraisal"
RUNS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".runs"))
os.makedirs(RUNS_ROOT, exist_ok=True)

def _parse_form_to_params(form: Dict[str, Any]) -> Dict[str, Any]:
    params = {}
    for k, v in form.items():
        if isinstance(v, UploadFile) or k == "file":
            continue
        params[k] = str(v)
    return params

def _load_csv_from_upload(upload: UploadFile | None) -> pd.DataFrame:
    if upload is None:
        raise HTTPException(status_code=400, detail="CSV file is required (multipart/form-data with 'file').")
    return pd.read_csv(io.BytesIO(upload.file.read()))

def _ensure_run_dir(run_id: str) -> str:
    run_dir = os.path.join(RUNS_ROOT, AGENT_NAME, run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir

@router.post("/run")
async def run_asset_agent(request: Request, file: UploadFile | None = File(None)) -> Dict[str, Any]:
    """
    POST /v1/agents/asset_appraisal/run
    Returns:
      {
        "run_id": "...",
        "rows": N,
        "data": [ {row}, {row}, ... ]    # FULL row array for UI
      }
    Also persists merged.csv under services/api/.runs/asset_appraisal/<run_id>/
    """
    try:
        form = await request.form()
    except Exception:
        form = {}

    params = _parse_form_to_params(form)
    df = _load_csv_from_upload(file)

    try:
        from agents.asset_appraisal import agent as asset_agent
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import asset agent: {e}") from e

    result = None
    if hasattr(asset_agent, "run"):
        result = asset_agent.run(df, params)
    elif hasattr(asset_agent, "run_asset_appraisal"):
        result = asset_agent.run_asset_appraisal(df, **params)
    else:
        raise HTTPException(status_code=500, detail="No valid run() in asset agent")

    if not isinstance(result, dict) or "merged_df" not in result:
        raise HTTPException(status_code=500, detail="Asset agent did not return 'merged_df'.")

    out_df: pd.DataFrame = result["merged_df"]
    run_id: str = result.get("run_id") or f"asset_{int(time.time())}"

    run_dir = _ensure_run_dir(run_id)
    merged_path = os.path.join(run_dir, "merged.csv")
    try:
        out_df.to_csv(merged_path, index=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to persist merged.csv: {e}")

    # Return full rows; do NOT run through a json-sanitizer that strips data.
    data: List[Dict[str, Any]] = out_df.to_dict(orient="records")
    return {"run_id": run_id, "rows": len(data), "data": data}
