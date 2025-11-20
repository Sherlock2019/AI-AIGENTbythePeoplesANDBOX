"""Utility loader for `data.llm_profiles` with resilient import logic."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List, Dict


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ROOT_STR = str(_PROJECT_ROOT.resolve())
if _PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_STR)


def get_llm_profiles() -> List[Dict[str, str]]:
    """Return the `model_full` list from `data.llm_profiles`, even when cwd varies."""
    try:
        from data.llm_profiles import model_full as profiles  # type: ignore
        return profiles
    except ModuleNotFoundError:
        candidate = _PROJECT_ROOT / "data" / "llm_profiles.py"
        if not candidate.exists():
            raise
        spec = importlib.util.spec_from_file_location("data.llm_profiles", candidate)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return getattr(module, "model_full")


__all__ = ["get_llm_profiles"]
