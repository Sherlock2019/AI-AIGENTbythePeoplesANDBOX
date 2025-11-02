#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# Helper: pause between stages
# ─────────────────────────────────────────────────────────────
pause() {
  echo
  read -r -p "⏸  Press [Enter] to continue…"
  echo
}

# ─────────────────────────────────────────────────────────────
# Stage 0 — Sanity & paths
# ─────────────────────────────────────────────────────────────
ROOT="$(pwd)"
API_DIR="$ROOT/services/api"
API_ROUTERS_DIR="$API_DIR/routers"
COMMON_DIR="$ROOT/services/common/hub"
CONFIG_DIR="$ROOT/config"
UI_DIR="$ROOT/services/ui"
UI_COMPONENTS_DIR="$UI_DIR/components"
REQ_FILE="$ROOT/requirements.txt"
ENV_EXAMPLE="$ROOT/.env.example"
MAIN_PY="$API_DIR/main.py"

echo "==> Repo root: $ROOT"

mkdir -p "$API_ROUTERS_DIR" "$COMMON_DIR" "$CONFIG_DIR" "$UI_COMPONENTS_DIR"

echo "==> Created directories:"
echo "    - $API_ROUTERS_DIR"
echo "    - $COMMON_DIR"
echo "    - $CONFIG_DIR"
echo "    - $UI_COMPONENTS_DIR"
pause

# ─────────────────────────────────────────────────────────────
# Stage 1 — requirements.txt (append if missing)
# ─────────────────────────────────────────────────────────────
echo "==> Updating requirements.txt"
touch "$REQ_FILE"
add_req() {
  local pkg="$1"
  grep -qiE "^${pkg%%=*}([=><].*)?$" "$REQ_FILE" || echo "$pkg" >> "$REQ_FILE"
}
add_req "huggingface_hub>=0.24"
add_req "datasets>=2.19"
add_req "kaggle>=1.6"
add_req "fastapi>=0.111"
add_req "uvicorn>=0.30"
add_req "pydantic>=2"
add_req "tqdm"
add_req "python-dotenv"

echo "==> requirements.txt updated."
pause

# ─────────────────────────────────────────────────────────────
# Stage 2 — config registries (YAML)
# ─────────────────────────────────────────────────────────────
echo "==> Writing config/model_registry.yaml"
cat > "$CONFIG_DIR/model_registry.yaml" <<'YAML'
defaults:
  cache_dir: ${AIGENT_CACHE}/models

models:
  - id: "phi3:3.8b"
    repo: "microsoft/Phi-3-mini-4k-instruct"
    revision: "main"
    role: "instruct_llm"
    framework: "transformers"
    files: ["config.json","model.safetensors","tokenizer.json","tokenizer_config.json"]

  - id: "mistral:7b-instruct"
    repo: "mistralai/Mistral-7B-Instruct-v0.3"
    revision: "main"
    role: "instruct_llm"
    framework: "transformers"
    files: ["config.json","model.safetensors","tokenizer.json","tokenizer_config.json"]

  - id: "credit:lr-baseline"
    repo: "Sherlock2019/credit-lr-baseline"
    revision: "main"
    role: "tabular_model"
    framework: "joblib"
    files: ["model.joblib","meta.json"]
YAML

echo "==> Writing config/dataset_registry.yaml"
cat > "$CONFIG_DIR/dataset_registry.yaml" <<'YAML'
defaults:
  cache_dir: ${AIGENT_CACHE}/datasets

datasets:
  - id: "loan:synthetic"
    source: "hf"
    repo: "Sherlock2019/loan-synthetic"
    subset: null
    split: "train"
    task: "credit_appraisal"
    format: "parquet|csv"

  - id: "kaggle:credit_risk"
    source: "kaggle"
    repo: "mlg-ulb/creditcardfraud"
    task: "risk_detection"
    format: "csv"
    files: ["creditcard.csv"]
YAML
echo "==> Registries written."
pause

# ─────────────────────────────────────────────────────────────
# Stage 3 — common hub utils (registry, hf, kaggle)
# ─────────────────────────────────────────────────────────────
echo "==> Writing services/common/hub/registry.py"
cat > "$COMMON_DIR/registry.py" <<'PY'
import os, yaml
from dataclasses import dataclass
from typing import List, Optional

def _env_expand(v: str):
    if not isinstance(v, str): return v
    return os.path.expandvars(os.path.expanduser(v))

@dataclass
class ModelEntry:
    id: str
    repo: str
    revision: str
    role: str
    framework: str
    files: List[str]
    cache_dir: str

@dataclass
class DatasetEntry:
    id: str
    source: str
    repo: str
    task: str
    format: str
    split: Optional[str] = None
    subset: Optional[str] = None
    files: Optional[List[str]] = None
    cache_dir: Optional[str] = None

