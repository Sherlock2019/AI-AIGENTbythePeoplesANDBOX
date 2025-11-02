from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from services.common.hub.registry import load_model_registry
from services.common.hub.hf_utils import ensure_model_files

MODELS_YAML = os.getenv("MODEL_REGISTRY", "config/model_registry.yaml")
router = APIRouter(prefix="/v1/hub/models", tags=["hub-models"])

class EnsureRequest(BaseModel):
    model_id: str

@router.get("/list")
def list_models():
    regs = load_model_registry(MODELS_YAML)
    return [{"id": r.id, "repo": r.repo, "role": r.role, "framework": r.framework, "cache_dir": r.cache_dir} for r in regs]

@router.post("/ensure")
def ensure_model(req: EnsureRequest):
    regs = load_model_registry(MODELS_YAML)
    item = next((r for r in regs if r.id == req.model_id), None)
    if not item:
        raise HTTPException(status_code=404, detail=f"Model id not found: {req.model_id}")
    paths = ensure_model_files(item.repo, item.files, item.revision, item.cache_dir)
    return {"model_id": item.id, "paths": paths, "role": item.role, "framework": item.framework}
