"""Conversational Memory and State Management Module.
Persists multi-turn conversations into SQLite/PostgreSQL, maintains isolated session context,
structured rolling summaries, pending questions, and discussed opportunities cache.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.models.entities import Conversation, ConversationMessage, User, StudentProfile

logger = logging.getLogger(__name__)

class ConversationState:
    def __init__(
        self,
        conversation_id: str,
        user_id: Optional[str] = None,
        anonymous_session_id: Optional[str] = None,
        title: str = "New Conversation",
        summary: Optional[str] = None,
        pending_question: Optional[Dict[str, Any]] = None,
        discussed_opportunities: Optional[List[Dict[str, Any]]] = None,
        student_memory: Optional[Dict[str, Any]] = None,
        turn_count: int = 0
    ):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.anonymous_session_id = anonymous_session_id
        self.title = title
        self.summary = summary or ""
        self.pending_question = pending_question
        self.discussed_opportunities = discussed_opportunities or []
        self.student_memory = student_memory or {}
        self.turn_count = turn_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "anonymous_session_id": self.anonymous_session_id,
            "title": self.title,
            "summary": self.summary,
            "pending_question": self.pending_question,
            "discussed_opportunities": self.discussed_opportunities,
            "student_memory": self.student_memory,
            "student_profile": self.student_memory,
            "turn_count": self.turn_count
        }

    def serialize_state_data(self) -> str:
        return json.dumps({
            "pending_question": self.pending_question,
            "discussed_opportunities": self.discussed_opportunities,
            "student_memory": self.student_memory,
            "turn_count": self.turn_count
        })

def get_or_create_conversation(
    db: Session,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    anonymous_session_id: Optional[str] = None,
    initial_title: Optional[str] = None
) -> Conversation:
    """Retrieves an existing conversation or creates an isolated new session."""
    conv = None
    if conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conv:
            if user_id and conv.user_id and conv.user_id != user_id:
                logger.warning(f"Unauthorized conversation access attempt: user {user_id} tried accessing {conv.id}")
                conv = None

    if not conv:
        import uuid
        new_id = conversation_id if conversation_id else str(uuid.uuid4())
        conv = Conversation(
            id=new_id,
            user_id=user_id,
            anonymous_session_id=anonymous_session_id or f"anon_{uuid.uuid4().hex[:12]}",
            title=initial_title or "New Opportunity Exploration",
            summary="",
            state_data=json.dumps({
                "pending_question": None,
                "discussed_opportunities": [],
                "student_memory": {},
                "turn_count": 0
            })
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    return conv

def load_conversation_state(db: Session, conversation: Conversation) -> ConversationState:
    """Loads typed state from persisted conversation record."""
    state_dict = {}
    if conversation.state_data:
        try:
            state_dict = json.loads(conversation.state_data)
        except Exception:
            state_dict = {}

    return ConversationState(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        anonymous_session_id=conversation.anonymous_session_id,
        title=conversation.title,
        summary=conversation.summary,
        pending_question=state_dict.get("pending_question"),
        discussed_opportunities=state_dict.get("discussed_opportunities", []),
        student_memory=state_dict.get("student_memory", {}),
        turn_count=state_dict.get("turn_count", 0)
    )

def save_conversation_state(db: Session, conversation: Conversation, state: ConversationState):
    """Persists updated state and rolling summary to the database."""
    conversation.summary = state.summary
    conversation.title = state.title
    conversation.state_data = state.serialize_state_data()
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)

def record_turn(
    db: Session,
    conversation_id: str,
    user_message: str,
    assistant_message: str,
    intent: Optional[str] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None
):
    """Persists user and assistant messages for auditability and history restoration."""
    import uuid
    u_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=user_message,
        intent=intent,
        created_at=datetime.utcnow()
    )
    db.add(u_msg)

    a_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_message,
        intent=intent,
        citations=json.dumps(citations or []),
        tool_calls=json.dumps(tool_calls or []),
        created_at=datetime.utcnow()
    )
    db.add(a_msg)
    db.commit()

def load_message_history(
    db: Session,
    conversation_id: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Loads chronological message history for a conversation."""
    msgs = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation_id
    ).order_by(ConversationMessage.created_at.asc()).limit(limit).all()

    formatted = []
    for m in msgs:
        cit = []
        if m.citations:
            try:
                cit = json.loads(m.citations)
            except Exception:
                cit = []
        formatted.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "intent": m.intent,
            "citations": cit,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
    return formatted

def update_structured_summary(state: ConversationState, recent_user: str, recent_assistant: str):
    """Updates a compact, high-value structured summary of the conversation."""
    facts = []
    if state.student_memory:
        for k, v in state.student_memory.items():
            facts.append(f"{k}: {v}")
    
    opps = [o.get("title", "") for o in state.discussed_opportunities[-4:] if o.get("title")]
    
    summary_lines = [
        f"- Target Objective: {state.title}",
        f"- Verified Student Memory: {', '.join(facts) if facts else 'None provided yet'}",
        f"- Opportunities Discussed: {', '.join(opps) if opps else 'None yet'}",
        f"- Pending Question: {state.pending_question.get('question') if state.pending_question else 'None'}"
    ]
    state.summary = "\n".join(summary_lines)

def list_user_conversations(
    db: Session,
    user_id: Optional[str] = None,
    anonymous_session_id: Optional[str] = None,
    limit: int = 15
) -> List[Dict[str, Any]]:
    """Lists conversations isolated by user or anonymous session."""
    query = db.query(Conversation)
    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    elif anonymous_session_id:
        query = query.filter(Conversation.anonymous_session_id == anonymous_session_id)
    else:
        return []

    conversations = query.order_by(desc(Conversation.updated_at)).limit(limit).all()
    results = []
    for c in conversations:
        results.append({
            "id": c.id,
            "title": c.title,
            "summary": c.summary,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "message_count": len(c.messages)
        })
    return results

def delete_user_conversation(
    db: Session,
    conversation_id: str,
    user_id: Optional[str] = None,
    anonymous_session_id: Optional[str] = None
) -> bool:
    """Securely deletes a conversation and cascade deletes its messages."""
    query = db.query(Conversation).filter(Conversation.id == conversation_id)
    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    elif anonymous_session_id:
        query = query.filter(Conversation.anonymous_session_id == anonymous_session_id)

    conv = query.first()
    if not conv:
        return False

    db.delete(conv)
    db.commit()
    return True

def rename_user_conversation(
    db: Session,
    conversation_id: str,
    new_title: str,
    user_id: Optional[str] = None,
    anonymous_session_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Renames a conversation title."""
    query = db.query(Conversation).filter(Conversation.id == conversation_id)
    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    elif anonymous_session_id:
        query = query.filter(Conversation.anonymous_session_id == anonymous_session_id)

    conv = query.first()
    if not conv:
        return None

    conv.title = new_title.strip()[:255]
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)
    return {
        "id": conv.id,
        "title": conv.title,
        "updated_at": conv.updated_at.isoformat()
    }
