"""FastAPI Conversational AI Assistant Chat & Memory Routes.
Integrates intent routing, persistent multi-turn conversations, isolated user sessions,
rolling structured summaries, and evidence citation delivery.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import StudentProfile, User, Conversation
from app.core.auth import get_optional_user
from app.agent.orchestrator import agent_orchestrator
from app.agent.memory import (
    get_or_create_conversation,
    load_conversation_state,
    load_message_history,
    list_user_conversations,
    delete_user_conversation,
    rename_user_conversation
)

router = APIRouter(prefix="/api/v1", tags=["Conversational AI Assistant"])

class ChatMessageRequest(BaseModel):
    message: str = Field(..., description="Student's natural language question or request")
    conversation_id: Optional[str] = Field(default=None, description="Unique conversation UUID")
    session_id: Optional[str] = Field(default=None, description="Optional anonymous session identifier")
    student_id: Optional[str] = Field(default=None, description="Optional student ID for profile memory injection")

class Citation(BaseModel):
    title: str
    url: str

class ChatResponse(BaseModel):
    response: str
    tool_calls: List[Dict[str, Any]] = []
    citations: List[Citation] = []
    conversation_id: str
    session_id: str
    intent: Optional[str] = None
    summary: Optional[str] = None
    timestamp: str

class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)

@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(
    payload: ChatMessageRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Submits a user message to the Opportunity Intelligence AI agent.
    Grounds answers in ChromaDB knowledge, evaluates eligibility,
    persists conversational context in PostgreSQL/SQLite, and returns verified citations.
    """
    # 1. Resolve student profile
    student_profile = None
    user_id = current_user.id if current_user else None

    if user_id and current_user.student_profile:
        sp = current_user.student_profile
        student_profile = {
            "full_name": sp.full_name,
            "university": sp.university,
            "field_of_study": sp.field_of_study,
            "degree_level": sp.degree_level,
            "year_of_study": sp.year_of_study,
            "county_of_origin": sp.county_of_origin,
            "gpa_or_grade": sp.gpa_or_grade,
            "preferred_categories": sp.preferred_categories
        }
    elif payload.student_id:
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

    # 2. Resolve or create conversation
    active_session_id = payload.session_id or f"sess_{user_id or 'anon'}"
    conv = get_or_create_conversation(
        db=db,
        conversation_id=payload.conversation_id,
        user_id=user_id,
        anonymous_session_id=active_session_id,
        initial_title=payload.message[:40]
    )

    # 3. Process Turn through the Agent Orchestrator Pipeline
    result = agent_orchestrator.process_turn(
        message=payload.message,
        conversation_id=conv.id,
        db=db,
        user_id=user_id,
        session_id=active_session_id,
        student_profile=student_profile
    )

    return ChatResponse(
        response=result["response"],
        tool_calls=result.get("tool_calls", []),
        citations=result.get("citations", []),
        conversation_id=conv.id,
        session_id=active_session_id,
        intent=result.get("intent"),
        summary=result.get("state", {}).get("summary"),
        timestamp=datetime.utcnow().isoformat()
    )

@router.get("/conversations")
def list_conversations(
    session_id: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Lists conversations for the authenticated user or anonymous session."""
    user_id = current_user.id if current_user else None
    return list_user_conversations(db=db, user_id=user_id, anonymous_session_id=session_id)

@router.get("/conversations/{conversation_id}")
def get_conversation_history(
    conversation_id: str,
    session_id: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Retrieves full message history, rolling summary, and state for a conversation."""
    user_id = current_user.id if current_user else None
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Isolation check
    if conv.user_id and user_id and conv.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot access another user's conversation.")

    state = load_conversation_state(db, conv)
    messages = load_message_history(db, conversation_id)

    return {
        "id": conv.id,
        "title": conv.title,
        "summary": conv.summary,
        "state": state.to_dict(),
        "messages": messages
    }

@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    payload: RenameConversationRequest,
    session_id: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Renames a conversation title."""
    user_id = current_user.id if current_user else None
    res = rename_user_conversation(db=db, conversation_id=conversation_id, new_title=payload.title, user_id=user_id, anonymous_session_id=session_id)
    if not res:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
    return res

@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    session_id: Optional[str] = Query(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Deletes a conversation and its messages."""
    user_id = current_user.id if current_user else None
    success = delete_user_conversation(db=db, conversation_id=conversation_id, user_id=user_id, anonymous_session_id=session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")
    return {"status": "success", "message": f"Conversation {conversation_id} successfully deleted."}
