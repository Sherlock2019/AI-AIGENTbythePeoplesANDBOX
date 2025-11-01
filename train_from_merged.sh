#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
# CONFIG (paths & API)
# ─────────────────────────────────────────────
ROOT="$HOME/credit-appraisal-agent-poc"
RUNS_ROOT="$ROOT/services/api/.runs"
TMP_FEEDBACK="$RUNS_ROOT/tmp_feedback"
API_URL="http://localhost:8090"

mkdir -p "$TMP_FEEDBACK" "$ROOT/.logs"

# ─────────────────────────────────────────────
# CLI FLAGS
#   --auto-balance       : if only one class is present, flip a small subset
#   --flip-frac <float>  : fraction to flip when auto-balancing (default 0.10)
#   --min-flip <int>     : minimum rows to flip (default 50)
# ─────────────────────────────────────────────
AUTO_BALANCE=False
FLIP_FRAC="0.10"
MIN_FLIP="50"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--auto-balance] [--flip-frac <0..1>] [--min-flip <int>]

Description:
  Trains a candidate model from the latest merged.csv, optionally auto-balancing
  if your dataset has only one class in the labels.

Options:
  --auto-balance        Enable synthetic balancing when only one class exists
  --flip-frac FLOAT     Fraction of rows to flip (default: ${FLIP_FRAC})
  --min-flip INT        Minimum number of rows to flip (default: ${MIN_FLIP})
  -h, --help            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto-balance) AUTO_BALANCE=True; shift ;;
    --flip-frac)    FLIP_FRAC="${2:-0.10}"; shift 2 ;;
    --min-flip)     MIN_FLIP="${2:-50}"; shift 2 ;;
    -h|--help)      usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

# ─────────────────────────────────────────────
# STEP 1 — Find latest merged.csv
# ─────────────────────────────────────────────
LATEST_MERGED=$(find "$RUNS_ROOT" -type f -name "merged.csv" -printf "%T@ %p\n" 2>/dev/null | sort -nr | head -n1 | awk '{print $2}')

if [[ -z "${LATEST_MERGED:-}" ]]; then
  echo "❌ No merged.csv found under $RUNS_ROOT"
  exit 1
fi
echo "📂 Latest merged.csv found: $LATEST_MERGED"

# ─────────────────────────────────────────────
# STEP 2 — Prepare a feedback CSV that:
#   - guarantees label column 'human_decision' exists
#   - optionally auto-balances if only one class
#   Output path: $TMP_FEEDBACK/merged_feedback.prepped.csv
# ─────────────────────────────────────────────
STAGED_FEEDBACK_RAW="$TMP_FEEDBACK/merged_feedback.csv"
STAGED_FEEDBACK_PREP="$TMP_FEEDBACK/merged_feedback.prepped.csv"

cp -f "$LATEST_MERGED" "$STAGED_FEEDBACK_RAW"

python3 - <<PY
import os, sys, json
import pandas as pd
import numpy as np
from pathlib import Path

raw_path = Path("$STAGED_FEEDBACK_RAW")
out_path = Path("$STAGED_FEEDBACK_PREP")
auto_balance = ${AUTO_BALANCE}
flip_frac = float("${FLIP_FRAC}")
min_flip = int("${MIN_FLIP}")

df = pd.read_csv(raw_path)

# 1) Ensure a usable label column
label_col = None
if "human_decision" in df.columns:
    label_col = "human_decision"
elif "decision" in df.columns:
    # derive a human_decision column from AI decision
    df["human_decision"] = df["decision"].astype(str).str.lower()
    label_col = "human_decision"
elif "label" in df.columns:
    # binary numeric labels; convert to human_decision for training API
    df["human_decision"] = df["label"].map({1:"approved", 0:"denied"})
    label_col = "human_decision"
elif "target" in df.columns:
    df["human_decision"] = df["target"].map({1:"approved", 0:"denied"})
    label_col = "human_decision"
else:
    sys.exit("❌ No label column (human_decision/decision/label/target) found in merged.csv")

