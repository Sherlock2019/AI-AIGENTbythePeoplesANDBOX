# services/api/routers/reports.py
from __future__ import annotations

import io
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse

RUNS_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/api/.runs")
router = APIRouter()

def _run_dir(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id)

@router.get("/v1/runs/{run_id}/report")
def get_report(run_id: str, format: str = "csv"):
    rdir = _run_dir(run_id)
    if not os.path.isdir(rdir):
        raise HTTPException(status_code=404, detail="run not found")

    if format == "csv":
        f = os.path.join(rdir, "merged.csv")
        if not os.path.isfile(f):
            raise HTTPException(404, "merged.csv not found")
        return FileResponse(f, media_type="text/csv", filename="merged.csv")

    if format == "scores_csv":
        f = os.path.join(rdir, "scores.csv")
        if not os.path.isfile(f):
            raise HTTPException(404, "scores.csv not found")
        return FileResponse(f, media_type="text/csv", filename="scores.csv")

    if format == "explanations_csv":
        f = os.path.join(rdir, "explanations.csv")
        if not os.path.isfile(f):
            raise HTTPException(404, "explanations.csv not found")
        return FileResponse(f, media_type="text/csv", filename="explanations.csv")

    if format == "json":
        f = os.path.join(rdir, "summary.json")
        if not os.path.isfile(f):
            raise HTTPException(404, "summary.json not found")
        return FileResponse(f, media_type="application/json", filename="summary.json")

    if format == "pdf":
        f = os.path.join(rdir, "run.pdf")
        if not os.path.isfile(f):
            raise HTTPException(404, "run.pdf not found")
        return FileResponse(f, media_type="application/pdf", filename="run.pdf")

    raise HTTPException(400, "unknown format")

