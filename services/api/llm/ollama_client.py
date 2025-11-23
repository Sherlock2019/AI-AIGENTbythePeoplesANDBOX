"""Lightweight Ollama client for Phi-3 (Ollama) inference."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from threading import Lock
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

def _normalize_base(url: str) -> str:
    if not url:
        return "http://localhost:11434"
    parsed = urlsplit(url)
    path = parsed.path or ""
    if path.startswith("/api/"):
        path = ""
    elif "/api/" in path:
        path = path.split("/api/", 1)[0]
    rebuilt = parsed._replace(path=path, query="", fragment="")
    base = urlunsplit(rebuilt).rstrip("/")
    return base or "http://localhost:11434"


OLLAMA_URL = _normalize_base(os.getenv("OLLAMA_URL", "http://localhost:11434"))
OLLAMA_MODEL = os.getenv("SANDBOX_CHATBOT_MODEL", os.getenv("OLLAMA_MODEL", "phi3:latest"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / ".logs"
PID_DIR = PROJECT_ROOT / ".pids"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PID_DIR.mkdir(parents=True, exist_ok=True)
OLLAMA_AUTOSTART_LOG = LOG_DIR / "ollama_autostart.log"
OLLAMA_AUTOSTART_PID = PID_DIR / "ollama_autostart.pid"
_OLLAMA_LOCK = Lock()


class OllamaError(RuntimeError):
    """Raised when the Ollama service cannot fulfill a request."""


def _build_payload(prompt: str, model: str | None = None) -> Dict[str, Any]:
    target_model = (model or OLLAMA_MODEL).strip()
    if not target_model:
        raise OllamaError("Ollama model name missing. Set SANDBOX_CHATBOT_MODEL or OLLAMA_MODEL.")
    return {
        "model": target_model,
        "messages": [
            {"role": "system", "content": os.getenv("OLLAMA_SYSTEM_PROMPT", "")},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
        },
    }


def _ping_ollama() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_URL.rstrip('/')}/api/tags", timeout=5)
        resp.raise_for_status()
        return True
    except requests.RequestException:
        return False


def _ensure_ollama_server(force_pull: bool = False) -> None:
    if _ping_ollama() and not force_pull:
        return

    with _OLLAMA_LOCK:
        if _ping_ollama() and not force_pull:
            return

        cli = shutil.which("ollama")
        if cli is None:
            raise OllamaError(
                "Ollama CLI not found. Install from https://ollama.com/download or set OLLAMA_URL."
            )

        if not force_pull:
            try:
                old_pid = int(OLLAMA_AUTOSTART_PID.read_text().strip())
            except Exception:
                old_pid = None
            if old_pid:
                try:
                    os.kill(old_pid, 0)
                except OSError:
                    OLLAMA_AUTOSTART_PID.unlink(missing_ok=True)

        log_file = open(OLLAMA_AUTOSTART_LOG, "ab")
        try:
            proc = subprocess.Popen(
                [cli, "serve"],
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )
            OLLAMA_AUTOSTART_PID.write_text(str(proc.pid))

            for _ in range(20):
                if _ping_ollama():
                    break
                time.sleep(1)
            else:
                proc.terminate()
                raise OllamaError(
                    f"Ollama server failed to start. Check {OLLAMA_AUTOSTART_LOG} for details."
                )

            try:
                subprocess.run(
                    [cli, "pull", OLLAMA_MODEL],
                    stdout=log_file,
                    stderr=log_file,
                    check=False,
                )
            except Exception:
                logger.debug("Ollama model pull skipped", exc_info=True)

            try:
                requests.post(
                    f"{OLLAMA_URL.rstrip('/')}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [{"role": "user", "content": "ready check"}],
                        "stream": False,
                    },
                    timeout=30,
                )
            except requests.RequestException:
                logger.debug("Ollama warm-up request failed; continuing.")
        finally:
            try:
                log_file.flush()
                log_file.close()
            except Exception:
                pass


def _generate_via_http(payload: Dict[str, Any], *, timeout: int | None = None) -> str:
    url = f"{OLLAMA_URL.rstrip('/')}/api/chat"
    try:
        resp = requests.post(url, json=payload, timeout=timeout or OLLAMA_TIMEOUT)
    except requests.RequestException as exc:
        raise OllamaError(f"Ollama request failed: {exc}") from exc
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        snippet = resp.text[:1000]
        raise OllamaError(f"Ollama HTTP {resp.status_code}: {snippet}") from exc

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        logger.error("Ollama returned invalid JSON: %s", resp.text[:500])
        raise OllamaError("Ollama returned invalid JSON") from exc

    messages = data.get("message") or data.get("messages")
    content = None
    if isinstance(messages, dict):
        content = messages.get("content")
    elif isinstance(messages, list):
        for entry in reversed(messages):
            if isinstance(entry, dict) and entry.get("role") == "assistant":
                content = entry.get("content")
                break
    if not content:
        logger.error("Unexpected Ollama payload: %s", data)
        raise OllamaError("Ollama response missing assistant content")
    return str(content).strip()


def _generate_via_cli(prompt: str, model: str) -> str:
    cli = shutil.which("ollama")
    if cli is None:
        raise OllamaError("Ollama CLI not found for fallback generation.")
    try:
        proc = subprocess.run(
            [cli, "run", model],
            input=prompt,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise OllamaError(f"Ollama CLI failed: {stderr}") from exc
    return (proc.stdout or "").strip()


def ollama_generate(prompt: str, *, model: str | None = None, timeout: int | None = None) -> str:
    """
    Send a blocking generate request to a local Ollama server.
    Falls back to the `ollama run` CLI when the HTTP endpoint is unavailable.
    """
    _ensure_ollama_server()
    payload = _build_payload(prompt, model=model)
    target_model = payload["model"]
    try:
        return _generate_via_http(payload, timeout=timeout)
    except OllamaError as exc:
        logger.warning("Ollama HTTP path failed (%s). Falling back to CLI.", exc)
        _ensure_ollama_server(force_pull=True)
        return _generate_via_cli(prompt, target_model)


__all__ = ["ollama_generate", "OllamaError"]
