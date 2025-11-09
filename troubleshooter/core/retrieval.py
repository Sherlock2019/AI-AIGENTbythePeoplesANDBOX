from __future__ import annotations

from typing import List

from .memory import CaseMemory
from .types import RetrievalHit


class Retriever:
    def __init__(self, memory: CaseMemory):
        self.memory = memory

    def find(self, problem: str, context: str | None, k: int = 5) -> List[RetrievalHit]:
        query = (problem + "\n" + (context or "")).strip()
        hits: List[RetrievalHit] = []
        for idx, score in self.memory.search(query, k):
            if idx < len(self.memory.cases):
                hits.append(RetrievalHit(case=self.memory.cases[idx], score=score))
        return hits
