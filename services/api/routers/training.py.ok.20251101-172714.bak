# services/api/routers/training.py
from __future__ import annotations

import os, io, json, time, shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

# ---- Credit model utils (existing, works today) ----
from agents.credit_appraisal import model_utils as MU

# ---- Try asset model utils if you add them later; we fall back to inline trainer otherwise ----
try:
    from agents.asset_appraisal import model_utils as AMU  # optional
    _HAVE_AMU = True
except Exception:
    _HAVE_AMU = False

from pydantic import BaseModel, Field, field_validator

# IMPORTANT: prefix is /v1 so we can serve BOTH:
# - /v1/training/* (credit JSON paths you already use)
# - /v1/agents/{agent_id}/training/* (agent-scoped paths used by your UI)
router = APIRouter(prefix="/v1", tags=["training"])

# ───────────────────────────────────────────────────────────────
# Shared paths (asset)
# ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]  # <repo>/services/api/routers -> <repo>
STATE_DIR = ROOT / "services" / "api" / ".state"
RUNS_DIR  = ROOT / "services" / "api" / ".runs"

ASSET_TRAINED_DIR   = ROOT / "agents" / "asset_appraisal" / "models" / "trained"
ASSET_PRODUCTION_FP = ROOT / "agents" / "asset_appraisal" / "models" / "production" / "model.joblib"
ASSET_META_FP       = STATE_DIR / "asset_production_meta.json"

for d in [STATE_DIR, RUNS_DIR, ASSET_TRAINED_DIR, ASSET_PRODUCTION_FP.parent]:
    d.mkdir(parents=True, exist_ok=True)

# sklearn is optional (WSL slim envs may lack scipy); we fallback to numpy normal-eq
try:
    from sklearn.linear_model import LinearRegression
    import joblib
    _HAVE_SK = True
except Exception:
    _HAVE_SK = False
    joblib = None  # type: ignore

def _now_tag() -> str:
    return time.strftime("%Y%m%d-%H%M%S")

