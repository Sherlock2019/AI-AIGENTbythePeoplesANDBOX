"""Simple local vector store using numpy for similarity search."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np


class LocalVectorStore:
    def __init__(self, store_dir: Path | None = None):
        if store_dir is None:
            store_dir = Path(__file__).resolve().parents[1] / ".rag_store"
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_path = self.store_dir / "embeddings.npy"
        self.metadata_path = self.store_dir / "metadata.json"
        self._embeddings: np.ndarray | None = None
        self._metadata: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.embeddings_path.exists() and self.metadata_path.exists():
            self._embeddings = np.load(self.embeddings_path)
            with self.metadata_path.open("r", encoding="utf-8") as f:
                self._metadata = json.load(f)
        else:
            self._embeddings = None
            self._metadata = []

    @property
    def available(self) -> bool:
        return self._embeddings is not None and self._embeddings.shape[0] > 0

    def add_vectors(self, vectors: Iterable[Iterable[float]], metadata: Iterable[Dict[str, Any]]) -> None:
        vector_list = list(vectors)
        meta_list = list(metadata)
        if not vector_list:
            return
        arr = np.array(vector_list, dtype=np.float32)
        if arr.ndim != 2:
            raise ValueError("Vectors must have shape (n, dim)")

        if self._embeddings is None:
            self._embeddings = arr
        else:
            if arr.shape[1] != self._embeddings.shape[1]:
                raise ValueError("Embedding dimension mismatch with existing store")
            self._embeddings = np.vstack([self._embeddings, arr])

        self._metadata.extend(meta_list)

    def save(self) -> None:
        if self._embeddings is None:
            return
        np.save(self.embeddings_path, self._embeddings)
        with self.metadata_path.open("w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)

    def query(self, vector: Iterable[float], top_k: int = 3) -> List[Dict[str, Any]]:
        if not self.available:
            return []
        vec = np.array(vector, dtype=np.float32)
        if vec.ndim == 2:
            vec = vec[0]
        vec_norm = np.linalg.norm(vec)
        if vec_norm == 0:
            return []
        matrix = self._embeddings  # type: ignore[assignment]
        matrix_norms = np.linalg.norm(matrix, axis=1)
        denom = (matrix_norms * vec_norm) + 1e-10
        scores = (matrix @ vec) / denom
        idx = np.argsort(scores)[::-1][:top_k]
        results = []
        for i in idx:
            meta = dict(self._metadata[i])
            meta["score"] = float(scores[i])
            results.append(meta)
        return results
