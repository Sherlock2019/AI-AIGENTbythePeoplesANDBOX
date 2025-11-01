# services/train/train_credit.py
import os, json, argparse, hashlib, joblib
import pandas as pd, numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, balanced_accuracy_score
from sklearn.ensemble import GradientBoostingClassifier

ROOT = os.path.expanduser("~/credit-appraisal-agent-poc")
RUNS_DIR = os.path.join(ROOT, "services", "api", ".runs")
FEEDBACK_DIR = os.path.join(RUNS_DIR, "feedback")
TRAIN_DIR = os.path.join(RUNS_DIR, "train")
MODELS_DIR = os.path.join(ROOT, "models", "credit")

def _read_many_csv(paths: list[str]) -> pd.DataFrame:
    frames = []
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            try:
                frames.append(pd.read_csv(p))
            except Exception:
                pass
    if not frames:
        raise RuntimeError("No input CSV found.")
    return pd.concat(frames, ignore_index=True)

def build_training_frame(base_csvs: list[str], cutoff_date: str | None) -> tuple[pd.DataFrame, list[str]]:
    base = _read_many_csv(base_csvs).drop_duplicates("application_id")
    # optional cutoff: tolerate when base lacks timestamp
    if cutoff_date and "timestamp_utc" in base.columns:
        base = base[base["timestamp_utc"] >= cutoff_date]

    # fold in feedback (last write wins)
    fb_frames = []
    if os.path.isdir(FEEDBACK_DIR):
        for f in os.listdir(FEEDBACK_DIR):
            if f.endswith(".csv"):
                fb_frames.append(pd.read_csv(os.path.join(FEEDBACK_DIR, f)))
    fb = pd.concat(fb_frames, ignore_index=True) if fb_frames else pd.DataFrame(columns=["application_id"])
    if not fb.empty:
        fb = fb.sort_values("timestamp_utc").drop_duplicates("application_id", keep="last")

    feat_cols_fb = [c for c in fb.columns if c.startswith("feature_")]
    cols_for_merge = ["application_id","y_true"] + feat_cols_fb if "y_true" in fb.columns else ["application_id"] + feat_cols_fb
    merged = base.merge(fb[cols_for_merge] if not fb.empty else base[["application_id"]], on="application_id", how="left")

    # apply corrected features where present
    for c in feat_cols_fb:
        base_col = c.replace("feature_", "")
        if base_col in merged.columns:
            merged[base_col] = merged[c].combine_first(merged[base_col])

    # build label
    if "y_true" not in merged.columns:
        raise RuntimeError("No labels in feedback yet. Append feedback rows first.")
    y = merged["y_true"].replace({-1: np.nan})
    df = merged[~y.isna()].copy()
    df["y"] = y.dropna().astype(int)

    # choose numeric features (exclude IDs/meta/leakage-y columns)
    ignore = {"application_id","y","y_true","timestamp","timestamp_utc","reviewer_id","notes",
              "reason_codes","model_version_at_score","source_run_id","dataset_hash_at_score"}
    feat_cols = [c for c in df.columns if c not in ignore and pd.api.types.is_numeric_dtype(df[c])]
    return df, feat_cols

def train_and_persist(df: pd.DataFrame, feat_cols: list[str], job_id: str):
    X, y = df[feat_cols], df["y"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    clf = GradientBoostingClassifier()
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:,1]
    preds = (proba >= 0.5).astype(int)

    metrics = {
        "auc": float(roc_auc_score(yte, proba)),
        "f1": float(f1_score(yte, preds)),
        "bal_acc": float(balanced_accuracy_score(yte, preds)),
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
        "features": feat_cols,
    }

    # version dir
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    ds_hash = hashlib.md5(pd.util.hash_pandas_object(df[feat_cols+['y']], index=False).values).hexdigest()[:8]
    version_dir = os.path.join(MODELS_DIR, f"{stamp}__{ds_hash}")
    os.makedirs(version_dir, exist_ok=True)

    # persist
    joblib.dump(clf, os.path.join(version_dir, "model.pkl"))
    with open(os.path.join(version_dir, "feature_columns.json"), "w") as f:
        json.dump(feat_cols, f)
    with open(os.path.join(version_dir, "training_report.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    # update "current" symlink (best effort)
    os.makedirs(MODELS_DIR, exist_ok=True)
    link = os.path.join(MODELS_DIR, "current")
    try:
        if os.path.islink(link) or os.path.exists(link):
            os.remove(link)
        os.symlink(os.path.relpath(version_dir, MODELS_DIR), link)
    except Exception:
        pass

    # write status for API
    os.makedirs(TRAIN_DIR, exist_ok=True)
    with open(os.path.join(TRAIN_DIR, f"{job_id}.metrics.json"), "w") as f:
        json.dump({"version_dir": version_dir, **metrics}, f, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = json.load(open(args.config))

    base_csvs = cfg.get("base_csv_globs", [os.path.join(RUNS_DIR, "latest", "results.csv")])
    cutoff = cfg.get("cutoff_date")  # e.g., "2024-01-01"

    print(f"[train] job={args.job} cutoff={cutoff} base={base_csvs}")
    df, feat_cols = build_training_frame(base_csvs, cutoff)
    print(f"[train] rows={len(df)} features={len(feat_cols)}")
    train_and_persist(df, feat_cols, args.job)
    print("[train] done")

if __name__ == "__main__":
    main()

