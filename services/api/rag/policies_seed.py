"""Seed unified credit & asset policies into the local vector store."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Union

from services.api.rag.embeddings import embed_texts
from services.api.rag.local_store import LocalVectorStore
from services.api.rag.policies_text import CREDIT_ASSET_POLICY_TEXT
from services.api.rag.utils import chunk_text

if TYPE_CHECKING:
    from services.api.rag.chroma_store import ChromaVectorStore

# Type hint for store parameter (supports both LocalVectorStore and ChromaVectorStore)
VectorStore = Union[LocalVectorStore, "ChromaVectorStore"]

POLICY_NAMESPACE = "policies"
POLICY_TITLE = "Unified Credit & Asset Appraisal Policy"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def _infer_section(chunk: str) -> str:
    for line in chunk.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned[0].isdigit() or "Policy" in cleaned or cleaned.startswith(("🏦", "🏡", "🔗", "🔥")):
            return cleaned
    return "Unified Credit & Asset Appraisal Policy"


def _manifest_path(store: VectorStore) -> Path:
    return store.store_dir / "policies_manifest.json"


def _load_manifest(store: VectorStore) -> dict:
    path = _manifest_path(store)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _save_manifest(store: VectorStore, manifest: dict) -> None:
    path = _manifest_path(store)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def seed_policy_documents(store: VectorStore) -> None:
    """Ensure unified policy text is embedded into the local vector store."""
    text = CREDIT_ASSET_POLICY_TEXT.strip()
    if not text:
        return

    manifest = _load_manifest(store)
    current_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if manifest.get("hash") == current_hash and store.namespace_present(POLICY_NAMESPACE):
        return

    store.remove_namespace(POLICY_NAMESPACE)
    chunks: List[str] = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        return

    vectors = embed_texts(chunks)
    version = datetime.now(timezone.utc).isoformat()
    metadata = []
    for idx, chunk in enumerate(chunks):
        metadata.append(
            {
                "id": f"policy_chunk_{idx}",
                "namespace": POLICY_NAMESPACE,
                "source": "policy",
                "title": POLICY_TITLE,
                "version": version,
                "section": _infer_section(chunk),
                "snippet": chunk[:600],
            }
        )

    store.add_vectors(vectors, metadata)
    store.save()
    _save_manifest(store, {"hash": current_hash, "version": version})


__all__ = ["seed_policy_documents"]
