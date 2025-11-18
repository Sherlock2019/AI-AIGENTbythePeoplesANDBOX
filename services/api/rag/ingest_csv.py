"""CSV ingestion helpers for the Gemma chatbot RAG store."""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import pandas as pd

from ..utils.chatbot_events import log_chatbot_event
from .chroma_store import get_collection, reset_collection
from .embeddings import embed_texts
from .utils import chunk_text

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAX_ROWS = int(os.getenv("CHATBOT_RAG_MAX_ROWS", "750"))
MAX_FILES_PER_SOURCE = int(os.getenv("CHATBOT_RAG_MAX_FILES_PER_SOURCE", "5"))

DEFAULT_CSV_DIRS: Tuple[Path, ...] = (
    PROJECT_ROOT / ".tmp_runs",
    PROJECT_ROOT / "services" / "ui" / ".tmp_runs",
    PROJECT_ROOT / "anti-fraud-kyc-agent" / ".tmp_runs",
)


def _agent_output_dirs() -> Iterable[Path]:
    agents_root = PROJECT_ROOT / "agents"
    if not agents_root.exists():
        return []
    for csv_path in agents_root.rglob("output"):
        if csv_path.is_dir():
            yield csv_path


def _hash_id(source: str, row_idx: int) -> str:
    return f"{source}-{row_idx}"


def _row_to_text(row: pd.Series) -> str:
    parts = []
    for col, value in row.items():
        if pd.isna(value):
            continue
        parts.append(f"{col}={value}")
    return "; ".join(parts)


def _latest_csvs(root: Path, limit: int) -> List[Path]:
    if not root.exists():
        return []
    if root.is_file() and root.suffix.lower() == ".csv":
        return [root]
    if not root.is_dir():
        return []
    try:
        candidates = sorted(
            (p for p in root.rglob("*.csv") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception as exc:
        logger.warning("Failed to enumerate %s: %s", root, exc)
        return []
    return candidates[:limit] if limit else candidates


def _iter_files(paths: Iterable[Path], limit: int) -> Iterable[Path]:
    for path in paths:
        for candidate in _latest_csvs(path, limit):
            yield candidate


def discover_csv_files(additional: Sequence[Path] | None = None) -> List[Path]:
    files = list(_iter_files(DEFAULT_CSV_DIRS, MAX_FILES_PER_SOURCE))
    for output_dir in _agent_output_dirs():
        files.extend(list(_iter_files([output_dir], MAX_FILES_PER_SOURCE)))
    if additional:
        files.extend(list(_iter_files(additional, MAX_FILES_PER_SOURCE)))
    deduped: Dict[str, Path] = {}
    for path in files:
        deduped[str(path.resolve())] = path
    return list(deduped.values())


def infer_agent_from_path(path: Path) -> str | None:
    lower = str(path).lower()
    if "asset" in lower:
        return "asset_appraisal"
    if "credit" in lower or "score" in lower:
        return "credit_appraisal"
    if "fraud" in lower or "kyc" in lower:
        return "anti_fraud_kyc"
    if "unified" in lower:
        return "unified_risk"
    return None


def _ingest_dataframe(df: pd.DataFrame, *, source: str, agent_id: str | None = None) -> int:
    if df.empty:
        return 0
    working = df.head(MAX_ROWS)
    documents = []
    metadatas = []
    ids = []
    for idx, (_, row) in enumerate(working.iterrows()):
        text = _row_to_text(row)
        if not text:
            continue
        doc_id = _hash_id(source, idx)
        documents.append(text)
        meta = {
            "source": source,
            "row_index": idx,
            "snippet": text[:500],
        }
        if agent_id:
            meta["agent"] = agent_id
        metadatas.append(meta)
        ids.append(doc_id)
    if not documents:
        return 0
    embeddings = embed_texts(documents)
    collection = get_collection()
    try:
        collection.delete(where={"source": source})
    except Exception:
        pass
    try:
        collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    except Exception as exc:
        # Local Chroma stores occasionally corrupt segments; reset and retry once.
        if "StopIteration" in str(exc):
            reset_collection()
            collection = get_collection()
            collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        else:
            raise
    return len(documents)


def _ingest_paths(files: Sequence[Path]) -> Dict[str, int]:
    processed = 0
    rows = 0
    log_chatbot_event("ingest.csv.start", files=len(files))
    for csv_path in files:
        try:
            df = pd.read_csv(csv_path)
        except Exception as exc:
            logger.warning("Failed to ingest %s: %s", csv_path, exc)
            continue
        agent_name = infer_agent_from_path(csv_path)
        ingested = _ingest_dataframe(df, source=str(csv_path), agent_id=agent_name)
        if ingested:
            processed += 1
            rows += ingested
    stats = {"files_processed": processed, "rows_indexed": rows}
    log_chatbot_event("ingest.csv.finish", **stats)
    return stats


def ingest_paths(paths: Sequence[Path]) -> Dict[str, int]:
    return _ingest_paths(list(paths))


def ingest_all_csvs(extra_paths: Sequence[Path] | None = None) -> Dict[str, int]:
    files = discover_csv_files(additional=extra_paths)
    return _ingest_paths(files)


def ingest_text_blob(
    text: str,
    *,
    source: str,
    agent_id: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> Dict[str, int]:
    text = (text or "").strip()
    if not text:
        return {"files_processed": 0, "rows_indexed": 0}

    chunks = chunk_text(
        text,
        chunk_size or int(os.getenv("CHATBOT_RAG_TEXT_CHUNK", "1200")),
        chunk_overlap or int(os.getenv("CHATBOT_RAG_TEXT_OVERLAP", "200")),
    )
    embeddings = embed_texts(chunks)
    collection = get_collection()
    try:
        collection.delete(where={"source": source})
    except Exception:
        pass
    metadatas = [
        {
            "source": source,
            "kind": "upload",
            "agent": agent_id,
            "chunk_index": idx,
            "snippet": chunk[:500],
        }
        for idx, chunk in enumerate(chunks)
    ]
    ids = [f"{source}-{idx}" for idx in range(len(chunks))]
    collection.upsert(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    stats = {"files_processed": 1, "rows_indexed": len(chunks)}
    log_chatbot_event("ingest.upload.text", agent_id=agent_id, **stats)
    return stats


def ingest_uploaded_csv_bytes(payload: bytes, filename: str, agent_id: str | None = None) -> Dict[str, int]:
    try:
        df = pd.read_csv(io.BytesIO(payload))
    except Exception as exc:
        raise ValueError(f"Could not parse CSV '{filename}': {exc}") from exc
    rows = _ingest_dataframe(df, source=f"upload:{filename}", agent_id=agent_id)
    stats = {"files_processed": int(rows > 0), "rows_indexed": rows}
    log_chatbot_event("ingest.upload.csv", agent_id=agent_id, filename=filename, rows=rows)
    return stats


__all__ = [
    "ingest_all_csvs",
    "ingest_uploaded_csv_bytes",
    "ingest_text_blob",
    "discover_csv_files",
    "ingest_paths",
    "infer_agent_from_path",
]
