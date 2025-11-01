# services/api/routers/runs.py
from __future__ import annotations

import os
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

ROOT = os.path.expanduser("~/credit-appraisal-agent-poc")
RUNS_ROOT = os.path.join(ROOT, "services", "api", ".runs")
os.makedirs(RUNS_ROOT, exist_ok=True)

router = APIRouter(prefix="/v1/runs", tags=["runs"])


def _find_run_dir(run_id: str) -> str:
    d = os.path.join(RUNS_ROOT, run_id)
    if os.path.isdir(d):
        return d
    # allow legacy: scan subdirs
    for name in os.listdir(RUNS_ROOT):
        cand = os.path.join(RUNS_ROOT, name)
        if os.path.isdir(cand) and name == run_id:
            return cand
    raise HTTPException(status_code=404, detail="Run not found")


@router.get("/{run_id}")
def get_run(run_id: str = Path(..., description="Run ID returned from /agents/run")):
    run_dir = _find_run_dir(run_id)
    summary_json = os.path.join(run_dir, "summary.json")
    if os.path.exists(summary_json):
        with open(summary_json) as f:
            summary = json.load(f)
    else:
        summary = {}
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "artifacts": {
            "scores_csv": os.path.join(run_dir, "scores.csv"),
            "explanations_csv": os.path.join(run_dir, "explanations.csv"),
            "merged_csv": os.path.join(run_dir, "merged.csv"),
            "scores_json": os.path.join(run_dir, "scores.json"),
            "explanations_json": os.path.join(run_dir, "explanations.json"),
            "summary_json": summary_json,
            "pdf_report": os.path.join(run_dir, f"{run_id}_credit_report.pdf"),
        },
        "summary": summary,
    }


@router.get("/{run_id}/report")
def download_report(
    run_id: str = Path(..., description="Run ID"),
    format: Literal["pdf", "scores_csv", "explanations_csv", "csv", "json"] = Query(
        "pdf",
        description="Pick one: pdf (report), scores_csv, explanations_csv, csv (merged), json (combined JSON).",
    ),
):
    run_dir = _find_run_dir(run_id)

    if format == "pdf":
        path = os.path.join(run_dir, f"{run_id}_credit_report.pdf")
        if not os.path.exists(path):
            raise HTTPException(404, "PDF not found")
        return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))

    if format == "scores_csv":
        path = os.path.join(run_dir, "scores.csv")
        if not os.path.exists(path):
            raise HTTPException(404, "Scores CSV not found")
        return FileResponse(path, media_type="text/csv", filename=f"scores_{run_id}.csv")

    if format == "explanations_csv":
        path = os.path.join(run_dir, "explanations.csv")
        if not os.path.exists(path):
            raise HTTPException(404, "Explanations CSV not found")
        return FileResponse(path, media_type="text/csv", filename=f"explanations_{run_id}.csv")

    if format == "csv":
        path = os.path.join(run_dir, "merged.csv")
        if not os.path.exists(path):
            raise HTTPException(404, "Merged CSV not found")
        return FileResponse(path, media_type="text/csv", filename=f"merged_{run_id}.csv")

    if format == "json":
        # Build a compact JSON bundle
        scores_json = os.path.join(run_dir, "scores.json")
        expl_json = os.path.join(run_dir, "explanations.json")
        summary_json = os.path.join(run_dir, "summary.json")

        data = {}
        if os.path.exists(scores_json):
            data["scores"] = json.load(open(scores_json))
        if os.path.exists(expl_json):
            data["explanations"] = json.load(open(expl_json))
        if os.path.exists(summary_json):
            data["summary"] = json.load(open(summary_json))
        return JSONResponse(data)

    return PlainTextResponse("Unsupported format", status_code=400)
