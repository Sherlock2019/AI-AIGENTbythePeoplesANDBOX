#!/usr/bin/env python3
"""Ingest CSV outputs into the local RAG store (one-shot)."""
from __future__ import annotations

import argparse
from pathlib import Path

from services.api.rag.ingest import LocalIngestor, discover_csv_files

DEFAULT_DIRS = [
    Path("services/ui/.tmp_runs"),
    Path("services/ui/exports"),
    Path("anti-fraud-kyc-agent/.tmp_runs"),
]


def main():
    parser = argparse.ArgumentParser(description="Send agent CSV outputs to the local RAG store.")
    parser.add_argument("--dirs", nargs="*", type=Path, default=DEFAULT_DIRS, help="Directories to scan.")
    parser.add_argument("--store", type=Path, default=None, help="Optional path for the local store directory.")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows per CSV.")
    parser.add_argument("--dry-run", action="store_true", help="Scan only.")
    args = parser.parse_args()

    ingestor = LocalIngestor(args.store)
    files = discover_csv_files(args.dirs)
    if not files:
        print("No CSV files found.")
        return
    files_processed, vectors = ingestor.ingest_files(
        files,
        max_rows=args.max_rows or 0,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print(f"[dry-run] Would process {files_processed} files.")
    else:
        print(f"Ingested {vectors} vectors from {files_processed} files into the local store.")


if __name__ == "__main__":
    main()
