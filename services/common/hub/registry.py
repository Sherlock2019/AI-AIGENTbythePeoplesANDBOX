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