def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_model_registry(path: str) -> List[ModelEntry]:
    cfg = _load_yaml(path)
    default_cache = _env_expand(cfg.get("defaults", {}).get("cache_dir", "./.cache/models"))
    out = []
    for m in cfg.get("models", []):
        out.append(ModelEntry(
            id=m["id"],
            repo=m["repo"],
            revision=m.get("revision","main"),
            role=m.get("role","generic"),
            framework=m.get("framework","transformers"),
            files=m.get("files",[]),
            cache_dir=_env_expand(m.get("cache_dir", default_cache)),
        ))
    return out

def load_dataset_registry(path: str) -> List[DatasetEntry]:
    cfg = _load_yaml(path)
    default_cache = _env_expand(cfg.get("defaults", {}).get("cache_dir", "./.cache/datasets"))
    out = []
    for d in cfg.get("datasets", []):
        out.append(DatasetEntry(
            id=d["id"],
            source=d["source"],
            repo=d["repo"],
            task=d.get("task","generic"),
            format=d.get("format",""),
            split=d.get("split"),
            subset=d.get("subset"),
            files=d.get("files"),
            cache_dir=_env_expand(d.get("cache_dir", default_cache)),
        ))
    return out
PY

echo "==> Writing services/common/hub/hf_utils.py"
cat > "$COMMON_DIR/hf_utils.py" <<'PY'
import os, shutil
from typing import Dict, List
from huggingface_hub import hf_hub_download, login

HF_TOKEN = os.getenv("HF_TOKEN")
HF_HOME = os.getenv("HF_HOME")
HF_HUB_CACHE = os.getenv("HF_HUB_CACHE")

def hf_login_if_needed():
    if HF_TOKEN:
        try:
            login(HF_TOKEN)
        except Exception:
            pass

def ensure_model_files(repo: str, files: List[str], revision: str="main", cache_dir: str="./.cache/models") -> Dict[str,str]:
    """
    Download specific model files into cache_dir/<safe_repo> and return local paths.
    """
    os.makedirs(cache_dir, exist_ok=True)
    hf_login_if_needed()
    safe = repo.replace("/", "__")
    local_dir = os.path.join(cache_dir, safe)
    os.makedirs(local_dir, exist_ok=True)

    paths = {}
    for fname in files:
        p = hf_hub_download(repo_id=repo, filename=fname, revision=revision, cache_dir=HF_HUB_CACHE or HF_HOME)
        dst = os.path.join(local_dir, os.path.basename(fname))
        if not os.path.exists(dst):
            try:
                shutil.copy2(p, dst)
            except Exception:
                pass
        paths[fname] = dst
    return paths
PY

echo "==> Writing services/common/hub/kaggle_utils.py"
cat > "$COMMON_DIR/kaggle_utils.py" <<'PY'
import os, pathlib, subprocess, json
from typing import List, Dict

KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME")
KAGGLE_KEY = os.getenv("KAGGLE_KEY")
KAGGLE_CONFIG_DIR = os.getenv("KAGGLE_CONFIG_DIR", os.path.expanduser("~/.kaggle"))

def ensure_kaggle_credentials():
    """
    Support either env vars or ~/.kaggle/kaggle.json
    """
    os.makedirs(KAGGLE_CONFIG_DIR, exist_ok=True)
    cred_path = os.path.join(KAGGLE_CONFIG_DIR, "kaggle.json")
    if KAGGLE_USERNAME and KAGGLE_KEY:
        payload = {"username": KAGGLE_USERNAME, "key": KAGGLE_KEY}
        with open(cred_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.chmod(cred_path, 0o600)
    if not os.path.exists(cred_path):
        raise RuntimeError("Kaggle credentials missing. Set env vars or place kaggle.json at: " + cred_path)

def kaggle_download(owner_repo: str, files: List[str] | None, out_dir: str) -> Dict[str, str]:
    """
    Downloads a Kaggle dataset (or specific files) into out_dir using Kaggle CLI.
    """
    ensure_kaggle_credentials()
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)

    # Download entire dataset then filter
    cmd = ["kaggle","datasets","download","-d",owner_repo,"-p",out_dir,"--unzip"]
    subprocess.run(cmd, check=True)

    if not files:
        return {f: os.path.join(out_dir, f) for f in os.listdir(out_dir)}

    paths = {}
    for f in files:
        p = os.path.join(out_dir, f)
        if not os.path.exists(p):
            cand = [os.path.join(out_dir, x) for x in os.listdir(out_dir) if x.endswith(os.path.basename(f))]
            if cand: p = cand[0]
        if not os.path.exists(p):
            raise FileNotFoundError(f"Expected Kaggle file not found: {f}")
        paths[f] = p
    return paths
PY

echo "==> Common hub utils written."
pause

# ─────────────────────────────────────────────────────────────
# Stage 4 — API routers (models + datasets) and patch main.py
# ─────────────────────────────────────────────────────────────
echo "==> Writing services/api/routers/hub_models.py"
cat > "$API_ROUTERS_DIR/hub_models.py" <<'PY'
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
PY

