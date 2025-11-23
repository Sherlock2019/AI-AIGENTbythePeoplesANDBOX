"""Chatbot endpoints backed by Phi-3 via Ollama + Chroma RAG."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from services.api.llm.ollama_client import OllamaError, ollama_generate
from services.api.rag.chroma_store import reset_collection
from services.api.rag.ingest_agents import ingest_agent_pages
from services.api.rag.ingest_csv import (
    ingest_all_csvs,
    ingest_text_blob,
    ingest_uploaded_csv_bytes,
)
from services.api.rag.ingest_docs import ingest_docs
from services.api.rag.run_history import prune_agent_run_history
from services.api.rag.howto_loader import get_howto_snippet
from services.api.rag.retriever import query_rag
from services.api.utils.chatbot_events import log_chatbot_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

_BOOTSTRAPPED = False


class ChatbotRequest(BaseModel):
    question: str = Field(..., min_length=2)
    top_k: int = Field(5, ge=1, le=10)
    agent_id: str | None = Field(default=None, description="Optional persona/agent focus")


class ChatbotResponse(BaseModel):
    answer: str
    sources: List[dict]
    context_used: str


def _ensure_bootstrapped() -> None:
    global _BOOTSTRAPPED
    if not _BOOTSTRAPPED:
        log_chatbot_event("bootstrap.start")
        ingest_all_csvs()
        ingest_agent_pages()
        ingest_docs()
        log_chatbot_event("bootstrap.finish")
        _BOOTSTRAPPED = True


def _build_prompt(context: str, question: str, *, rag_hit: bool) -> str:
    if rag_hit:
        guidance = (
            "You are the AI Sandbox Assistant using Phi-3 via Ollama. "
            "Answer strictly from the CONTEXT provided below. "
            "Do not invent facts outside of that context. "
            "When an agent pipeline has multiple stages, summarize them in order "
            "(Intake → Privacy → Valuation → Human Review → Monitoring → Reporting)."
        )
        context_block = context
    else:
        guidance = (
            "You are the AI Sandbox Assistant using Phi-3 via Ollama. "
            "No relevant documents were retrieved for this question. "
            "You still must answer using your general domain knowledge (credit, asset, fraud ops). "
            "Do NOT reply that you cannot answer. "
            "Give a concise, high-level answer and mention that the RAG store had no matches."
        )
        context_block = "No contextual snippets were retrieved."

    return (
        f"SYSTEM:\n{guidance}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        f"USER:\n{question.strip()}\n\nASSISTANT:"
    )


@router.post("/refresh")
def refresh_rag(reset: bool = False):
    log_chatbot_event("rag.refresh.start", reset=reset)
    reset_collection()
    prune_stats = prune_agent_run_history()
    csv_stats = ingest_all_csvs()
    agent_stats = ingest_agent_pages()
    doc_stats = ingest_docs()
    log_chatbot_event(
        "rag.refresh.finish",
        reset=reset,
        csv_rows=csv_stats.get("rows_indexed", 0),
        agent_chunks=agent_stats.get("rows_indexed", 0),
        doc_chunks=doc_stats.get("rows_indexed", 0),
        pruned=prune_stats.get("entries_removed", 0),
    )
    return {
        "status": "ok",
        "csv": csv_stats,
        "agent_ui": agent_stats,
        "docs": doc_stats,
        "pruned_runs": prune_stats,
    }


@router.post("/ingest")
async def ingest_upload(file: UploadFile = File(...), agent_id: str | None = None):
    data = await file.read()
    try:
        stats = ingest_uploaded_csv_bytes(data, file.filename, agent_id=agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", **stats}


@router.post("/ingest/file")
async def ingest_any_file(file: UploadFile = File(...), agent_id: str | None = None):
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file.")
    name = file.filename or "upload"
    if name.lower().endswith(".csv"):
        try:
            stats = ingest_uploaded_csv_bytes(payload, name, agent_id=agent_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", **stats}
    try:
        text = payload.decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Decode failed: {exc}") from exc
    stats = ingest_text_blob(text, source=f"upload:{name}", agent_id=agent_id)
    return {"status": "ok", **stats}


@router.post("/chat", response_model=ChatbotResponse)
def chat_with_agent(payload: ChatbotRequest):
    _ensure_bootstrapped()
    context, sources, best_score, resolved_agent = query_rag(
        payload.question,
        top_k=payload.top_k,
        agent_id=payload.agent_id,
        min_score=0.30,
    )
    rag_hit = bool(sources)
    howto_snippet = get_howto_snippet(payload.agent_id, payload.question)
    if howto_snippet:
        guide_block = f"Agent Workflow Guide:\n{howto_snippet.strip()}"
        if context:
            context = f"{guide_block}\n\n---\n{context}"
        else:
            context = guide_block
        sources = [{"file": "howto:guide", "score": "1.000"}] + sources
        rag_hit = True
    mode = "rag" if rag_hit else "fallback"
    log_chatbot_event(
        "chat.request",
        agent_id=payload.agent_id or "auto",
        resolved_agent=resolved_agent or payload.agent_id or "auto",
        top_k=payload.top_k,
        mode=mode,
        best_score=best_score,
    )
    prompt = _build_prompt(context if rag_hit else "", payload.question, rag_hit=rag_hit)
    try:
        answer = ollama_generate(prompt)
    except OllamaError as exc:
        logger.error("Phi-3 request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Phi-3/Ollama backend unavailable.") from exc
    log_chatbot_event(
        "chat.answer",
        agent_id=payload.agent_id or "auto",
        resolved_agent=resolved_agent or payload.agent_id or "auto",
        mode=mode,
    )
    return ChatbotResponse(answer=answer, sources=sources, context_used=context if rag_hit else "")
