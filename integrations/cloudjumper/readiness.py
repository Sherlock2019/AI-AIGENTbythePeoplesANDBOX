"""Production readiness gate.

The controls are chosen to match what CloudJumper's importer actually checks, so
a candidate that passes here does not get rejected on arrival. CloudJumper warns
when `cloudjumper-handoff.yaml` lacks a model licence, data sensitivity, project
owner or health endpoint — all four are blocking controls below.

Two rules, same as CloudJumper's own scorer:
  - the formula is visible
  - NOT_CHECKED is never counted as a pass; it lowers confidence instead
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

PASS, WARNING, FAIL, NOT_CHECKED = "PASS", "WARNING", "FAIL", "NOT_CHECKED"

# (control_key, title, required, remediation)
CONTROLS: Dict[str, List[Tuple[str, str, bool, str]]] = {
    "business": [
        ("business_owner", "Business owner identified", True, "Name the accountable business sponsor."),
        ("business_problem", "Business problem stated", True, "Describe the problem this solves."),
        ("baseline_kpi", "Baseline KPI recorded", False, "Record today's measured value."),
        ("target_kpi", "Target KPI recorded", True, "State the KPI this must move, and by how much."),
        ("estimated_value", "Expected value estimated", False, "Estimate the annual value."),
    ],
    "technical": [
        ("technical_owner", "Technical owner identified", True, "Name the engineer accountable."),
        ("agent_version", "Agent version recorded", True, "Pin the agent version being promoted."),
        ("source_reference", "Source repository or artifact recorded", True, "Record the repo URL or artifact id."),
        ("model_name", "Model identified", True, "Record which model this runs on."),
        ("model_version", "Model version recorded", True, "Pin the model version."),
        # CloudJumper warns on a missing licence, so it blocks here.
        ("model_license", "Model licence declared", True, "Declare the model licence before production."),
        ("health_endpoint", "Health endpoint declared", True, "Expose and declare /health."),
    ],
    "data": [
        ("data_owner", "Data owner identified", True, "Name the accountable data owner."),
        ("data_sensitivity", "Data classified", True, "Classify as LOW / MEDIUM / HIGH / REGULATED."),
        ("data_location", "Data location known", True, "Record where the data physically lives."),
        ("pii_reviewed", "PII status reviewed", True, "Confirm whether personal data is processed."),
        ("transfer_policy", "External transfer policy set", False, "State whether data may leave the boundary."),
    ],
    "governance": [
        ("human_approval", "Human approval requirement decided", True, "Decide whether actions need approval."),
        ("evaluation_report", "Evaluation evidence attached", True, "Attach the evaluation report."),
        ("rollback", "Rollback behaviour described", True, "Describe what happens when the agent is disabled."),
    ],
    "operations": [
        ("production_owner", "Provisional production owner named", True, "Name who operates this once live."),
        ("target_environment", "Target environment selected", False, "Pick the intended environment."),
    ],
}

_POINTS = {PASS: 1.0, WARNING: 0.5, FAIL: 0.0}


def _v(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return True          # an explicit False is a decision, not an omission
    return bool(value) or value == 0


def evaluate(candidate: Dict[str, Any], evidence: Dict[str, Any] | None = None) -> Dict[str, str]:
    """Resolve every control. `evidence` maps evidence_type -> present."""
    ev = evidence or {}
    r: Dict[str, str] = {}

    r["business_owner"] = PASS if _v(candidate.get("business_owner")) else FAIL
    r["business_problem"] = PASS if _v(candidate.get("business_problem")) else FAIL
    r["baseline_kpi"] = PASS if _v(candidate.get("baseline_kpi")) else NOT_CHECKED
    r["target_kpi"] = PASS if _v(candidate.get("target_kpi")) else FAIL
    r["estimated_value"] = PASS if _v(candidate.get("estimated_value")) else NOT_CHECKED

    r["technical_owner"] = PASS if _v(candidate.get("technical_owner")) else FAIL
    r["agent_version"] = PASS if _v(candidate.get("agent_version")) else FAIL
    r["source_reference"] = PASS if (_v(candidate.get("source_repository")) or _v(candidate.get("source_commit"))) else FAIL
    r["model_name"] = PASS if _v(candidate.get("model_name")) else FAIL
    r["model_version"] = PASS if _v(candidate.get("model_version")) else FAIL
    r["model_license"] = PASS if _v(candidate.get("model_license")) else FAIL
    r["health_endpoint"] = PASS if _v(candidate.get("health_endpoint")) else FAIL

    r["data_owner"] = PASS if _v(candidate.get("data_owner")) else FAIL
    r["data_sensitivity"] = PASS if _v(candidate.get("data_sensitivity")) else FAIL
    r["data_location"] = PASS if _v(candidate.get("data_location")) else FAIL
    # An unreviewed PII question is unchecked, not a pass. Defaulting False here
    # would let "nobody looked" read exactly like "we checked, there is none".
    r["pii_reviewed"] = PASS if candidate.get("pii_reviewed") is True else NOT_CHECKED
    r["transfer_policy"] = PASS if candidate.get("external_transfer_allowed") is not None else NOT_CHECKED

    r["human_approval"] = PASS if candidate.get("human_approval_required") is not None else FAIL
    r["evaluation_report"] = PASS if ev.get("EVALUATION_REPORT") else FAIL
    r["rollback"] = PASS if _v(candidate.get("rollback_behaviour")) else NOT_CHECKED

    r["production_owner"] = PASS if _v(candidate.get("production_owner")) else FAIL
    r["target_environment"] = PASS if _v(candidate.get("target_environment")) else NOT_CHECKED

    # Regulated data raises the bar rather than merely being recorded.
    if str(candidate.get("data_sensitivity") or "").upper() in ("HIGH", "REGULATED"):
        if not _v(candidate.get("data_location")):
            r["data_location"] = FAIL
        if r["pii_reviewed"] == NOT_CHECKED:
            r["pii_reviewed"] = FAIL
    return r


def assess(candidate: Dict[str, Any], evidence: Dict[str, Any] | None = None) -> Dict[str, Any]:
    results = evaluate(candidate, evidence)

    categories: Dict[str, Any] = {}
    blockers: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    passed = failed = warned = unchecked = 0

    for category, controls in CONTROLS.items():
        scored = 0.0
        possible = 0
        detail = []
        for key, title, required, remediation in controls:
            outcome = results.get(key, NOT_CHECKED)
            detail.append({"control_key": key, "title": title, "required": required, "status": outcome})
            if outcome == NOT_CHECKED:
                unchecked += 1
            else:
                scored += _POINTS[outcome]
                possible += 1
                if outcome == PASS:
                    passed += 1
                elif outcome == WARNING:
                    warned += 1
                else:
                    failed += 1
            if outcome == FAIL and required:
                blockers.append({"control_key": key, "title": title, "remediation": remediation})
            elif outcome in (WARNING, FAIL):
                warnings.append({"control_key": key, "title": title, "remediation": remediation})

        categories[category] = {
            "score": int(round((scored / possible) * 100)) if possible else 0,
            "checked": possible,
            "not_checked": len(controls) - possible,
            "controls": detail,
        }

    total_checked = passed + warned + failed
    total = total_checked + unchecked
    score = int(round((sum(_POINTS[results[k]] for k in results if results[k] != NOT_CHECKED) / total_checked) * 100)) if total_checked else 0
    confidence = int(round((total_checked / total) * 100)) if total else 0

    if blockers:
        verdict = "BLOCKED"
    elif confidence < 60:
        verdict = "MANUAL_REVIEW"
    elif score >= 90:
        verdict = "READY"
    else:
        verdict = "READY_WITH_CHANGES"

    return {
        "score": score,
        "verdict": verdict,
        "confidence": confidence,
        "passed": passed,
        "warnings": warned,
        "failed": failed,
        "not_checked": unchecked,
        "blockers": blockers,
        "warning_items": warnings,
        "categories": categories,
        "formula": (
            "score = Σ(PASS=1, WARNING=0.5, FAIL=0) ÷ controls_checked; "
            "NOT_CHECKED is excluded from the score and reported as confidence. "
            "Any failed required control forces BLOCKED regardless of score."
        ),
        # The gate the API enforces before a bundle may be built.
        "can_generate_package": not blockers,
    }
