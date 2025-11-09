from __future__ import annotations

from datetime import datetime
from typing import List

from .types import Case, FirstPrinciplesPlan, RetrievalHit
from .utils import bulletize

SAFETY_RULES = [
    "Never run destructive commands (rm -rf, kill -9 on unknown pid)",
    "Redact tokens/keys; no data exfiltration",
    "Prefer reversible, minimal changes and snapshot first",
]


def merge_strategy(plan: FirstPrinciplesPlan, hits: List[RetrievalHit]) -> List[str]:
    learned = [
        f"Pattern from {hit.case.id}: {hit.case.resolution[:120]}…" for hit in hits[:3]
    ]
    core = [
        "Validate environment: users/groups, PATH, runtime libs",
        "Map observed errors to nearest cases and pull known fixes",
        "Apply minimal reversible changes; document before execution",
        "Re-run targeted tests; persist successful playbook",
    ]
    return bulletize(learned + core)


def reflect(
    problem: str,
    context: str | None,
    plan: FirstPrinciplesPlan,
    strategy: List[str],
    outcome: str,
) -> str:
    ts = datetime.utcnow().isoformat()
    return "\n".join(
        [
            f"Post‑mortem @ {ts}",
            f"Problem: {problem}",
            f"Context: {context}",
            "Assumptions: " + "; ".join(plan.assumptions),
            "Constraints: " + "; ".join(plan.constraints),
            "Strategy: " + "; ".join(strategy),
            "Outcome: " + outcome,
            "Lessons: prefer minimal change; verify with targeted tests.",
        ]
    )


def to_case(
    problem: str,
    context: str | None,
    plan: FirstPrinciplesPlan,
    strategy: List[str],
    resolution: str,
    tags: List[str],
) -> Case:
    return Case(
        id=f"CASE-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        problem=problem,
        context=context,
        root_causes=["environment-mismatch"],
        resolution=resolution,
        steps=strategy,
        tags=tags,
        signals={
            "fp_assumptions": plan.assumptions,
            "fp_constraints": plan.constraints,
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
