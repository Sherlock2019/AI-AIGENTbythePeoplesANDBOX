"""Unified chat assistant endpoint backed by local RAG store + CSV fallback."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import requests

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from services.api.rag.embeddings import embed_texts
from services.api.rag.local_store import LocalVectorStore
from services.api.rag.policies_seed import seed_policy_documents
from services.api.rag.howto_loader import get_howto_snippet

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAG_DOC_PATHS = [
    PROJECT_ROOT / "docs" / "unified-theme.md",
    PROJECT_ROOT / "README.md",
]
CSV_SOURCE_DIRS = [
    PROJECT_ROOT / "services" / "ui" / "credit_handoff",
    PROJECT_ROOT / "agents" / "credit_appraisal" / "sample_data",
]
CSV_MAX_FILES = int(os.getenv("CHAT_CSV_MAX_FILES", "6"))
CSV_MAX_ROWS = int(os.getenv("CHAT_CSV_MAX_ROWS", "200"))
VECTOR_CACHE_TTL = int(os.getenv("CHAT_RAG_REFRESH_SECONDS", "60"))
STATIC_SNIPPETS = [
    {
        "id": "fraud_flow",
        "title": "Anti-Fraud/KYC workflow",
        "text": (
            "Anti-Fraud & KYC agent runs Intake → Privacy → Verification → Fraud rules → "
            "Review → Reporting. Each stage preserves anonymized artifacts so the chatbot "
            "can explain rule breaches or rerun investigations."
        ),
    },
    {
        "id": "asset_vs_credit",
        "title": "Asset vs Credit crossover",
        "text": (
            "Asset appraisal outputs (FMV, encumbrances, comps) are shareable with the "
            "credit agent to justify approvals. Use the assistant to push summaries to "
            "credit or request a unified risk packet."
        ),
    },
]

FAQ_ENTRIES: Dict[str, List[Dict[str, str]]] = {
    "anti_fraud_kyc": [
        {"question": "How do I rerun the fraud rules for the current borrower?", "answer": "Use the stage menu → Fraud → Re-run or ask the assistant to trigger `rerun_stage`."},
        {"question": "What does the privacy scrub remove?", "answer": "PII columns (SSN, phone, address) and document metadata before sharing artifacts."},
        {"question": "How can I export the KYC audit trail?", "answer": "Go to Report tab or ask the assistant to generate the audit package for the recent run."},
        {"question": "Where do I see sanction list hits?", "answer": "Fraud tab → Alerts panel; the assistant can summarize `sanctions_hits` as well."},
    ],
    "default": [
        {"question": "Explain current stage", "answer": "Assistant walks through the stage steps."},
        {"question": "How do I share outputs with another agent?", "answer": "Use orchestration actions or ask assistant to handoff artifacts."},
    ],
}

RAG_TOP_K = int(os.getenv("CHAT_RAG_TOP_K", "3"))
_store_env = os.getenv("LOCAL_RAG_STORE")
LOCAL_STORE = LocalVectorStore(Path(_store_env) if _store_env else None)
seed_policy_documents(LOCAL_STORE)

_VECTOR_CACHE: Dict[str, Any] = {"built_at": 0.0, "vectorizer": None, "matrix": None, "docs": []}

def _normalize_base(url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    if not url:
        return "http://localhost:11434"
    parsed = urlsplit(url)
    path = parsed.path or ""
    if path.startswith("/api/"):
        path = ""
    elif "/api/" in path:
        path = path.split("/api/", 1)[0]
    rebuilt = parsed._replace(path=path, query="", fragment="")
    base = urlunsplit(rebuilt).rstrip("/")
    return base or "http://localhost:11434"


OLLAMA_URL = _normalize_base(os.getenv("OLLAMA_URL", "http://localhost:11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2:9b")
USE_OLLAMA = os.getenv("CHAT_USE_MISTRAL", "1") not in {"0", "false", "False"}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "context"] = "user"
    content: str = ""
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    page_id: str = Field(..., min_length=2)
    context: Dict[str, Any] = Field(default_factory=dict)
    history: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    mode: str
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str
    context_summary: List[str] = Field(default_factory=list)
    retrieved: List[Dict[str, Any]] = Field(default_factory=list)
    faq_options: List[str] = Field(default_factory=list)


def _load_documents() -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for snippet in STATIC_SNIPPETS:
        docs.append(snippet)

    for path in RAG_DOC_PATHS:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            docs.append(
                {
                    "id": path.name,
                    "title": path.name.replace("_", " "),
                    "text": text,
                }
            )
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)

    docs.extend(_load_csv_documents())
    return docs


def _load_csv_documents() -> List[Dict[str, Any]]:
    csv_docs: List[Dict[str, Any]] = []
    highlight_cols = [
        "application_id",
        "decision",
        "score",
        "reason",
        "pd",
        "ltv",
        "dti",
        "stage",
        "status",
    ]
    for directory in CSV_SOURCE_DIRS:
        if not directory.exists() or not directory.is_dir():
            continue
        try:
            candidates = sorted(
                (p for p in directory.glob("*.csv") if p.is_file()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:CSV_MAX_FILES]
        except Exception as exc:
            logger.warning("Failed to enumerate csv dir %s: %s", directory, exc)
            continue
        for path in candidates:
            try:
                df = pd.read_csv(path)
            except Exception as exc:
                logger.warning("Failed to read csv %s: %s", path, exc)
                continue
            if df.empty:
                continue
            subset = df.head(CSV_MAX_ROWS)
            for idx, (_, row) in enumerate(subset.iterrows()):
                kv_pairs = []
                highlights = {}
                for col, value in row.items():
                    if pd.isna(value):
                        continue
                    text_value = str(value)
                    kv_pairs.append(f"{col}={text_value}")
                    if col in highlight_cols and col not in highlights:
                        highlights[col] = text_value
                if not kv_pairs:
                    continue
                csv_docs.append(
                    {
                        "id": f"{path.stem}-{idx}",
                        "title": f"{path.stem} row {idx + 1}",
                        "text": "; ".join(kv_pairs),
                        "source": str(path),
                        "meta": highlights,
                    }
                )
    return csv_docs


def _build_vector_store() -> Tuple[Optional[TfidfVectorizer], Optional[Any], List[Dict[str, Any]]]:
    docs = _load_documents()
    if not docs:
        return None, None, []
    texts = [doc["text"] for doc in docs]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix, docs


def _get_vector_store() -> Tuple[Optional[TfidfVectorizer], Optional[Any], List[Dict[str, Any]]]:
    now = time.time()
    global _VECTOR_CACHE
    built_at = _VECTOR_CACHE.get("built_at", 0.0)
    vectorizer = _VECTOR_CACHE.get("vectorizer")
    if not vectorizer or (now - built_at) > VECTOR_CACHE_TTL:
        vectorizer, matrix, docs = _build_vector_store()
        _VECTOR_CACHE = {
            "built_at": now,
            "vectorizer": vectorizer,
            "matrix": matrix,
            "docs": docs,
        }
    return _VECTOR_CACHE["vectorizer"], _VECTOR_CACHE["matrix"], _VECTOR_CACHE["docs"]


def _infer_mode(page_id: str, context: Dict[str, Any]) -> str:
    lowered = page_id.lower()
    if "asset" in lowered:
        return "Asset"
    if "credit" in lowered:
        return "Credit"
    if "fraud" in lowered or "kyc" in lowered:
        return "Fraud/KYC"
    if "unified" in lowered or "supervisor" in lowered:
        return "Unified Risk"
    if context.get("agent_type"):
        return str(context["agent_type"]).title()
    return "Assistant"


def _resolve_agent_key(page_id: str) -> str | None:
    lowered = (page_id or "").lower()
    if "asset" in lowered:
        return "asset_appraisal"
    if "credit" in lowered and "scoring" not in lowered:
        return "credit_appraisal"
    if "scoring" in lowered:
        return "credit_scoring"
    if "fraud" in lowered or "kyc" in lowered:
        return "anti_fraud_kyc"
    return None


def _summarize_context(context: Dict[str, Any]) -> List[str]:
    summary: List[str] = []
    stage = context.get("stage") or context.get("asset_stage") or context.get("credit_stage")
    if stage:
        summary.append(f"Stage: {stage}")
    dataset = context.get("dataset_name") or context.get("active_dataset")
    if dataset:
        summary.append(f"Dataset: {dataset}")
    entity = context.get("entity_name") or context.get("selected_case")
    if entity:
        summary.append(f"Entity: {entity}")
    last_error = context.get("last_error")
    if last_error:
        summary.append(f"Error: {str(last_error)[:120]}")
    run_id = context.get("run_id") or context.get("training_id")
    if run_id:
        summary.append(f"Run ID: {run_id}")
    return summary[:4]


def _retrieve_store_docs(question: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not LOCAL_STORE.available or not question:
        return []
    ctx_blob = " ".join(f"{k}:{v}" for k, v in context.items() if isinstance(v, (str, int, float)))
    query = f"{question}\n{ctx_blob}"
    try:
        vector = embed_texts([query])[0]
    except Exception as exc:
        logger.warning("Failed to embed query for local store: %s", exc)
        return []
    policy_hits = LOCAL_STORE.query(vector, top_k=RAG_TOP_K, namespace="policies")
    general_hits = LOCAL_STORE.query(vector, top_k=RAG_TOP_K)

    policy_entries: List[Dict[str, Any]] = []
    merged: Dict[str, Dict[str, Any]] = {}

    def _add_entry(hit: Dict[str, Any], boost: float = 1.0) -> Dict[str, Any]:
        entry_id = hit.get("id") or hit.get("title") or hit.get("source") or f"local_doc_{len(merged)}"
        score = float(hit.get("score") or 0.0) * boost
        snippet = hit.get("snippet") or hit.get("text", "")
        record = {
            "id": entry_id,
            "title": hit.get("title") or hit.get("id") or "match",
            "score": score,
            "snippet": (snippet or "")[:600],
            "source": hit.get("source"),
            "metadata": hit,
        }
        existing = merged.get(entry_id)
        if not existing or score > existing["score"]:
            merged[entry_id] = record
        return merged[entry_id]

    for hit in policy_hits:
        policy_entries.append(_add_entry(hit, boost=1.25))

    for hit in general_hits:
        if hit.get("namespace") == "policies":
            continue
        _add_entry(hit)

    ranked = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
    results = ranked[:RAG_TOP_K]

    if policy_entries and not any((entry and entry.get("metadata", {}).get("namespace") == "policies") for entry in results):
        top_policy = max(
            (entry for entry in policy_entries if entry),
            key=lambda item: item["score"],
            default=None,
        )
        if top_policy:
            results = [top_policy] + [item for item in results if item["id"] != top_policy["id"]]
            results = results[:RAG_TOP_K]

    return results


def _retrieve_fallback_docs(question: str, context: Dict[str, Any], top_k: int = RAG_TOP_K) -> List[Dict[str, Any]]:
    vectorizer, doc_matrix, doc_library = _get_vector_store()
    if not question or not vectorizer or doc_matrix is None:
        return []
    ctx_blob = " ".join(f"{k}:{v}" for k, v in context.items() if isinstance(v, (str, int, float)))
    query = f"{question}\n{ctx_blob}"
    try:
        q_vec = vectorizer.transform([query])
        scores = cosine_similarity(q_vec, doc_matrix).ravel()
    except Exception as exc:
        logger.warning("Vector retrieval failed: %s", exc)
        return []
    idx = scores.argsort()[::-1][:top_k]
    results: List[Dict[str, Any]] = []
    for rank in idx:
        if scores[rank] <= 0:
            continue
        doc = doc_library[rank]
        excerpt = doc["text"].strip().splitlines()
        snippet = " ".join(excerpt[:6])[:600]
        results.append(
            {
                "id": doc.get("id", f"doc_{rank}"),
                "title": doc.get("title", doc.get("id", f"Doc {rank+1}")),
                "score": float(scores[rank]),
                "snippet": snippet,
                "source": doc.get("source"),
                "metadata": doc.get("meta", {}),
            }
        )
    return results


def _dedupe_docs(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for doc in items:
        doc_id = doc.get("id") or doc.get("title")
        if not doc_id:
            continue
        if doc_id in seen:
            continue
        deduped.append(doc)
        seen.add(doc_id)
        if len(deduped) >= limit:
            break
    return deduped


def _compose_lightweight_reply(payload: ChatRequest, retrieved: List[Dict[str, Any]], mode: str) -> str:
    if not retrieved:
        return (
            f"{mode} assistant couldn't find any matches for '{payload.message}'. "
            "Ingest fresh agent docs or CSV outputs via the local RAG scripts "
            "(seed_local_rag_from_csv.py / seed_local_rag_agent_docs.py) and try again."
        )

    intro = (
        f"Here's what I can see from a {mode.lower()} perspective after checking {len(retrieved)} matching files. "
        "I'm summarizing the most relevant snippets below:"
    )

    def _summarize_doc(doc: Dict[str, Any]) -> str:
        title = doc.get("title") or doc.get("id", "match")
        snippet = (doc.get("snippet") or "").replace("\n", " ").strip()
        meta = doc.get("metadata") or {}
        highlights = []
        for field in ("application_id", "borrower", "decision", "score", "pd", "ltv", "dti"):
            value = meta.get(field)
            if value:
                highlights.append(f"{field}={value}")
        highlight_text = ", ".join(highlights)
        pieces = []
        if highlight_text:
            pieces.append(highlight_text)
        if snippet:
            pieces.append(snippet)
        detail = " — ".join(pieces) if pieces else "See linked document for details."
        source = Path(doc["source"]).name if doc.get("source") else None
        source_note = f" (source: {source})" if source else ""
        return f"{title}: {detail[:400]}{source_note}"

    detail_sentences = [
        _summarize_doc(doc)
        for doc in retrieved[:3]
    ]
    if len(retrieved) > 3:
        detail_sentences.append(
            f"There are {len(retrieved) - 3} more matches in the retrieval panel if you need deeper evidence."
        )

    closing = (
        "Let me know if you want a deeper dive into any borrower, need another dataset ingested, "
        "or want me to push this summary to another agent."
    )

    return " ".join([intro] + detail_sentences + [closing])


def _maybe_generate_llm_reply(payload: ChatRequest, retrieved: List[Dict[str, Any]], mode: str) -> Optional[str]:
    if not USE_OLLAMA or not OLLAMA_MODEL:
        return None
    context_blocks: List[str] = []
    howto_added = 0
    general_added = 0
    for doc in retrieved:
        snippet = (doc.get("snippet") or doc.get("text") or "").strip()
        title = doc.get("title") or doc.get("id", "match")
        namespace = (doc.get("metadata") or {}).get("namespace")
        if namespace == "howto":
            if howto_added >= 2:
                continue
            context_blocks.append(f"[HOW-TO] {title}\n{snippet}")
            howto_added += 1
        else:
            if general_added >= 5:
                continue
            context_blocks.append(f"[{title}]\n{snippet}")
            general_added += 1
        if general_added >= 5 and howto_added >= 2:
            break
    if not context_blocks:
        context_blocks = ["No supporting documents were retrieved for this question."]
    elif howto_added:
        context_blocks.insert(0, "Refer to the agent workflow guide below:")
    context_blob = "\n\n".join(context_blocks)
    system_prompt = (
        "You are a banking AI assistant specialized in "
        f"{mode}. Answer strictly using the supplied context. "
        "Cite document titles inline where helpful and keep responses concise (2-4 sentences). "
        "If the context explicitly says none was retrieved, you must still answer using your base knowledge. "
        "Do NOT reply that you cannot answer; instead provide a best-effort explanation and state that RAG had no matches."
    )
    user_prompt = (
        f"Question: {payload.message}\n\nContext:\n{context_blob}\n\n"
        "Answer:"
    )
    try:
        resp = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.2},
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message") or data.get("messages")
        content = None
        if isinstance(message, dict):
            content = message.get("content")
        elif isinstance(message, list):
            for entry in reversed(message):
                if isinstance(entry, dict) and entry.get("role") == "assistant":
                    content = entry.get("content")
                    break
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception as exc:
        logger.warning("LLM generate failed: %s", exc)
    return None


def _suggest_actions(req: ChatRequest) -> List[Dict[str, Any]]:
    text = req.message.lower()
    actions: List[Dict[str, Any]] = []

    def _action(label: str, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "label": label,
            "command": command,
            "payload": payload or {},
        }

    if any(word in text for word in ("rerun", "re-run", "retry")):
        actions.append(_action("Re-run current stage", "rerun_stage", {"stage": req.context.get("stage")}))
    if "promote" in text and "model" in text:
        actions.append(_action("Promote model to production", "promote_model", {"model": req.context.get("selected_model")}))
    if "report" in text or "summary" in text:
        actions.append(_action("Generate unified report", "generate_report", {"page_id": req.page_id}))
    if "handoff" in text or "credit" in text and "asset" in req.page_id:
        actions.append(_action("Send results to credit agent", "handoff_credit", {"from": req.page_id}))
    if not actions:
        actions.append(_action("Explain current step", "explain_stage", {"stage": req.context.get("stage")}))
    return actions


def _faq_for_page(page_id: str) -> List[str]:
    lowered = page_id.lower()
    if "fraud" in lowered or "kyc" in lowered:
        bucket = FAQ_ENTRIES.get("anti_fraud_kyc", [])
    else:
        bucket = FAQ_ENTRIES.get("default", [])
    return [entry["question"] for entry in bucket][:5]


@router.post("/v1/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    mode = _infer_mode(payload.page_id, payload.context)
    context_summary = _summarize_context(payload.context)
    agent_key = _resolve_agent_key(payload.page_id)
    howto_snippet = get_howto_snippet(agent_key, payload.message)
    howto_doc = (
        {
            "id": f"{agent_key or 'agent'}_howto",
            "title": "Agent Workflow Guide",
            "score": 1.35,
            "snippet": howto_snippet,
            "source": "howto",
            "metadata": {"namespace": "howto", "agent": agent_key},
        }
        if howto_snippet
        else None
    )
    store_docs = _retrieve_store_docs(payload.message, payload.context)
    if not store_docs:
        store_docs = _retrieve_fallback_docs(payload.message, payload.context)
    combined: List[Dict[str, Any]] = []
    if howto_doc:
        combined.append(howto_doc)
    combined.extend(store_docs)
    retrieved = _dedupe_docs(combined, RAG_TOP_K)
    reply_text = _maybe_generate_llm_reply(payload, retrieved, mode) or _compose_lightweight_reply(payload, retrieved, mode)

    actions = _suggest_actions(payload)
    timestamp = datetime.now(timezone.utc).isoformat()
    faq_options = _faq_for_page(payload.page_id)

    return ChatResponse(
        reply=reply_text,
        mode=mode,
        actions=actions,
        timestamp=timestamp,
        context_summary=context_summary,
        retrieved=retrieved,
        faq_options=faq_options,
    )
