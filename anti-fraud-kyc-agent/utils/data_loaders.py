import pandas as pd, os, subprocess
from datasets import load_dataset

def load_hf_dataset_as_df(repo_id):
    ds = load_dataset(repo_id)
    split = next(iter(ds.keys()))
    return ds[split].to_pandas()

def download_kaggle_dataset(ref, dest):
    os.makedirs(dest, exist_ok=True)
    cmd = ["kaggle", "datasets", "download", "-d", ref, "-p", dest, "--unzip"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    for f in os.listdir(dest):
        if f.endswith(".csv"):
            return os.path.join(dest, f)
    raise FileNotFoundError("No CSV found")
