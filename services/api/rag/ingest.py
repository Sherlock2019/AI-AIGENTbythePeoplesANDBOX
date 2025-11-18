"""Compatibility wrapper exposing legacy ingest helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Sequence

from .chroma_store import get_collection
from .embeddings import embed_texts
from .ingest_csv import discover_csv_files, ingest_paths

DEFAULT_MAX_ROWS = 500


class LocalIngestor:
    """Backwards-compatible shim that reuses the Chroma ingestion path."""

    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path

    def ingest_text_chunks(self, chunks: Sequence[Dict], *, dry_run: bool = False) -> int:
        if dry_run:
            return len(chunks)
        collection = get_collection()
        texts = []
        metadatas = []
        ids = []
        for idx, chunk in enumerate(chunks):
            text = chunk.get("text")
            if not text:
                continue
            texts.append(text)
            metadatas.append(chunk.get("metadata") or {})
            ids.append(chunk.get("id") or f"chunk_{idx}")
        if not texts:
            return 0
        vectors = embed_texts(texts)
        collection.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
        return len(texts)

    def ingest_files(
        self,
        paths: Iterable[Path],
        *,
        max_rows: int = DEFAULT_MAX_ROWS,
        dry_run: bool = False,
    ) -> tuple[int, int]:
        files = list(paths)
        if dry_run:
            return len(files), 0
        stats = ingest_paths(files)
        return stats["files_processed"], stats["rows_indexed"]


def load_state(state_file: Path) -> Dict[str, float]:
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text())
    except Exception:
        return {}


def save_state(state_file: Path, state: Dict[str, float]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


__all__ = ["LocalIngestor", "discover_csv_files", "load_state", "save_state", "DEFAULT_MAX_ROWS"]