df[label_col] = df[label_col].astype(str).str.lower().str.strip()

# 2) Check class distribution
vc = df[label_col].value_counts()
print("🔍 Label distribution before prep:")
print(vc)

if len(vc.index) < 2:
    if not auto_balance:
        sys.exit("❌ Only one class present. Re-run with --auto-balance to synthesize the missing class.")
    # Auto-balance: flip a small subset to create the missing class
    n = len(df)
    if n == 0:
        sys.exit("❌ merged.csv is empty")
    # decide which class is present and which is missing
    present = vc.index[0] if len(vc.index) else None
    missing = "approved" if present == "denied" else "denied"
    # rows eligible to flip: currently 'present'
    idx = df.index[df[label_col] == present].to_list()
    k = max(min_flip, int(len(idx) * flip_frac))
    k = min(k, len(idx))  # cap
    if k == 0:
        sys.exit("❌ Not enough rows to auto-balance")
    to_flip = np.random.default_rng(42).choice(idx, size=k, replace=False)
    df.loc[to_flip, label_col] = missing
    df.loc[to_flip, "synthetic_label"] = True
    # Optionally tag rule_reasons to mark synthetic
    if "rule_reasons" in df.columns:
        # Leave as-is (we don't require it for training); the model uses numeric features only
        pass
    print(f"✅ Auto-balanced: flipped {k} row(s) from '{present}' to '{missing}'.")

# 3) Persist prepped CSV
df.to_csv(out_path, index=False)
print(f"📦 Prepped feedback CSV: {out_path}")
PY

echo "📦 Staged (raw):   $STAGED_FEEDBACK_RAW"
echo "📦 Staged (prepped): $STAGED_FEEDBACK_PREP"

# ─────────────────────────────────────────────
# STEP 3 — Train candidate model
# ─────────────────────────────────────────────
echo "🚀 Training candidate model from prepped CSV..."
TRAIN_RESPONSE=$(curl -s -X POST "$API_URL/v1/training/train" \
  -H "Content-Type: application/json" \
  -d "{
    \"feedback_csvs\": [\"$STAGED_FEEDBACK_PREP\"],
    \"user_name\": \"dzoan nguyen\",
    \"agent_name\": \"credit_appraisal\",
    \"algo_name\": \"credit_lr\"
  }")

echo "📊 Train response:"
if command -v jq >/dev/null 2>&1; then
  echo "$TRAIN_RESPONSE" | jq .
else
  echo "$TRAIN_RESPONSE"
fi

MODEL_NAME=$(python3 - <<PY
import json,sys
data=json.loads('''$TRAIN_RESPONSE''')
print(data.get("model_name",""))
PY
)

if [[ -z "$MODEL_NAME" ]]; then
  echo "❌ Training failed."
  exit 1
fi

# ─────────────────────────────────────────────
# STEP 4 — Promote to production
# ─────────────────────────────────────────────
echo "📤 Promoting $MODEL_NAME to production..."
PROMOTE_RESPONSE=$(curl -s -X POST "$API_URL/v1/training/promote" \
  -H "Content-Type: application/json" \
  -d "{\"model_name\":\"$MODEL_NAME\"}")

if command -v jq >/dev/null 2>&1; then
  echo "$PROMOTE_RESPONSE" | jq .
else
  echo "$PROMOTE_RESPONSE"
fi

# ─────────────────────────────────────────────
# STEP 5 — Restart API (optional)
# ─────────────────────────────────────────────
echo "🔁 Restarting API..."
pkill -f "uvicorn services.api.main:app" || True
nohup uvicorn services.api.main:app --host 0.0.0.0 --port 8090 --reload >"$ROOT/.logs/api.log" 2>&1 &
sleep 2

# ─────────────────────────────────────────────
# STEP 6 — Verify production model
# ─────────────────────────────────────────────
echo "🧠 Production model verification:"
ls -lh "$ROOT/agents/credit_appraisal/models/production/" || True
echo "✅ Done."
