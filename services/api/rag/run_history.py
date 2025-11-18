"""Helpers to prune historical agent run artifacts so RAG stays fresh."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIRS = [
    PROJECT_ROOT / ".tmp_runs",
    PROJECT_ROOT / "services" / "ui" / ".tmp_runs",
    PROJECT_ROOT / "anti-fraud-kyc-agent" / ".tmp_runs",
]

logger = logging.getLogger(__name__)


def _list_agent_run_dirs() -> List[Path]:
    """Return per-agent .tmp_runs directories under agents/."""
    agents_root = PROJECT_ROOT / "agents"
    if not agents_root.exists():
        return []
    results: List[Path] = []
    for path in agents_root.iterdir():
        if not path.is_dir():
            continue
        runs_dir = path / ".tmp_runs"
        if runs_dir.exists():
            results.append(runs_dir)
    return results


def _prune_files(root: Path, keep: int) -> int:
    """Delete files/directories beyond the newest `keep` entries."""
    if keep <= 0 or not root.exists():
        return 0

    entries = []
    for path in root.glob("*"):
        try:
            entries.append((path.stat().st_mtime, path))
        except FileNotFoundError:
            continue
    entries.sort(key=lambda item: item[0], reverse=True)

    removed = 0
    for _, path in entries[keep:]:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            removed += 1
        except Exception as exc:
            logger.debug("Failed pruning %s: %s", path, exc)
    return removed


def prune_agent_run_history(keep_last: int = 5) -> Dict[str, int]:
    """Prune historical artifacts so each agent keeps only the newest runs."""
    stats = {"directories": 0, "entries_removed": 0}
    run_dirs = DEFAULT_RUN_DIRS + _list_agent_run_dirs()
    for run_dir in run_dirs:
        removed = _prune_files(run_dir, keep_last)
        if removed:
            stats["directories"] += 1
            stats["entries_removed"] += removed
    return stats


__all__ = ["prune_agent_run_history"]
