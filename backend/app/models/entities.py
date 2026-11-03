"""
SQLAlchemy ORM Entities for Opportunity Intelligence AI.
Defines:
- StudentProfile
- Opportunity
- TrackedApplication
- ApplicationChecklist
"""

import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="student")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student_profile = relationship("StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    university = Column(String(255), nullable=False)
    field_of_study = Column(String(255), nullable=False)
    degree_level = Column(String(50), nullable=False)
    degree_title = Column(String(255), nullable=True)
    specialisations = Column(String(255), nullable=True)
    expected_graduation = Column(String(50), nullable=True)
    country = Column(String(100), nullable=True, default="Kenya")
    year_of_study = Column(Integer, nullable=False)
    graduation_year = Column(Integer, nullable=True)
    county_of_origin = Column(String(100), nullable=True)
    gpa_or_grade = Column(String(50), nullable=True)
    preferred_categories = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="student_profile")
    tracked_applications = relationship("TrackedApplication", back_populates="student", cascade="all, delete-orphan")

class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String(100), primary_key=True)
    title = Column(String(255), nullable=False)
    provider = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    target_audience = Column(String(255), nullable=True)
    fields_of_study = Column(Text, nullable=True)
    degree_levels = Column(String(255), nullable=True)
    official_url = Column(Text, nullable=False)
    application_deadline = Column(String(50), nullable=True)
    status = Column(String(50), default="open")
    is_verified = Column(Boolean, default=True)
    verification_date = Column(String(50), nullable=True)
    source_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tracked_applications = relationship("TrackedApplication", back_populates="opportunity", cascade="all, delete-orphan")

class TrackedApplication(Base):
    __tablename__ = "tracked_applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    opportunity_id = Column(String(100), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False)
    stage = Column(String(50), default="Saved")
    target_submission_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "opportunity_id", name="uq_student_opportunity"),
    )

    student = relationship("StudentProfile", back_populates="tracked_applications")
    opportunity = relationship("Opportunity", back_populates="tracked_applications")
    checklists = relationship("ApplicationChecklist", back_populates="tracked_application", cascade="all, delete-orphan")

class ApplicationChecklist(Base):
    __tablename__ = "application_checklists"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tracked_application_id = Column(String(36), ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False)
    task_description = Column(Text, nullable=False)
    is_completed = Column(Boolean, default=False)
    required_document_type = Column(String(100), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    tracked_application = relationship("TrackedApplication", back_populates="checklists")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    anonymous_session_id = Column(String(100), nullable=True, index=True)
    title = Column(String(255), default="New Conversation", nullable=False)
    summary = Column(Text, nullable=True)
    state_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at")

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    citations = Column(Text, nullable=True)
    tool_calls = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
