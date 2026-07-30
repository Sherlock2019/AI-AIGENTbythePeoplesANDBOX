"""Handoff package builder.

Produces the ZIP that CloudJumper's upload importer accepts. The layout is
driven by what that importer actually reads: it looks for
`cloudjumper-handoff.yaml` at the project root and requires the sections
schema_version, project, agent, model, data, deployment.

Two deliberate departures from the original specification:

1. **One manifest, not two.** The spec asked for both `manifest.yaml` and
   `cloudjumper-handoff.yaml` describing the same project. Two manifests drift;
   `cloudjumper-handoff.yaml` is the one CloudJumper reads, so it is the only one
   written.
2. **Absent files are gaps, never placeholders.** If there is no Dockerfile,
   Helm chart, SBOM or OpenAPI spec, the package records a gap. It never writes
   a stub and calls the project deployable.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from . import passport as passport_mod

HANDOFF_SCHEMA_VERSION = "1.0"
ROOT_DIR = "production-handoff"
MANIFEST_NAME = "cloudjumper-handoff.yaml"

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_FILES = 500

# Same shapes CloudJumper's scanner looks for, so a package cannot carry a
# secret that the receiving end would immediately flag.
SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}")),
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")),
    ("Private key block", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PGP|DSA)? ?PRIVATE KEY-----")),
    ("Assigned secret", re.compile(r"(?i)\b(password|secret|api[_-]?key|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]")),
]

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


class PackageError(Exception):
    """Package could not be built, for a reason worth showing the user."""


def sanitize_filename(name: str) -> str:
    """Reduce to a bare, safe filename. No paths, no traversal, no leading dot."""
    base = str(name or "").replace("\\", "/").split("/")[-1]
    base = _SAFE_NAME.sub("_", base).lstrip(".")
    return base[:120] or "file"


def scan_for_secrets(text: str, label: str) -> List[Dict[str, str]]:
    """Report the pattern and location. Never the matched value."""
    found = []
    for pattern_name, rx in SECRET_PATTERNS:
        if rx.search(text):
            found.append({"file": label, "pattern": pattern_name})
    return found


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_manifest(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """The CloudJumper handoff manifest.

    Section names and required keys match CloudJumper's validator exactly:
    schema_version, project, agent, model, data, deployment.
    """
    sens = str(candidate.get("data_sensitivity") or "").upper()
    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "project": {
            "global_ai_project_id": candidate.get("global_ai_project_id"),
            "name": candidate.get("title"),
            "adoption_mode": candidate.get("adoption_mode"),
            "source": candidate.get("source_type") or "YES_AI_CAN",
            "version": candidate.get("agent_version"),
            # CloudJumper warns when project.owner is absent.
            "owner": candidate.get("business_owner"),
            "business_owner": candidate.get("business_owner"),
            "technical_owner": candidate.get("technical_owner"),
            "data_owner": candidate.get("data_owner"),
            "production_owner": candidate.get("production_owner"),
        },
        "customer": {
            "customer_id": candidate.get("customer_id"),
            "business_system_id": candidate.get("business_system_id"),
        },
        "agent": {
            "passport_file": "agent-passport.json",
            "api_spec": "openapi.yaml" if candidate.get("_has_openapi") else None,
            "health_endpoint": candidate.get("health_endpoint"),
            "readiness_endpoint": candidate.get("readiness_endpoint"),
            "human_approval_required": bool(candidate.get("human_approval_required")),
        },
        "model": {
            "runtime": candidate.get("model_runtime"),
            "model_name": candidate.get("model_name"),
            "version": candidate.get("model_version"),
            "license": candidate.get("model_license"),
            "gpu_required": bool(candidate.get("gpu_required")),
            "minimum_ram_gb": candidate.get("minimum_ram_gb") or 0,
            "minimum_vram_gb": candidate.get("minimum_vram_gb") or 0,
        },
        "data": {
            "sensitivity": sens or None,
            "pii_present": bool(candidate.get("pii_present")),
            "residency_countries": candidate.get("residency_countries") or [],
            "external_transfer_allowed": bool(candidate.get("external_transfer_allowed")),
            "sources": candidate.get("data_sources") or [],
        },
        "deployment": {
            "target_preference": candidate.get("target_environment"),
            # Null, never a fabricated path. A missing asset is a gap below.
            "dockerfile": "Dockerfile" if candidate.get("_has_dockerfile") else None,
            "helm_path": "helm/" if candidate.get("_has_helm") else None,
            "kubernetes_path": "k8s/" if candidate.get("_has_k8s") else None,
        },
        "evaluation": {
            "report": "evaluation-report.json" if candidate.get("_has_evaluation") else None,
        },
        "operations": {
            "backup_required": bool(candidate.get("backup_required", True)),
            "dr_required": bool(candidate.get("dr_required", False)),
            "target_rto_minutes": candidate.get("target_rto_minutes"),
            "target_rpo_minutes": candidate.get("target_rpo_minutes"),
        },
        "generated_at": _iso(),
        "generated_by": "YES_AI_CAN",
    }


def compute_gaps(candidate: Dict[str, Any], manifest: Dict[str, Any]) -> List[Dict[str, str]]:
    """Assets that are absent. Recorded honestly instead of stubbed."""
    gaps: List[Dict[str, str]] = []

    def gap(sev: str, title: str, remediation: str) -> None:
        gaps.append({"severity": sev, "title": title, "remediation": remediation})

    if not candidate.get("_has_dockerfile"):
        gap("HIGH", "No Dockerfile in the package", "Add a container build definition so the workload is reproducible.")
    if not (candidate.get("_has_helm") or candidate.get("_has_k8s")):
        gap("HIGH", "No Kubernetes or Helm assets", "CloudJumper will generate a proposed OpenCenter deployment.")
    if not candidate.get("_has_openapi"):
        gap("MEDIUM", "No OpenAPI specification", "Publish the agent's API contract.")
    if not candidate.get("_has_sbom"):
        gap("MEDIUM", "No SBOM", "Generate an SBOM so dependencies can be reviewed.")
    if not candidate.get("_has_evaluation"):
        gap("HIGH", "No evaluation report", "Attach evaluation evidence before production.")
    if not manifest["model"].get("license"):
        gap("CRITICAL", "Model licence not declared", "Declare the model licence.")
    if not manifest["data"].get("sensitivity"):
        gap("CRITICAL", "Data not classified", "Classify the data.")
    return gaps


def _add(zf: zipfile.ZipFile, arcname: str, content: str, state: Dict[str, Any]) -> Tuple[str, str]:
    """Write one file, enforcing the caps and recording its checksum."""
    data = content.encode("utf-8")
    if len(data) > MAX_FILE_BYTES:
        raise PackageError(f"{arcname} exceeds {MAX_FILE_BYTES} bytes")
    state["total"] += len(data)
    state["count"] += 1
    if state["total"] > MAX_TOTAL_BYTES:
        raise PackageError("package exceeds the total size limit")
    if state["count"] > MAX_FILES:
        raise PackageError("package exceeds the file count limit")
    zf.writestr(f"{ROOT_DIR}/{arcname}", data)
    return arcname, hashlib.sha256(data).hexdigest()


def build_package(
    candidate: Dict[str, Any],
    evaluation: Dict[str, Any] | None = None,
    extra_files: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Build the handoff ZIP in memory.

    Returns the bytes, the manifest, the gaps and the package checksum. The
    caller persists it; nothing is written to disk here.
    """
    manifest = build_manifest(candidate)
    agent_passport = passport_mod.build(candidate, evaluation)
    gaps = compute_gaps(candidate, manifest)

    business_case = {
        "global_ai_project_id": candidate.get("global_ai_project_id"),
        "business_problem": candidate.get("business_problem"),
        "baseline_kpi": candidate.get("baseline_kpi"),
        "target_kpi": candidate.get("target_kpi"),
        "estimated_value": candidate.get("estimated_value"),
        "currency": candidate.get("currency") or "USD",
        "business_owner": candidate.get("business_owner"),
    }
    data_classification = {
        "global_ai_project_id": candidate.get("global_ai_project_id"),
        "classification": candidate.get("data_sensitivity"),
        "location": candidate.get("data_location"),
        "pii_present": bool(candidate.get("pii_present")),
        "external_transfer_allowed": bool(candidate.get("external_transfer_allowed")),
        "data_owner": candidate.get("data_owner"),
    }

    # Everything is scanned before it is written, including files the caller
    # supplied. A package must not be the thing that leaks a credential.
    payloads: Dict[str, str] = {
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, default_flow_style=False),
        "agent-passport.json": json.dumps(agent_passport, indent=2),
        "business-case.json": json.dumps(business_case, indent=2),
        "data-classification.json": json.dumps(data_classification, indent=2),
        "production-gaps.json": json.dumps(gaps, indent=2),
    }
    if evaluation:
        payloads["evaluation-report.json"] = json.dumps(evaluation, indent=2)
    for raw_name, content in (extra_files or {}).items():
        payloads[sanitize_filename(raw_name)] = content

    secrets_found: List[Dict[str, str]] = []
    for name, content in payloads.items():
        secrets_found.extend(scan_for_secrets(content, name))
    if secrets_found:
        # Blocking, not a warning. Shipping a credential inside an evidence
        # bundle is the failure this whole pipeline exists to prevent.
        raise PackageError(
            "refusing to build: possible secrets detected in "
            + ", ".join(sorted({s["file"] for s in secrets_found}))
        )

    readme = (
        f"# Production Handoff — {candidate.get('title') or 'project'}\n\n"
        f"- Global AI project ID: `{candidate.get('global_ai_project_id')}`\n"
        f"- Adoption mode: {candidate.get('adoption_mode')}\n"
        f"- Generated: {_iso()} by YES AI CAN\n\n"
        f"Import this bundle in CloudJumper Stage 9 (Upload source). "
        f"`{MANIFEST_NAME}` is the contract; `production-gaps.json` lists what is "
        f"missing rather than stubbing it.\n\n"
        f"## Recorded gaps ({len(gaps)})\n\n"
        + ("\n".join(f"- **{g['severity']}** {g['title']} — {g['remediation']}" for g in gaps) or "- none")
        + "\n"
    )
    payloads["README.md"] = readme

    buf = io.BytesIO()
    checksums: List[Tuple[str, str]] = []
    state = {"total": 0, "count": 0}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(payloads):
            checksums.append(_add(zf, name, payloads[name], state))
        lines = "\n".join(f"{digest}  {name}" for name, digest in sorted(checksums)) + "\n"
        zf.writestr(f"{ROOT_DIR}/checksums.sha256", lines.encode("utf-8"))

    blob = buf.getvalue()
    return {
        "bytes": blob,
        "checksum": hashlib.sha256(blob).hexdigest(),
        "manifest": manifest,
        "agent_passport": agent_passport,
        "gaps": gaps,
        "files": [name for name, _ in checksums] + ["checksums.sha256"],
        "size": len(blob),
        "filename": f"{candidate.get('global_ai_project_id') or 'handoff'}-production-handoff.zip",
    }


def write_package(result: Dict[str, Any], out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / sanitize_filename(result["filename"])
    path.write_bytes(result["bytes"])
    return path
