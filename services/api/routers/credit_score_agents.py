# services/api/routers/credit_score_agents.py
from __future__ import annotations
import io, os, json, time
from typing import Any, Dict
import numpy as np, pandas as pd
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

router = APIRouter(tags=["credit_score_agent"])

AGENT_NAME = "credit_score"
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
async def run_credit_score_agent(request: Request, file: UploadFile | None = File(None)) -> Dict[str, Any]:
    """Endpoint: /v1/credit_score/run - Calculate credit scores (300-850)"""
    try:
        form = await request.form()
    except Exception:
        form = {}

    params = _parse_form_to_params(form)
    df = _load_csv_from_upload(file)

    try:
        from agents.credit_score.runner import calculate_credit_score
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import credit_score agent: {e}") from e

    run_id = f"credit_score_{int(time.time())}"

    # Calculate credit scores
    df_scored = calculate_credit_score(df, params)

    # Save results
    run_dir = _ensure_run_dir(run_id)
    scored_path = os.path.join(run_dir, "scored.csv")
    df_scored.to_csv(scored_path, index=False)

    # Prepare response
    result = {
        "run_id": run_id,
        "scored_df": df_scored.to_dict("records"),
        "summary": {
            "total_records": len(df_scored),
            "avg_score": float(df_scored["credit_score"].mean()),
            "min_score": int(df_scored["credit_score"].min()),
            "max_score": int(df_scored["credit_score"].max()),
            "median_score": float(df_scored["credit_score"].median()),
        },
        "artifacts": {
            "scored_csv": scored_path
        }
    }

    return {"run_id": run_id, "result": _json_safe(result)}


@router.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "agent": "credit_score"}
