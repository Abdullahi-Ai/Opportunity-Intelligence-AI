"""
Opportunity Intelligence AI - FastAPI Application Gateway.
Provides REST API endpoints for:
- RAG Vector Knowledge Retrieval (ChromaDB)
- Deterministic Agent Tool Execution (Search, Eligibility, Deadline, Checklist)
- System Health & Ingestion Management
"""

import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

from app.config import settings
from app.db.session import engine
from app.rag import get_vector_store
from app.rag.ingest import run_ingestion
from app.agent.tools import (
    SearchOpportunitiesInput,
    tool_search_opportunities,
    DeadlineCountdownInput,
    tool_calculate_deadline_countdown,
    AssessEligibilityInput,
    tool_assess_eligibility,
    GenerateChecklistInput,
    tool_generate_application_checklist
)
from app.api.endpoints import router as tracker_router
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Full-Stack Agentic AI Platform for University Students in Kenya",
    version="1.0.0"
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(tracker_router)
app.include_router(chat_router)

PREVIEW_ORIGIN_REGEX = r"^https://opportunity-intelligence-ai(-[a-z0-9-]+)?\.vercel\.app$"

is_production = settings.APP_ENV.lower() in ["production", "prod", "staging"]
configured_origins = [origin.strip() for origin in (settings.ALLOWED_ORIGINS or "").split(",") if origin.strip()]
dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

if is_production:
    if not configured_origins:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: ALLOWED_ORIGINS must be explicitly configured in production. Localhost fallback is prohibited."
        )
    if "*" in configured_origins:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Wildcard origin '*' is prohibited in production when credentials are enabled."
        )
    effective_origins = configured_origins
    preview_origin_regex = PREVIEW_ORIGIN_REGEX
else:
    effective_origins = list(dict.fromkeys(configured_origins + dev_origins)) if configured_origins else dev_origins
    preview_origin_regex = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=effective_origins,
    allow_origin_regex=preview_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request size guard (1MB max payload to prevent serverless memory exhaustion)
MAX_REQUEST_BODY_SIZE = 1_000_000

@app.middleware("http")
async def security_and_payload_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
        return JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={"detail": "Request payload too large. Maximum allowed size is 1 MB."}
        )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )

@app.exception_handler(Exception)
async def unhandled_exception_sanitizer(request: Request, exc: Exception):
    logger.error("Unhandled server exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )

@app.get("/", tags=["System"])
def root():
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "status": "operational",
        "docs_url": "/docs"
    }

@app.get("/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
def health_check():
    store = get_vector_store()
    stats = store.get_stats()
    is_postgres = engine.dialect.name == "postgresql"
    vector_backend = "pgvector" if is_postgres else "chromadb"
    return {
        "status": "healthy",
        "vector_backend": vector_backend,
        "vector_store": {
            "backend": vector_backend,
            "collection_name": stats.get("collection_name", "opportunity_chunks"),
            "total_chunks_indexed": stats.get("total_chunks", 0)
        },
        "chromadb": {
            "collection_name": stats.get("collection_name", "opportunity_chunks"),
            "total_chunks_indexed": stats.get("total_chunks", 0)
        },
        "llm_provider": "Groq",
        "model": settings.GROQ_MODEL
    }

@app.post("/api/v1/rag/ingest", tags=["RAG"])
def trigger_ingestion():
    """Triggers batch document ingestion from raw markdown into ChromaDB."""
    try:
        result = run_ingestion()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )

@app.post("/api/v1/rag/search", tags=["RAG"])
def search_knowledge_base(payload: SearchOpportunitiesInput):
    """Semantic vector search against verified opportunity chunks in ChromaDB."""
    return tool_search_opportunities(payload)

@app.post("/api/v1/agent/deadline-countdown", tags=["Agent Tools"])
def calculate_deadline(payload: DeadlineCountdownInput):
    """Deterministic date arithmetic to calculate remaining days until application close."""
    return tool_calculate_deadline_countdown(payload)

@app.post("/api/v1/agent/assess-eligibility", tags=["Agent Tools"])
def assess_eligibility(payload: AssessEligibilityInput):
    """Evaluates student academic profile against published opportunity criteria."""
    return tool_assess_eligibility(payload)

@app.post("/api/v1/agent/generate-checklist", tags=["Agent Tools"])
def generate_checklist(payload: GenerateChecklistInput):
    """Produces a structured document and application task checklist."""
    return tool_generate_application_checklist(payload)
