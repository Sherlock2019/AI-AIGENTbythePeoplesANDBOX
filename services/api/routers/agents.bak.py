# services/api/routers/agents.py
from __future__ import annotations

import io
import os
import re
import json
import uuid
import shutil
from typing import Optional, List, Dict, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

# Ensure project root is on PYTHONPATH when launched via creditstart.sh
from agents.credit_appraisal.agent import agent as credit_agent  # type: ignore

router = APIRouter(prefix="/v1/agents", tags=["agents"])

# Paths
ROOT = os.path.expanduser("~/credit-appraisal-agent-poc")
RUNS_ROOT = os.path.join(ROOT, "services", "api", ".runs")
os.makedirs(RUNS_ROOT, exist_ok=True)

SAMPLE_CSV = os.path.join(
    ROOT, "agents", "credit_appraisal", "sample_data", "credit_sample.csv"
)

# ---------- helpers ----------

def _boolish(v: Optional[str | bool], default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return default

def parse_terms_csv(s: Optional[str]) -> List[int]:
    """
    Accept "12, 24,36", "12,24.0" etc → [12, 24, 36]
    """
    if not s:
        return []
    out: List[int] = []
    for tok in str(s).split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(int(float(tok)))
        except Exception:
            pass
    return out

_num_pat = re.compile(r"[-+]?\d*\.?\d+")
def coerce_numeric(series: pd.Series, as_int: bool = False) -> pd.Series:
    """
    Robust numeric coercion:
    - extracts first numeric token (so '36 months' -> 36, '45%' -> 45, '75,000' -> 75000)
    - handles empty/None/NaN
    """
    if pd.api.types.is_numeric_dtype(series):
        return series

    s = series.astype(str).str.replace(",", "", regex=False)
    s = s.str.extract(_num_pat, expand=False)
    vals = pd.to_numeric(s, errors="coerce")
    if as_int:
        return vals.round().astype("Int64")
    return vals

def normalize_agent_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map common alternate field names into the agent's expected schema.
    Does not drop any columns; only adds/mirrors when missing.
    """
    out = df.copy()
    if "employment_years" not in out.columns and "employment_length" in out.columns:
        out["employment_years"] = out["employment_length"]
    if "loan_term_months" not in out.columns and "loan_duration_months" in out.columns:
        out["loan_term_months"] = out["loan_duration_months"]
    if "debt_to_income" not in out.columns and "DTI" in out.columns:
        out["debt_to_income"] = out["DTI"]
    return out

def apply_tuning_filters(df: pd.DataFrame, filt: Dict[str, Any]) -> pd.DataFrame:
    """
    Apply business rules with robust type coercion.
    Also normalizes numeric columns back into df so downstream code is safe.
    """
    out = normalize_agent_schema(df)

    # Coerce/normalize all potentially-filtered columns
    if "employment_years" in out.columns:
        out["employment_years"] = coerce_numeric(out["employment_years"], as_int=True)

    if "debt_to_income" in out.columns:
        out["debt_to_income"] = coerce_numeric(out["debt_to_income"]).astype(float)
        if out["debt_to_income"].dropna().gt(1.2).any():
            out["debt_to_income"] = out["debt_to_income"] / 100.0
        out["debt_to_income"] = out["debt_to_income"].clip(lower=0)

    if "credit_history_length" in out.columns:
        out["credit_history_length"] = coerce_numeric(out["credit_history_length"], as_int=True)

    if "num_delinquencies" in out.columns:
        out["num_delinquencies"] = coerce_numeric(out["num_delinquencies"], as_int=True)

    if "current_loans" in out.columns:
        out["current_loans"] = coerce_numeric(out["current_loans"], as_int=True)

    if "requested_amount" in out.columns:
        out["requested_amount"] = coerce_numeric(out["requested_amount"]).astype(float)

    if "loan_term_months" in out.columns:
        out["loan_term_months"] = coerce_numeric(out["loan_term_months"], as_int=True)

    # Build mask and apply
    m = pd.Series(True, index=out.index, dtype=bool)

    v = filt.get("min_employment_years")
    if v is not None and "employment_years" in out.columns:
        m &= out["employment_years"].fillna(-10) >= int(v)

    v = filt.get("max_debt_to_income")
    if v is not None and "debt_to_income" in out.columns:
        m &= out["debt_to_income"].fillna(np.inf) <= float(v)

    v = filt.get("min_credit_history_length")
    if v is not None and "credit_history_length" in out.columns:
        m &= out["credit_history_length"].fillna(-10) >= int(v)

    v = filt.get("max_num_delinquencies")
    if v is not None and "num_delinquencies" in out.columns:
        m &= out["num_delinquencies"].fillna(10_000) <= int(v)

    v = filt.get("max_current_loans")
    if v is not None and "current_loans" in out.columns:
        m &= out["current_loans"].fillna(10_000) <= int(v)

    vmin = filt.get("requested_amount_min")
    vmax = filt.get("requested_amount_max")
    if "requested_amount" in out.columns:
        if vmin is not None:
            m &= out["requested_amount"].fillna(-np.inf) >= float(vmin)
        if vmax is not None:
            m &= out["requested_amount"].fillna(np.inf) <= float(vmax)

    allow = filt.get("loan_term_months_allowed") or []
    if allow and "loan_term_months" in out.columns:
        allowed = set(int(x) for x in allow)
        m &= out["loan_term_months"].isin(list(allowed))

    return out.loc[m].reset_index(drop=True)

# ---------- endpoint ----------

@router.post("/credit_appraisal/run")
async def run_agent(
    # dataset choice
    use_sample: str = Form(default="false"),
    use_llm_narrative: str = Form(default="false"),
    file: Optional[UploadFile] = File(default=None),

    # tuning overrides (all optional)
    threshold: Optional[float] = Form(default=None),
    target_approval_rate: Optional[float] = Form(default=None),

    min_employment_years: Optional[int] = Form(default=None),
    max_debt_to_income: Optional[float] = Form(default=None),
    min_credit_history_length: Optional[int] = Form(default=None),
    max_num_delinquencies: Optional[int] = Form(default=None),
    max_current_loans: Optional[int] = Form(default=None),
    requested_amount_min: Optional[float] = Form(default=None),
    requested_amount_max: Optional[float] = Form(default=None),
    loan_term_months_allowed: Optional[str] = Form(default=None),
):
    """
    Runs the credit_appraisal agent. Works with:
      • Sample dataset (use_sample=true)
      • Uploaded/prepared CSV (use_sample=false, file provided)

    Applies Credit Tuning filters with robust numeric coercion.
    """
    try:
        run_id = f"run_{uuid.uuid4().hex}"
        run_dir = os.path.join(RUNS_ROOT, run_id)
        os.makedirs(run_dir, exist_ok=True)

        # 1) Load dataframe
        use_sample_flag = _boolish(use_sample, False)
        if use_sample_flag:
            if not os.path.exists(SAMPLE_CSV):
                raise HTTPException(status_code=500, detail=f"Sample CSV not found at {SAMPLE_CSV}")
            df = pd.read_csv(SAMPLE_CSV)
        else:
            if file is None:
                raise HTTPException(status_code=400, detail="CSV file is required when use_sample=false")
            raw = await file.read()
            if not raw:
                file.file.seek(0)
                raw = await file.read()
            df = pd.read_csv(io.BytesIO(raw))

        # 2) Build filters and apply with robust coercion
        filters = {
            "min_employment_years": min_employment_years,
            "max_debt_to_income": max_debt_to_income,
            "min_credit_history_length": min_credit_history_length,
            "max_num_delinquencies": max_num_delinquencies,
            "max_current_loans": max_current_loans,
            "requested_amount_min": requested_amount_min,
            "requested_amount_max": requested_amount_max,
            "loan_term_months_allowed": parse_terms_csv(loan_term_months_allowed),
        }
        df_filtered = apply_tuning_filters(df, filters)

        if len(df_filtered) == 0:
            raise HTTPException(status_code=400, detail="All rows were filtered out by the tuning constraints.")

        # 3) Save filtered CSV for this run
        csv_path = os.path.join(run_dir, "applications.csv")
        df_filtered.to_csv(csv_path, index=False)

        # 4) Agent context
        ctx = {
            "narrative": None if (not _boolish(use_llm_narrative, False)) else "Please summarize key portfolio drivers.",
            # keep structured tuning
            "tuning": {
                "threshold": threshold,
                "target_approval_rate": target_approval_rate,
                **filters,
            },
            # 👉 also pass top-level keys so the agent can read them easily
            "threshold": threshold,
            "target_accept_rate": target_approval_rate,  # agent may look for this name
        }

        # 5) Invoke agent
        result = credit_agent.run({"applications_csv": csv_path}, ctx)

        # 6) Persist artifacts + inline CSV text for UI
        scores = result.get("scores", [])
        exps = result.get("explanations", [])
        summary = result.get("summary", {})

        scores_csv = os.path.join(run_dir, "scores.csv")
        exp_csv = os.path.join(run_dir, "explanations.csv")
        merged_csv = os.path.join(run_dir, "merged.csv")
        scores_json = os.path.join(run_dir, "scores.json")
        df_json = os.path.join(run_dir, "df.json")
        summary_json = os.path.join(run_dir, "summary.json")

        pd.DataFrame(scores).to_csv(scores_csv, index=False)
        pd.DataFrame(exps).to_csv(exp_csv, index=False)
        (pd.DataFrame(exps) if exps else pd.DataFrame(scores)).to_csv(merged_csv, index=False)

        with open(scores_json, "w") as f:
            json.dump(scores, f)
        with open(df_json, "w") as f:
            json.dump(exps, f)
        with open(summary_json, "w") as f:
            json.dump(summary, f)

        pdf_out = None
        artifacts = result.get("artifacts", {}) or {}
        if artifacts.get("explanation_pdf") and os.path.exists(artifacts["explanation_pdf"]):
            pdf_out = os.path.join(run_dir, f"{run_id}_credit_report.pdf")
            if os.path.abspath(artifacts["explanation_pdf"]) != os.path.abspath(pdf_out):
                shutil.copyfile(artifacts["explanation_pdf"], pdf_out)

        payload = {
            "run_id": run_id,
            "result": {
                "run_id": run_id,
                "scores": scores,
                "explanations": exps,
                "summary": summary,
                "scores_csv_text": pd.DataFrame(scores).to_csv(index=False),
                "explanations_csv_text": pd.DataFrame(exps).to_csv(index=False),
                "artifacts": {
                    "run_dir": run_dir,
                    "scores_csv": scores_csv,
                    "explanations_csv": exp_csv,
                    "scores_json": scores_json,
                    "df_json": df_json,
                    "summary_json": summary_json,
                    "explanation_pdf": pdf_out,
                },
            },
        }
        return JSONResponse(payload)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Run error: {type(e).__name__}: {e}")
