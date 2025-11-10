"""Embedding utilities shared by chat+ingestion flows."""
from __future__ import annotations

import os
from typing import Iterable, List

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = os.getenv("SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2")
_MODEL: SentenceTransformer | None = None
_DEVICE = "cpu"


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(DEFAULT_MODEL, device=_DEVICE)
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
    vectors = encoder.encode(payload, show_progress_bar=False)
    return [vec.tolist() for vec in vectors]
