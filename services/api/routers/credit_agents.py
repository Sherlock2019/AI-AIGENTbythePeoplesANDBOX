# services/api/routers/credit_agents.py
from __future__ import annotations
import io, os, json, time
from typing import Any, Dict
import numpy as np, pandas as pd
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

router = APIRouter(tags=["credit_agent"])

AGENT_NAME = "credit_appraisal"
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


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, pd.DataFrame):
        return {"shape": obj.shape, "columns": list(obj.columns)}
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    return obj


@router.post("/run")
async def run_credit_agent(request: Request, file: UploadFile | None = File(None)) -> Dict[str, Any]:
    """Endpoint: /v1/credit/run"""
    try:
        form = await request.form()
    except Exception:
        form = {}

    params = _parse_form_to_params(form)
    df = _load_csv_from_upload(file)

    try:
        from agents.credit_appraisal import agent as credit_agent
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import credit agent: {e}") from e

    run_id = f"credit_{int(time.time())}"

    if hasattr(credit_agent, "run"):
        result = credit_agent.run(df, params)
    elif hasattr(credit_agent, "run_credit_appraisal"):
        result = credit_agent.run_credit_appraisal(df, **params)
    else:
        raise HTTPException(status_code=500, detail="No valid run() in credit agent")

    run_dir = _ensure_run_dir(run_id)
    merged_path = os.path.join(run_dir, "merged.csv")

    if isinstance(result, dict) and "merged_df" in result:
        result["merged_df"].to_csv(merged_path, index=False)

    return {"run_id": run_id, "result": _json_safe(result)}
