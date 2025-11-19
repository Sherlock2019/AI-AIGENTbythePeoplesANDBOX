# services/api/routers/agents.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Query, Body
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Any, Optional
import pandas as pd
import io, json, uuid, os
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Import concrete runners (no stubs)
try:
    from agents.asset_appraisal.runner import run as run_asset_appraisal  # noqa
except Exception as e:
    raise RuntimeError(f"Missing or broken asset_appraisal runner: {e}") from e

try:
    from agents.credit_appraisal.runner import run as run_credit_appraisal  # noqa
except Exception as e:
    raise RuntimeError(f"Missing or broken credit_appraisal runner: {e}") from e

try:
    from agents.credit_score.runner import run as run_credit_score  # noqa
except Exception as e:
    raise RuntimeError(f"Missing or broken credit_score runner: {e}") from e

try:
    from agents.legal_compliance.runner import run as run_legal_compliance  # noqa
except Exception as e:
    raise RuntimeError(f"Missing or broken legal_compliance runner: {e}") from e

try:
    from agents.real_estate_evaluator.runner import run as run_real_estate_evaluator  # noqa
    from agents.real_estate_evaluator.agent import run as agent_real_estate_evaluator  # noqa
except Exception as e:
    logger.warning(f"real_estate_evaluator agent not available: {e}")
    run_real_estate_evaluator = None
    agent_real_estate_evaluator = None

AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "asset_appraisal": {
        "id": "asset_appraisal",
        "display_name": "Asset Appraisal Agent",
        "aliases": ["asset"],
        "runner": run_asset_appraisal,
    },
    "credit_appraisal": {
        "id": "credit_appraisal",
        "display_name": "Credit Appraisal Agent",
        "aliases": ["credit"],
        "runner": run_credit_appraisal,
    },
    "credit_score": {
        "id": "credit_score",
        "display_name": "Credit Score Agent",
        "aliases": ["score"],
        "runner": run_credit_score,
    },
    "legal_compliance": {
        "id": "legal_compliance",
        "display_name": "Legal & Compliance Agent",
        "aliases": ["compliance", "legal"],
        "runner": run_legal_compliance,
    },
}

if run_real_estate_evaluator:
    AGENT_REGISTRY["real_estate_evaluator"] = {
        "id": "real_estate_evaluator",
        "display_name": "Real Estate Evaluator Agent",
        "aliases": ["real_estate", "re_evaluator"],
        "runner": run_real_estate_evaluator,
        "agent_func": agent_real_estate_evaluator,  # Full agent function that returns dict
    }

_ALIAS_TO_CANON: Dict[str, str] = {}
for canon, meta in AGENT_REGISTRY.items():
    _ALIAS_TO_CANON[canon] = canon
    for al in meta.get("aliases", []):
        _ALIAS_TO_CANON[al] = canon

def _canonicalize(agent_id: str) -> str:
    cid = _ALIAS_TO_CANON.get(agent_id)
    if not cid:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")
    return cid

def _read_csv_from_upload(upload: UploadFile) -> pd.DataFrame:
    raw = upload.file.read()
    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {e}") from e

