#!/usr/bin/env python3
"""Ingest agent source files + curated FAQs into the local RAG store."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Dict

from services.api.rag.ingest import LocalIngestor

FAQ_ENTRIES = [
    {
        "agent": "credit",
        "question": "How does the Credit Appraisal agent explain rejections?",
        "answer": "It combines PD, rule breaches, and narrative text so operators know which policy threshold failed.",
    },
    {
        "agent": "asset",
        "question": "What is ai_adjusted value in the Asset Appraisal workflow?",
        "answer": "An AI-adjusted FMV that blends comps, encumbrance detection, and operator overrides to guard against overstated collateral.",
    },
    {
        "agent": "fraud_kyc",
        "question": "How do I rerun the fraud rules for the current borrower?",
        "answer": "Within the Fraud tab or via the chatbot action `rerun_stage`, which replays Stage D against the latest intake artifacts.",
    },
    {
        "agent": "unified",
        "question": "What does unified_risk_decision.json contain?",
        "answer": "Borrower identity verdict, asset FMV/realizable values, credit score + PD, consolidated risk tier, final approve/review/reject, reason codes, and evidence pointers.",
    },
]


AGENT_KEYWORDS = {
    "credit": ["credit"],
    "asset": ["asset"],
    "fraud_kyc": ["fraud", "kyc"],
    "unified": ["unified"],
}


def discover_agent_files() -> List[tuple[Path, str]]:
    root = Path("services/ui/pages")
    if not root.exists():
        return []
    results: List[tuple[Path, str]] = []
    seen: set[Path] = set()
    for path in root.rglob("*.py"):
        if "_old" in path.parts:
            continue
        lower_name = path.name.lower()
        for agent, keywords in AGENT_KEYWORDS.items():
            if any(keyword in lower_name for keyword in keywords):
                if path not in seen:
                    results.append((path, agent))
                    seen.add(path)
                break
    return results


def chunk_text(text: str, *, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Ingest agent docs and FAQs into the local RAG store")
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ingestor = LocalIngestor(args.store)

    chunk_payloads: List[Dict] = []
    agent_files = discover_agent_files()
    if not agent_files:
        print("[warn] No agent files discovered under services/ui/pages/")
    for path, agent in agent_files:
        if not path.exists():
            print(f"[skip] Missing file {path}")
            continue
        text = path.read_text(encoding="utf-8")
        for idx, chunk in enumerate(chunk_text(text)):
            chunk_payloads.append(
                {
                    "id": f"{agent}_src_{idx}",
                    "text": chunk,
                    "metadata": {"source": str(path), "agent": agent, "kind": "source_code"},
                }
            )

    for entry in FAQ_ENTRIES:
        chunk_payloads.append(
            {
                "id": f"faq_{entry['agent']}_{abs(hash(entry['question']))}",
                "text": f"FAQ Question: {entry['question']}\nAnswer: {entry['answer']}",
                "metadata": {"agent": entry["agent"], "kind": "faq"},
            }
        )

    total = ingestor.ingest_text_chunks(chunk_payloads, dry_run=args.dry_run)
    if args.dry_run:
        print(f"[dry-run] Prepared {total} chunks.")
    else:
        print(f"Ingested {total} text chunks into the local store.")


if __name__ == "__main__":
    main()
