"""Embedding utilities shared by chat+ingestion flows."""
from __future__ import annotations

import os
from typing import Iterable, List

from sentence_transformers import SentenceTransformer

# Try to import select_device, fallback to "cpu" if not available
try:
    from .utils import select_device
    _DEVICE = select_device()
except ImportError:
    _DEVICE = "cpu"

DEFAULT_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
_MODEL: SentenceTransformer | None = None


def _load_model(device: str | None = None) -> SentenceTransformer:
    global _MODEL, _DEVICE
    target = device or _DEVICE
    _DEVICE = target
    _MODEL = SentenceTransformer(DEFAULT_MODEL, device=target)
    return _MODEL


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        return _load_model(_DEVICE)
    return _MODEL


def embeddings_available() -> bool:
    try:
        _get_model()
        return True
    except Exception:
        return False


def embed_texts(texts: Iterable[str], model: str | None = None) -> List[List[float]]:
    payload = list(texts)
    if not payload:
        return []
    encoder = _get_model()
    if model and model != DEFAULT_MODEL:
        encoder = SentenceTransformer(model, device=_DEVICE)
    try:
        vectors = encoder.encode(payload, show_progress_bar=False)
    except Exception:
        if _DEVICE != "cpu":
            # Fallback to CPU if GPU execution fails.
            encoder = _load_model("cpu")
            vectors = encoder.encode(payload, show_progress_bar=False)
        else:
            raise
    return [vec.tolist() for vec in vectors]
