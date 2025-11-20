"""Unified chat assistant endpoint backed by local RAG store + CSV fallback."""
from __future__ import annotations

import logging
import os
import time
import tempfile
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple
from collections import deque

import requests

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from services.api.rag.embeddings import embed_texts, embeddings_available
from services.api.rag.local_store import LocalVectorStore
from services.api.rag.ingest import LocalIngestor
from services.api.middleware.logging_middleware import add_log_entry

# Try to import optional modules
try:
    from services.api.rag.policies_seed import seed_policy_documents
except ImportError:
    seed_policy_documents = None

try:
    from services.api.rag.howto_loader import get_howto_snippet
except ImportError:
    get_howto_snippet = None

# Try to import ChromaDB and reranker (optional enhancements)
try:
    from services.api.rag.chroma_store import ChromaVectorStore
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    ChromaVectorStore = None

try:
    from services.api.rag.reranker import rerank_documents, reranker_available
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False
    rerank_documents = None
    reranker_available = lambda: False

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
RESPONSE_CACHE_TTL = int(os.getenv("CHAT_RESPONSE_CACHE_SECONDS", "300"))  # 5 minutes
RAG_QUALITY_THRESHOLD = float(os.getenv("CHAT_RAG_THRESHOLD", "0.35"))  # Updated from 0.3 to 0.35
MAX_CONVERSATION_HISTORY = int(os.getenv("CHAT_MAX_HISTORY", "10"))  # Last 10 turns

# Response cache: {question_hash: (response, timestamp)}
_response_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
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

RAG_TOP_K = int(os.getenv("CHAT_RAG_TOP_K", "5"))  # Increased from 3 to 5 for better coverage
USE_CHROMADB = os.getenv("USE_CHROMADB", "true").lower() in {"true", "1", "yes"}
USE_RERANKING = os.getenv("USE_RERANKING", "true").lower() in {"true", "1", "yes"}
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "3"))  # After reranking, return top 3

_store_env = os.getenv("LOCAL_RAG_STORE")

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

# Initialize vector store (ChromaDB preferred, fallback to LocalVectorStore)
if USE_CHROMADB and CHROMADB_AVAILABLE:
    try:
        chroma_store_path = Path(_store_env).parent / ".chroma_store" if _store_env else None
        CHROMA_STORE = ChromaVectorStore(chroma_store_path)
        LOCAL_STORE = CHROMA_STORE  # Use ChromaDB as primary store
        logger.info("Using ChromaDB vector store with metadata filtering support")
    except Exception as exc:
        logger.warning(f"ChromaDB initialization failed, falling back to LocalVectorStore: {exc}")
        LOCAL_STORE = LocalVectorStore(Path(_store_env) if _store_env else None)
else:
    LOCAL_STORE = LocalVectorStore(Path(_store_env) if _store_env else None)
    if USE_CHROMADB:
        logger.info("ChromaDB not available, using LocalVectorStore. Install chromadb for metadata filtering.")

# Seed policy documents if available
if seed_policy_documents:
    try:
        seed_policy_documents(LOCAL_STORE)
    except Exception as exc:
        logger.warning(f"Failed to seed policy documents: {exc}")

_VECTOR_CACHE: Dict[str, Any] = {"built_at": 0.0, "vectorizer": None, "matrix": None, "docs": []}

