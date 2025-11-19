"""Utilities to load agent how-to guides for chat workflows."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict

HOWTO_PATH = Path(__file__).resolve().parents[3] / "services" / "ui" / "pages" / "howto.md"

_SECTION_PREFIXES = {
    "universal": ("🧱", "✅", "🧩"),
    "asset_appraisal": ("🏦",),
    "credit_appraisal": ("💳",),
    "anti_fraud_kyc": ("🕵️",),
    "credit_scoring": ("📊",),
    "troubleshooter": ("🛠️",),
    "chatbot": ("🤖",),
    "cross_agent": ("🔗",),
    "approval": ("🔥",),
}

_QUESTION_KEYWORDS = ("how", "workflow", "stage", "steps", "guide", "process", "playbook", "a0", "phase")
_AGENT_KEYWORDS = {
    "asset_appraisal": ("asset", "collateral", "fmv", "haircut"),
    "credit_appraisal": ("credit", "borrower", "loan"),
    "anti_fraud_kyc": ("fraud", "kyc", "sanction"),
    "credit_scoring": ("scoring", "pd", "model"),
    "troubleshooter": ("troubleshoot", "issue"),
    "chatbot": ("chatbot", "rag"),
}


def _detect_section(line: str) -> str | None:
    stripped = line.strip()
    for key, prefixes in _SECTION_PREFIXES.items():
        if any(stripped.startswith(prefix) for prefix in prefixes):
            return key
    return None


@lru_cache(maxsize=1)
def _load_sections() -> Dict[str, str]:
    if not HOWTO_PATH.exists():
        return {}
    text = HOWTO_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections: Dict[str, str] = {}
    current_key = "universal"
    buffer: list[str] = []

    def flush():
        if buffer:
            sections[current_key] = "\n".join(buffer).strip()

    for line in lines:
        key = _detect_section(line)
        if key:
            flush()
            buffer = [line]
            current_key = key
        else:
            buffer.append(line)
    flush()
    return sections


def get_howto_snippet(agent_id: str | None, question: str | None) -> str:
    """Return the how-to text for the agent/question if the user asked for workflows."""
    if not question:
        return ""
    lower = question.lower()
    if not any(keyword in lower for keyword in _QUESTION_KEYWORDS):
        return ""
    sections = _load_sections()
    if not sections:
        return ""
    if agent_id and agent_id in sections:
        return sections[agent_id]
    for agent_key, keywords in _AGENT_KEYWORDS.items():
        if any(token in lower for token in keywords) and agent_key in sections:
            return sections[agent_key]
    return sections.get("universal", "")


__all__ = ["get_howto_snippet"]
