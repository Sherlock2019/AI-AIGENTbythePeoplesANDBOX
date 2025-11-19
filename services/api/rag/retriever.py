"""Semantic retriever built on top of the ChromaDB collection."""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from .chroma_store import get_collection
from .embeddings import embed_texts


def query_rag(
    question: str,
    *,
    top_k: int = 8,
    agent_id: str | None = None,
    min_score: float = 0.25,
    auto_scope: bool = True,
) -> Tuple[str, List[Dict[str, str]], float, str | None]:
    collection = get_collection()
    if collection.count() == 0:
        return "", [], 0.0, None

    where = {"agent": agent_id} if agent_id else None
    embeddings = embed_texts([question])
    results = collection.query(
        embeddings=embeddings,
        n_results=top_k,
        where=where,
    )
    docs = results.get("documents", [[]])[0] if results.get("documents") else []
    metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
    distances = results.get("distances", [[]])[0] if results.get("distances") else []

    hits: List[Dict[str, str]] = []
    for doc, meta, dist in zip(docs, metadatas, distances):
        if not doc:
            continue
        meta = meta or {}
        src = meta.get("source", "unknown")
        similarity = 1.0 - float(dist or 0.0)
        snippet = meta.get("snippet", doc[:400])
        agent = meta.get("agent")
        label = f"{agent}:{src}" if agent else src
        hits.append(
            {
                "agent": agent,
                "label": label,
                "snippet": snippet,
                "similarity": similarity,
            }
        )

    filtered: List[Dict[str, str]] = [hit for hit in hits if hit["similarity"] >= min_score]
    if not filtered:
        return "", [], 0.0, None

    resolved_agent: str | None = agent_id
    if not resolved_agent and auto_scope:
        non_global: Sequence[Dict[str, str]] = [hit for hit in filtered if hit["agent"]]
        pool: Sequence[Dict[str, str]] = non_global or filtered
        best = max(pool, key=lambda hit: hit["similarity"])
        resolved_agent = best.get("agent")
        # Keep only hits for the resolved agent when available, otherwise keep global hits.
        if resolved_agent:
            filtered = [hit for hit in filtered if hit["agent"] == resolved_agent]
        else:
            filtered = [hit for hit in filtered if not hit["agent"]]
            if not filtered:
                filtered = [best]

    context_chunks = [f"[{hit['label']}] {hit['snippet']}" for hit in filtered]
    sources: List[Dict[str, str]] = [
        {"file": hit["label"], "score": f"{hit['similarity']:.3f}"} for hit in filtered
    ]
    best_score = max(hit["similarity"] for hit in filtered)
    context_text = "\n".join(context_chunks)
    return context_text, sources, best_score, resolved_agent


__all__ = ["query_rag"]
