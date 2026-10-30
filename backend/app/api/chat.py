"""
FastAPI Conversational AI Assistant Chat Route.
Integrates Groq LLM agent orchestration, persistent student profile memory injection,
session context management, and evidence citation delivery.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import StudentProfile
from app.agent.orchestrator import agent_orchestrator

router = APIRouter(prefix="/api/v1", tags=["Conversational AI Assistant"])

class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Student's natural language question or request")
    session_id: Optional[str] = Field(default="default_session", description="Session identifier for multi-turn context")
    student_id: Optional[str] = Field(default=None, description="Optional student ID for preference memory injection")

class Citation(BaseModel):
    title: str
    url: str

class ChatResponse(BaseModel):
    response: str
    tool_calls: List[Dict[str, Any]] = []
    citations: List[Citation] = []
    session_id: str
    timestamp: str

@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    """
    Submits a user message to the Opportunity Intelligence AI agent.
    Grounds answers in ChromaDB knowledge, evaluates eligibility,
    and returns citations to verified official Kenyan sources.
    """
    student_profile = None
    if payload.student_id:
        student = db.query(StudentProfile).filter(StudentProfile.id == payload.student_id).first()
        if student:
            student_profile = {
                "full_name": student.full_name,
                "university": student.university,
                "field_of_study": student.field_of_study,
                "degree_level": student.degree_level,
                "year_of_study": student.year_of_study,
                "county_of_origin": student.county_of_origin,
                "gpa_or_grade": student.gpa_or_grade,
                "preferred_categories": student.preferred_categories
            }

    result = agent_orchestrator.chat(
        message=payload.message,
        session_id=payload.session_id or "default_session",
        student_profile=student_profile
    )

    return ChatResponse(
        response=result["response"],
        tool_calls=result.get("tool_calls", []),
        citations=result.get("citations", []),
        session_id=payload.session_id or "default_session",
        timestamp=datetime.utcnow().isoformat()
    )
