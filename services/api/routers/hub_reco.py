from fastapi import APIRouter, HTTPException, Query
import os, yaml
from services.common.hub.registry import load_model_registry, load_dataset_registry

MODELS_YAML = os.getenv("MODEL_REGISTRY", "config/model_registry.yaml")
DATASETS_YAML = os.getenv("DATASET_REGISTRY", "config/dataset_registry.yaml")

router = APIRouter(prefix="/v1/hub/recommendations", tags=["hub-recommendations"])

def _load_reco():
    with open(MODELS_YAML, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("recommendations", {})

@router.get("/list")
def list_all():
    return _load_reco()

@router.get("/for")
def for_agent_task(agent: str = Query(...), task: str = Query(...)):
    rec = _load_reco()
    if agent not in rec:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent}")
    if task not in rec[agent]:
        raise HTTPException(status_code=404, detail=f"Unknown task for {agent}: {task}")
    payload = rec[agent][task]

    # Expand to include existence hints
    ms = {m.id: m for m in load_model_registry(MODELS_YAML)}
    ds = {d.id: d for d in load_dataset_registry(DATASETS_YAML)}
    models = []
    for mid in payload.get("models", []):
        m = ms.get(mid)
        if m:
            models.append({"id": m.id, "repo": m.repo, "role": m.role, "framework": m.framework})
    datasets = []
    for did in payload.get("datasets", []):
        d = ds.get(did)
        if d:
            datasets.append({"id": d.id, "source": d.source, "repo": d.repo, "task": d.task})
    return {"agent": agent, "task": task, "models": models, "datasets": datasets}
