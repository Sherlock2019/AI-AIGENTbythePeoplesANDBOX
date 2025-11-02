# services/api/routers/asset_reporting.py
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
import pandas as pd, io, json, glob, os
from datetime import datetime

router = APIRouter(prefix="/v1/asset_appraisal", tags=["asset_appraisal_reporting"])
RUNS_DIR = os.environ.get("RUNS_DIR", "./.tmp_runs")

def _latest(pattern: str) -> str | None:
    files = sorted(glob.glob(os.path.join(RUNS_DIR, pattern)))
    return files[-1] if files else None

@router.get("/portfolio", response_class=JSONResponse)
def get_portfolio():
    """Return latest decision/policy/verification table with status labels."""
    for pat in ["risk_decision.*.csv","policy_haircuts.*.csv","verification_status.*.csv","valuation_ai.*.csv"]:
        path = _latest(pat)
        if path:
            df = pd.read_csv(path)
            # Derive status_label (same logic as UI)
            df["verification_status"] = df.get("verification_status","verified")
            df["encumbrance_flag"] = df.get("encumbrance_flag", False)
            df["policy_breaches"] = df.get("policy_breaches","")
            df["confidence"] = df.get("confidence", 80.0)
            df["decision"] = df.get("decision","review")
            df["valuation_gap_pct"] = df.get("valuation_gap_pct", 0.0)
            df["fraud_flag"] = df.get("fraud_flag", False)

            def label_row(r):
                if bool(r.get("fraud_flag")) or ("fraud" in str(r.get("verification_status","")).lower()) or (bool(r.get("encumbrance_flag")) and "verified" not in str(r.get("verification_status","")).lower()):
                    return "FRAUD / ENCUMBRANCE"
                if len(str(r.get("policy_breaches",""))) > 0 or float(r.get("confidence",0)) < 70 or abs(float(r.get("valuation_gap_pct",0))) >= 10 or str(r.get("decision","")).lower() in ("review","reject"):
                    return "RISKY"
                return "VALIDATED"

            df["status_label"] = [label_row(r) for _, r in df.iterrows()]
            return JSONResponse(json.loads(df.to_json(orient="records")))
    raise HTTPException(status_code=404, detail="No portfolio artifacts found")

@router.get("/credit_collateral.csv")
def get_credit_collateral_csv():
    """Return latest credit collateral CSV."""
    path = _latest("credit_collateral_input.*.csv")
    if not path:
        raise HTTPException(404, "credit_collateral_input not found")
    return StreamingResponse(open(path, "rb"), media_type="text/csv")

@router.get("/opportunities")
def get_opportunities():
    """Return latest opportunities JSON."""
    path = _latest("opportunities.*.json")
    if not path:
        return JSONResponse({"generated_at": datetime.utcnow().isoformat(), "count": 0, "items": []})
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    return JSONResponse(data)
