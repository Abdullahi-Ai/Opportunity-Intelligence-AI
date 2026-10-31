"""
Opportunity Intelligence AI - FastAPI Application Gateway.
Provides REST API endpoints for:
- RAG Vector Knowledge Retrieval (ChromaDB)
- Deterministic Agent Tool Execution (Search, Eligibility, Deadline, Checklist)
- System Health & Ingestion Management
"""

import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.rag.ingest import run_ingestion
from app.rag.vector_store import vector_store
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

allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["System"])
def root():
    return {
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "status": "operational",
        "docs_url": "/docs"
    }

@app.get("/api/v1/health", tags=["System"])
def health_check():
    stats = vector_store.get_stats()
    return {
        "status": "healthy",
        "chromadb": {
            "collection_name": stats["collection_name"],
            "total_chunks_indexed": stats["total_chunks"]
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
