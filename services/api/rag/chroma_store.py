"""ChromaDB helper utilities for the sandbox chatbot."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

# Disable noisy telemetry + remote capture by default.
os.environ.setdefault("CHROMA_TELEMETRY_DISABLED", "true")

import chromadb
from chromadb.api.models import Collection

DB_ROOT = Path(__file__).resolve().parent / "rag_db"
DB_ROOT.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = os.getenv("SANDBOX_RAG_COLLECTION", "sandbox_rag")

_CLIENT: Optional[chromadb.PersistentClient] = None
_COLLECTION: Optional[Collection.Collection] = None  # type: ignore[attr-defined]


def reset_collection() -> None:
    """Delete the local Chroma store and clear cached client state."""
    global _CLIENT, _COLLECTION
    _CLIENT = None
    _COLLECTION = None
    if DB_ROOT.exists():
        shutil.rmtree(DB_ROOT, ignore_errors=True)
    DB_ROOT.mkdir(parents=True, exist_ok=True)


def get_collection() -> Collection.Collection:  # type: ignore[attr-defined]
    global _CLIENT, _COLLECTION
    if _COLLECTION is None:
        _CLIENT = chromadb.PersistentClient(path=str(DB_ROOT))
        _COLLECTION = _CLIENT.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _COLLECTION


__all__ = ["get_collection", "reset_collection", "DB_ROOT", "COLLECTION_NAME"]
