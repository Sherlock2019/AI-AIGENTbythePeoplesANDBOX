# services/api/routers/decision.py
# ─────────────────────────────────────────────
# 🤖 Decision Orchestrator — Unified Loan Recommendation
# Combines Credit + Asset Appraisal outputs into one decision.
# ─────────────────────────────────────────────
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests, os, datetime

router = APIRouter(prefix="/v1/agents/decision", tags=["loan_decision"])

CREDIT_API = os.getenv("CREDIT_API_URL", "http://localhost:8090/v1/agents/credit_appraisal/run")
ASSET_API = os.getenv("ASSET_API_URL", "http://localhost:8090/v1/agents/asset_appraisal/run")

# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class LoanApplication(BaseModel):
    applicant_name: str
    income: float
    loan_amount: float
    asset_description: str
    asset_declared_value: float

# ─────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────
@router.post("/evaluate")
def evaluate_application(data: LoanApplication):
    """Run both Credit and Asset Appraisal Agents and return unified recommendation."""

    # 1️⃣ Run Asset Appraisal Agent
    try:
        asset_resp = requests.post(
            ASSET_API,
            json={
                "description": data.asset_description,
                "declared_value": data.asset_declared_value,
                "owner": data.applicant_name
            },
            timeout=60
        )
        asset = asset_resp.json().get("result", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Asset appraisal failed: {e}")

    # 2️⃣ Run Credit Appraisal Agent
    try:
        credit_resp = requests.post(
            CREDIT_API,
            json={
                "applicant_name": data.applicant_name,
                "income": data.income,
                "loan_amount": data.loan_amount,
                "collateral_verified_value": asset.get("estimated_value", 0),
                "legal_verified": asset.get("legal_verified", False),
                "fraud_flag": asset.get("fraud_flag", False)
            },
            timeout=60
        )
        credit = credit_resp.json().get("result", {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Credit appraisal failed: {e}")

    # 3️⃣ Combine Results — Simple Weighted Logic
    asset_score = asset.get("valuation_confidence", 0.8)
    credit_score = credit.get("approval_score", 0.7) if credit else 0.7

    fraud_flag = asset.get("fraud_flag", False)
    legal_verified = asset.get("legal_verified", False)

    combined_score = round((asset_score * 0.4 + credit_score * 0.6), 3)
    decision = "✅ APPROVE"
    reason = "Meets eligibility and collateral confidence threshold."

    if fraud_flag:
        decision = "❌ REJECT"
        reason = "Fraud indicators present in asset verification."
    elif not legal_verified:
        decision = "🟡 REVERIFY"
        reason = "Collateral ownership unverified."

    elif combined_score < 0.65:
        decision = "🟡 REVERIFY"
        reason = "Low combined confidence score."

    # 4️⃣ Final Unified Output
    result = {
        "applicant_name": data.applicant_name,
        "loan_amount": data.loan_amount,
        "combined_score": combined_score,
        "credit_score": credit_score,
        "asset_score": asset_score,
        "fraud_flag": fraud_flag,
        "legal_verified": legal_verified,
        "decision": decision,
        "reason": reason,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "asset_summary": asset,
        "credit_summary": credit
    }

    return {"status": "success", "result": result}
