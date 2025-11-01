# services/api/main.py
from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

APP_NAME = "Demo Agent API"
APP_VERSION = "1.4.0"  # bumped for new features

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Credit Appraisal PoC API with tunable guardrails, training, and downloads.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS (credentials-safe; no '*')
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

# Routers
from services.api.routers.system import router as system_router
from services.api.routers.agents import router as agents_router
from services.api.routers.reports import router as reports_router
from services.api.routers.training import router as training_router

app.include_router(system_router)
app.include_router(agents_router)
app.include_router(reports_router)
app.include_router(training_router)

# Root/health
@app.get("/")
def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "version": APP_VERSION})
