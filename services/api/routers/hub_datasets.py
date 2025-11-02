from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from datasets import load_dataset
from services.common.hub.registry import load_dataset_registry
from services.common.hub.kaggle_utils import kaggle_download

DATASETS_YAML = os.getenv("DATASET_REGISTRY", "config/dataset_registry.yaml")
router = APIRouter(prefix="/v1/hub/datasets", tags=["hub-datasets"])

class EnsureDatasetRequest(BaseModel):
    dataset_id: str

@router.get("/list")
def list_datasets():
    regs = load_dataset_registry(DATASETS_YAML)
    return [{"id": r.id, "source": r.source, "repo": r.repo, "task": r.task, "cache_dir": r.cache_dir} for r in regs]

@router.post("/ensure")
def ensure_dataset(req: EnsureDatasetRequest):
    regs = load_dataset_registry(DATASETS_YAML)
    d = next((x for x in regs if x.id == req.dataset_id), None)
    if not d:
        raise HTTPException(status_code=404, detail=f"Dataset id not found: {req.dataset_id}")

    if d.source == "hf":
        ds = load_dataset(d.repo, d.subset, split=d.split) if d.split else load_dataset(d.repo, d.subset)
        return {"dataset_id": d.id, "source": "hf", "repo": d.repo,
                "split": d.split, "subset": d.subset,
                "columns": list(ds.features.keys()) if hasattr(ds, "features") else None}

    if d.source == "kaggle":
        paths = kaggle_download(d.repo, d.files, d.cache_dir)
        return {"dataset_id": d.id, "source": "kaggle", "repo": d.repo, "paths": paths}

    raise HTTPException(status_code=400, detail=f"Unsupported source: {d.source}")
