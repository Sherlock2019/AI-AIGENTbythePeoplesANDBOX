"""Unified Risk Orchestration API router."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

RUNS_DIR = Path(__file__).resolve().parent.parent / ".runs" / "unified"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


class AssetSection(BaseModel):
    fmv: float = Field(..., description="Fair market value from asset agent")
    ai_adjusted: float = Field(..., description="AI adjusted valuation")
    realizable_value: float = Field(..., description="Estimated realizable value")
    encumbrance_flags: List[str] = []


class FraudSection(BaseModel):
    risk_score: float = Field(..., ge=0, le=1)
    risk_tier: str
    sanction_hits: List[str] = []
    kyc_passed: bool = True


class CreditSection(BaseModel):
    credit_score: int = Field(..., ge=0, le=900)
    probability_default: float = Field(..., ge=0, le=1)
    approval: str = Field(..., description="approve/review/reject")
    ndi: Optional[float] = None


class UnifiedRequest(BaseModel):
    borrower_id: str
    loan_id: Optional[str] = None
    asset: AssetSection
    fraud: FraudSection
    credit: CreditSection
    metadata: Dict[str, str] = {}


router = APIRouter(prefix="/v1/unified", tags=["unified"])


def _compute_risk(asset: AssetSection, fraud: FraudSection, credit: CreditSection) -> Dict[str, str]:
    score_components = []
    overall = 0.0

    collateral_ratio = asset.realizable_value / max(asset.ai_adjusted, 1e-6)
    score_components.append(("collateral_ratio", collateral_ratio))
    overall += min(collateral_ratio, 1.2)

    fraud_component = 1 - fraud.risk_score
    score_components.append(("fraud_safety", fraud_component))
    overall += fraud_component

    credit_component = 1 - credit.probability_default
    score_components.append(("credit_health", credit_component))
    overall += credit_component

    normalized = overall / len(score_components)
    if normalized >= 0.8:
        tier = "low"
    elif normalized >= 0.55:
        tier = "medium"
    else:
        tier = "high"

    recommendation = "approve"
    if fraud.risk_score >= 0.6 or credit.probability_default >= 0.35:
        recommendation = "reject"
    elif tier == "medium" or credit.approval == "review":
        recommendation = "review"

    return {
        "aggregated_score": round(normalized, 3),
        "risk_tier": tier,
        "recommendation": recommendation,
    }


def _save_decision(payload: Dict[str, any]) -> Path:
    run_id = payload["run_id"]
    dest = RUNS_DIR / f"{run_id}.unified_risk_decision.json"
    with dest.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return dest


@router.post("/decision")
def create_unified_decision(body: UnifiedRequest):
    if not body.borrower_id:
        raise HTTPException(status_code=400, detail="borrower_id required")

    run_id = body.loan_id or f"unified_{body.borrower_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    risk = _compute_risk(body.asset, body.fraud, body.credit)

    decision_payload = {
        "run_id": run_id,
        "borrower_id": body.borrower_id,
        "loan_id": body.loan_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asset": body.asset.model_dump(),
        "fraud": body.fraud.model_dump(),
        "credit": body.credit.model_dump(),
        "metadata": body.metadata,
        "risk_summary": risk,
    }

    file_path = _save_decision(decision_payload)
    return {
        "run_id": run_id,
        "risk_summary": risk,
        "decision": decision_payload,
        "artifact_path": str(file_path),
    }
