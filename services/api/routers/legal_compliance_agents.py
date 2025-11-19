# services/api/routers/legal_compliance_agents.py
from __future__ import annotations
import io, os, json, time
from typing import Any, Dict
import numpy as np, pandas as pd
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

router = APIRouter(tags=["legal_compliance_agent"])

AGENT_NAME = "legal_compliance"
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
async def run_legal_compliance_agent(request: Request, file: UploadFile | None = File(None)) -> Dict[str, Any]:
    """Endpoint: /v1/legal_compliance/run - Run compliance checks"""
    try:
        form = await request.form()
    except Exception:
        form = {}

    params = _parse_form_to_params(form)
    df = _load_csv_from_upload(file)

    try:
        from agents.legal_compliance.runner import run_compliance_checks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import legal_compliance agent: {e}") from e

    run_id = f"legal_compliance_{int(time.time())}"

    # Run compliance checks
    df_checked = run_compliance_checks(df, params)

    # Save results
    run_dir = _ensure_run_dir(run_id)
    checked_path = os.path.join(run_dir, "compliance_checked.csv")
    df_checked.to_csv(checked_path, index=False)

    # Prepare response
    result = {
        "run_id": run_id,
        "checked_df": df_checked.to_dict("records"),
        "summary": {
            "total_records": len(df_checked),
            "cleared": int((df_checked["compliance_status"] == "✅ Cleared").sum()),
            "on_hold": int((df_checked["compliance_status"] == "🚫 Hold – Escalate").sum()),
            "conditional": int((df_checked["compliance_status"] == "🟠 Conditional").sum()),
            "avg_compliance_score": float(df_checked["compliance_score"].mean()),
        },
        "artifacts": {
            "compliance_csv": checked_path
        }
    }

    return {"run_id": run_id, "result": _json_safe(result)}


@router.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "agent": "legal_compliance"}
