from __future__ import annotations

from typing import List

from .types import FirstPrinciplesPlan

TEMPLATES = {
    "assumptions": [
        "Environment is configured (OS, PATH, dependencies)",
        "Inputs/logs reflect the real failure",
        "Recent change correlates with failure",
    ],
    "constraints": [
        "No production downtime allowed",
        "Avoid irreversible actions without backup",
        "Maintain data integrity and audit trails",
    ],
}


def derive_plan(problem: str, context: str | None = None) -> FirstPrinciplesPlan:
    ctx = (context or "").lower()
    assumptions: List[str] = list(TEMPLATES["assumptions"])
    constraints: List[str] = list(TEMPLATES["constraints"])

    if "wsl" in ctx:
        assumptions.append("Host ↔ WSL path/uid mapping can break runtime")
        constraints.append("Minimize host PATH mutations")
    if "docker" in ctx:
        assumptions.append("Container image may miss OS libraries or users")
    if "getpwuid" in ctx or "vcruntime" in ctx:
        assumptions.append("User/group resolution or runtime libs missing")

    subproblems: List[str] = [
        "Collect minimal repro and correlate with last change",
        "Inspect logs for first failing call stack",
        "Validate runtime dependencies (users, groups, libs)",
        "Verify mounts/paths/env vars for mismatches",
    ]

    tests: List[str] = [
        "`id -a` / `getent passwd` should succeed inside env",
        "`ldd` on binaries/Python should resolve libs",
        "Check PATH for ghost/unmounted entries",
        "Run slimmed-down startup without optional plugins",
    ]

    return FirstPrinciplesPlan(
        assumptions=assumptions,
        constraints=constraints,
        subproblems=subproblems,
        tests=tests,
    )
