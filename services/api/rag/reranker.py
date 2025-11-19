"""Reranking utilities for improving RAG retrieval quality."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from sentence_transformers import CrossEncoder
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Default reranker model (lightweight, CPU-friendly)
# Try mini first (faster), fallback to base (better quality)
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"  # Mini model for CPU efficiency
_reranker_model: Optional[Any] = None


def _get_reranker_model(model_name: Optional[str] = None) -> Optional[Any]:
    """Get or initialize the reranker model."""
    global _reranker_model
    
    if not RERANKER_AVAILABLE:
        logger.warning("Reranker not available. Install with: pip install sentence-transformers")
        return None
    
    if _reranker_model is None:
        try:
            model_to_use = model_name or DEFAULT_RERANKER_MODEL
            logger.info(f"Loading reranker model: {model_to_use}")
            # Try mini model first, fallback to base if mini fails
            try:
                _reranker_model = CrossEncoder(model_to_use)
            except Exception:
                # Fallback to base model if mini not available
                logger.warning(f"Mini model {model_to_use} not available, trying base model")
                _reranker_model = CrossEncoder("BAAI/bge-reranker-base")
            logger.info("Reranker model loaded successfully")
        except Exception as exc:
            logger.error(f"Failed to load reranker model: {exc}")
            return None
    
    return _reranker_model


def rerank_documents(
    query: str,
    documents: List[Dict[str, Any]],
    top_k: Optional[int] = None,
    model_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Rerank retrieved documents using a cross-encoder model.
    
    Args:
        query: The user's query/question
        documents: List of document dictionaries with 'snippet' or 'text' field
        top_k: Number of top documents to return (None = return all)
        model_name: Optional reranker model name
    
    Returns:
        Reranked list of documents sorted by relevance score
    """
    if not documents:
        return []
    
    reranker = _get_reranker_model(model_name)
    if not reranker:
        # Fallback: return documents as-is
        logger.debug("Reranker unavailable, returning documents without reranking")
        return documents
    
    try:
        # Prepare query-document pairs
        pairs = []
        for doc in documents:
            text = doc.get("snippet") or doc.get("text") or ""
            if text:
                pairs.append([query, text])
            else:
                pairs.append([query, ""])
        
        if not pairs:
            return documents
        
        # Get reranking scores
        scores = reranker.predict(pairs)
        
        # Combine scores with documents
        scored_docs = []
        for doc, score in zip(documents, scores):
            # Update score with reranking score (weighted combination)
            original_score = doc.get("score", 0.0)
            # Combine original similarity score with reranking score
            # Weight: 30% original, 70% reranking (reranking is more accurate)
            combined_score = (original_score * 0.3) + (float(score) * 0.7)
            
            updated_doc = dict(doc)
            updated_doc["score"] = combined_score
            updated_doc["rerank_score"] = float(score)
            scored_docs.append(updated_doc)
        
        # Sort by combined score (descending)
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top_k if specified
        if top_k is not None:
            return scored_docs[:top_k]
        
        return scored_docs
        
    except Exception as exc:
        logger.error(f"Reranking failed: {exc}")
        # Fallback: return original documents
        return documents


def reranker_available() -> bool:
    """Check if reranker is available."""
    return RERANKER_AVAILABLE and _get_reranker_model() is not None
