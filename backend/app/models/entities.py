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

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    university = Column(String(255), nullable=False)
    field_of_study = Column(String(255), nullable=False)
    degree_level = Column(String(50), nullable=False)  # Undergraduate, Diploma, Masters, PhD
    year_of_study = Column(Integer, nullable=False)
    graduation_year = Column(Integer, nullable=True)
    county_of_origin = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tracked_applications = relationship("TrackedApplication", back_populates="student", cascade="all, delete-orphan")

class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String(100), primary_key=True)  # Matches raw document ID, e.g. 'opp-safaricom-attachment-2026'
    title = Column(String(255), nullable=False)
    provider = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    official_url = Column(Text, nullable=False)
    application_deadline = Column(String(50), nullable=True)
    is_verified = Column(Boolean, default=True)
    verification_date = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tracked_applications = relationship("TrackedApplication", back_populates="opportunity", cascade="all, delete-orphan")

class TrackedApplication(Base):
    __tablename__ = "tracked_applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    opportunity_id = Column(String(100), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False)
    stage = Column(String(50), default="Saved")  # Saved, Drafting, Submitted, Interview, Accepted, Rejected
    target_submission_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "opportunity_id", name="uq_student_opportunity"),
    )

    # Relationships
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

    # Relationships
    tracked_application = relationship("TrackedApplication", back_populates="checklists")
