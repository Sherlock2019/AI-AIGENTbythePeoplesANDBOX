#!/usr/bin/env python3
"""
Concatenate the primary agent Streamlit pages into a single file.

Usage:
    python scripts/cat_agents.py /tmp/all_agents.py

If no output path is supplied, the script prints the merged content to stdout.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

AGENT_PATHS = [
    Path("services/ui/pages/credit_appraisal.py"),
    Path("services/ui/pages/asset_appraisal.py"),
    Path("services/ui/pages/anti_fraud_kyc.py"),
]


def read_agent(path: Path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        raise SystemExit(f"Missing agent file: {path}")


def merge_agents() -> str:
    chunks = []
    for path in AGENT_PATHS:
        chunks.append("#" * 120)
        chunks.append(f"# SOURCE: {path}")
        chunks.append("#" * 120)
        chunks.append(read_agent(path))
        chunks.append("")  # spacer newline
    return "\n".join(chunks).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Concatenate agent pages into one file.")
    parser.add_argument(
        "output",
        nargs="?",
        help="Optional destination file. If omitted, merged source is printed to stdout.",
    )
    args = parser.parse_args()

    merged = merge_agents()

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(merged)
        print(f"Wrote merged agents to {out_path}")
    else:
        sys.stdout.write(merged)


if __name__ == "__main__":
    main()
