from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Case(BaseModel):
    id: str
    problem: str
    context: Optional[str] = None
    root_causes: List[str] = []
    resolution: str = ""
    steps: List[str] = []
    tags: List[str] = []
    signals: Dict[str, Any] = {}


class SolveRequest(BaseModel):
    problem: str
    context: Optional[str] = None
    allow_tools: bool = False
    max_suggestions: int = 5


class FirstPrinciplesPlan(BaseModel):
    assumptions: List[str]
    constraints: List[str]
    subproblems: List[str]
    tests: List[str]


class RetrievalHit(BaseModel):
    case: Case
    score: float


class SolveResponse(BaseModel):
    plan: FirstPrinciplesPlan
    retrieved: List[RetrievalHit]
    strategy: List[str]
    attempted_tools: List[str]
    postmortem: str
    new_case: Case
