# AI Troubleshooter Agent — First‑Principles + Case Memory

Minimal FastAPI service that:

1. derives troubleshooting steps via a first‑principles planner,
2. looks up similar solved cases with TF‑IDF + optional Sentence‑Transformers embeddings,
3. merges fresh reasoning with prior solutions into a safe execution strategy,
4. runs allow‑listed shell/python tools behind a safety toggle,
5. writes a post‑mortem and persists the new case back to memory.

## Quick start

```bash
cd troubleshooter
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

### Demo request

```bash
curl -s -X POST http://localhost:8000/solve \
  -H 'Content-Type: application/json' \
  -d '{
    "problem": "Web service fails on startup in Docker after moving to Ubuntu 22.04",
    "context": "Logs show getpwuid errors and missing vcruntime in WSL; service uses Python 3.10."
  }' | jq .
```

### Endpoints

| Method | Path         | Description                                      |
| ------ | ------------ | ------------------------------------------------ |
| GET    | `/health`    | Basic service status + case count                |
| GET    | `/cases/{id}`| Retrieve a stored case                           |
| POST   | `/cases`     | Insert a new solved case                         |
| POST   | `/solve`     | Full pipeline (plan → retrieve → reflect → store)|

### Design highlights

- **First‑principles planner** extracts assumptions, constraints, sub‑problems, and tests.
- **Hybrid memory**: TF‑IDF keyword search plus embeddings (if available) for semantic matches.
- **Safe tools**: shell/python helpers allow only non‑destructive commands and whitelisted builtins.
- **Reflection loop**: every solve run produces a post‑mortem and stores a new reusable case.
