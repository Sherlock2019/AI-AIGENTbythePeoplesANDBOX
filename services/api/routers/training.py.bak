# services/api/routers/training.py
from __future__ import annotations

import os
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

# Model utils from the credit appraisal agent
from agents.credit_appraisal import model_utils as MU

router = APIRouter(prefix="/v1/training", tags=["training"])


# ───────────────────────────────────────────────────────────────
# Pydantic models
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
# Endpoints
# ───────────────────────────────────────────────────────────────

@router.post("/train")
def train(req: TrainRequest) -> Dict[str, Any]:
    """
    Train a candidate model using one or more human-feedback CSVs.
    Payload contract:
      {
        "feedback_csvs": ["/abs/path/feedback1.csv", "..."],
        "user_name": "Alice",
        "agent_name": "credit_appraisal",
        "algo_name": "credit_lr"
      }
    """
    try:
        resp = MU.fit_candidate_on_feedback(
            feedback_csvs=req.feedback_csvs,
            user_name=req.user_name,
            agent_name=req.agent_name,
            algo_name=req.algo_name,
        )
        return resp
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Training failed: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Training failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {e}")


@router.post("/promote")
def promote(req: Optional[PromoteRequest] = None) -> Dict[str, Any]:
    """
    Promote a trained model to production.

    - If body is missing or model_name is None/blank: promote the latest trained model.
    - If model_name is given (either a filename or a full path), we sanitize to basename.
    """
    try:
        # Fallback when body is missing entirely
        model_name = None if req is None else (req.model_name or None)

        if not model_name:
            # auto-promote the latest trained model
            return MU.promote_last_trained_to_production()

        # allow callers sending full absolute path — sanitize to filename
        model_name = os.path.basename(model_name)
        return MU.promote_to_production(model_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Promote failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Promote failed: {e}")


@router.get("/production_meta")
def production_meta() -> Dict[str, Any]:
    """
    Returns:
      { "has_production": bool, "meta": {...} }
    """
    try:
        return MU.get_production_meta()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch production meta: {e}")


@router.get("/list_models")
def list_models(kind: str = "trained") -> Dict[str, Any]:
    """
    List available models.
      kind ∈ {"trained","production"}
    """
    try:
        models = MU.list_available_models(kind=kind)
        return {"kind": kind, "models": models}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {e}")