def _list_asset_trained_models() -> list[Path]:
    if not ASSET_TRAINED_DIR.exists():
        return []
    return sorted(
        ASSET_TRAINED_DIR.glob("model-*.joblib"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

# ───────────────────────────────────────────────────────────────
# Pydantic models (credit JSON API you already use)
# ───────────────────────────────────────────────────────────────
class TrainRequest(BaseModel):
    feedback_csvs: List[str] = Field(..., description="Absolute paths to feedback CSVs")
    user_name: str
    agent_name: str = "credit_appraisal"
    algo_name: str = "credit_lr"

    @field_validator("feedback_csvs")
    @classmethod
    def _check_csvs_exist(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("feedback_csvs must be a non-empty list of paths.")
        missing = [p for p in v if not os.path.exists(p)]
        if missing:
            raise ValueError(f"The following feedback_csvs do not exist: {missing}")
        return v

class PromoteRequest(BaseModel):
    # Optional, if omitted we will promote the latest trained model
    model_name: Optional[str] = None

# ───────────────────────────────────────────────────────────────
# CREDIT endpoints (unchanged paths)
#   /v1/training/train
#   /v1/training/promote
#   /v1/training/list_models
# ───────────────────────────────────────────────────────────────
@router.post("/training/train")
def train_credit_json(req: TrainRequest) -> Dict[str, Any]:
    try:
        return MU.fit_candidate_on_feedback(
            feedback_csvs=req.feedback_csvs,
            user_name=req.user_name,
            agent_name=req.agent_name,
            algo_name=req.algo_name,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Training failed: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Training failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {e}")

@router.post("/training/promote")
def promote_credit_json(req: Optional[PromoteRequest] = None) -> Dict[str, Any]:
    try:
        model_name = None if req is None else (req.model_name or None)
        if not model_name:
            return MU.promote_last_trained_to_production()
        model_name = os.path.basename(model_name)
        return MU.promote_to_production(model_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Promote failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Promote failed: {e}")

@router.get("/training/list_models")
def list_models(kind: str = "trained") -> Dict[str, Any]:
    try:
        models = MU.list_available_models(kind=kind)
        return {"kind": kind, "models": models}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {e}")

# ───────────────────────────────────────────────────────────────
# PRODUCTION META (agent-scoped)  /v1/training/production_meta?agent_id=...
# ───────────────────────────────────────────────────────────────
@router.get("/training/production_meta")
def production_meta(agent_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """
    agent_id:
      - "credit_appraisal" -> delegates to MU.get_production_meta()
      - "asset_appraisal"  -> reads asset production state
      - None               -> backward-compat: returns asset if present else credit
    """
    try:
        if agent_id == "credit_appraisal":
            return MU.get_production_meta()

        if agent_id == "asset_appraisal":
            if ASSET_PRODUCTION_FP.exists():
                meta = {"version": "1.x", "source": "production"}
                if ASSET_META_FP.exists():
                    try:
                        meta.update(json.loads(ASSET_META_FP.read_text()))
                    except Exception:
                        pass
                # normalize key names to match your UI expectations
                if "model_path" not in meta:
                    meta["model_path"] = str(ASSET_PRODUCTION_FP)
                return {"status": "ok", "has_production": True, "meta": meta, "agent_id": "asset_appraisal"}
            return {"status": "ok", "has_production": False, "meta": {}, "agent_id": "asset_appraisal"}

        # Fallback detection order: asset first (if present), else credit
        if ASSET_PRODUCTION_FP.exists():
            m = {"version": "1.x", "source": "production", "model_path": str(ASSET_PRODUCTION_FP)}
            if ASSET_META_FP.exists():
                try:
                    m.update(json.loads(ASSET_META_FP.read_text()))
                except Exception:
                    pass
            return {"status": "ok", "has_production": True, "meta": m, "agent_id": "asset_appraisal"}
        return MU.get_production_meta()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch production meta: {e}")

# ───────────────────────────────────────────────────────────────
# ASSET endpoints (multipart) used by your UI/CLI:
#   POST /v1/agents/{agent_id}/training/train_asset
#   POST /v1/agents/{agent_id}/training/promote_last
# Optional CREDIT wrappers for path symmetry:
#   POST /v1/agents/{agent_id}/training/train_credit
#   POST /v1/agents/{agent_id}/training/promote_last_credit
# ───────────────────────────────────────────────────────────────
@router.post("/agents/{agent_id}/training/train_asset")
async def train_asset_multipart(
    agent_id: str,
    files: List[UploadFile] = File(..., description="One or more CSV feedback files"),
    meta: Optional[str] = Form(None),
) -> Dict[str, Any]:
    if agent_id not in {"asset_appraisal", "asset"}:
        raise HTTPException(status_code=404, detail=f"Unsupported agent '{agent_id}' for train_asset")

    # If you later provide AMU with a rich trainer, delegate to it:
    if _HAVE_AMU and hasattr(AMU, "fit_candidate_on_feedback_multipart"):
        try:
            return await AMU.fit_candidate_on_feedback_multipart(files=files, meta_json=meta)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Asset training failed: {e}")

    # Minimal built-in trainer (keeps you unblocked now)
    raw_frames: list[pd.DataFrame] = []
    save_dir = RUNS_DIR / f"asset-train-{_now_tag()}"
    save_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        blob = await f.read()
        (save_dir / f.filename).write_bytes(blob)
        try:
            raw_frames.append(pd.read_csv(io.BytesIO(blob)))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse CSV '{f.filename}': {e}")

    if not raw_frames:
        raise HTTPException(status_code=400, detail="No CSV files provided")

    df = pd.concat(raw_frames, ignore_index=True)

    # choose target
    target_col = "ai_adjusted" if "ai_adjusted" in df.columns else ("market_value" if "market_value" in df.columns else None)
    if not target_col:
        raise HTTPException(status_code=422, detail="No target column (ai_adjusted or market_value) found in feedback CSVs")

    candidate_feats = [
        "age_years","condition_score","legal_penalty","loan_amount",
        "employment_years","credit_history_years","delinquencies",
        "current_loans","DTI","LTV"
    ]
    feats = [c for c in candidate_feats if c in df.columns]
    if not feats:
        raise HTTPException(status_code=422, detail=f"No usable numeric features present. Expected any of: {candidate_feats}")

    X = df[feats].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    y = pd.to_numeric(df[target_col], errors="coerce").fillna(0.0).values

    model_path = ASSET_TRAINED_DIR / f"model-{_now_tag()}.joblib"
    if _HAVE_SK:
        m = LinearRegression()
        m.fit(X, y)
        joblib.dump({"model": m, "features": feats, "target": target_col}, model_path)
    else:
        X1 = np.c_[np.ones((X.shape[0], 1)), X]
        w  = np.linalg.pinv(X1) @ y
        np.save(model_path.with_suffix(".npy"), {"w": w, "features": feats, "target": target_col})
        shutil.copy2(model_path.with_suffix(".npy"), model_path)  # keep .joblib filename for UI

    meta_obj = json.loads(meta) if meta else {}
    job_meta = {
        "status": "submitted",
        "agent_id": "asset_appraisal",
        "algo": meta_obj.get("algo_name") or "asset_lr",
        "saved_feedback_dir": str(save_dir),
        "trained_model": str(model_path),
        "created_at": _now_tag(),
        "features": feats,
        "target": target_col,
        "rows": int(df.shape[0]),
        "sklearn": _HAVE_SK,
        "meta": meta_obj,
    }
    (save_dir / "train_meta.json").write_text(json.dumps(job_meta, indent=2))
    return job_meta

@router.post("/agents/{agent_id}/training/promote_last")
def promote_asset_last(agent_id: str) -> Dict[str, Any]:
    if agent_id not in {"asset_appraisal", "asset"}:
        raise HTTPException(status_code=404, detail=f"Unsupported agent '{agent_id}' for promote_last")

    models = _list_asset_trained_models()
    if not models:
        raise HTTPException(status_code=404, detail="No trained models found for asset_appraisal")

    newest = models[0]
    shutil.copy2(newest, ASSET_PRODUCTION_FP)
    meta = {
        "version": "1.x",
        "source": "trained",
        "promoted_from": str(newest),
        "promoted_at": _now_tag(),
        "model_path": str(ASSET_PRODUCTION_FP),
    }
    ASSET_META_FP.write_text(json.dumps(meta, indent=2))
    return {"status": "ok", "promoted_to": str(ASSET_PRODUCTION_FP), "meta": meta, "agent_id": "asset_appraisal"}

# (Optional) Credit wrappers for symmetry with your successful CLI/UI flows:
@router.post("/agents/{agent_id}/training/train_credit")
async def train_credit_agent_scoped(
    agent_id: str,
    files: List[UploadFile] = File(...),
    meta: Optional[str] = Form(None),
) -> Dict[str, Any]:
    if agent_id not in {"credit_appraisal", "credit"}:
        raise HTTPException(status_code=404, detail=f"Unsupported agent '{agent_id}' for train_credit")

    # Accept either: (a) meta JSON + uploaded file(s) we save then pass to MU, or (b) caller already did MU JSON path flow
    save_dir = RUNS_DIR / f"credit-train-{_now_tag()}"
    save_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        blob = await f.read()
        fp = save_dir / f.filename
        fp.write_bytes(blob)
        saved.append(str(fp))

    meta_obj = json.loads(meta) if meta else {}
    try:
        return MU.fit_candidate_on_feedback(
            feedback_csvs=saved,
            user_name=meta_obj.get("user_name", "unknown"),
            agent_name="credit_appraisal",
            algo_name=meta_obj.get("algo_name", "credit_lr"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Credit training failed: {e}")

@router.post("/agents/{agent_id}/training/promote_last_credit")
def promote_credit_agent_scoped(agent_id: str) -> Dict[str, Any]:
    if agent_id not in {"credit_appraisal", "credit"}:
        raise HTTPException(status_code=404, detail=f"Unsupported agent '{agent_id}' for promote_last_credit")
    try:
        return MU.promote_last_trained_to_production()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Credit promote failed: {e}")
