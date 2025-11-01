# services/api/routers/system.py
from __future__ import annotations
import os, json, time
from typing import List, Dict, Any
from fastapi import APIRouter

router = APIRouter(tags=["system"])

ROOT = os.path.expanduser("~/credit-appraisal-agent-poc")
MODELS_DIR = os.path.join(ROOT, "agents", "credit_appraisal", "models")
PROD_DIR = os.path.join(MODELS_DIR, "production")
TRAINED_DIR = os.path.join(MODELS_DIR, "trained")

def _ls_joblib(dirpath: str, kind: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(dirpath):
        return out
    for fn in os.listdir(dirpath):
        if not fn.endswith(".joblib"):
            continue
        path = os.path.join(dirpath, fn)
        st = os.stat(path)
        out.append({
            "id": f"{kind}:{fn}",
            "kind": kind,
            "filename": fn,
            "path": path,
            "size": st.st_size,
            "mtime": st.st_mtime,
            "mtime_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        })
    return sorted(out, key=lambda x: x["mtime"], reverse=True)

@router.get("/v1/system/models")
def list_models() -> Dict[str, Any]:
    items = _ls_joblib(PROD_DIR, "production") + _ls_joblib(TRAINED_DIR, "trained")
    # Optionally read meta.json to highlight active production model
    active = None
    meta_path = os.path.join(PROD_DIR, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            active = meta.get("active_model")
        except Exception:
            pass
    return {"items": items, "active_model_path": active}
