#!/usr/bin/env python3
# tests/test_api_reports.py
"""
Automated E2E tests for Credit + Asset Appraisal Agents & Reports API.
This script verifies:
  - /v1/agents/<agent>/run
  - /v1/runs/<agent>/<run_id>/report (json + csv)
  - /v1/runs/<agent>/list
"""

import os
import io
import json
import requests
import pandas as pd
from pprint import pprint

BASE_URL = os.getenv("API_URL", "http://localhost:8090")
TMP_DIR = "/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

AGENTS = ["credit_appraisal", "asset_appraisal"]

# ─────────────────────────────────────────────
# Helper — create tiny CSV for tests
# ─────────────────────────────────────────────
def make_test_csv(agent: str) -> str:
    if agent == "credit_appraisal":
        df = pd.DataFrame([
            {"customer_id": "C001", "income": 4000, "loan_amount": 2000, "credit_score": 720},
            {"customer_id": "C002", "income": 2500, "loan_amount": 1800, "credit_score": 610},
        ])
    else:
        df = pd.DataFrame([
            {"asset_id": "A001", "asset_type": "House", "base_value_hint": 150000, "requested_amount": 90000},
            {"asset_id": "A002", "asset_type": "Car", "base_value_hint": 30000, "requested_amount": 25000},
        ])
    path = os.path.join(TMP_DIR, f"test_{agent}.csv")
    df.to_csv(path, index=False)
    return path


# ─────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────
def test_agent(agent: str):
    print(f"\n🧩 Testing agent: {agent}")
    csv_path = make_test_csv(agent)
    files = {"file": open(csv_path, "rb")}

    # 1️⃣ Run the agent
    print(f"→ Running {agent}...")
    r = requests.post(f"{BASE_URL}/v1/agents/{agent}/run", files=files, timeout=120)
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        return
    data = r.json()
    pprint(data)
    run_id = data.get("run_id")
    if not run_id:
        print("❌ No run_id returned")
        return

    # 2️⃣ Fetch JSON report
    print(f"→ Fetching JSON report for {run_id}...")
    r_json = requests.get(f"{BASE_URL}/v1/runs/{agent}/{run_id}/report?format=json")
    print(f"Status: {r_json.status_code}")
    if r_json.ok:
        pprint(r_json.json())
    else:
        print(r_json.text)

    # 3️⃣ Fetch CSV report
    print(f"→ Fetching CSV report for {run_id}...")
    r_csv = requests.get(f"{BASE_URL}/v1/runs/{agent}/{run_id}/report?format=csv")
    print(f"Status: {r_csv.status_code}")
    if r_csv.ok:
        out_path = os.path.join(TMP_DIR, f"{agent}_{run_id}.csv")
        with open(out_path, "wb") as f:
            f.write(r_csv.content)
        print(f"✅ CSV downloaded: {out_path}")
    else:
        print(r_csv.text)

    # 4️⃣ List runs
    print(f"→ Listing all runs for {agent}...")
    r_list = requests.get(f"{BASE_URL}/v1/runs/{agent}/list")
    print(f"Status: {r_list.status_code}")
    pprint(r_list.json())


# ─────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print(f"🔍 Testing API base: {BASE_URL}")
    for ag in AGENTS:
        try:
            test_agent(ag)
        except Exception as e:
            print(f"❌ Exception during {ag} test: {e}")
