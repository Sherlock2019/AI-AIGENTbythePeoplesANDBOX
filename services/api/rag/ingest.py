"""Shared helpers for ingesting CSV artifacts into the local RAG store."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple, Any

import pandas as pd

from .embeddings import embed_texts, embeddings_available
from .local_store import LocalVectorStore

# Try to import ChromaDB (optional)
try:
    from .chroma_store import ChromaVectorStore
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    ChromaVectorStore = None

DEFAULT_MAX_ROWS = int(os.getenv("RAG_INGEST_MAX_ROWS", "500"))


def discover_csv_files(paths: Iterable[Path]) -> List[Path]:
    out: List[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file() and path.suffix.lower() == ".csv":
            out.append(path)
        else:
            out.extend(sorted(p for p in path.rglob("*.csv") if p.is_file()))
    return out


def row_to_text(row: pd.Series) -> str:
    kv = []
    for col, value in row.items():
        if pd.isna(value):
            continue
        kv.append(f"{col}={value}")
    return "; ".join(kv)


def chunked(seq: Sequence, size: int):
    for start in range(0, len(seq), size):
        yield seq[start : start + size]


class LocalIngestor:
    """Handles ingestion into the local vector store (supports both LocalVectorStore and ChromaDB)."""

    def __init__(self, store_path: Path | None = None, use_chromadb: bool = True):
        if not embeddings_available():
            raise RuntimeError("SentenceTransformer embeddings unavailable (model download failed).")
        
        # Use ChromaDB if available and requested, otherwise fallback to LocalVectorStore
        if use_chromadb and CHROMADB_AVAILABLE:
            try:
                chroma_path = Path(store_path).parent / ".chroma_store" if store_path else None
                self._store = ChromaVectorStore(chroma_path)
                self._using_chromadb = True
            except Exception as exc:
                print(f"Warning: ChromaDB initialization failed, using LocalVectorStore: {exc}")
                self._store = LocalVectorStore(store_path)
                self._using_chromadb = False
        else:
            self._store = LocalVectorStore(store_path)
            self._using_chromadb = False

    def ingest_text_chunks(self, chunks: Sequence[Dict[str, Any]], *, dry_run: bool = False) -> int:
        if not chunks:
            return 0
        texts: List[str] = []
        metadata: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            text = chunk.get("text")
            if not text:
                continue
            chunk_id = chunk.get("id") or f"chunk_{i}"
            meta = chunk.get("metadata") or {}
            meta.setdefault("id", chunk_id)
            meta.setdefault("title", meta.get("title", chunk_id))
            meta.setdefault("snippet", text[:600])
            meta.setdefault("text", text)
            texts.append(text)
            metadata.append(meta)
            if dry_run:
                print(f"[dry-run] prepared text chunk {chunk_id} (len={len(text)})")
        if dry_run:
            return len(texts)
        vectors = embed_texts(texts)
        self._store.add_vectors(vectors, metadata)
        self._store.save()
        return len(texts)

    def ingest_files(
        self,
        paths: Iterable[Path],
        *,
        max_rows: int = DEFAULT_MAX_ROWS,
        dry_run: bool = False,
    ) -> Tuple[int, int]:
        total_vectors = 0
        files_processed = 0
        for path in paths:
            try:
                df = pd.read_csv(path)
            except Exception as exc:
                print(f"[skip] {path}: {exc}")
                continue
            if df.empty:
                continue
            if max_rows:
                df = df.head(max_rows)
            texts = [row_to_text(row) for _, row in df.iterrows()]
            metadata = [
                {"source": str(path), "row_index": idx, "title": path.stem, "text": text}
                for idx, text in enumerate(texts)
            ]
            ids = [f"{path.stem}-{idx}" for idx in range(len(texts))]
            if dry_run:
                print(f"[dry-run] {path} → {len(texts)} rows prepared")
                files_processed += 1
                continue
            vectors = embed_texts(texts)
            stored_meta = []
            for vid, meta, snippet in zip(ids, metadata, texts):
                meta = dict(meta)
                meta.setdefault("id", vid)
                meta.setdefault("snippet", snippet[:600])
                stored_meta.append(meta)
            self._store.add_vectors(vectors, stored_meta)
            self._store.save()
            total_vectors += len(vectors)
            files_processed += 1
            print(f"[ingested] {path} → {len(texts)} rows")
        return files_processed, total_vectors


def load_state(state_file: Path) -> Dict[str, float]:
    if not state_file.exists():
        return {}
    try:
        data = json.loads(state_file.read_text())
        return {str(k): float(v) for k, v in data.items()}
    except Exception:
        return {}


def save_state(state_file: Path, state: Dict[str, float]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))

__all__ = ["LocalIngestor", "discover_csv_files", "load_state", "save_state", "DEFAULT_MAX_ROWS"]