# where we persist run artifacts (…/services/api/.runs)
RUNS_DIR = Path(__file__).resolve().parent.parent / ".runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup_old_csv_runs(runs_dir: Path, agent_id: str, keep_last_n: int = 10):
    """Keep only the last N CSV files per agent, delete older ones."""
    if not runs_dir.exists():
        return
    
    # Find all CSV files for this agent
    pattern = f"{agent_id}_*.merged.csv"
    csv_files = sorted(runs_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if len(csv_files) <= keep_last_n:
        return
    
    # Keep the most recent N files, delete the rest
    files_to_delete = csv_files[keep_last_n:]
    deleted_count = 0
    for csv_file in files_to_delete:
        try:
            # Also delete corresponding JSON file if it exists
            json_file = csv_file.with_suffix('.merged.json')
            if json_file.exists():
                json_file.unlink()
            csv_file.unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete {csv_file}: {e}")
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old CSV runs for agent {agent_id}, kept {keep_last_n} most recent")

@router.get("/v1/agents")
def list_agents():
    items = []
    for meta in AGENT_REGISTRY.values():
        items.append({
            "id": meta["id"],
            "display_name": meta.get("display_name", meta["id"]),
            "aliases": meta.get("aliases", []),
        })
    return {"agents": items}

@router.get("/v1/agents/list")
def list_agents_alt():
    return list_agents()

@router.post("/v1/agents/{agent_id}/run")
async def run_agent(
    agent_id: str,
    file: UploadFile = File(..., description="CSV file"),

    # Legacy / classic fields (kept for compat)
    use_llm: Optional[str] = Form(None),
    llm: Optional[str] = Form(None),
    flavor: Optional[str] = Form(None),
    selected_model: Optional[str] = Form(None),
    agent_name: Optional[str] = Form(None),
    rule_mode: Optional[str] = Form(None),
    max_dti: Optional[str] = Form(None),
    min_ndi_ratio: Optional[str] = Form(None),
    min_emp: Optional[str] = Form(None),
    min_hist: Optional[str] = Form(None),
    max_delin: Optional[str] = Form(None),
    req_min: Optional[str] = Form(None),
    req_max: Optional[str] = Form(None),
    allowed_terms: Optional[str] = Form(None),
    monthly_relief: Optional[str] = Form(None),
    threshold: Optional[str] = Form(None),
    target_approval_rate: Optional[str] = Form(None),
    random_band: Optional[str] = Form(None),
    random_approval_band: Optional[str] = Form(None),
    currency_code: Optional[str] = Form(None),
    currency_symbol: Optional[str] = Form(None),

    # New UI names
    use_llm_narrative: Optional[str] = Form(None),
    llm_model: Optional[str] = Form(None),
    hardware_flavor: Optional[str] = Form(None),
    min_employment_years: Optional[str] = Form(None),
    max_debt_to_income: Optional[str] = Form(None),
    min_credit_history_length: Optional[str] = Form(None),
    max_num_delinquencies: Optional[str] = Form(None),
    requested_amount_min: Optional[str] = Form(None),
    requested_amount_max: Optional[str] = Form(None),
    loan_term_months_allowed: Optional[str] = Form(None),
    monthly_debt_relief: Optional[str] = Form(None),
    ):
    canon = _canonicalize(agent_id)
    df = _read_csv_from_upload(file)

    # normalize params into a single dict
    params: Dict[str, Any] = {
        "use_llm": (use_llm or use_llm_narrative),
        "llm": (llm or llm_model),
        "flavor": (flavor or hardware_flavor),
        "selected_model": selected_model,
        "agent_name": (agent_name or canon),
        "rule_mode": rule_mode,

        "currency_code": currency_code,
        "currency_symbol": currency_symbol,

        "max_dti": (max_dti or max_debt_to_income),
        "min_emp": (min_emp or min_employment_years),
        "min_hist": (min_hist or min_credit_history_length),
        "max_delin": (max_delin or max_num_delinquencies),
        "req_min": (req_min or requested_amount_min),
        "req_max": (req_max or requested_amount_max),
        "allowed_terms": (allowed_terms or loan_term_months_allowed),
        "monthly_relief": (monthly_relief or monthly_debt_relief),

        "threshold": threshold,
        "target_approval_rate": target_approval_rate,
        "random_band": (random_band or random_approval_band),
    }
    # coerce boolean-ish strings
    for k in ("use_llm", "random_band"):
        v = params.get(k)
        if isinstance(v, str):
            params[k] = v.strip().lower() in ("true", "1", "yes", "on")

    runner = AGENT_REGISTRY[canon]["runner"]
    out_df = runner(df, params)
    if not isinstance(out_df, pd.DataFrame):
        raise HTTPException(status_code=500, detail="Runner did not return a DataFrame")

    # create a run_id and persist artifacts so the UI can fetch them later
    run_id = f"{canon}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    csv_path = RUNS_DIR / f"{run_id}.merged.csv"
    json_path = RUNS_DIR / f"{run_id}.merged.json"

    out_df.to_csv(csv_path, index=False)
    out_df.to_json(json_path, orient="records")

    # Auto-ingest CSV into RAG store after each run
    try:
        from services.api.rag.ingest import LocalIngestor
        ingestor = LocalIngestor()
        ingestor.ingest_files([csv_path], max_rows=200, dry_run=False)
        logger.info(f"Auto-ingested {csv_path} into RAG store")
    except Exception as e:
        logger.warning(f"Failed to auto-ingest CSV into RAG: {e}")

    # Cleanup: Keep only last 10 CSV runs per agent
    try:
        _cleanup_old_csv_runs(RUNS_DIR, canon, keep_last_n=10)
    except Exception as e:
        logger.warning(f"Failed to cleanup old CSV runs: {e}")

    meta = {
        "runner_used": f"{runner.__module__}.run",
        "rows": int(out_df.shape[0]),
        "cols": int(out_df.shape[1]),
        "currency_code": params.get("currency_code"),
        "currency_symbol": params.get("currency_symbol"),
    }

    # keep result body tiny – UI will fetch via /v1/runs/{run_id}/report
    return JSONResponse(content={
        "run_id": run_id,
        "agent_id": canon,
        "result": [],         # intentionally empty (prevents huge payloads)
        "meta": meta,
        "artifacts": {        # optional hints; UI can ignore and still call /v1/runs/...
            "csv_path": str(csv_path),
            "json_path": str(json_path),
        }
    })

@router.get("/v1/runs/{run_id}/report")
def get_run_report(run_id: str, format: str = Query("csv", regex="^(csv|json)$")):
    """
    Minimal endpoint the UI expects:
    GET /v1/runs/{run_id}/report?format=csv|json
    """
    csv_path = RUNS_DIR / f"{run_id}.merged.csv"
    json_path = RUNS_DIR / f"{run_id}.merged.json"

    if format == "csv":
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="CSV report not found")
        return FileResponse(path=str(csv_path), media_type="text/csv", filename=f"{run_id}.csv")

    # format == "json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="JSON report not found")
    return FileResponse(path=str(json_path), media_type="application/json", filename=f"{run_id}.json")


@router.post("/v1/agents/{agent_id}/run/json")
async def run_agent_json(
    agent_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """Endpoint that accepts JSON payload with df and params for agents that support it"""
    canon = _canonicalize(agent_id)
    
    # Check if agent supports JSON mode
    agent_meta = AGENT_REGISTRY.get(canon)
    if not agent_meta:
        raise HTTPException(status_code=404, detail=f"Agent '{canon}' not found")
    
    agent_func = agent_meta.get("agent_func")
    if not agent_func:
        raise HTTPException(status_code=400, detail=f"Agent '{canon}' does not support JSON mode")
    
    # Extract df and params from payload
    df_data = payload.get("df", [])
    params = payload.get("params", {})
    
    if not df_data:
        raise HTTPException(status_code=400, detail="Missing 'df' in payload")
    
    # Convert to DataFrame
    try:
        df = pd.DataFrame(df_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid DataFrame data: {e}")
    
    # Run agent
    try:
        result = agent_func(df, params)
        # Convert DataFrame to dict for JSON serialization
        if "evaluated_df" in result and isinstance(result["evaluated_df"], pd.DataFrame):
            result["evaluated_df"] = result["evaluated_df"].to_dict(orient="records")
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error running agent {canon}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}")
