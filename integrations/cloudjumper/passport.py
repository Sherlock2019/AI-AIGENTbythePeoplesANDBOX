"""Agent Passport — the portable record of what an agent is and may do.

Consumed verbatim by CloudJumper's AI 4 the People import provider, so field
names here are the contract, not an internal convention.

Empty means empty. A field with no evidence is emitted as null or an empty list
rather than a plausible default: a passport that invents a licence or an
approval requirement is worse than one that admits the gap.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

SCHEMA_VERSION = "1.0"


def _iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _clean(value: Any) -> Any:
    """Blank strings become null so consumers cannot mistake '' for a value."""
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return value


def build(candidate: Dict[str, Any], evaluation: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ev = evaluation or {}
    passport: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "global_ai_project_id": candidate.get("global_ai_project_id"),
        "agent": {
            "id": _clean(candidate.get("agent_id")),
            "name": _clean(candidate.get("title")),
            "version": _clean(candidate.get("agent_version")),
            "business_purpose": _clean(candidate.get("business_problem")),
            "adoption_mode": candidate.get("adoption_mode"),
            "source_type": candidate.get("source_type"),
        },
        "owners": {
            "business": _clean(candidate.get("business_owner")),
            "technical": _clean(candidate.get("technical_owner")),
            "data": _clean(candidate.get("data_owner")),
            "production": _clean(candidate.get("production_owner")),
        },
        "model": {
            "runtime": _clean(candidate.get("model_runtime")),
            "name": _clean(candidate.get("model_name")),
            "version": _clean(candidate.get("model_version")),
            "license": _clean(candidate.get("model_license")),
            "gpu_required": bool(candidate.get("gpu_required")),
            "minimum_ram_gb": candidate.get("minimum_ram_gb") or 0,
            "minimum_vram_gb": candidate.get("minimum_vram_gb") or 0,
        },
        "data": {
            "classification": _clean(candidate.get("data_sensitivity")),
            "location": _clean(candidate.get("data_location")),
            "pii_present": bool(candidate.get("pii_present")),
            "external_transfer_allowed": bool(candidate.get("external_transfer_allowed")),
        },
        "permissions": {
            "human_approval_required": bool(candidate.get("human_approval_required")),
            # Never inferred. An empty prohibited-actions list means "not yet
            # declared", and the readiness gate is what forces it to be filled.
            "allowed_actions": candidate.get("allowed_actions") or [],
            "prohibited_actions": candidate.get("prohibited_actions") or [],
        },
        "interfaces": {
            "health_endpoint": _clean(candidate.get("health_endpoint")),
            "readiness_endpoint": _clean(candidate.get("readiness_endpoint")),
        },
        "source": {
            "repository": _clean(candidate.get("source_repository")),
            "commit": _clean(candidate.get("source_commit")),
        },
        "evaluation": {
            "report_present": bool(ev),
            "score": ev.get("score"),
            "summary": _clean(ev.get("summary")),
        },
        "business_case": {
            "baseline_kpi": _clean(candidate.get("baseline_kpi")),
            "target_kpi": _clean(candidate.get("target_kpi")),
            "estimated_value": candidate.get("estimated_value"),
            "currency": candidate.get("currency") or "USD",
        },
        "rollback_behaviour": _clean(candidate.get("rollback_behaviour")),
        "generated_at": _iso(),
        "generated_by": "YES_AI_CAN",
    }
    return passport


# Metadata about *when* the passport was made, not about what the agent is.
# Excluded from the checksum so the same agent facts always hash the same.
_VOLATILE = ("generated_at",)


def checksum(payload: Dict[str, Any]) -> str:
    """Stable SHA-256 over the passport's content.

    Reproducible on purpose: the same agent, packaged twice, must produce the
    same digest. That is what lets the checksum act as an idempotency key for a
    later CloudJumper submission and lets a reviewer prove two bundles describe
    the same thing. Including the generation timestamp would make every build
    look like a different agent.
    """
    content = {k: v for k, v in payload.items() if k not in _VOLATILE}
    blob = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def missing_fields(passport: Dict[str, Any]) -> List[str]:
    """Fields CloudJumper's importer warns about when absent."""
    gaps: List[str] = []
    if not passport.get("model", {}).get("license"):
        gaps.append("model.license")
    if not passport.get("data", {}).get("classification"):
        gaps.append("data.classification")
    if not passport.get("owners", {}).get("business"):
        gaps.append("owners.business")
    if not passport.get("interfaces", {}).get("health_endpoint"):
        gaps.append("interfaces.health_endpoint")
    if not passport.get("agent", {}).get("version"):
        gaps.append("agent.version")
    return gaps
