"""Structured event logging utilities for chatbot ingestion + retrieval."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / ".logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "chatbot-events.log"

_LOCK = Lock()
_logger = logging.getLogger(__name__)


def log_chatbot_event(event: str, **fields: Any) -> None:
    """Append a JSON line capturing key chatbot events under .logs/."""
    payload: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    payload.update(fields)

    try:
        line = json.dumps(payload, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.debug("Failed to serialize chatbot log payload: %s", exc)
        return

    try:
        with _LOCK:
            with LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception as exc:  # pragma: no cover - defensive
        _logger.debug("Failed to write chatbot log line: %s", exc)


__all__ = ["log_chatbot_event", "LOG_PATH"]
