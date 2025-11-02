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
