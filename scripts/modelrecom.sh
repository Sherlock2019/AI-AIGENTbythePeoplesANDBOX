#!/usr/bin/env bash
set -euo pipefail

ROOT="$(pwd)"
CONFIG_DIR="$ROOT/config"
API_ROUTERS_DIR="$ROOT/services/api/routers"
UI_COMPONENTS_DIR="$ROOT/services/ui/components"
MAIN_PY="$ROOT/services/api/main.py"

echo "==> Patching registries with recommendations…"
# Append (or create) recommendations into model/dataset registries
# Safe append: if block exists, we overwrite the tail.

# --- model_registry.yaml: add 'recommendations' matrix ---
python - "$CONFIG_DIR/model_registry.yaml" <<'PY'
import sys, yaml, os
p = sys.argv[1]
data = {}
if os.path.exists(p):
    with open(p,'r',encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

data.setdefault('recommendations', {})
rec = data['recommendations']

# Credit Appraisal recommendations
rec['credit_appraisal'] = {
  'scoring_tabular':    {'models': ['credit:lr-baseline'], 'datasets': ['loan:synthetic','kaggle:credit_risk']},
  'narratives_llm':     {'models': ['phi3:3.8b','mistral:7b-instruct'], 'datasets': []},
  'explain_rerank':     {'models': ['mistral:7b-instruct'], 'datasets': []}
}

# Asset Appraisal recommendations
rec['asset_appraisal'] = {
  'valuation_tabular':  {'models': ['credit:lr-baseline'], 'datasets': ['loan:synthetic']},
  'evidence_ocr':       {'models': [], 'datasets': []},  # plug your OCR later (e.g., doctr/textract)
  'vision_compare':     {'models': [], 'datasets': []},
  'narratives_llm':     {'models': ['phi3:3.8b','mistral:7b-instruct'], 'datasets': []}
}

with open(p,'w',encoding='utf-8') as f:
    yaml.safe_dump(data, f, sort_keys=False)
print("model_registry.yaml updated")
PY

# --- dataset_registry.yaml: (no change required; already referenced by id) ---
echo "dataset_registry.yaml already has ids referenced; nothing to change."

echo "==> Adding recommendations router…"
cat > "$API_ROUTERS_DIR/hub_reco.py" <<'PY'
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
PY

# Patch main.py once
grep -q "hub_reco" "$MAIN_PY" || cat >> "$MAIN_PY" <<'PY'

# === Auto-added by setup_hub_reco_patch.sh ===
try:
    from services.api.routers import hub_reco
    try:
        app  # reuse if exists
    except NameError:
        from fastapi import FastAPI
        app = FastAPI()
    app.include_router(hub_reco.router)
except Exception:
    pass
# === End auto-added ===
PY

echo "==> Updating Hub UI to show recommendations…"
cat > "$UI_COMPONENTS_DIR/hub_panel_reco.py" <<'PY'
import streamlit as st, requests, json

def show_recommended_panel(api_url: str, agent_id: str, task_id: str, key_prefix: str="reco"):
    st.markdown(f"**Recommended for**: `{agent_id}` · `{task_id}`")
    try:
        r = requests.get(f"{api_url}/v1/hub/recommendations/for", params={"agent": agent_id, "task": task_id}, timeout=10)
        r.raise_for_status()
        payload = r.json()
        models = payload.get("models", [])
        datasets = payload.get("datasets", [])
        c1, c2 = st.columns(2)

        with c1:
            st.caption("Models")
            if not models:
                st.write("—")
            for m in models:
                bid = f"{key_prefix}_ensure_model_{m['id']}"
                st.write(f"- `{m['id']}` · {m['framework']} · {m['repo']}")
                if st.button(f"Ensure {m['id']}", key=bid):
                    rr = requests.post(f"{api_url}/v1/hub/models/ensure", json={"model_id": m["id"]}, timeout=600)
                    st.success(f"Ensured {m['id']}")
                    st.json(rr.json())

        with c2:
            st.caption("Datasets")
            if not datasets:
                st.write("—")
            for d in datasets:
                bid = f"{key_prefix}_ensure_ds_{d['id']}"
                st.write(f"- `{d['id']}` · {d['source']} · {d['repo']}")
                if st.button(f"Ensure {d['id']}", key=bid):
                    rr = requests.post(f"{api_url}/v1/hub/datasets/ensure", json={"dataset_id": d["id"]}, timeout=900)
                    st.success(f"Ensured {d['id']}")
                    st.json(rr.json())
PY

echo "✅ Patch complete."
echo
echo "Next steps:"
echo "1) Restart API: uvicorn services.api.main:app --reload --port 8090"
echo "2) In Streamlit (Asset Stage 3), add:"
echo "     from services.ui.components.hub_panel_reco import show_recommended_panel"
echo "     show_recommended_panel(API_URL, agent_id='asset_appraisal', task_id='valuation_tabular', key_prefix='asset_val')"
echo "3) In Streamlit (Credit Stage 3), add:"
echo "     show_recommended_panel(API_URL, agent_id='credit_appraisal', task_id='scoring_tabular', key_prefix='credit_score')"
