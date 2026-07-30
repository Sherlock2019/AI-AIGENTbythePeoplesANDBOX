"""CloudJumper submission client.

Standard library only, on purpose: this file is used by both YES AI CAN and
AI 4 the People, whose virtualenvs differ. Adding a dependency would mean
maintaining it in two places.

Sends a production handoff bundle to CloudJumper's one-shot intake, which
creates the project, imports it, assesses production gaps and builds a plan in
a single call.

Credentials: the API key is read from an environment variable named by
CLOUDJUMPER_API_KEY_REFERENCE. The key itself is never stored, never logged and
never written into a project record — only the variable's *name* is configuration.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import ssl
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_TIMEOUT = 120


class CloudJumperError(Exception):
    """Submission failed. Carries whether it is safe to retry."""

    def __init__(self, message: str, *, status: int = 0, retry_safe: bool = False, correlation_id: str = ""):
        super().__init__(message)
        self.status = status
        self.retry_safe = retry_safe
        self.correlation_id = correlation_id


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_configured() -> bool:
    return bool(_env("CLOUDJUMPER_API_BASE_URL") and _api_key())


def _api_key() -> str:
    ref = _env("CLOUDJUMPER_API_KEY_REFERENCE", "CLOUDJUMPER_API_KEY")
    return _env(ref)


def _redact(text: str) -> str:
    """Strip anything key-shaped before text reaches a log or a UI."""
    key = _api_key()
    if key and key in text:
        text = text.replace(key, "***")
    return text


def config_summary() -> Dict[str, Any]:
    """Safe to display. Reports whether a key is set, never its value."""
    ref = _env("CLOUDJUMPER_API_KEY_REFERENCE", "CLOUDJUMPER_API_KEY")
    return {
        "enabled": _env("CLOUDJUMPER_ENABLED", "1") not in ("0", "false", "no"),
        "base_url": _env("CLOUDJUMPER_API_BASE_URL") or None,
        "web_url": _env("CLOUDJUMPER_WEB_URL") or None,
        "api_key_reference": ref,
        "api_key_present": bool(_api_key()),
        "verify_tls": _verify_tls(),
        "configured": is_configured(),
    }


def _verify_tls() -> bool:
    return _env("CLOUDJUMPER_VERIFY_TLS", "1") not in ("0", "false", "no")


def _ssl_context() -> Optional[ssl.SSLContext]:
    if _verify_tls():
        ca = _env("CLOUDJUMPER_CA_BUNDLE")
        if ca and Path(ca).is_file():
            return ssl.create_default_context(cafile=ca)
        return None  # urllib's default verification
    # Explicit opt-out only, for a self-signed dev CloudJumper.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _multipart(fields: Dict[str, str], file_field: str, filename: str, blob: bytes) -> tuple[bytes, str]:
    boundary = f"----cloudjumper{uuid.uuid4().hex}"
    out = bytearray()
    for key, value in fields.items():
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        out += f"{value}\r\n".encode()
    ctype = mimetypes.guess_type(filename)[0] or "application/zip"
    out += f"--{boundary}\r\n".encode()
    out += f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
    out += f"Content-Type: {ctype}\r\n\r\n".encode()
    out += blob
    out += f"\r\n--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _request(method: str, path: str, *, body: bytes = b"", content_type: str = "",
             correlation_id: str = "", timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    base = _env("CLOUDJUMPER_API_BASE_URL").rstrip("/")
    if not base:
        raise CloudJumperError("CLOUDJUMPER_API_BASE_URL is not set", retry_safe=False)
    key = _api_key()
    if not key:
        ref = _env("CLOUDJUMPER_API_KEY_REFERENCE", "CLOUDJUMPER_API_KEY")
        raise CloudJumperError(f"no API key: environment variable {ref} is empty", retry_safe=False)

    req = urllib.request.Request(base + path, data=body or None, method=method)
    req.add_header("X-API-Key", key)
    req.add_header("Accept", "application/json")
    req.add_header("X-Correlation-ID", correlation_id or uuid.uuid4().hex)
    req.add_header("User-Agent", f"{_env('CLOUDJUMPER_CLIENT_NAME', 'yes-ai-can')}/1.0")
    if content_type:
        req.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        # 5xx and timeouts may be retried; 4xx will fail identically next time.
        raise CloudJumperError(
            _redact(f"CloudJumper returned {exc.code}: {detail}"),
            status=exc.code,
            retry_safe=exc.code >= 500,
            correlation_id=correlation_id,
        ) from exc
    except urllib.error.URLError as exc:
        raise CloudJumperError(
            _redact(f"cannot reach CloudJumper: {exc.reason}"), retry_safe=True, correlation_id=correlation_id
        ) from exc
    except json.JSONDecodeError as exc:
        raise CloudJumperError("CloudJumper returned a non-JSON response", retry_safe=True) from exc


def health_check() -> Dict[str, Any]:
    """Confirm reachability and whether our key is accepted."""
    try:
        meta = _request("GET", "/ai-adoption/meta", timeout=15)
    except CloudJumperError as exc:
        return {"reachable": False, "error": str(exc)}
    auth = meta.get("auth") or {}
    return {
        "reachable": True,
        "authenticated_as": auth.get("service_caller"),
        "service_auth_configured": auth.get("service_auth_configured"),
        "adoption_modes": meta.get("adoption_modes"),
        "submit_endpoint": meta.get("submit_endpoint"),
    }


def submit_bundle(
    bundle_path: str | Path,
    *,
    name: str,
    adoption_mode: str,
    global_ai_project_id: str = "",
    business_owner: str = "",
    technical_owner: str = "",
    data_owner: str = "",
    production_owner: str = "",
    business_goal: str = "",
    data_sensitivity: str = "",
    palantir_required: bool = False,
    customer_id: str = "",
    correlation_id: str = "",
) -> Dict[str, Any]:
    """Send a handoff bundle to CloudJumper for deployment assessment.

    Idempotent: CloudJumper keys on global_ai_project_id plus the bundle
    checksum, so re-sending the same bundle returns the existing project rather
    than creating a duplicate. That makes retrying a timeout safe.
    """
    path = Path(bundle_path)
    if not path.is_file():
        raise CloudJumperError(f"bundle not found: {path}", retry_safe=False)
    blob = path.read_bytes()

    metadata = {
        "name": name,
        "adoption_mode": adoption_mode,
        "global_ai_project_id": global_ai_project_id,
        "business_owner": business_owner,
        "technical_owner": technical_owner,
        "data_owner": data_owner,
        "production_owner": production_owner,
        "business_goal": business_goal,
        "data_sensitivity": data_sensitivity,
        "palantir_required": bool(palantir_required),
        "customer_id": customer_id,
        "package_checksum": hashlib.sha256(blob).hexdigest(),
    }
    body, ctype = _multipart({"metadata": json.dumps(metadata)}, "file", path.name, blob)
    result = _request(
        "POST", "/ai-adoption/submit",
        body=body, content_type=ctype,
        correlation_id=correlation_id or uuid.uuid4().hex,
    )
    if result.get("project_id"):
        result["cloudjumper_url"] = project_url(result["project_id"])
    return result


def project_url(cloudjumper_project_id: str) -> Optional[str]:
    """Deep link. Project id only — never a credential in a URL."""
    template = _env("CLOUDJUMPER_PROJECT_URL_TEMPLATE")
    if template:
        return template.replace("{cloudjumper_project_id}", str(cloudjumper_project_id))
    web = _env("CLOUDJUMPER_WEB_URL")
    return f"{web.rstrip('/')}/ai-powerup" if web else None
