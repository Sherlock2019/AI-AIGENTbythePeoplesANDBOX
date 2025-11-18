"""Shared helpers for chatbot RAG ingestion."""
from __future__ import annotations

from typing import List


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Return overlapping text chunks for embedding."""
    if chunk_size <= 0:
        return [text]
    cleaned = text or ""
    length = len(cleaned)
    if length <= chunk_size:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    while start < length:
        end = min(length, start + chunk_size)
        chunks.append(cleaned[start:end])
        if end == length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def select_device() -> str:
    """Return 'cuda' when GPU is available, otherwise 'cpu'."""
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


__all__ = ["chunk_text", "select_device"]
