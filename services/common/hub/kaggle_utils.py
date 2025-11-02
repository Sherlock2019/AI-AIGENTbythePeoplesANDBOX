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