OLLAMA_URL = _normalize_base(os.getenv("OLLAMA_URL", "http://localhost:11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:latest")  # Default to phi3:latest - better instruction following
USE_OLLAMA = os.getenv("CHAT_USE_OLLAMA", "1") not in {"0", "false", "False"}
USE_GEMMA_FALLBACK = os.getenv("CHAT_USE_GEMMA_FALLBACK", "1") not in {"0", "false", "False"}

# Recommended models in priority order (smaller/faster models first for CPU)
RECOMMENDED_MODELS = ["gemma2:2b", "phi3", "mistral", "gemma2:9b"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system", "context"] = "user"
    content: str = ""
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    page_id: str = Field(..., min_length=2)
    context: Dict[str, Any] = Field(default_factory=dict)
    history: List[ChatMessage] = Field(default_factory=list)
    model: Optional[str] = Field(default=None, description="Ollama model to use for generation")
    agent_id: Optional[str] = Field(default=None, description="Agent ID to use (e.g., 'chatbot' for unified chatbot agent)")


class ChatResponse(BaseModel):
    reply: str
    mode: str
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str
    context_summary: List[str] = Field(default_factory=list)
    retrieved: List[Dict[str, Any]] = Field(default_factory=list)
    faq_options: List[str] = Field(default_factory=list)
    confidence: Optional[str] = Field(default=None, description="Confidence level: high, medium, low")
    confidence_score: Optional[float] = Field(default=None, description="Numeric confidence score (0-1)")
    related_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    source_type: Optional[str] = Field(default=None, description="Source: rag, general_knowledge, cached")


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
    """Retrieve documents from vector store with optional metadata filtering and reranking."""
    if not LOCAL_STORE.available or not question:
        return []
    
    ctx_blob = " ".join(f"{k}:{v}" for k, v in context.items() if isinstance(v, (str, int, float)))
    query = f"{question}\n{ctx_blob}"
    
    try:
        vector = embed_texts([query])[0]
    except Exception as exc:
        logger.warning("Failed to embed query for local store: %s", exc)
        return []
    
    # Build metadata filter if using ChromaDB
    filter_dict = None
    if USE_CHROMADB and CHROMADB_AVAILABLE and isinstance(LOCAL_STORE, ChromaVectorStore):
        # Filter by agent_type if available in context
        agent_type = context.get("agent_type")
        if agent_type:
            filter_dict = {"agent_type": str(agent_type)}
    
    # Query vector store (retrieve more for reranking if enabled)
    retrieve_k = RAG_TOP_K * 2 if USE_RERANKING and reranker_available() else RAG_TOP_K
    
    # Try to query policies namespace if available, otherwise use general query
    policy_hits = []
    general_hits = []
    
    if USE_CHROMADB and CHROMADB_AVAILABLE and isinstance(LOCAL_STORE, ChromaVectorStore):
        # ChromaDB supports namespace filtering
        try:
            policy_hits = LOCAL_STORE.query(vector, top_k=RAG_TOP_K, namespace="policies", filter_dict=filter_dict, score_threshold=RAG_QUALITY_THRESHOLD)
        except Exception:
            pass
        general_hits = LOCAL_STORE.query(
            vector,
            top_k=retrieve_k,
            filter_dict=filter_dict,
            score_threshold=RAG_QUALITY_THRESHOLD
        )
    else:
        # LocalVectorStore - try namespace if supported
        try:
            policy_hits = LOCAL_STORE.query(vector, top_k=RAG_TOP_K, namespace="policies")
        except Exception:
            pass
        general_hits = LOCAL_STORE.query(vector, top_k=retrieve_k)
    
    # Merge policy and general hits with boosting
    merged: Dict[str, Dict[str, Any]] = {}
    
    def _add_entry(hit: Dict[str, Any], boost: float = 1.0) -> Dict[str, Any]:
        entry_id = hit.get("id") or hit.get("title") or hit.get("source") or f"local_doc_{len(merged)}"
        score = float(hit.get("score") or 0.0) * boost
        snippet = hit.get("snippet") or hit.get("text", "")
        record = {
            "id": entry_id,
            "title": hit.get("title") or hit.get("id", "match"),
            "score": score,
            "snippet": (snippet or "")[:600],
            "source": hit.get("source"),
            "metadata": hit,
        }
        existing = merged.get(entry_id)
        if not existing or score > existing["score"]:
            merged[entry_id] = record
        return merged[entry_id]
    
    # Add policy hits with boost
    for hit in policy_hits:
        _add_entry(hit, boost=1.25)
    
    # Add general hits (skip if already in policies)
    for hit in general_hits:
        if hit.get("namespace") == "policies":
            continue
        _add_entry(hit)
    
    results = sorted(merged.values(), key=lambda item: item["score"], reverse=True)
    
    # Apply reranking if enabled
    if USE_RERANKING and reranker_available() and results:
        try:
            logger.debug(f"Reranking {len(results)} documents")
            results = rerank_documents(question, results, top_k=RERANK_TOP_K)
            logger.debug(f"Reranking complete, returning top {len(results)} documents")
        except Exception as exc:
            logger.warning(f"Reranking failed, using original results: {exc}")
    
    # Ensure top policy is included if available
    if policy_hits and not any((entry and entry.get("metadata", {}).get("namespace") == "policies") for entry in results[:RAG_TOP_K]):
        top_policy = max(
            (_add_entry(hit, boost=1.25) for hit in policy_hits),
            key=lambda item: item["score"],
            default=None,
        )
        if top_policy:
            results = [top_policy] + [item for item in results if item["id"] != top_policy["id"]]
    
    # Return top K results
    return results[:RAG_TOP_K]


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


def _clean_code_artifacts(text: str) -> str:
    """Remove code artifacts and extract clean text from snippets."""
    if not text:
        return ""
    
    lines = text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip code-only lines
        if stripped.startswith(("st.", "import ", "from ", "def ", "class ", "if ", "elif ", "else:", "return ", "with ", "try:", "except", "finally:", "    ", "\t")):
            # Check if it's a docstring or comment
            if stripped.startswith(('"""', "'''", "#", "###", "##")):
                # Keep docstrings and comments, but clean them
                cleaned = stripped.lstrip('#').lstrip('*').lstrip('-').strip()
                if cleaned.startswith('"""') or cleaned.startswith("'''"):
                    # Extract docstring content
                    cleaned = cleaned.strip('"""').strip("'''").strip()
                if cleaned and len(cleaned) > 10:
                    cleaned_lines.append(cleaned)
            continue
        
        # Skip lines that are mostly code
        if any(char in stripped for char in ['(', ')', '[', ']', '{', '}']) and len(stripped) < 50:
            # Might be code, but check if it's meaningful text
            if not any(keyword in stripped.lower() for keyword in ["def ", "class ", "import ", "from ", "return ", "="]):
                # Could be meaningful, keep it
                if len(stripped) > 15:
                    cleaned_lines.append(stripped)
            continue
        
        # Keep meaningful text lines
        if len(stripped) > 15 and not stripped.startswith(("st.", "import ", "from ", "def ", "class ")):
            # Remove markdown code markers
            cleaned = stripped.lstrip('#').lstrip('*').lstrip('-').lstrip('1234567890.').strip()
            if cleaned and len(cleaned) > 10:
                cleaned_lines.append(cleaned)
    
    # Join and clean up
    cleaned_text = " ".join(cleaned_lines)
    
    # Remove common code patterns
    cleaned_text = cleaned_text.replace("st.title(", "").replace("st.markdown(", "")
    cleaned_text = cleaned_text.replace('"""', "").replace("'''", "")
    cleaned_text = cleaned_text.replace("with tab_", "").replace("with st.", "")
    
    # Remove excessive whitespace
    cleaned_text = " ".join(cleaned_text.split())
    
    return cleaned_text[:500]  # Limit length


def _extract_meaningful_text(snippet: str) -> str:
    """Extract meaningful text from code snippets (docstrings, comments, markdown)."""
    # Use the improved cleaning function
    return _clean_code_artifacts(snippet)


def _extract_clean_answer(snippet: str, question: str) -> Optional[str]:
    """Extract a clean answer from a snippet that directly addresses the question."""
    if not snippet or not question:
        return None
    
    question_lower = question.lower()
    question_keywords = [w for w in question_lower.split() if len(w) > 3]
    
    # Clean the snippet
    cleaned = _clean_code_artifacts(snippet)
    if not cleaned or len(cleaned) < 20:
        return None
    
    # Look for sentences that contain question keywords
    sentences = [s.strip() for s in cleaned.split('.') if s.strip() and len(s.strip()) > 20]
    
    # Score sentences by relevance
    scored_sentences = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        score = sum(1 for keyword in question_keywords if keyword in sentence_lower)
        if score > 0:
            scored_sentences.append((score, sentence))
    
    # Sort by relevance and return top sentences
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    
    if scored_sentences:
        # Return top 2-3 most relevant sentences
        top_sentences = [s for _, s in scored_sentences[:3]]
        return ". ".join(top_sentences) + "."
    
    # Fallback: return first meaningful sentence
    if sentences:
        return sentences[0] + "."
    
    return None


def _compose_lightweight_reply(payload: ChatRequest, retrieved: List[Dict[str, Any]], mode: str) -> str:
    """Compose a clean, readable reply based on retrieved documents with banking knowledge fallback."""
    question_lower = payload.message.lower()
    is_banking_terms = any(term in question_lower for term in ["pd", "dti", "ltv", "ndi", "fmv", "probability of default", "debt to income", "loan to value"])
    is_definition_question = any(term in question_lower for term in ["define", "definition", "what is", "what are", "explain", "lexical", "terms"])
    
    # Banking definitions to include if relevant
    banking_defs = {}
    if is_banking_terms:
        banking_defs = {
            "pd": "**PD (Probability of Default)**: The likelihood that a borrower will fail to repay a loan, typically expressed as a percentage (0-100%). Higher PD indicates higher risk.",
            "dti": "**DTI (Debt-to-Income Ratio)**: A borrower's total monthly debt payments divided by their gross monthly income, expressed as a percentage. Formula: (Total Monthly Debt / Gross Monthly Income) × 100. Lower DTI is better (typically <43% for approval).",
            "ltv": "**LTV (Loan-to-Value Ratio)**: The ratio of a loan amount to the appraised value of the collateral, expressed as a percentage. Formula: (Loan Amount / Collateral Value) × 100. Lower LTV is safer (typically <80% for conventional loans).",
            "ndi": "**NDI (Net Disposable Income)**: Income remaining after all expenses and debt obligations. Used to assess repayment capacity.",
            "fmv": "**FMV (Fair Market Value)**: The estimated market value of an asset based on comparable sales and market conditions.",
        }
    
    if not retrieved:
        if is_banking_terms and is_definition_question:
            definitions = [
                banking_defs[term]
                for term in ["pd", "dti", "ltv", "ndi", "fmv"]
                if term in question_lower and term in banking_defs
            ]
            if definitions:
                return (
                    "**Executive Summary:** Core banking terms defined for your request.\n\n"
                    "**Key Points:**\n"
                    + "\n".join(f"- {definition}" for definition in definitions)
                    + "\n\n📘 *Source: Assistant general knowledge base. Upload artifacts for richer, document-grounded answers.*"
                )
        return (
            "**Executive Summary:** No documents matched your question in the current knowledge base.\n\n"
            "**Key Points:**\n"
            "- Upload additional PDFs, CSVs, or notes so I can cite them directly.\n"
            "- Rephrase the prompt with more context (asset ID, borrower name, stage, etc.).\n"
            "- Specify which agent or workflow you’d like me to reference.\n\n"
            "📘 *Answer generated from the assistant’s core knowledge base.*"
        )

    # Try to extract clean answers from retrieved documents
    clean_answers = []
    for doc in retrieved[:5]:  # Check more docs
        snippet = (doc.get("snippet") or doc.get("text") or "").strip()
        if not snippet:
            continue
        
        # Try to extract a clean answer
        answer = _extract_clean_answer(snippet, payload.message)
        if answer:
            clean_answers.append(answer)
    
    key_points: List[str] = []
    summary_sentence = (
        f"{mode} assistant found {len(retrieved)} high-confidence snippet(s) aligned with your question."
    )
    
    if clean_answers:
        for doc, answer in zip(retrieved[: len(clean_answers)], clean_answers):
            label = doc.get("title") or doc.get("id", "Insight")
            answer_clean = answer.strip().rstrip(".!?")
            key_points.append(f"- **{label}** — {answer_clean}.")
    elif cleaned_snippets:
        for doc, snippet in zip(retrieved[: len(cleaned_snippets)], cleaned_snippets):
            label = doc.get("title") or doc.get("id", "Insight")
            snippet_clean = snippet.strip().rstrip(".!?")
            key_points.append(f"- **{label}** — {snippet_clean}.")
    
    # Fallback: use cleaned snippets with better formatting
    cleaned_snippets = []
    for doc in retrieved[:3]:
        snippet = (doc.get("snippet") or doc.get("text") or "").strip()
        cleaned = _clean_code_artifacts(snippet)
        if cleaned and len(cleaned) > 30:
            cleaned_snippets.append(cleaned[:400])  # Increased limit
    
    if not key_points:
        for doc in retrieved[:3]:
            snippet = _clean_code_artifacts((doc.get("snippet") or doc.get("text") or "")[:400])
            if snippet:
                label = doc.get("title") or doc.get("id", "Insight")
                key_points.append(f"- **{label}** — {snippet.strip().rstrip('.!?')}." )
    
    if is_banking_terms and is_definition_question:
        for term, definition in banking_defs.items():
            if term in question_lower:
                key_points.append(f"- {definition}")
    
    if not key_points:
        key_points.append("- No clean text fragments were available even though documents were retrieved. Consider uploading clearer notes or asking for a different angle.")
    
    source_lines = [
        f"- {doc.get('title') or doc.get('id')} (score {float(doc.get('score') or 0.0):.2f})"
        for doc in retrieved[:RAG_TOP_K]
    ]
    
    response = f"**Executive Summary:** {summary_sentence}\n\n**Key Points:**\n" + "\n".join(key_points)
    
    if source_lines:
        response += "\n\n**Source Highlights:**\n" + "\n".join(source_lines)
    
    return response[:1200] + ("..." if len(response) > 1200 else "")


def _maybe_generate_llm_reply(payload: ChatRequest, retrieved: List[Dict[str, Any]], mode: str, model_name: Optional[str] = None, conversation_history: Optional[str] = None, initial_answer: Optional[str] = None) -> Optional[str]:
    """Generate LLM reply using RAG context. Prioritizes RAG data."""
    model_to_use = model_name or payload.model or OLLAMA_MODEL
    if not USE_OLLAMA or not model_to_use or not retrieved:
        logger.debug("Skipping LLM generation: USE_OLLAMA=%s, model=%s, retrieved=%d", USE_OLLAMA, model_to_use, len(retrieved))
        return None
    
    # Filter and extract meaningful content from snippets
    filtered_retrieved = []
    for doc in retrieved[:5]:
        snippet = (doc.get("snippet") or doc.get("text") or "").strip()
        score = doc.get("score", 0.0)
        
        # Extract meaningful text even from code snippets
        meaningful_text = _extract_meaningful_text(snippet)
        if not meaningful_text:
            meaningful_text = snippet  # Fallback to original
        
        # Only skip if truly empty or very low relevance
        if len(meaningful_text) > 30 and score > 0.1:
            # Create a modified doc with extracted text
            modified_doc = dict(doc)
            modified_doc["snippet"] = meaningful_text
            modified_doc["text"] = meaningful_text
            filtered_retrieved.append(modified_doc)
    
    # Use filtered or fall back to original if all were filtered
    docs_to_use = filtered_retrieved if filtered_retrieved else retrieved[:2]
    
    context_blocks = []
    for idx, doc in enumerate(docs_to_use, start=1):
        snippet = (doc.get("snippet") or doc.get("text") or "").strip()
        title = doc.get("title") or doc.get("id", f"doc_{idx}")
        score = doc.get("score", 0.0)
        # Clean up snippet - remove excessive code if present
        snippet_clean = snippet
        if "def " in snippet or "import " in snippet:
            # Try to extract meaningful text from code snippets
            lines = snippet.split("\n")
            text_lines = [l for l in lines if not l.strip().startswith(("def ", "import ", "from ", "class ", "if ", "    ")) and len(l.strip()) > 10]
            if text_lines:
                snippet_clean = " ".join(text_lines[:3])  # Reduced from 5 to 3 lines
        # Limit snippet length to reduce prompt size
        snippet_clean = snippet_clean[:400]  # Limit to 400 chars per snippet
        context_blocks.append(f"[{title} (relevance: {score:.3f})]\n{snippet_clean}")
    
    context_blob = "\n\n".join(context_blocks)
    
    # Use provided conversation history or build from payload
    if conversation_history is None:
        conversation_history = _build_conversation_context(payload.history if hasattr(payload, 'history') else [])
    
    # Detect if question is asking for definitions
    question_lower = payload.message.lower()
    is_definition_question = any(term in question_lower for term in ["define", "definition", "what is", "what are", "explain", "lexical", "terms", "meaning"])
    is_banking_terms = any(term in question_lower for term in ["pd", "dti", "ltv", "ndi", "fmv", "probability of default", "debt to income", "loan to value"])
    
    # Add banking definitions if relevant terms detected
    banking_definitions = ""
    if is_banking_terms:
        banking_definitions = (
            "\n\n**Banking Term Definitions (use these if context doesn't provide them):**\n"
            "- **PD (Probability of Default)**: The likelihood that a borrower will fail to repay a loan, typically expressed as a percentage (0-100%). Higher PD indicates higher risk.\n"
            "- **DTI (Debt-to-Income Ratio)**: A borrower's total monthly debt payments divided by their gross monthly income, expressed as a percentage. Formula: (Total Monthly Debt / Gross Monthly Income) × 100. Lower DTI is better (typically <43% for approval).\n"
            "- **LTV (Loan-to-Value Ratio)**: The ratio of a loan amount to the appraised value of the collateral, expressed as a percentage. Formula: (Loan Amount / Collateral Value) × 100. Lower LTV is safer (typically <80% for conventional loans).\n"
            "- **NDI (Net Disposable Income)**: Income remaining after all expenses and debt obligations. Used to assess repayment capacity.\n"
            "- **FMV (Fair Market Value)**: The estimated market value of an asset based on comparable sales and market conditions.\n"
        )
    
    # Improved prompt that handles both documentation and code snippets, with conversation history
    # If initial_answer is provided, enhance it with RAG context
    if initial_answer:
        system_prompt = (
            "You are a knowledgeable banking AI assistant specialized in "
            f"{mode}. Your task is to enhance an existing answer with additional context from the knowledge base.\n\n"
            "**CRITICAL INSTRUCTIONS:**\n"
            "1. **You already have an initial answer** - Use it as the foundation and enhance it with the Retrieved Context below.\n"
            "2. **Supplement with RAG data** - The context below contains relevant information from the knowledge base. Add valuable details that complement your initial answer.\n"
            "3. **Prioritize your knowledge** - Your initial answer comes first, then supplement with RAG context.\n"
        )
        user_prompt_prefix = f"**Initial Answer (use as foundation):**\n{initial_answer}\n\n**Retrieved Context from Knowledge Base:**\n"
    else:
        system_prompt = (
            "You are a knowledgeable banking AI assistant specialized in "
            f"{mode}. Your task is to provide clear, accurate, and well-structured answers.\n\n"
            "**CRITICAL INSTRUCTIONS:**\n"
            "1. **Use your knowledge base FIRST** - Answer the question using your built-in knowledge.\n"
            "2. **Supplement with Retrieved Context** - The context below contains relevant information from the knowledge base. Use it to enhance your answer.\n"
            "3. **Prioritize your knowledge** - Your knowledge comes first, then supplement with RAG context.\n"
        )
        user_prompt_prefix = "**Retrieved Context from Knowledge Base:**\n"
    
    # Add formatting requirements to system prompt
    system_prompt += (
        "\n4. **ALWAYS format with bullet points** - Structure your answer using bullet points (-) for key information. Break down complex answers into clear bullet points.\n"
        "5. **Formatting requirements (MANDATORY):**\n"
        "   - **ALWAYS start with a brief summary sentence, then use bullet points**\n"
        "   - Use **bold** for key terms and acronyms\n"
        "   - Use bullet points (-) for ALL key information, lists, and main points\n"
        "   - Use numbered lists (1., 2., 3.) for steps or sequential information\n"
        "   - Use code blocks (```) for formulas\n"
        "   - Format example: 'Here's the answer:\n- **Key Point 1**: Explanation\n- **Key Point 2**: Explanation\n- **Key Point 3**: Explanation'\n"
        "6. **Response structure:** Start with 1-2 sentences summary, then bullet points for details\n"
        "7. **Be direct** - Answer the question immediately, don't say 'I'm a banking AI assistant' or similar.\n"
        "8. **Use context** - Reference specific information from the retrieved context when available.\n"
        "9. **IMPORTANT**: If your answer doesn't naturally have bullet points, break it down into bullet points anyway. Every answer MUST have bullet points."
    )
    
    history_context = f"\n\n**Previous Conversation:**\n{conversation_history}\n" if conversation_history else ""
    
    user_prompt = (
        f"**User Question:** {payload.message}\n"
        f"{history_context}"
        f"{user_prompt_prefix}{context_blob}\n"
        f"{banking_definitions}\n"
        f"\n**Your Task:** Provide a clear, well-structured answer that:\n"
        f"- Starts with a brief 1-2 sentence summary\n"
        f"- Uses bullet points (-) for ALL key information\n"
        f"- Uses information from the Retrieved Context when relevant\n"
        f"- Combines context with your banking knowledge for completeness\n"
        f"- Formats key terms in **bold**\n"
        f"\n**CRITICAL**: Your answer MUST include bullet points. Format like this:\n"
        f"Brief summary sentence.\n\n"
        f"- **Key Point 1**: Detailed explanation\n"
        f"- **Key Point 2**: Detailed explanation\n"
        f"- **Key Point 3**: Additional details\n"
        f"\n**Answer:**"
    )
    
    try:
        logger.debug("Calling Ollama LLM: model=%s, question=%s", model_to_use, payload.message[:50])
        # Reduced timeout - Ollama can be slow, but we want fast fallback
        resp = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/generate",
            json={
                "model": model_to_use,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 6000, "num_ctx": 6000},  # Lower temp (0.1) for precision, larger context (6000) for banking docs
            },
            timeout=30,  # Increased timeout to allow model to generate complete answers
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response") or data.get("data") or ""
        if isinstance(text, str) and text.strip():
            logger.debug("LLM generated response: %d chars", len(text))
            return text.strip()
        else:
            logger.warning("LLM returned empty response")
    except requests.exceptions.Timeout:
        logger.debug("LLM generate timeout after 10s for model %s - using lightweight reply", model_to_use)
    except requests.exceptions.ConnectionError as exc:
        logger.error("LLM connection error: %s - Is Ollama running at %s?", exc, OLLAMA_URL)
    except requests.exceptions.HTTPError as exc:
        logger.error("LLM HTTP error %d: %s", exc.response.status_code if hasattr(exc, 'response') else 0, exc)
    except Exception as exc:
        logger.error("LLM generate failed: %s (type: %s)", exc, type(exc).__name__)
    return None


def _generate_gemma_fallback(payload: ChatRequest, mode: str, model_name: Optional[str] = None, conversation_history: Optional[str] = None) -> Optional[str]:
    """Generate generic model answer. Mode can be banking-specific or general."""
    model_to_use = model_name or payload.model or OLLAMA_MODEL
    if not USE_OLLAMA or not model_to_use:
        return None
    
    # Use provided conversation history or build from payload
    if conversation_history is None:
        conversation_history = _build_conversation_context(payload.history if hasattr(payload, 'history') else [])
    
    # Enhanced prompt with banking knowledge (if banking mode AND banking question)
    question_lower = payload.message.lower()
    # Check if question is actually banking-related
    is_banking_question = any(term in question_lower for term in [
        "pd", "dti", "ltv", "credit", "loan", "mortgage", "borrower", "debt", "income", 
        "default", "risk", "appraisal", "asset", "fraud", "kyc", "compliance", "banking",
        "financial", "underwriting", "approval", "reject", "score", "probability"
    ])
    # Only use banking mode if both the context suggests banking AND the question is banking-related
    is_banking_mode = is_banking_question and (
        "banking" in mode.lower() or "credit" in mode.lower() or "asset" in mode.lower() or 
        "fraud" in mode.lower() or "kyc" in mode.lower() or "compliance" in mode.lower()
    )
    
    if is_banking_mode:
        # Add specific guidance for common banking terms
        banking_guidance = ""
        if any(term in question_lower for term in ["pd", "probability of default", "dti", "debt to income", "ltv", "loan to value"]):
            banking_guidance = (
                "\n\nImportant banking definitions:\n"
                "- PD (Probability of Default): The likelihood that a borrower will fail to repay a loan, typically expressed as a percentage.\n"
                "- DTI (Debt-to-Income Ratio): A borrower's total monthly debt payments divided by their gross monthly income, expressed as a percentage.\n"
                "- LTV (Loan-to-Value Ratio): The ratio of a loan amount to the appraised value of the collateral, expressed as a percentage.\n"
            )
        
        system_prompt = (
            f"You are a knowledgeable banking AI assistant specialized in {mode}. "
            "**CRITICAL: You MUST answer questions directly. NEVER give generic responses like 'I'm a banking AI assistant' or 'I can help with...'\n\n"
            "**YOUR JOB:** When asked a question, provide the actual answer immediately.\n\n"
            "**EXAMPLE - If asked 'Explain PD, DTI, LTV':**\n"
            "DO THIS:\n"
            "Here are the key credit risk terms:\n\n"
            "- **PD (Probability of Default)**: The likelihood that a borrower will fail to repay a loan, typically expressed as a percentage (0-100%). Higher PD indicates higher risk.\n"
            "- **DTI (Debt-to-Income Ratio)**: A borrower's total monthly debt payments divided by their gross monthly income, expressed as a percentage. Formula: (Total Monthly Debt / Gross Monthly Income) × 100. Lower DTI is better (typically <43% for approval).\n"
            "- **LTV (Loan-to-Value Ratio)**: The ratio of a loan amount to the appraised value of the collateral, expressed as a percentage. Formula: (Loan Amount / Collateral Value) × 100. Lower LTV is safer (typically <80% for conventional loans).\n\n"
            "DO NOT DO THIS:\n"
            "'I'm a banking AI assistant. I can help with credit questions.'\n\n"
            "**RULES:**\n"
            "1. Answer the question directly - provide definitions, explanations, facts\n"
            "2. Use bullet points (-) for ALL information\n"
            "3. Use **bold** for key terms\n"
            "4. Start with a brief summary sentence\n"
            "5. NEVER say 'I'm a banking AI assistant' or similar\n"
        )
        
        history_context = f"\n\nPrevious Conversation:\n{conversation_history}\n" if conversation_history else ""
        user_prompt = (
            f"**User Question:** {payload.message}\n"
            f"{history_context}"
            f"{banking_guidance}"
            "\n\n**YOUR TASK:** Answer the question above directly and completely.\n"
            "**DO NOT** say 'I'm a banking AI assistant' or similar phrases.\n"
            "**DO** provide the actual answer with definitions and explanations.\n"
            "\n**CRITICAL FORMATTING:**\n"
            "- Start with a brief 1-2 sentence summary\n"
            "- Then use bullet points (-) for ALL key information\n"
            "- Use **bold** for key terms and acronyms\n"
            "- For definitions: provide clear, detailed explanations\n"
            "\n**Example format:**\n"
            "Here are the key credit terms:\n\n"
            "- **PD (Probability of Default)**: Detailed explanation...\n"
            "- **DTI (Debt-to-Income Ratio)**: Detailed explanation...\n"
            "- **LTV (Loan-to-Value Ratio)**: Detailed explanation...\n"
            "\n**Now answer the question:**"
        )
    else:
        # General-purpose mode for non-banking questions
        system_prompt = (
            "You are a helpful AI assistant with broad knowledge. "
            "**YOUR PRIMARY JOB:** Answer questions directly and completely using your knowledge.\n\n"
            "**CRITICAL INSTRUCTIONS:**\n"
            "1. **ALWAYS answer the question** - Provide actual information and explanations\n"
            "2. **NEVER say** 'I'm a banking AI assistant' or 'I can help with...' - Just answer the question\n"
            "3. **Use your knowledge** - Draw from your training data to provide accurate answers\n"
            "4. **ALWAYS use bullet points** - Format ALL information as bullet points\n"
            "5. **Be comprehensive** - Provide detailed explanations when appropriate\n"
            "\n**Formatting requirements:**\n"
            "- Start with 1-2 sentence summary\n"
            "- Then bullet points (-) for ALL key information\n"
            "- Use **bold** for important terms\n"
            "- Keep responses well-structured\n"
            "\n**Example:**\n"
            "Question: Why is the sky blue?\n"
            "Answer: The sky appears blue due to how sunlight interacts with Earth's atmosphere.\n\n"
            "- **Rayleigh Scattering**: Blue light has shorter wavelengths and scatters more than other colors\n"
            "- **Atmospheric Particles**: Tiny particles in the air scatter blue light in all directions\n"
            "- **Human Vision**: Our eyes are more sensitive to blue light\n"
        )
        
        history_context = f"\n\nPrevious Conversation:\n{conversation_history}\n" if conversation_history else ""
        user_prompt = (
            f"**User Question:** {payload.message}\n"
            f"{history_context}"
            "\n\n**YOUR TASK:** Answer this question directly and completely using your knowledge.\n"
            "**DO NOT** say 'I'm a banking AI assistant' or similar phrases.\n"
            "**DO** provide the actual answer with explanations.\n"
            "\n**CRITICAL FORMATTING:**\n"
            "- Start with a brief 1-2 sentence summary\n"
            "- Then use bullet points (-) for ALL key information\n"
            "- Use **bold** for key terms\n"
            "\n**Now answer the question:**"
        )
    
    try:
        logger.debug("Calling Ollama for generic fallback: model=%s", model_to_use)
        resp = requests.post(
            f"{OLLAMA_URL.rstrip('/')}/api/generate",
            json={
                "model": model_to_use,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 6000, "num_ctx": 6000},  # Lower temp (0.1) for precision, larger context (6000)
            },
            timeout=30,  # Increased timeout to allow model to generate complete answers
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response") or data.get("data")
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception as exc:
        logger.warning("Generic model fallback failed: %s", exc)
    return None


def _dedupe_docs(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Remove duplicate documents based on ID or title."""
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
    """Return up to 10 FAQs for the given page_id, prioritizing agent-specific FAQs."""
    lowered = page_id.lower()
    
    # Try to match agent-specific FAQs from chatbot_assistant.py ROLE_CONFIG
    try:
        from services.ui.pages.chatbot_assistant import ROLE_CONFIG
        for role_key, role_data in ROLE_CONFIG.items():
            if role_data.get("page_id", "").lower() == lowered:
                faqs = role_data.get("faqs", [])
                if faqs:
                    return faqs[:10]  # Return up to 10 FAQs
    except Exception:
        pass
    
    # Fallback to legacy FAQ_ENTRIES
    if "fraud" in lowered or "kyc" in lowered:
        bucket = FAQ_ENTRIES.get("anti_fraud_kyc", [])
    elif "credit_score" in lowered or "score" in lowered:
        # Credit Score specific FAQs (fallback - should use ROLE_CONFIG)
        return [
            "How does the Credit Score agent calculate scores?",
            "What factors are used in credit score calculation?",
            "What is the scoring range (300-850)?",
            "How do I export credit scores to Credit Appraisal Agent?",
            "What data inputs does the Credit Score agent need?",
            "What is the difference between credit score and credit rating?",
            "How are payment history and credit utilization weighted?",
            "What credit score ranges indicate poor, fair, good, and excellent credit?",
            "How does credit history length affect the score?",
            "Can I see a breakdown of score components for a borrower?",
        ]
    elif "legal_compliance" in lowered or "compliance" in lowered:
        # Legal Compliance specific FAQs (fallback - should use ROLE_CONFIG)
        return [
            "How does the Legal Compliance agent check sanctions?",
            "What is PEP (Politically Exposed Person) detection?",
            "How are licensing requirements verified?",
            "What compliance scores indicate approval readiness?",
            "How do compliance verdicts feed into Credit Appraisal?",
            "What sanctions lists does the agent check against?",
            "How does KYC risk scoring work in the compliance agent?",
            "What are the different compliance statuses (approved, review, rejected)?",
            "How are policy flags generated and what do they mean?",
            "What happens when a borrower fails compliance checks?",
        ]
    elif "credit" in lowered and "appraisal" in lowered:
        # Credit Appraisal specific FAQs (fallback - should use ROLE_CONFIG)
        return [
            "Explain the lexical definitions for PD, DTI, LTV, and other credit terms.",
            "How does the Credit Appraisal agent work end-to-end?",
            "What are the step-by-step stages in this agent?",
            "What inputs and outputs does the credit agent expect?",
            "How do I explain an approve vs review decision?",
            "What is probability of default (PD) and how is it calculated?",
            "How does the credit agent handle rule-based vs model-based decisions?",
            "What are the key metrics used in credit scoring (NDI, DTI, LTV)?",
            "How can I rerun Stage C - Credit AI Evaluation?",
            "What is the difference between classic rules and NDI-based rules?",
        ]
    elif "asset" in lowered:
        # Asset Appraisal specific FAQs (fallback - should use ROLE_CONFIG)
        return [
            "How does the Asset Appraisal agent work from intake to report?",
            "What are the stage-by-stage steps in the asset workflow?",
            "Define the key terms (FMV, AI-adjusted, realizable, encumbrance).",
            "What inputs and outputs does the asset agent consume/produce?",
            "How are AI-adjusted FMVs derived?",
            "What is the difference between FMV and realizable value?",
            "How does the agent handle different asset types (residential, commercial, industrial)?",
            "What factors affect the condition score and legal penalty?",
            "How are comparable properties (comps) used in valuation?",
            "What happens when an asset has encumbrances or liens?",
        ]
    elif "unified" in lowered:
        # Unified Risk specific FAQs (fallback - should use ROLE_CONFIG)
        return [
            "How does the Unified Risk Orchestration agent work?",
            "What are the stages in unified risk decisioning?",
            "How does it combine asset, credit, and fraud signals?",
            "What is the final decision workflow?",
            "How do I export unified risk reports?",
            "What is the aggregated risk score and how is it calculated?",
            "How does the agent weight different risk factors (asset, credit, fraud)?",
            "What are the three risk tiers (low, medium, high) and their thresholds?",
            "How does the unified agent handle conflicting signals from different agents?",
            "What is the difference between approve, review, and reject recommendations?",
        ]
    else:
        bucket = FAQ_ENTRIES.get("default", [])
    
    return [entry["question"] for entry in bucket][:10]  # Return up to 10 FAQs


@router.get("/v1/chat/models")
def list_available_models() -> Dict[str, Any]:
    """List available Ollama models for chat generation. Prioritizes recommended models."""
    try:
        resp = requests.get(f"{OLLAMA_URL.rstrip('/')}/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        all_models = [model.get("name", "") for model in data.get("models", [])]
        
        # Sort models: recommended first, then others
        recommended_found = [m for m in RECOMMENDED_MODELS if m in all_models]
        other_models = [m for m in all_models if m not in RECOMMENDED_MODELS]
        sorted_models = recommended_found + sorted(other_models)
        
        # Use first recommended model as default if available, otherwise use OLLAMA_MODEL
        default_model = recommended_found[0] if recommended_found else OLLAMA_MODEL
        if default_model not in sorted_models:
            default_model = sorted_models[0] if sorted_models else OLLAMA_MODEL
        
        return {
            "models": sorted_models if sorted_models else RECOMMENDED_MODELS,
            "recommended": RECOMMENDED_MODELS,
            "default": default_model,
            "ollama_url": OLLAMA_URL,
        }
    except Exception as exc:
        logger.warning("Failed to list Ollama models: %s", exc)
        # Fallback to recommended models if API fails
        return {
            "models": RECOMMENDED_MODELS,
            "recommended": RECOMMENDED_MODELS,
            "default": OLLAMA_MODEL,
            "ollama_url": OLLAMA_URL,
            "error": str(exc),
            "note": "Using recommended models fallback - Ollama API unavailable",
        }


@router.post("/v1/chat/upload")
async def upload_file_to_rag(
    file: UploadFile = File(...),
    max_rows: int = 500,
) -> Dict[str, Any]:
    """Upload and ingest a file into the RAG database."""
    try:
        if not embeddings_available():
            raise HTTPException(status_code=503, detail="Embeddings service unavailable")
        
        # Determine file type
        file_ext = Path(file.filename or "").suffix.lower()
        allowed_extensions = {".txt", ".csv", ".py", ".html", ".md", ".json", ".pdf", ".xml"}
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type {file_ext} not supported. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        
        try:
            ingestor = LocalIngestor()
            chunks = []
            
            # Process based on file type
            if file_ext == ".csv":
                # CSV: process as rows
                df = pd.read_csv(tmp_path)
                if df.empty:
                    raise HTTPException(status_code=400, detail="CSV file is empty")
                if max_rows:
                    df = df.head(max_rows)
                for idx, row in df.iterrows():
                    text = "; ".join(f"{col}={val}" for col, val in row.items() if pd.notna(val))
                    chunks.append({
                        "id": f"{Path(file.filename).stem}-{idx}",
                        "text": text,
                        "metadata": {
                            "source": file.filename,
                            "row_index": idx,
                            "title": f"{Path(file.filename).stem} row {idx}",
                        }
                    })
            elif file_ext == ".pdf":
                # PDF: extract text (requires PyPDF2 or pdfplumber)
                try:
                    import PyPDF2
                    with open(tmp_path, "rb") as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        text_parts = []
                        for page_num, page in enumerate(pdf_reader.pages):
                            text = page.extract_text()
                            if text.strip():
                                text_parts.append(text)
                        full_text = "\n\n".join(text_parts)
                        if full_text.strip():
                            # Split into chunks
                            chunk_size = 1000
                            for i in range(0, len(full_text), chunk_size):
                                chunk_text = full_text[i:i+chunk_size]
                                chunks.append({
                                    "id": f"{Path(file.filename).stem}-chunk-{i//chunk_size}",
                                    "text": chunk_text,
                                    "metadata": {
                                        "source": file.filename,
                                        "page": i // chunk_size,
                                        "title": f"{Path(file.filename).stem} page {i//chunk_size + 1}",
                                    }
                                })
                except ImportError:
                    raise HTTPException(status_code=503, detail="PDF processing requires PyPDF2. Install with: pip install PyPDF2")
            else:
                # Text files: read and chunk
                try:
                    text_content = tmp_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text_content = tmp_path.read_bytes().decode("utf-8", errors="ignore")
                
                if not text_content.strip():
                    raise HTTPException(status_code=400, detail="File appears to be empty")
                
                # Split into chunks (1000 chars each)
                chunk_size = 1000
                for i in range(0, len(text_content), chunk_size):
                    chunk_text = text_content[i:i+chunk_size]
                    chunks.append({
                        "id": f"{Path(file.filename).stem}-chunk-{i//chunk_size}",
                        "text": chunk_text,
                        "metadata": {
                            "source": file.filename,
                            "chunk_index": i // chunk_size,
                            "title": f"{Path(file.filename).stem} chunk {i//chunk_size + 1}",
                        }
                    })
            
            if not chunks:
                raise HTTPException(status_code=400, detail="No content extracted from file")
            
            # Ingest chunks
            total_ingested = ingestor.ingest_text_chunks(chunks, dry_run=False)
            
            return {
                "success": True,
                "message": f"Successfully ingested {total_ingested} chunks from {file.filename}",
                "chunks_ingested": total_ingested,
                "filename": file.filename,
            }
        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()
                
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("File upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(exc)}")


def _get_confidence_level(score: float, source_type: str) -> Tuple[str, float]:
    """Determine confidence level based on RAG score or source type."""
    if source_type == "rag":
        if score >= 0.5:
            return "high", score
        elif score >= 0.35:
            return "medium", score
        else:
            return "low", score
    elif source_type == "general_knowledge":
        return "medium", 0.5  # Medium confidence for general knowledge
    else:
        return "low", 0.3


def _generate_related_questions(question: str, mode: str, retrieved: List[Dict[str, Any]]) -> List[str]:
    """Generate related question suggestions based on the current question and context."""
    related = []
    question_lower = question.lower()
    
    # Extract key terms
    key_terms = []
    banking_terms = ["pd", "dti", "ltv", "credit", "score", "appraisal", "asset", "fraud", "compliance"]
    for term in banking_terms:
        if term in question_lower:
            key_terms.append(term)
    
    # Mode-specific suggestions
    if "credit" in mode.lower():
        if "pd" in question_lower:
            related.extend([
                "How is PD calculated?",
                "What is a good PD value?",
                "How does PD affect loan approval?"
            ])
        elif "dti" in question_lower:
            related.extend([
                "What is an acceptable DTI ratio?",
                "How is DTI calculated?",
                "How does DTI impact credit decisions?"
            ])
        elif "ltv" in question_lower:
            related.extend([
                "What is a good LTV ratio?",
                "How does LTV affect loan terms?",
                "What is the maximum LTV for approval?"
            ])
        else:
            related.extend([
                "What is PD (Probability of Default)?",
                "How does the credit appraisal process work?",
                "What factors affect credit decisions?"
            ])
    elif "asset" in mode.lower():
        related.extend([
            "What is FMV (Fair Market Value)?",
            "How are assets appraised?",
            "What factors affect asset valuation?"
        ])
    elif "fraud" in mode.lower() or "kyc" in mode.lower():
        related.extend([
            "How does fraud detection work?",
            "What is KYC verification?",
            "What are common fraud indicators?"
        ])
    elif "compliance" in mode.lower():
        related.extend([
            "What is PEP detection?",
            "How are sanctions checked?",
            "What compliance scores indicate approval?"
        ])
    
    # Generic follow-ups if we have retrieved documents
    if retrieved:
        related.append("Can you provide more details?")
        related.append("What are the key steps involved?")
    
    # Limit to 3-4 related questions
    return related[:4]


def _format_response_with_structure(text: str, mode: str, confidence: str) -> str:
    """Format response with structured markdown for better readability. ALWAYS ensures bullet points."""
    import re
    
    if not text or not text.strip():
        return text
    
    text = text.strip()
    
    # Check if already has bullet points
    has_bullets = bool(re.search(r'^[\s]*[-•*]\s', text, re.MULTILINE)) or bool(re.search(r'^\d+[\.\)]\s', text, re.MULTILINE))
    
    # If already well-formatted with bullets, just add confidence if needed
    if has_bullets and ("**" in text or text.startswith("#")):
        if confidence != "high":
            confidence_emoji = {"high": "✅", "medium": "⚠️", "low": "💡"}.get(confidence, "💡")
            text += f"\n\n{confidence_emoji} *Confidence: {confidence.title()}*"
        return text
    
    # Convert to bullet points if missing
    if not has_bullets:
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # If it's a short answer (1-2 sentences), convert to bullet format
        if len(sentences) <= 2:
            # Try to extract key points
            formatted = sentences[0] if sentences else text
            if len(sentences) > 1:
                formatted += "\n\n**Key Points:**\n"
                for i, sent in enumerate(sentences[1:], 1):
                    # Extract key terms and format
                    sent_clean = sent.rstrip('.!?')
                    formatted += f"- {sent_clean}\n"
            else:
                # Single sentence - break it down if possible
                if len(sentences[0]) > 100:
                    # Try to split long sentence
                    parts = re.split(r'[,;]\s+', sentences[0])
                    if len(parts) > 1:
                        formatted = parts[0] + "\n\n**Details:**\n"
                        for part in parts[1:]:
                            formatted += f"- {part.strip()}\n"
                    else:
                        formatted = f"{sentences[0]}\n\n**Summary:**\n- {sentences[0]}"
                else:
                    formatted = f"{sentences[0]}\n\n**Key Point:**\n- {sentences[0]}"
        else:
            # Multiple sentences - format as summary + bullets
            summary = sentences[0] if len(sentences[0]) < 150 else sentences[0][:150] + "..."
            formatted = f"{summary}\n\n**Key Points:**\n"
            for sent in sentences[1:]:
                sent_clean = sent.rstrip('.!?')
                # Bold key terms if found
                if any(term in sent_clean.lower() for term in ["pd", "dti", "ltv", "fmv", "ndi", "kyc", "pep"]):
                    for term in ["PD", "DTI", "LTV", "FMV", "NDI", "KYC", "PEP"]:
                        sent_clean = re.sub(rf'\b{term}\b', f'**{term}**', sent_clean, flags=re.IGNORECASE)
                formatted += f"- {sent_clean}\n"
    else:
        # Has bullets but may need formatting improvements
        formatted = text
        # Ensure bold formatting for key terms
        for term in ["PD", "DTI", "LTV", "FMV", "NDI", "KYC", "PEP", "Probability of Default", "Debt-to-Income", "Loan-to-Value"]:
            formatted = re.sub(rf'\b{term}\b', f'**{term}**', formatted, flags=re.IGNORECASE)
    
    # Add confidence indicator
    if confidence != "high":
        confidence_emoji = {"high": "✅", "medium": "⚠️", "low": "💡"}.get(confidence, "💡")
        formatted += f"\n\n{confidence_emoji} *Confidence: {confidence.title()}*"
    
    return formatted.strip()


def _check_response_cache(question: str, page_id: str) -> Optional[Dict[str, Any]]:
    """Check if we have a cached response for this question."""
    # Create cache key from question and page context
    cache_key = hashlib.md5(f"{question.lower().strip()}:{page_id}".encode()).hexdigest()
    
    if cache_key in _response_cache:
        cached_response, cached_time = _response_cache[cache_key]
        age = time.time() - cached_time
        if age < RESPONSE_CACHE_TTL:
            logger.debug(f"Cache hit for question: {question[:50]} (age: {age:.1f}s)")
            return cached_response
        else:
            # Expired cache entry
            del _response_cache[cache_key]
    
    return None


def _store_response_cache(question: str, page_id: str, response: Dict[str, Any]):
    """Store response in cache."""
    cache_key = hashlib.md5(f"{question.lower().strip()}:{page_id}".encode()).hexdigest()
    _response_cache[cache_key] = (response, time.time())
    
    # Clean up old cache entries (keep last 100)
    if len(_response_cache) > 100:
        # Remove oldest 20 entries
        sorted_entries = sorted(_response_cache.items(), key=lambda x: x[1][1])
        for key, _ in sorted_entries[:20]:
            del _response_cache[key]


def _build_conversation_context(history: List[ChatMessage], max_turns: int = MAX_CONVERSATION_HISTORY) -> str:
    """Build conversation context from history for multi-turn conversations."""
    if not history or len(history) == 0:
        return ""
    
    # Take last N turns (user-assistant pairs)
    recent_history = history[-max_turns:] if len(history) > max_turns else history
    
    context_parts = []
    for msg in recent_history:
        role = msg.role if hasattr(msg, 'role') else msg.get('role', 'user')
        content = msg.content if hasattr(msg, 'content') else msg.get('content', '')
        if role in ['user', 'assistant'] and content:
            context_parts.append(f"{role.title()}: {content}")
    
    return "\n\n".join(context_parts) if context_parts else ""


def _is_banking_related(question: str, page_id: str, context: Dict[str, Any]) -> bool:
    """Check if the question is related to banking, finance, credit, or the current agent context."""
    question_lower = question.lower()
    
    # Banking/finance keywords
    banking_keywords = [
        "credit", "loan", "borrower", "lender", "debt", "interest", "mortgage",
        "pd", "dti", "ltv", "fico", "score", "appraisal", "collateral", "asset",
        "fraud", "kyc", "sanction", "pep", "compliance", "risk", "default",
        "approval", "reject", "review", "underwriting", "valuation", "fmv",
        "financial", "banking", "bank", "finance", "payment", "delinquency",
        "application", "decision", "policy", "rule", "workflow", "stage",
        "agent", "model", "training", "dataset", "export", "report"
    ]
    
    # Check if question contains banking keywords
    if any(keyword in question_lower for keyword in banking_keywords):
        return True
    
    # Check page context - if on a banking agent page, assume banking-related
    page_lower = page_id.lower()
    banking_pages = ["credit", "asset", "fraud", "kyc", "compliance", "risk", "unified"]
    if any(bp in page_lower for bp in banking_pages):
        return True
    
    # Check agent_type in context
    agent_type = context.get("agent_type", "").lower()
    if agent_type and any(bp in agent_type for bp in banking_pages):
        return True
    
    return False


def _faq_for_page(page_id: str) -> List[str]:
    """Return up to 10 FAQs for the given page_id, prioritizing agent-specific FAQs."""
    lowered = page_id.lower()
    
    # Try to match agent-specific FAQs from chatbot_assistant.py ROLE_CONFIG
    try:
        from services.ui.pages.chatbot_assistant import ROLE_CONFIG
        for role_key, role_data in ROLE_CONFIG.items():
            if role_data.get("page_id", "").lower() == lowered:
                faqs = role_data.get("faqs", [])
                if faqs:
                    return faqs[:10]  # Return up to 10 FAQs
    except Exception:
        pass
    
    # Fallback to legacy FAQ_ENTRIES
    if "fraud" in lowered or "kyc" in lowered:
        bucket = FAQ_ENTRIES.get("anti_fraud_kyc", [])
    elif "credit_score" in lowered or "score" in lowered:
        # Credit Score specific FAQs
        return [
            "How does the Credit Score agent calculate scores?",
            "What factors are used in credit score calculation?",
            "What is the scoring range (300-850)?",
            "How do I export credit scores to Credit Appraisal Agent?",
            "What data inputs does the Credit Score agent need?",
        ]
    elif "legal_compliance" in lowered or "compliance" in lowered:
        # Legal Compliance specific FAQs
        return [
            "How does the Legal Compliance agent check sanctions?",
            "What is PEP (Politically Exposed Person) detection?",
            "How are licensing requirements verified?",
            "What compliance scores indicate approval readiness?",
            "How do compliance verdicts feed into Credit Appraisal?",
        ]
    elif "credit" in lowered and "appraisal" in lowered:
        # Credit Appraisal specific FAQs
        return [
            "Explain the lexical definitions for PD, DTI, LTV, and other credit terms.",
            "How does the Credit Appraisal agent work end-to-end?",
            "What are the step-by-step stages in this agent?",
            "What inputs and outputs does the credit agent expect?",
            "How do I explain an approve vs review decision?",
        ]
    elif "asset" in lowered:
        # Asset Appraisal specific FAQs
        return [
            "How does the Asset Appraisal agent work from intake to report?",
            "What are the stage-by-stage steps in the asset workflow?",
            "Define the key terms (FMV, AI-adjusted, realizable, encumbrance).",
            "What inputs and outputs does the asset agent consume/produce?",
            "How are AI-adjusted FMVs derived?",
        ]
    elif "unified" in lowered:
        # Unified Risk specific FAQs
        return [
            "How does the Unified Risk Orchestration agent work?",
            "What are the stages in unified risk decisioning?",
            "How does it combine asset, credit, and fraud signals?",
            "What is the final decision workflow?",
            "How do I export unified risk reports?",
        ]
    else:
        bucket = FAQ_ENTRIES.get("default", [])
    
    return [entry["question"] for entry in bucket][:10]  # Return up to 10 FAQs


@router.post("/v1/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    import time
    start_time = time.time()
    
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Check cache first
    cached_response = _check_response_cache(payload.message, payload.page_id)
    if cached_response:
        cached_response["source_type"] = "cached"
        return ChatResponse(**cached_response)

    # Log chat request
    if add_log_entry:
        add_log_entry({
            "type": "chat_request",
            "message": payload.message[:100],
            "page_id": payload.page_id,
            "model": payload.model,
        })

    mode = _infer_mode(payload.page_id, payload.context)
    context_summary = _summarize_context(payload.context)
    # Use unified chatbot agent if agent_id is provided and set to "chatbot"
    # This ensures all agents use the same chatbot backend for consistent behavior
    agent_id = getattr(payload, 'agent_id', None)
    if agent_id == "chatbot":
        agent_key = "chatbot_assistant"  # Use unified chatbot agent
    else:
        agent_key = _resolve_agent_key(payload.page_id)  # Fallback to page_id resolution
    
    # Try to get howto snippet if available
    howto_doc = None
    if get_howto_snippet:
        try:
            howto_snippet = get_howto_snippet(agent_key, payload.message)
            if howto_snippet:
                howto_doc = {
                    "id": f"{agent_key or 'agent'}_howto",
                    "title": "Agent Workflow Guide",
                    "score": 1.35,
                    "snippet": howto_snippet,
                    "source": "howto",
                    "metadata": {"namespace": "howto", "agent": agent_key},
                }
        except Exception:
            pass
    
    # Check if question is banking-related
    is_banking = _is_banking_related(payload.message, payload.page_id, payload.context)
    
    model_to_use = payload.model or OLLAMA_MODEL
    llm_time = 0
    rag_time = 0
    tfidf_time = 0
    reply_text = ""
    confidence = "medium"
    confidence_score = 0.5
    source_type = "general_knowledge"
    related_questions = []
    retrieved: List[Dict[str, Any]] = []
    
    conversation_history = _build_conversation_context(payload.history if hasattr(payload, 'history') else [])
    
    # ── Step 1: Retrieve from RAG (primary store first) ─────────────────────────
    primary_hits: List[Dict[str, Any]] = []
    if LOCAL_STORE.available:
        try:
            rag_start = time.time()
            primary_hits = _retrieve_store_docs(payload.message, payload.context)
            rag_time = (time.time() - rag_start) * 1000
        except Exception as exc:
            logger.warning("Vector store retrieval failed: %s", exc)
    
    if howto_doc:
        primary_hits = [howto_doc] + primary_hits
    
    # Fallback to TF-IDF cache if no vector hits
    if not primary_hits:
        try:
            tfidf_start = time.time()
            fallback_hits = _retrieve_fallback_docs(payload.message, payload.context)
            tfidf_time = (time.time() - tfidf_start) * 1000
            primary_hits = fallback_hits
        except Exception as exc:
            logger.warning("TF-IDF fallback retrieval failed: %s", exc)
    
    retrieved = _dedupe_docs(primary_hits, RAG_TOP_K) if primary_hits else []
    
    if retrieved:
        # Use RAG-derived answer first
        source_type = "rag"
        top_score = float(retrieved[0].get("score") or 0.0)
        confidence, confidence_score = _get_confidence_level(top_score, "rag")
        rag_answer = _compose_lightweight_reply(payload, retrieved, mode)
        
        # Enhance with LLM if available (still grounded in context)
        llm_answer = None
        if USE_OLLAMA and model_to_use:
            try:
                llm_start = time.time()
                llm_answer = _maybe_generate_llm_reply(
                    payload,
                    retrieved,
                    mode,
                    model_name=model_to_use,
                    conversation_history=conversation_history,
                    initial_answer=rag_answer,
                )
                llm_time = (time.time() - llm_start) * 1000
            except Exception as exc:
                logger.debug("LLM enhancement failed: %s", exc)
                llm_answer = None
        
        reply_text = llm_answer.strip() if llm_answer else rag_answer
        reply_text = _format_response_with_structure(reply_text, mode, confidence)
        reply_text += "\n\n📚 *Answer grounded in your uploaded knowledge base.*"
    else:
        # ── Step 2: General-knowledge fallback via model ───────────────────────
        logger.info("No RAG context available – falling back to model knowledge.")
        source_type = "general_knowledge"
        confidence, confidence_score = _get_confidence_level(0.0, "general_knowledge")
        
        kb_answer = None
        if USE_OLLAMA and model_to_use:
            try:
                llm_start = time.time()
                kb_answer = _generate_gemma_fallback(payload, mode, model_to_use, conversation_history)
                llm_time = (time.time() - llm_start) * 1000
            except Exception as exc:
                logger.debug("General knowledge generation failed: %s", exc)
                kb_answer = None
        
        if not kb_answer:
            fallback_msg = (
                f"I apologize, but I couldn't generate a complete answer for '{payload.message}'. "
                "Please try rephrasing your question or upload relevant documents to the chat knowledge base."
            )
            reply_text = _format_response_with_structure(fallback_msg, mode, confidence)
        else:
            reply_text = _format_response_with_structure(kb_answer, mode, confidence)
        
        reply_text += "\n\n📘 *Answer generated from the assistant’s general knowledge base.*"
    
    related_questions = _generate_related_questions(payload.message, mode, retrieved)

    actions = _suggest_actions(payload)
    timestamp = datetime.now(timezone.utc).isoformat()
    faq_options = _faq_for_page(payload.page_id)
    
    # Build response
    response_data = {
        "reply": reply_text,
        "mode": mode,
        "actions": actions,
        "timestamp": timestamp,
        "context_summary": context_summary,
        "retrieved": retrieved,
        "faq_options": faq_options,
        "confidence": confidence,
        "confidence_score": confidence_score,
        "related_questions": related_questions,
        "source_type": source_type,
    }
    
    # Cache the response (only cache successful responses with good confidence)
    if confidence in ["high", "medium"] and len(reply_text) > 50:
        _store_response_cache(payload.message, payload.page_id, response_data)
    
    # Log chat response with performance metrics
    if add_log_entry:
        total_time = (time.time() - start_time) * 1000
        add_log_entry({
            "type": "chat_response",
            "duration_ms": total_time,
            "rag_time_ms": rag_time,
            "tfidf_time_ms": tfidf_time,
            "llm_time_ms": llm_time,
            "retrieved_count": len(retrieved),
            "reply_length": len(reply_text),
            "confidence": confidence,
            "source_type": source_type,
        })

    return ChatResponse(**response_data)
