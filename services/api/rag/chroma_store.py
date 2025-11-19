<<<<<<< HEAD
"""ChromaDB vector store integration for improved RAG with metadata filtering."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """ChromaDB-based vector store with metadata filtering support."""
    
    def __init__(self, store_dir: Path | None = None, collection_name: str = "rag_documents"):
        if not CHROMADB_AVAILABLE:
            raise RuntimeError(
                "ChromaDB not available. Install with: pip install chromadb"
            )
        
        if store_dir is None:
            store_dir = Path(__file__).resolve().parents[1] / ".chroma_store"
        
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.store_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
        except Exception as exc:
            logger.error("Failed to create ChromaDB collection: %s", exc)
            raise
    
    @property
    def available(self) -> bool:
        """Check if ChromaDB store is available and has documents."""
        try:
            return self.collection.count() > 0
        except Exception:
            return False
    
    def add_vectors(
        self,
        vectors: Iterable[Iterable[float]],
        metadata: Iterable[Dict[str, Any]]
    ) -> None:
        """Add vectors and metadata to the store."""
        vector_list = list(vectors)
        meta_list = list(metadata)
        
        if not vector_list:
            return
        
        if len(vector_list) != len(meta_list):
            raise ValueError("Vectors and metadata must have same length")
        
        # Prepare data for ChromaDB
        ids = []
        documents = []
        metadatas = []
        embeddings = []
        
        for i, (vec, meta) in enumerate(zip(vector_list, meta_list)):
            # Generate ID if not present
            doc_id = meta.get("id") or f"doc_{i}"
            ids.append(str(doc_id))
            
            # Extract text/document content
            text = meta.get("text") or meta.get("snippet") or ""
            documents.append(text)
            
            # Prepare metadata (ChromaDB requires string values)
            chroma_meta = {}
            for key, value in meta.items():
                if key not in ["id", "text", "snippet"]:
                    # Convert to string for ChromaDB
                    if isinstance(value, (str, int, float, bool)):
                        chroma_meta[key] = value
                    else:
                        chroma_meta[key] = str(value)
            
            # Store original metadata in a special field
            chroma_meta["_original_meta"] = str(meta)
            metadatas.append(chroma_meta)
            
            # Convert vector to list
            embeddings.append(list(vec))
        
        # Add to collection
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"Added {len(ids)} documents to ChromaDB collection '{self.collection_name}'")
        except Exception as exc:
            logger.error("Failed to add vectors to ChromaDB: %s", exc)
            raise
    
    def query(
        self,
        vector: Iterable[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Query the vector store with optional metadata filtering."""
        if not self.available:
            return []
        
        vec = list(vector)
        
        # Build where clause for filtering
        where = None
        if filter_dict:
            where = {}
            for key, value in filter_dict.items():
                where[key] = value
        
        try:
            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[vec],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # Convert to our format
            output = []
            if results["ids"] and len(results["ids"]) > 0:
                ids = results["ids"][0]
                distances = results["distances"][0]
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                
                for i, (doc_id, distance, doc_text, meta) in enumerate(
                    zip(ids, distances, documents, metadatas)
                ):
                    # Convert distance to similarity score (cosine distance -> similarity)
                    # ChromaDB returns distance (0 = identical, 2 = opposite)
                    # Convert to similarity score (1 = identical, 0 = opposite)
                    similarity_score = 1.0 - (distance / 2.0)
                    similarity_score = max(0.0, min(1.0, similarity_score))  # Clamp to [0, 1]
                    
                    # Filter by score threshold
                    if similarity_score < score_threshold:
                        continue
                    
                    # Reconstruct metadata
                    result_meta = dict(meta)
                    result_meta["id"] = doc_id
                    result_meta["score"] = similarity_score
                    result_meta["snippet"] = doc_text
                    result_meta["text"] = doc_text
                    
                    # Try to restore original metadata if available
                    if "_original_meta" in result_meta:
                        try:
                            import ast
                            original = ast.literal_eval(result_meta["_original_meta"])
                            result_meta.update(original)
                        except Exception:
                            pass
                    
                    output.append(result_meta)
            
            return output
            
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return []
    
    def delete_collection(self) -> None:
        """Delete the collection (for testing/reset)."""
        try:
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted ChromaDB collection '{self.collection_name}'")
        except Exception as exc:
            logger.warning("Failed to delete collection: %s", exc)
    
    def count(self) -> int:
        """Get the number of documents in the collection."""
        try:
            return self.collection.count()
        except Exception:
            return 0
=======
"""ChromaDB helper utilities for the sandbox chatbot."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

# Disable noisy telemetry + remote capture by default.
os.environ.setdefault("CHROMA_TELEMETRY_DISABLED", "true")

import chromadb
from chromadb.api.models import Collection

DB_ROOT = Path(__file__).resolve().parent / "rag_db"
DB_ROOT.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = os.getenv("SANDBOX_RAG_COLLECTION", "sandbox_rag")

_CLIENT: Optional[chromadb.PersistentClient] = None
_COLLECTION: Optional[Collection.Collection] = None  # type: ignore[attr-defined]


def reset_collection() -> None:
    """Delete the local Chroma store and clear cached client state."""
    global _CLIENT, _COLLECTION
    _CLIENT = None
    _COLLECTION = None
    if DB_ROOT.exists():
        shutil.rmtree(DB_ROOT, ignore_errors=True)
    DB_ROOT.mkdir(parents=True, exist_ok=True)


def get_collection() -> Collection.Collection:  # type: ignore[attr-defined]
    global _CLIENT, _COLLECTION
    if _COLLECTION is None:
        _CLIENT = chromadb.PersistentClient(path=str(DB_ROOT))
        _COLLECTION = _CLIENT.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _COLLECTION


__all__ = ["get_collection", "reset_collection", "DB_ROOT", "COLLECTION_NAME"]
>>>>>>> edc6fcd87ea2babb0c09187ad96df4e2130eaac2
