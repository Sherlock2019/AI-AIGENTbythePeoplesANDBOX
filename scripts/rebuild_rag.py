#!/usr/bin/env python3
"""Reset and rebuild the chatbot RAG store."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from services.api.rag.chroma_store import reset_collection  # noqa: E402
from services.api.rag.ingest_agents import ingest_agent_pages  # noqa: E402
from services.api.rag.ingest_csv import ingest_all_csvs, ingest_text_blob  # noqa: E402


TARGET_DIRS = [
    ("./agents", "agents"),
    ("./services/ui/pages", "ui"),
    ("./datasets/csv_uploaded", "csv"),
    ("./docs", "docs"),
]


def ingest_directory(path: str, namespace: str) -> None:
    base = Path(path)
    if not base.exists():
        return
    for file in base.rglob("*"):
        if not file.is_file():
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        ingest_text_blob(text, source=f"{namespace}:{file}", agent_id=namespace)


def main() -> None:
    print("Resetting vector store…")
    reset_collection()
    print("Ingesting CSV artifacts…")
    ingest_all_csvs()
    print("Ingesting agent UI pages…")
    ingest_agent_pages()
    for path, namespace in TARGET_DIRS:
        print(f"Ingesting directory {path} → namespace {namespace}")
        ingest_directory(path, namespace)
    print("RAG rebuild complete.")


if __name__ == "__main__":
    main()
