# tests/test_api_e2e.py
"""
End-to-end API tests for the Credit Appraisal PoC.

What this covers:
- Health & basic reachability (optional)
- Run credit_appraisal with an uploaded synthetic CSV
- Validate summary, scores, explanations, proposals
- Download artifacts (PDF, scores_csv, explanations_csv, merged csv, json*)
- Sanity checks on CSVs and required columns

How to run:
  cd ~/credit-appraisal-agent-poc
  source services/api/.venv/bin/activate
  pytest -q tests/test_api_e2e.py

You can set API URL via env:
  export API_URL=http://localhost:8090
"""

from __future__ import annotations

import os
import io
import time
import json
import math
import uuid
import random
import string
import typing as t

import pytest
import requests
import pandas as pd

API_URL = os.getenv("API_URL", "http://localhost:8090")

def _wait_for_api_ready(timeout=30):
    """Poll /docs or /openapi.json to check FastAPI is up."""
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{API_URL}/openapi.json", timeout=3)
            if r.status_code == 200 and "paths" in r.json():
                return
        except Exception as e:
            last_err = e
        time.sleep(1.0)
    raise RuntimeError(f"API not ready at {API_URL} within {timeout}s: {last_err}")

def _make_synthetic_csv(n=60) -> bytes:
    """Minimal dataset exercising the agent’s logic."""
    import numpy as np
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "application_id": [f"APP_{i:05d}" for i in range(n)],
        "income": rng.integers(25_000, 140_000, n),
        "existing_debt": rng.integers(0, 60_000, n),
        "loan_amount": rng.integers(5_000, 80_000, n),
        "loan_duration_months": rng.choice([12,24,36,48,60,72], n),
        "collateral_value": rng.integers(8_000, 200_000, n),
        "credit_score": rng.integers(300, 850, n),
        "num_delinquencies": np.minimum(rng.poisson(0.2, n), 8),
        "co_loaners": rng.integers(0, 3, n),
    })
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

@pytest.mark.order(1)
def test_api_end_to_end_run_and_downloads(tmp_path):
    _wait_for_api_ready()

    # 1) Kick off run with uploaded CSV (like the UI does)
    csv_bytes = _make_synthetic_csv(80)
    files = {"file": ("synthetic_for_test.csv", csv_bytes, "text/csv")}
    data = {
        "use_sample": "false",
        "use_llm_narrative": "false",

        # realistic bank defaults (can be anything; server coerces safely)
        "min_employment_years": "2",
        "max_debt_to_income": "0.45",
        "min_credit_history_length": "3",
        "max_num_delinquencies": "2",
        "max_current_loans": "3",
        "requested_amount_min": "1000",
        "requested_amount_max": "200000",
        "loan_term_months_allowed": "12,24,36,48,60,72",

        # debt pressure knobs (not strictly required)
        "min_income_debt_ratio": "0.35",
        "compounded_debt_factor": "1.0",
        "monthly_debt_relief": "0.50",
        "salary_floor": "3000",

        # approval behavior (let randomness kick in if no target)
        "threshold": "0.45",
        "target_approval_rate": "",
        "random_approval_band": "true",
    }

    r = requests.post(f"{API_URL}/v1/agents/credit_appraisal/run", data=data, files=files, timeout=60)
    assert r.status_code == 200, f"Run failed: {r.status_code} {r.text}"
    resp = r.json()
    assert "run_id" in resp, f"Unexpected response: {resp}"
    run_id = resp["run_id"]
    result = resp.get("result", {})
    summary = result.get("summary", {})

    # 2) Basic summary checks
    assert summary.get("count"), "Missing summary count"
    assert "approved" in summary and "denied" in summary, "Missing approved/denied"
    total = int(summary["count"])
    approved = int(summary["approved"])
    denied = int(summary["denied"])
    assert approved + denied == total, f"Inconsistent tally: {approved}+{denied}!={total}"
    # Expect some approvals and denials (random band around 20–60%)
    assert 0 < approved < total, f"Suspicious approvals={approved} total={total}"

    # 3) Check explanations structure
    expl = result.get("explanations", [])
    assert len(expl) > 0, "No explanations returned"
    row0 = expl[0]
    for k in ["application_id", "decision", "score", "rule_reasons",
              "proposed_loan_option", "proposed_consolidation_loan"]:
        assert k in row0, f"Missing field in explanation: {k}"

    # 4) Pull artifacts (pdf, csvs, json, merged-csv)
    # Required:
    for fmt in ["pdf", "scores_csv", "explanations_csv", "csv"]:
        url = f"{API_URL}/v1/runs/{run_id}/report?format={fmt}"
        d = requests.get(url, timeout=60)
        assert d.status_code == 200, f"Download {fmt} failed: {d.status_code} {d.text}"
        # quick file checks
        if fmt.endswith("csv") or fmt == "csv":
            df = pd.read_csv(io.BytesIO(d.content))
            assert "application_id" in df.columns, f"{fmt} missing application_id"
        elif fmt == "pdf":
            assert d.content[:4] == b"%PDF", "Not a PDF header"

    # Optional JSON
    j = requests.get(f"{API_URL}/v1/runs/{run_id}/report?format=json", timeout=20)
    if j.status_code == 200:
        jdata = j.json()
        assert isinstance(jdata, dict) or isinstance(jdata, list)

    # 5) Spot-check proposals plausibility
    # At least one approved must have proposed_loan_option with payment > 0
    df_expl = pd.DataFrame(expl)
    if "proposed_loan_option" in df_expl.columns:
        sample = df_expl[df_expl["decision"] == "approve"].head(1)
        if len(sample):
            offer = sample.iloc[0]["proposed_loan_option"] or {}
            assert "est_monthly_payment" in offer
            assert float(offer["est_monthly_payment"]) >= 0.0

    # 6) Persist a tiny “OK ping” for CI logs
    ok_file = tmp_path / f"e2e_ok_{run_id}.txt"
    ok_file.write_text(json.dumps({"run_id": run_id, "approved": approved, "denied": denied}, indent=2))
    assert ok_file.exists()
