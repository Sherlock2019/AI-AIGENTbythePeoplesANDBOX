# services/api/main.py
from __future__ import annotations

import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

APP_NAME = "Demo Agent API"
APP_VERSION = "1.4.2"  # bump: adds credit-training router include



# ── Ensure repo root is importable (so 'agents.*' works even if CWD varies) ──
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Credit/Asset Appraisal PoC API with tunable guardrails, training, and downloads.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─────────────────────────────────────────────────────────────
# CORS (credentials-safe; no '*'), overridable via CORS_ALLOW_ORIGINS
# ─────────────────────────────────────────────────────────────
DEFAULT_ORIGINS = [
    "http://localhost:8501", "http://127.0.0.1:8501",
    "http://localhost:8502", "http://127.0.0.1:8502",
    "http://localhost:8090", "http://127.0.0.1:8090",
    "http://localhost:3000", "http://127.0.0.1:3000",
]
_env = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = [o.strip() for o in _env.split(",") if o.strip()] or DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────
from services.api.routers.system import router as system_router
from services.api.routers.agents import (
    router as agents_router,
    AGENT_REGISTRY,
    _ALIAS_TO_CANON,
)
from services.api.routers.reports import router as reports_router
from services.api.routers.training import router as training_router
# NEW: credit training endpoints
from services.api.routers.training_credit import router as training_credit_router
from services.api.routers.chat import router as chat_router
from services.api.routers.chatbot import router as chatbot_router
from services.api.routers.unified import router as unified_router

app.include_router(system_router)
app.include_router(agents_router)
app.include_router(reports_router)
app.include_router(training_router)
app.include_router(training_credit_router)  # <-- IMPORTANT
app.include_router(chat_router)
app.include_router(chatbot_router)
app.include_router(unified_router)

# ─────────────────────────────────────────────────────────────
# Root/health
# ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "version": APP_VERSION})

# ─────────────────────────────────────────────────────────────
# /v1/health alias with richer diagnostics for UI Probe
# ─────────────────────────────────────────────────────────────
@app.get("/v1/health")
def health_v1():
    return JSONResponse({
        "status": "ok",
        "version": APP_VERSION,
        "services": ["api"],
        "cors_allowed": origins,
        # Expose discovered agents and alias map so the UI Probe can display them
        "agents": [meta["id"] for meta in AGENT_REGISTRY.values()],
        "aliases": _ALIAS_TO_CANON,
    })
