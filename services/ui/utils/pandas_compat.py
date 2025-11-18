from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import logging

import pandas as pd

logger = logging.getLogger(__name__)
_FALLBACK_WARNED = False


def _flatten(obj: Any, *, parent_key: str = "", sep: str = ".", level: int = 0, max_level: int | None = None) -> dict[str, Any]:
    items: dict[str, Any] = {}

    if isinstance(obj, Mapping):
        if max_level is not None and level >= max_level:
            items[parent_key or "value"] = obj
            return items
        for key, value in obj.items():
            key_str = str(key)
            new_key = f"{parent_key}{sep}{key_str}" if parent_key else key_str
            items.update(_flatten(value, parent_key=new_key, sep=sep, level=level + 1, max_level=max_level))
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        if max_level is not None and level >= max_level:
            items[parent_key or "value"] = obj
            return items
        for idx, value in enumerate(obj):
            idx_key = f"{parent_key}{sep}{idx}" if parent_key else str(idx)
            items.update(_flatten(value, parent_key=idx_key, sep=sep, level=level + 1, max_level=max_level))
    else:
        items[parent_key or "value"] = obj

    return items


def _fallback_json_normalize(
    data: Any,
    record_path: Any = None,
    meta: Any = None,
    meta_prefix: str | None = None,
    record_prefix: str | None = None,
    errors: str = "raise",
    sep: str = ".",
    max_level: int | None = None,
):
    if any(param is not None for param in (record_path, meta, meta_prefix, record_prefix)):
        raise ValueError("json_normalize fallback only supports flat records without record_path/meta options.")

    global _FALLBACK_WARNED
    if not _FALLBACK_WARNED:
        logger.warning("pandas.json_normalize unavailable; using simplified fallback implementation.")
        _FALLBACK_WARNED = True

    if isinstance(data, Mapping):
        rows = [data]
    elif isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        rows = list(data)
    else:
        rows = [data]

    normalized = []
    for entry in rows:
        if isinstance(entry, Mapping):
            normalized.append(_flatten(entry, sep=sep, max_level=max_level))
        else:
            normalized.append({"value": entry})

    return pd.DataFrame(normalized)


def ensure_json_normalize():
    try:
        from pandas import json_normalize as compat_json_normalize  # type: ignore
    except ImportError:
        try:
            from pandas.io.json import json_normalize as compat_json_normalize  # type: ignore[attr-defined]
        except ImportError:
            compat_json_normalize = _fallback_json_normalize

    if not hasattr(pd, "json_normalize"):
        pd.json_normalize = compat_json_normalize  # type: ignore[attr-defined]

    return compat_json_normalize


__all__ = ["ensure_json_normalize"]
