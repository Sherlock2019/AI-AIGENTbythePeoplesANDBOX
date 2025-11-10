#!/usr/bin/env python3
"""Continuously watch CSV output folders and ingest new files into the local RAG store."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from services.api.rag.ingest import (
    LocalIngestor,
    discover_csv_files,
    load_state,
    save_state,
)

DEFAULT_DIRS = [
    Path("services/ui/.tmp_runs"),
    Path("services/ui/exports"),
    Path("anti-fraud-kyc-agent/.tmp_runs"),
]
STATE_FILE = Path(".rag_ingest_state.json")


def main():
    parser = argparse.ArgumentParser(description="Watch CSV folders and ingest new files into the local RAG store.")
    parser.add_argument("--dirs", nargs="*", type=Path, default=DEFAULT_DIRS)
    parser.add_argument("--store", type=Path, default=None, help="Optional store directory.")
    parser.add_argument("--interval", type=int, default=120, help="Polling interval (seconds).")
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--state-file", type=Path, default=STATE_FILE)
    args = parser.parse_args()

    ingestor = LocalIngestor(args.store)
    state = load_state(args.state_file)

    print(f"Watching {len(args.dirs)} directories. Press Ctrl+C to stop.")
    try:
        while True:
            files = discover_csv_files(args.dirs)
            new_files = []
            for path in files:
                mtime = path.stat().st_mtime
                stored_mtime = state.get(str(path))
                if stored_mtime is None or mtime > stored_mtime:
                    new_files.append(path)
            if new_files:
                print(f"Ingesting {len(new_files)} new files...")
                ingestor.ingest_files(new_files, max_rows=args.max_rows or 0, dry_run=False)
                for path in new_files:
                    state[str(path)] = path.stat().st_mtime
                save_state(args.state_file, state)
            time.sleep(max(args.interval, 5))
    except KeyboardInterrupt:
        print("Watch loop stopped.")


if __name__ == "__main__":
    main()
