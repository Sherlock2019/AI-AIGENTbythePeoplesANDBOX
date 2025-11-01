# ~/credit-appraisal-agent-poc/services/api/routers/settings.py
from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1/settings", tags=["settings"])

SERVER_DEFAULT_TUNING: Dict[str, Any] = {
    "target_approval_rate": 0.50,
    "threshold": 0.45,
    "min_employment_years": 1,
    "max_debt_to_income": 0.40,
    "min_credit_history_length": 24,
    "max_num_delinquencies": 1,
    "max_current_loans": 3,
    "requested_amount_min": 2_000.0,
    "requested_amount_max": 150_000.0,
    "loan_term_months_allowed": [12, 24, 36, 48, 60],
}

@router.get("/credit_defaults")
def get_credit_defaults():
    return JSONResponse(SERVER_DEFAULT_TUNING)
