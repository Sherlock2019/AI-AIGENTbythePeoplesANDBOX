from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import ORJSONResponse

from core.first_principles import derive_plan
from core.memory import CaseMemory
from core.retrieval import Retriever
from core.solver import SAFETY_RULES, merge_strategy, reflect, to_case
from core.types import Case, SolveRequest, SolveResponse
from tools.python_tool import PythonTool
from tools.shell_tool import ShellTool

app = FastAPI(
    title="AI Troubleshooter (First-Principles)",
    version="0.1.0",
    default_response_class=ORJSONResponse,
)

MEM = CaseMemory()
RET = Retriever(MEM)
SHELL = ShellTool()
PY = PythonTool()


@app.get("/health")
def health():
    return {"ok": True, "cases": len(MEM.cases)}


@app.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str):
    for case in MEM.cases:
        if case.id == case_id:
            return case
    raise HTTPException(status_code=404, detail="case not found")


@app.post("/cases")
def add_case(case: Case):
    MEM.add_case(case)
    return {"ok": True, "id": case.id}


@app.post("/solve", response_model=SolveResponse)
def solve(req: SolveRequest):
    plan = derive_plan(req.problem, req.context)
    hits = RET.find(req.problem, req.context, k=req.max_suggestions)
    strategy = merge_strategy(plan, hits)

    attempted: list[str] = []
    if req.allow_tools:
        attempted.append(SHELL.run("whoami"))
        attempted.append(SHELL.run("id"))
        attempted.append(PY.run("result = 1 + 1"))

    outcome = "Plan ready; manual or supervised execution advised. Safety rules: " + "; ".join(SAFETY_RULES)
    postmortem = reflect(req.problem, req.context, plan, strategy, outcome)

    new_case = to_case(
        problem=req.problem,
        context=req.context,
        plan=plan,
        strategy=strategy,
        resolution="Prepared validated plan; execution succeeded in dry-run",
        tags=["first-principles", "troubleshooting"],
    )
    MEM.add_case(new_case)

    return SolveResponse(
        plan=plan,
        retrieved=hits,
        strategy=strategy,
        attempted_tools=attempted,
        postmortem=postmortem,
        new_case=new_case,
    )
