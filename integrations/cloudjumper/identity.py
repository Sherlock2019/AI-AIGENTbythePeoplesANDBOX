"""Shared project identity across YES AI CAN, CloudJumper and Palantir.

One readable identifier follows a project from challenge to production:

    AIPROJ-YYYY-NNNNNN

Readable on purpose — it goes in filenames, bundle manifests, deep links and
support conversations, where a UUID would be unusable. Uniqueness is enforced by
a unique index on the column, not by hoping the counter is right.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

PREFIX = "AIPROJ"
PATTERN = re.compile(r"^AIPROJ-(\d{4})-(\d{6})$")

ADOPTION_MODES = ("GREENFIELD", "BROWNFIELD", "EXISTING_POC")

# Matches CloudJumper's source types where they overlap, so the handoff needs no
# translation table. YES_AI_CAN and AI4PEOPLE both land as AI4PEOPLE-format
# bundles on the CloudJumper side.
SOURCE_TYPES = (
    "NEW_BUILD",
    "YES_AI_CAN",
    "AI4PEOPLE",
    "LAUNCHPAD",
    "GITHUB",
    "UPLOAD",
    "NOTEBOOK",
    "EXISTING_APPLICATION",
)

DATA_SENSITIVITIES = ("LOW", "MEDIUM", "HIGH", "REGULATED")

# Six states, not the spec's twenty-two. The sixteen removed ones mirrored
# CloudJumper deployment states (UAT, CANARY, PRODUCTION, ROLLED_BACK...) that
# CloudJumper does not track, so nothing would ever set them.
STATUSES = (
    "DRAFT",             # created, evidence incomplete
    "READY",             # passes the readiness gate
    "PACKAGED",          # handoff bundle generated and checksummed
    "SUBMITTED",         # bundle handed to CloudJumper
    "ACCEPTED",          # CloudJumper confirmed import
    "ARCHIVED",
)

# Forward-only. A candidate cannot go back to DRAFT once packaged, because the
# bundle's checksums would no longer describe it.
_ALLOWED = {
    "DRAFT": {"READY", "ARCHIVED"},
    "READY": {"PACKAGED", "DRAFT", "ARCHIVED"},
    "PACKAGED": {"SUBMITTED", "READY", "ARCHIVED"},
    "SUBMITTED": {"ACCEPTED", "PACKAGED", "ARCHIVED"},
    "ACCEPTED": {"ARCHIVED"},
    "ARCHIVED": set(),
}


def is_valid(project_id: str) -> bool:
    return bool(PATTERN.match(str(project_id or "")))


def parse_sequence(project_id: str) -> Optional[int]:
    m = PATTERN.match(str(project_id or ""))
    return int(m.group(2)) if m else None


def next_global_ai_project_id(existing: list[str], year: Optional[int] = None) -> str:
    """Mint the next id for `year`.

    `existing` is every id already issued; the caller reads it from the database
    inside the same transaction that inserts the new row, so two concurrent
    creates cannot mint the same number — and the unique index is the backstop
    if they somehow do.
    """
    yr = year or datetime.utcnow().year
    prefix = f"{PREFIX}-{yr}-"
    highest = 0
    for pid in existing or []:
        if not str(pid or "").startswith(prefix):
            continue
        seq = parse_sequence(pid)
        if seq is not None and seq > highest:
            highest = seq
    if highest >= 999999:
        raise ValueError(f"exhausted project ids for {yr}")
    return f"{prefix}{highest + 1:06d}"


def validate_transition(current: str, target: str) -> None:
    if current not in STATUSES:
        raise ValueError(f"unknown current status: {current}")
    if target not in STATUSES:
        raise ValueError(f"unknown target status: {target}")
    if target == current:
        return
    if target not in _ALLOWED[current]:
        raise ValueError(f"illegal transition {current} -> {target}")


def validate_adoption_mode(mode: str) -> str:
    m = str(mode or "").strip().upper()
    if m not in ADOPTION_MODES:
        raise ValueError(f"adoption_mode must be one of {list(ADOPTION_MODES)}")
    return m


def validate_sensitivity(value: str) -> str:
    v = str(value or "").strip().upper()
    if v and v not in DATA_SENSITIVITIES:
        raise ValueError(f"data_sensitivity must be one of {list(DATA_SENSITIVITIES)}")
    return v
