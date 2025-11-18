"""Ingest agent UI page files into the chatbot RAG store."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List

from ..utils.chatbot_events import log_chatbot_event
from .chroma_store import get_collection
from .embeddings import embed_texts
from .utils import chunk_text

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
UI_PAGES_DIR = PROJECT_ROOT / "services" / "ui" / "pages"
AGENT_CHUNK_SIZE = int(os.getenv("CHATBOT_RAG_AGENT_CHUNK", "1200"))
AGENT_CHUNK_OVERLAP = int(os.getenv("CHATBOT_RAG_AGENT_OVERLAP", "200"))


def discover_agent_files() -> List[Path]:
    if not UI_PAGES_DIR.exists():
        return []
    files = []
    for path in UI_PAGES_DIR.glob("*.py"):
        if path.is_file() and not path.name.startswith("_"):
            files.append(path)
    return sorted(files)


def ingest_agent_pages() -> Dict[str, int]:
    files = discover_agent_files()
    if not files:
        return {"files_processed": 0, "rows_indexed": 0}

    log_chatbot_event("ingest.agent_pages.start", files=len(files))
    collection = get_collection()
    processed = 0
    chunks_indexed = 0

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            continue

        agent_id = path.stem
        chunks = chunk_text(text, AGENT_CHUNK_SIZE, AGENT_CHUNK_OVERLAP)
        if not chunks:
            continue

        embeddings = embed_texts(chunks)
        ids = [f"{agent_id}_src_{idx}" for idx in range(len(chunks))]
        metadatas = [
            {
                "source": str(path),
                "kind": "agent_ui",
                "agent": agent_id,
                "chunk_index": idx,
            }
            for idx in range(len(chunks))
        ]
        collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
        processed += 1
        chunks_indexed += len(chunks)

    log_chatbot_event("ingest.agent_pages.finish", files=processed, chunks=chunks_indexed)
    return {"files_processed": processed, "rows_indexed": chunks_indexed}


__all__ = ["ingest_agent_pages", "discover_agent_files"]
