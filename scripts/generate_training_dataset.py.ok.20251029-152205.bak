#!/usr/bin/env python3
import argparse, os, uuid
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path.home() / "credit-appraisal-agent-poc"
OUT_DIR = ROOT / "agents" / "credit_appraisal" / "sample_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def gen_row(good: bool, rng: np.random.Generator) -> dict:
    income = float(max(1500, rng.normal(4000 if good else 2500, 1000)))
    loan = float(max(1000, rng.normal(12000 if good else 18000, 6000)))
    dur = int(np.clip(int(rng.normal(36, 12)), 6, 84))
    existing = float(max(0, rng.normal(400 if good else 900, 400)))
    credit = int(np.clip(int(rng.normal(700 if good else 600, 70)), 300, 850))
    dti = float(np.clip((existing + loan/max(dur/12,1))/max(income,1), 0.02, 1.2))
    collat = float(max(3000, loan * (1.2 if good else 0.7)))
    return {
        "application_id": f"app_{uuid.uuid4().hex[:8]}",
        "income": round(income, 2),
        "loan_amount": round(loan, 2),
        "loan_duration_months": dur,
        "existing_debt": round(existing, 2),
        "credit_score": credit,
        "collateral_value": round(collat, 2),
        "DTI": round(dti, 3),
        "__label": 1 if good else 0,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1000)
    ap.add_argument("--target-approval", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    rows = []
    approvals = 0
    for i in range(args.rows):
        want_good = (approvals / max(1, len(rows))) < args.target_approval
        r = gen_row(want_good, rng)
        rows.append(r)
        approvals += r["__label"]

    df = pd.DataFrame(rows)
    out_path = OUT_DIR / f"credit_training_synthetic_{args.rows}_{int(args.target_approval*100)}pct.csv"
    df.to_csv(out_path, index=False)
    ratio = float(df["__label"].mean())
    print(f"✅ Generated: {out_path}")
    print(f"ℹ️ Observed approval ratio: {ratio:.3f}")

if __name__ == "__main__":
    main()
