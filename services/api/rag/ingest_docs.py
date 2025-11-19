"""Ingest documentation (*.md, *.txt) for the chatbot RAG store."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Dict, Iterable, List

from .chroma_store import get_collection
from .embeddings import embed_texts
from .ingest_csv import infer_agent_from_path
from .utils import chunk_text
from ..utils.chatbot_events import log_chatbot_event

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOC_ROOTS: List[Path] = [
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "services" / "ui" / "components",
]
DOC_EXTENSIONS = {".md", ".markdown", ".txt"}
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def _hash_path(path: Path) -> str:
    digest = hashlib.md5(str(path).encode("utf-8"), usedforsecurity=False).hexdigest()
    return digest[:10]


def discover_docs(extra_roots: Iterable[Path] | None = None) -> List[Path]:
    paths: List[Path] = []
    for root in list(DOC_ROOTS) + list(extra_roots or []):
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in DOC_EXTENSIONS:
                paths.append(file_path)
    return sorted(paths)


def ingest_docs() -> Dict[str, int]:
    files = discover_docs()
    if not files:
        return {"files_processed": 0, "rows_indexed": 0}

    collection = get_collection()
    processed = 0
    chunks_total = 0

    for doc_path in files:
        try:
            text = doc_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to read doc %s: %s", doc_path, exc)
            continue

        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
        if not chunks:
            continue

        agent = infer_agent_from_path(doc_path) or "global"
        embeddings = embed_texts(chunks)
        doc_key = f"doc_{_hash_path(doc_path)}"
        metadatas = [
            {
                "source": str(doc_path),
                "kind": "doc",
                "agent": agent,
                "chunk_index": idx,
                "snippet": chunk[:400],
            }
            for idx, chunk in enumerate(chunks)
        ]
        ids = [f"{doc_key}_{idx}" for idx in range(len(chunks))]
        collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        processed += 1
        chunks_total += len(chunks)

    log_chatbot_event("ingest.docs", files=processed, chunks=chunks_total)
    return {"files_processed": processed, "rows_indexed": chunks_total}


__all__ = ["ingest_docs", "discover_docs"]
