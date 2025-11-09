from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..config import CACHE_DIR, EMBEDDINGS_MODEL, FIXTURES
from .types import Case

try:
    from sentence_transformers import SentenceTransformer

    _EMBEDDER = SentenceTransformer(EMBEDDINGS_MODEL)
except Exception:
    _EMBEDDER = None


class CaseMemory:
    def __init__(self, cases_path: Path = FIXTURES):
        self.cases_path = cases_path
        self.cases: List[Case] = []
        self._tfidf = None
        self._tfidf_matrix = None
        self._embeddings = None
        self._load()

    def _load(self):
        if self.cases_path.exists():
            data = json.loads(self.cases_path.read_text(encoding="utf-8"))
        else:
            data = []
        self.cases = [Case(**item) for item in data]
        self._reindex()

    def _reindex(self):
        corpus = [self._case_text(c) for c in self.cases] or [""]
        self._tfidf = TfidfVectorizer(min_df=1, max_features=5000)
        self._tfidf_matrix = self._tfidf.fit_transform(corpus)
        if _EMBEDDER:
            cache_file = CACHE_DIR / "embeddings.npy"
            self._embeddings = _EMBEDDER.encode(corpus, normalize_embeddings=True)
            np.save(cache_file, self._embeddings)
        else:
            self._embeddings = None

    def _case_text(self, case: Case) -> str:
        return " \n".join(
            [
                case.problem,
                case.context or "",
                " ".join(case.root_causes),
                case.resolution,
                " ".join(case.steps),
                " ".join(case.tags),
            ]
        )

    def save(self):
        self.cases_path.parent.mkdir(parents=True, exist_ok=True)
        self.cases_path.write_text(
            json.dumps([c.model_dump() for c in self.cases], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_case(self, case: Case):
        self.cases.append(case)
        self.save()
        self._reindex()

    def search(self, query: str, k: int = 5) -> List[Tuple[int, float]]:
        if not self.cases:
            return []
        q_tfidf = self._tfidf.transform([query])
        tfidf_scores = cosine_similarity(q_tfidf, self._tfidf_matrix)[0]

        if self._embeddings is not None and _EMBEDDER:
            q_emb = _EMBEDDER.encode([query], normalize_embeddings=True)
            emb_scores = (q_emb @ self._embeddings.T)[0]
            scores = 0.5 * tfidf_scores + 0.5 * emb_scores
        else:
            scores = tfidf_scores

        idxs = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in idxs]
