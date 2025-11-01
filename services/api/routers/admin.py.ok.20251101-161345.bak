# services/api/routers/admin.py
from __future__ import annotations
import os, io, json, zipfile, datetime, shutil
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/v1/admin", tags=["admin"])

ROOT = os.path.expanduser("~/credit-appraisal-agent-poc")
RUNS_DIR = os.path.join(ROOT, "services", "api", ".runs")
EXPORTS_DIR = os.path.join(RUNS_DIR, "exports")
SNAP_DIR = os.path.join(RUNS_DIR, "snapshots")
AGENT_DIR = os.path.join(ROOT, "agents", "credit_appraisal")
MODELS_DIR = os.path.join(AGENT_DIR, "models")
PROD_DIR = os.path.join(MODELS_DIR, "production")

os.makedirs(RUNS_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(SNAP_DIR, exist_ok=True)
os.makedirs(PROD_DIR, exist_ok=True)

def _zip_dir(zip_path: str, dir_to_zip: str):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(dir_to_zip):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, start=os.path.dirname(dir_to_zip))
                z.write(full, arc)

@router.post("/snapshot")
def create_snapshot(
    label: str = Form(default="manual"),
    include_runs: bool = Form(default="true"),
    include_models: bool = Form(default="true"),
):
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    snap_root = os.path.join(SNAP_DIR, f"{ts}_{label}")
    os.makedirs(snap_root, exist_ok=True)

    # configs / code
    keep = [
        os.path.join(ROOT, "services", "api", "main.py"),
        os.path.join(ROOT, "services", "api", "routers"),
        os.path.join(ROOT, "services", "ui", "app.py"),
        os.path.join(ROOT, "agents", "credit_appraisal", "agent.py"),
        os.path.join(ROOT, "agents", "credit_appraisal", "model_utils.py"),
    ]
    for p in keep:
        dst = os.path.join(snap_root, os.path.relpath(p, ROOT))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(p):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(p, dst)
        elif os.path.isfile(p):
            shutil.copyfile(p, dst)

    if include_runs.lower() == "true":
        dst = os.path.join(snap_root, os.path.relpath(RUNS_DIR, ROOT))
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(RUNS_DIR, dst)

    if include_models.lower() == "true":
        dst = os.path.join(snap_root, os.path.relpath(MODELS_DIR, ROOT))
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(MODELS_DIR, dst)

    return {"ok": True, "snapshot_dir": snap_root}

@router.post("/export")
def export_zip(label: str = Form(default="poc_export")):
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    snap_resp = create_snapshot(label=f"export_{label}", include_runs="true", include_models="true")
    snap_dir = snap_resp["snapshot_dir"]
    zip_path = os.path.join(EXPORTS_DIR, f"{label}_{ts}.zip")
    _zip_dir(zip_path, snap_dir)
    return {"ok": True, "zip_path": zip_path}

@router.get("/download")
def download_zip(path: str):
    if not os.path.exists(path) or not path.endswith(".zip"):
        raise HTTPException(404, "ZIP not found")
    return FileResponse(path, media_type="application/zip", filename=os.path.basename(path))
