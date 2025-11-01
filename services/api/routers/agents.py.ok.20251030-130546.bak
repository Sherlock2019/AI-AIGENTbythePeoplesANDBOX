# services/api/routers/agents.py
from __future__ import annotations

import io
import os
import json
import time
from typing import Any, Dict

import numpy as np
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Request, HTTPException

router = APIRouter(tags=["agents"])

AGENT_NAME = "credit_appraisal"
RUNS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".runs"))
os.makedirs(RUNS_ROOT, exist_ok=True)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _parse_form_to_params(form: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert starlette FormData into plain dict of strings -> values.
    Excludes UploadFile objects.
    """
    params: Dict[str, Any] = {}
    for k, v in form.items():
        if isinstance(v, UploadFile) or k == "file":
            continue
        if isinstance(v, (list, tuple)):
            params[k] = ",".join(map(str, v))
        else:
            params[k] = str(v)
    return params


def _load_csv_from_upload(upload: UploadFile | None) -> pd.DataFrame:
    if upload is None:
        raise HTTPException(status_code=400, detail="CSV file is required (multipart/form-data with 'file').")
    try:
        content = upload.file.read()
        return pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}") from e


def _ensure_run_dir(run_id: str) -> str:
    run_dir = os.path.join(RUNS_ROOT, run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _persist_minimal_artifacts(run_id: str, result: Dict[str, Any]) -> None:
    """
    Create minimal artifacts if the agent didn't persist any:
      - summary.json : contains the agent result minus large frames
      - merged.csv   : if provided as DataFrame or CSV content in result
    This won't overwrite files already present (so it's safe even if the agent wrote them).
    """
    run_dir = _ensure_run_dir(run_id)

    # Try to persist merged.csv if agent returned it explicitly
    merged_path = os.path.join(run_dir, "merged.csv")
    if not os.path.exists(merged_path):
        merged_df = None
        if isinstance(result, dict):
            # common keys where agent may put a DataFrame or CSV text
            for key in ("merged_df", "merged", "results_df"):
                if isinstance(result.get(key), pd.DataFrame):
                    merged_df = result.get(key)
                    break
            if merged_df is None:
                for key in ("merged_csv", "results_csv"):
                    csv_text = result.get(key)
                    if isinstance(csv_text, str) and csv_text.strip():
                        try:
                            df = pd.read_csv(io.StringIO(csv_text))
                            df.to_csv(merged_path, index=False)
                            merged_df = None  # already written
                            break
                        except Exception:
                            pass
        if isinstance(merged_df, pd.DataFrame):
            try:
                merged_df.to_csv(merged_path, index=False)
            except Exception:
                pass

    # Persist a small, JSON-safe summary (avoid DataFrames)
    summary_path = os.path.join(run_dir, "summary.json")
    if not os.path.exists(summary_path):
        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(_json_safe(result), f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def _json_safe(obj: Any, max_str: int = 10_000) -> Any:
    """
    Make objects JSON serializable:
      - pandas.DataFrame -> {"type":"dataframe","shape":...,"columns":[...]}
      - numpy scalars -> Python scalars
      - bytes -> str (limited)
      - other unknown -> repr() (limited)
      - dict/list/tuple -> recursive
    """
    # pandas
    if isinstance(obj, pd.DataFrame):
        return {
            "type": "dataframe",
            "shape": list(obj.shape),
            "columns": list(map(str, obj.columns)),
        }
    if isinstance(obj, pd.Series):
        return {
            "type": "series",
            "length": int(obj.shape[0]),
            "name": str(obj.name),
        }

    # numpy scalars
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)

    # containers
    if isinstance(obj, dict):
        return {str(k): _json_safe(v, max_str=max_str) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v, max_str=max_str) for v in obj]

    # bytes / strings
    if isinstance(obj, (bytes, bytearray)):
        s = obj.decode("utf-8", errors="replace")
        return s if len(s) <= max_str else s[:max_str] + "…"
    if isinstance(obj, str):
        return obj if len(obj) <= max_str else obj[:max_str] + "…"

    # primitives already OK (int, float, bool, None)
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj

    # fallback
    rep = repr(obj)
    return rep if len(rep) <= max_str else rep[:max_str] + "…"


# ─────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────
@router.post("/v1/agents/{agent_name}/run")
async def run_agent(agent_name: str, request: Request, file: UploadFile | None = File(None)) -> Dict[str, Any]:
    if agent_name != AGENT_NAME:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_name}'")

    # Read form data (for fields) and take the CSV from `file`
    try:
        form = await request.form()
    except Exception:
        form = {}

    params = _parse_form_to_params(form)
    df = _load_csv_from_upload(file)

    # Import agent module dynamically
    try:
        from agents.credit_appraisal import agent as credit_agent
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import agent: {e}") from e

    # Generate a fallback run_id
    fallback_run_id = f"run_{int(time.time())}"

    # Execute the agent with a stable contract
    try:
        if hasattr(credit_agent, "run") and callable(credit_agent.run):
            # New contract: run(df, params: dict) -> dict
            raw_result = credit_agent.run(df, params)
        elif hasattr(credit_agent, "run_credit_appraisal") and callable(credit_agent.run_credit_appraisal):
            # Legacy: run_credit_appraisal(df, **params) -> dict
            raw_result = credit_agent.run_credit_appraisal(df, **params)
        else:
            raise AttributeError(
                "Agent entry missing. Provide `run(df, params)` or `run_credit_appraisal(df, **kwargs)`."
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}") from e

    # Prefer the agent-provided run_id if present
    run_id = (raw_result or {}).get("run_id") or fallback_run_id

    # Persist minimal artifacts if the agent didn't already
    try:
        _persist_minimal_artifacts(run_id, raw_result or {})
    except Exception:
        # Don't fail the API if persistence is best-effort
        pass

    # Return a JSON-safe payload (strip dataframes/np types)
    safe_result = _json_safe(raw_result or {})

    return {
        "run_id": run_id,
        "result": safe_result,
    }
