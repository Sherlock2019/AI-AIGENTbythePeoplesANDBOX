# services/api/routers/training_credit.py
from __future__ import annotations

import os
import io
import json
import time
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["training-credit"])

# Base location for credit agent models
CREDIT_BASE = os.path.expanduser(
    "~/credit-appraisal-agent-poc/agents/credit_appraisal/models"
)
TRAINED_DIR = os.path.join(CREDIT_BASE, "trained")
PROD_DIR    = os.path.join(CREDIT_BASE, "production")

os.makedirs(TRAINED_DIR, exist_ok=True)
os.makedirs(PROD_DIR, exist_ok=True)

def _nowstamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")

@router.post("/agents/{agent_id}/training/train_credit")
async def train_credit(
    agent_id: str,
    files: List[UploadFile] = File(description="One or more feedback CSVs", default=[]),
    meta: Optional[str] = Form(default=None),
):
    """
    Minimal training stub for Credit Appraisal.
    - Stores uploaded CSVs under trained/<stamp>/
    - Creates a dummy model artifact model-<stamp>.joblib
    - Returns a job descriptor (id, paths)
    """
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id required")

    try:
        meta_json = json.loads(meta) if meta else {}
    except Exception:
        raise HTTPException(status_code=400, detail="invalid meta JSON")

    stamp = _nowstamp()
    job_dir = os.path.join(TRAINED_DIR, f"job-{stamp}")
    os.makedirs(job_dir, exist_ok=True)

    saved_csvs = []
    for f in files or []:
        # persist feedback CSVs
        buf = await f.read()
        outp = os.path.join(job_dir, f.filename or f"feedback-{int(time.time())}.csv")
        with open(outp, "wb") as w:
            w.write(buf)
        saved_csvs.append(outp)

    # Create a dummy trained model artifact
    model_name = f"model-{stamp}.joblib"
    model_path = os.path.join(TRAINED_DIR, model_name)
    with open(model_path, "wb") as w:
        w.write(b"DUMMY_CREDIT_MODEL_CONTENTS")

    job = {
        "status": "submitted",
        "agent_id": agent_id,
        "algo": meta_json.get("algo_name", "credit_lr"),
        "saved_feedback": saved_csvs,
        "trained_model": model_path,
        "created_at": stamp,
    }
    return JSONResponse(job)

@router.post("/agents/{agent_id}/training/promote_last_credit")
def promote_last_credit(agent_id: str):
    """
    Promotes the most recently created trained model to production/model.joblib
    """
    models = [
        os.path.join(TRAINED_DIR, f)
        for f in os.listdir(TRAINED_DIR)
        if f.endswith(".joblib")
    ]
    if not models:
        raise HTTPException(status_code=404, detail="No trained models found")

    last_model = max(models, key=os.path.getctime)
    prod_path = os.path.join(PROD_DIR, "model.joblib")
    os.makedirs(PROD_DIR, exist_ok=True)
    shutil.copy2(last_model, prod_path)

    return JSONResponse({
        "status": "ok",
        "promoted_from": last_model,
        "promoted_to": prod_path,
        "promoted_at": _nowstamp()
    })
