# services/api/routers/export.py
from __future__ import annotations

import io
import os
import zipfile
from typing import Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/v1", tags=["Export"])

ROOT = os.path.expanduser("~/credit-appraisal-agent-poc")
RUNS_ROOT = os.path.join(ROOT, "services", "api", ".runs")
AGENTS_DIR = os.path.join(ROOT, "agents")
SAMPLES_DIR = os.path.join(ROOT, "samples")
UI_DIR = os.path.join(ROOT, "services", "ui")
API_DIR = os.path.join(ROOT, "services", "api")

INCLUDE_PATHS = [
    ("agents", AGENTS_DIR),
    ("services/api", API_DIR),
    ("services/ui", UI_DIR),
    ("samples", SAMPLES_DIR),
    ("services/api/.runs", RUNS_ROOT),
]

@router.post("/export/bundle", summary="Export full PoC bundle as zip")
def export_bundle():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for label, base in INCLUDE_PATHS:
            if not os.path.exists(base): 
                continue
            for root, _, files in os.walk(base):
                for f in files:
                    fpath = os.path.join(root, f)
                    arcname = os.path.relpath(fpath, ROOT)
                    zf.write(fpath, arcname)
    mem.seek(0)
    return StreamingResponse(mem, media_type="application/zip", headers={
        "Content-Disposition": 'attachment; filename="rax_ai_sandbox_bundle.zip"'
    })

@router.post("/import/bundle", summary="Import a PoC bundle (zip)")
async def import_bundle(zip_file: UploadFile = File(...)):
    try:
        raw = await zip_file.read()
        mem = io.BytesIO(raw)
        with zipfile.ZipFile(mem, "r") as zf:
            zf.extractall(ROOT)
        return {"status": "ok", "extracted_to": ROOT}
    except Exception as e:
        raise HTTPException(400, f"Import failed: {e}")