echo "==> Writing services/api/routers/hub_datasets.py"
cat > "$API_ROUTERS_DIR/hub_datasets.py" <<'PY'
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
PY

# Patch services/api/main.py to include the routers (safe append)
echo "==> Patching $MAIN_PY to include hub routers (if not already)."
touch "$MAIN_PY"
grep -q "hub_models" "$MAIN_PY" || cat >> "$MAIN_PY" <<'PY'

# === Auto-added by setup_hub.sh ===
try:
    from fastapi import FastAPI
    from services.api.routers import hub_models, hub_datasets
    try:
        app  # if already defined, reuse
    except NameError:
        app = FastAPI()
    app.include_router(hub_models.router)
    app.include_router(hub_datasets.router)
except Exception as _e:
    # Keep main import-safe even when dev structure differs
    pass
# === End auto-added ===
PY

echo "==> API routers ready."
pause

# ─────────────────────────────────────────────────────────────
# Stage 5 — .env.example (tokens, cache)
# ─────────────────────────────────────────────────────────────
echo "==> Writing .env.example additions"
touch "$ENV_EXAMPLE"
cat >> "$ENV_EXAMPLE" <<'ENV'

# === HF / Kaggle / Cache (added by setup_hub.sh) ===
HF_TOKEN=
HF_HOME=$HOME/.cache/hf
HF_HUB_CACHE=$HOME/.cache/hf/hub

KAGGLE_USERNAME=
KAGGLE_KEY=
KAGGLE_CONFIG_DIR=$HOME/.kaggle

AIGENT_CACHE=$HOME/.cache/aigent

# Registry override (optional)
MODEL_REGISTRY=config/model_registry.yaml
DATASET_REGISTRY=config/dataset_registry.yaml
ENV
echo "==> .env.example updated."
pause

# ─────────────────────────────────────────────────────────────
# Stage 6 — Streamlit Hub panel (reusable)
# ─────────────────────────────────────────────────────────────
echo "==> Writing services/ui/components/hub_panel.py"
cat > "$UI_COMPONENTS_DIR/hub_panel.py" <<'PY'
import streamlit as st, requests

def show_hub_panel(api_url: str, expanded: bool=False, key_prefix: str="hub"):
    with st.expander("📦 Models & Datasets Hub", expanded=expanded):
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Hugging Face Models**")
            try:
                r = requests.get(f"{api_url}/v1/hub/models/list", timeout=10)
                models = r.json()
                model_ids = [m["id"] for m in models]
                mdl = st.selectbox("Select model", model_ids, key=f"{key_prefix}_model_sel")
                if st.button("Ensure model locally", key=f"{key_prefix}_ensure_model"):
                    r2 = requests.post(f"{api_url}/v1/hub/models/ensure", json={"model_id": mdl}, timeout=300)
                    st.success("Model ready")
                    st.json(r2.json())
            except Exception as e:
                st.error(f"Hub models error: {e}")

        with c2:
            st.markdown("**Datasets (HF & Kaggle)**")
            try:
                r = requests.get(f"{api_url}/v1/hub/datasets/list", timeout=10)
                dsets = r.json()
                ds_ids = [d["id"] for d in dsets]
                dsid = st.selectbox("Select dataset", ds_ids, key=f"{key_prefix}_dataset_sel")
                if st.button("Ensure dataset locally", key=f"{key_prefix}_ensure_dataset"):
                    r2 = requests.post(f"{api_url}/v1/hub/datasets/ensure", json={"dataset_id": dsid}, timeout=600)
                    st.success("Dataset ready")
                    st.json(r2.json())
            except Exception as e:
                st.error(f"Hub datasets error: {e}")
PY

echo "==> Hub UI panel ready."
echo "   To use in any Streamlit page:"
echo "     from services.ui.components.hub_panel import show_hub_panel"
echo "     show_hub_panel(API_URL, expanded=False, key_prefix='credit_hub')"
pause

# ─────────────────────────────────────────────────────────────
# Stage 7 — Offer to install requirements
# ─────────────────────────────────────────────────────────────
echo "==> Done writing files."
read -r -p "💡 Install/upgrade requirements in current Python env? [y/N] " ans
if [[ "${ans,,}" == "y" ]]; then
  pip install -U -r "$REQ_FILE"
  echo "✅ requirements installed."
else
  echo "ℹ️ Skipped pip install."
fi

echo
echo "🎉 All set!"
echo "• Start/Restart your API so the new routers mount:"
echo "    uvicorn services.api.main:app --reload --port 8090"
echo "• In your Streamlit pages (Credit/Asset), add:"
echo "    from services.ui.components.hub_panel import show_hub_panel"
echo "    show_hub_panel(API_URL, expanded=False, key_prefix='asset_hub')"
echo
