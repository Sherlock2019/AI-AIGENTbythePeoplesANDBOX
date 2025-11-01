# services/api/routers/training.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
import os, pandas as pd, uuid, subprocess, json

router = APIRouter(prefix="/v1/training", tags=["training"])
FEEDBACK_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/api/.runs/feedback")
RUNS_DIR = os.path.expanduser("~/credit-appraisal-agent-poc/services/api/.runs")
TRAIN_LOG_DIR = os.path.join(RUNS_DIR, "train")
os.makedirs(FEEDBACK_DIR, exist_ok=True)
os.makedirs(TRAIN_LOG_DIR, exist_ok=True)

class FeedbackItem(BaseModel):
    application_id: str
    y_true: int                # 1 approved/good, 0 declined/bad, -1 unknown
    label_confidence: float = 1.0
    reason_codes: list[str] = []
    notes: str = ""
    corrected_features: dict = {}   # e.g. {"salary": 1200, "employment_years": 5}
    y_pred: int | None = None
    p_pred: float | None = None
    model_version_at_score: str | None = None
    source_run_id: str | None = None
    dataset_hash_at_score: str | None = None
    reviewer_id: str = "anonymous"

@router.post("/feedback")
def submit_feedback(item: FeedbackItem):
    ts = datetime.utcnow().isoformat()
    row = {
        "application_id": item.application_id,
        "timestamp_utc": ts,
        "reviewer_id": item.reviewer_id,
        "y_true": item.y_true,
        "label_confidence": item.label_confidence,
        "reason_codes": ",".join(item.reason_codes),
        "notes": item.notes,
        "y_pred": item.y_pred,
        "p_pred": item.p_pred,
        "model_version_at_score": item.model_version_at_score,
        "source_run_id": item.source_run_id,
        "dataset_hash_at_score": item.dataset_hash_at_score,
    }
    for k, v in (item.corrected_features or {}).items():
        row[f"feature_{k}"] = v

    fname = os.path.join(FEEDBACK_DIR, f"feedback_{datetime.utcnow():%Y%m}.csv")
    df = pd.DataFrame([row])
    if os.path.exists(fname):
        df.to_csv(fname, mode="a", header=False, index=False)
    else:
        df.to_csv(fname, index=False)
    return {"status": "ok", "file": fname, "written": 1}

@router.post("/train")
def launch_training(config: dict):
    """
    Example config:
    {"split":{"train":0.7,"val":0.15,"test":0.15},
     "rebalance":"class_weights", "metrics":["auc","f1","bal_acc"],
     "feature_groups":["core","engineered"], "cutoff_date":"2024-01-01"}
    """
    job_id = str(uuid.uuid4())
    log_path = os.path.join(TRAIN_LOG_DIR, f"{job_id}.log")
    cfg_path = os.path.join(TRAIN_LOG_DIR, f"{job_id}.json")
    with open(cfg_path, "w") as f:
        json.dump(config, f)
    # Simple subprocess call to trainer
    trainer = os.path.expanduser("~/credit-appraisal-agent-poc/services/train/train_credit.py")
    if not os.path.exists(trainer):
        raise HTTPException(500, detail="trainer script not found")
    proc = subprocess.Popen(
        ["python", trainer, "--job", job_id, "--config", cfg_path],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )
    return {"status": "queued", "job_id": job_id, "log": log_path}

@router.get("/train/{job_id}/status")
def train_status(job_id: str):
    log_path = os.path.join(TRAIN_LOG_DIR, f"{job_id}.log")
    if not os.path.exists(log_path):
        raise HTTPException(404, detail="job not found")
    # lightweight status inference
    tail = ""
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()[-50:]
            tail = "".join(lines)
    except:
        pass
    # if a metrics file exists, return it
    metrics_path = os.path.join(TRAIN_LOG_DIR, f"{job_id}.metrics.json")
    metrics = None
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            metrics = json.load(f)
    return {"status": "running" if metrics is None else "complete", "metrics": metrics, "log_tail": tail}
