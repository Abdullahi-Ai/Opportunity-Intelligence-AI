"""
SQLAlchemy ORM Entities for Opportunity Intelligence AI.
Defines:
- StudentProfile
- Opportunity
- TrackedApplication
- ApplicationChecklist
"""

import uuid
from enum import Enum
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
    UniqueConstraint,
    Index,
    Numeric,
    CheckConstraint,
    event
)
from sqlalchemy.orm import relationship, validates
from app.db.session import Base

class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"

class CriterionCategory(str, Enum):
    """Controlled vocabulary of opportunity eligibility criterion categories."""
    MINIMUM_ACADEMIC_GRADE = "MINIMUM_ACADEMIC_GRADE"
    KCSE_GRADE = "KCSE_GRADE"
    NUMERIC_GPA = "NUMERIC_GPA"
    COUNTY_RESTRICTION = "COUNTY_RESTRICTION"
    GEOGRAPHIC_ALLOCATION = "GEOGRAPHIC_ALLOCATION"
    GRADUATION_YEAR_RANGE = "GRADUATION_YEAR_RANGE"
    MONTHS_SINCE_GRADUATION = "MONTHS_SINCE_GRADUATION"
    EXPECTED_GRADUATION_WINDOW = "EXPECTED_GRADUATION_WINDOW"
    ACADEMIC_STANDING = "ACADEMIC_STANDING"
    OTHER = "OTHER"

class CriterionOperator(str, Enum):
    """Controlled vocabulary of criterion evaluation operators."""
    GTE = "GTE"
    LTE = "LTE"
    EQ = "EQ"
    IN = "IN"
    BETWEEN = "BETWEEN"

class CriterionVerificationStatus(str, Enum):
    """Controlled criterion-specific verification status."""
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"

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
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_status = Column(String(30), default=VerificationStatus.UNVERIFIED.value, nullable=False)
    verification_date = Column(String(50), nullable=True)
    source_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tracked_applications = relationship("TrackedApplication", back_populates="opportunity", cascade="all, delete-orphan")
    # CRIT-02 & Correction 3: Protect audit history. passive_deletes="all" delegates constraint
    # enforcement entirely to the database ON DELETE RESTRICT foreign key, preventing SQLAlchemy
    # from issuing client-side cascading deletes of regulatory audit trails.
    verification_logs = relationship(
        "OpportunityVerificationLog",
        back_populates="opportunity",
        passive_deletes="all",
        order_by="desc(OpportunityVerificationLog.created_at)"
    )
    # Stage 2.2B-1: Protect eligibility criteria. passive_deletes="all" delegates constraint
    # enforcement entirely to the database ON DELETE RESTRICT foreign key, ensuring an opportunity
    # cannot be deleted while eligibility criteria exist.
    eligibility_criteria = relationship(
        "OpportunityEligibilityCriterion",
        back_populates="opportunity",
        passive_deletes="all",
        order_by="asc(OpportunityEligibilityCriterion.created_at)"
    )

class OpportunityVerificationLog(Base):
    __tablename__ = "opportunity_verification_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    opportunity_id = Column(String(100), ForeignKey("opportunities.id", ondelete="RESTRICT"), nullable=False, index=True)
    admin_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_email = Column(String(255), nullable=True)
    previous_status = Column(String(30), nullable=False)
    new_status = Column(String(30), nullable=False)
    official_source_url = Column(Text, nullable=True)
    evidence_notes = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_opp_ver_logs_opp_created", "opportunity_id", "created_at"),
    )

    opportunity = relationship("Opportunity", back_populates="verification_logs")
    admin = relationship("User")

class OpportunityEligibilityCriterion(Base):
    __tablename__ = "opportunity_eligibility_criteria"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    opportunity_id = Column(String(100), ForeignKey("opportunities.id", ondelete="RESTRICT"), nullable=False, index=True)
    criterion_type = Column(String(50), nullable=False, index=True)
    operator = Column(String(20), nullable=False)
    criterion_value = Column(String(255), nullable=False)
    grading_system = Column(String(50), nullable=True)
    numeric_scale = Column(Numeric(6, 2), nullable=True)
    is_mandatory = Column(Boolean, nullable=False, default=True)
    source_text = Column(Text, nullable=False)
    evidence_url = Column(Text, nullable=True)
    verification_status = Column(
        String(30),
        nullable=False,
        default=CriterionVerificationStatus.PENDING_REVIEW.value,
        index=True
    )
    verified_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_opp_crit_opp_type", "opportunity_id", "criterion_type"),
        Index("ix_opp_crit_opp_status", "opportunity_id", "verification_status"),
        CheckConstraint(
            "criterion_type IN ("
            "'MINIMUM_ACADEMIC_GRADE', 'KCSE_GRADE', 'NUMERIC_GPA', "
            "'COUNTY_RESTRICTION', 'GEOGRAPHIC_ALLOCATION', 'GRADUATION_YEAR_RANGE', "
            "'MONTHS_SINCE_GRADUATION', 'EXPECTED_GRADUATION_WINDOW', 'ACADEMIC_STANDING', 'OTHER'"
            ")",
            name="ck_opp_crit_type"
        ),
        CheckConstraint(
            "operator IN ('GTE', 'LTE', 'EQ', 'IN', 'BETWEEN')",
            name="ck_opp_crit_operator"
        ),
        CheckConstraint(
            "verification_status IN ('PENDING_REVIEW', 'VERIFIED', 'NEEDS_REVIEW', 'REJECTED')",
            name="ck_opp_crit_status"
        ),
        CheckConstraint(
            "length(trim(source_text)) > 0",
            name="ck_opp_crit_source_text_not_empty"
        ),
        CheckConstraint(
            "length(trim(criterion_value)) > 0",
            name="ck_opp_crit_value_not_empty"
        ),
        CheckConstraint(
            "numeric_scale IS NULL OR numeric_scale > 0",
            name="ck_opp_crit_numeric_scale_positive"
        ),
        CheckConstraint(
            "(verification_status != 'VERIFIED') OR "
            "(verified_at IS NOT NULL AND evidence_url IS NOT NULL AND length(trim(evidence_url)) > 0)",
            name="ck_opp_crit_verified_requirements"
        ),
        CheckConstraint(
            "(verification_status != 'PENDING_REVIEW') OR (verified_at IS NULL)",
            name="ck_opp_crit_pending_no_verified_meta"
        ),
    )

    opportunity = relationship("Opportunity", back_populates="eligibility_criteria")
    verified_by_admin = relationship("User")
    # Phase 2 Stage 2.2B-1A: Protect criterion audit history. passive_deletes="all" delegates constraint
    # enforcement entirely to the database ON DELETE RESTRICT foreign key, preventing SQLAlchemy
    # from issuing client-side cascading deletes of regulatory audit trails.
    verification_logs = relationship(
        "OpportunityCriterionVerificationLog",
        back_populates="criterion",
        passive_deletes="all",
        order_by="desc(OpportunityCriterionVerificationLog.created_at)"
    )

    @validates("criterion_type")
    def validate_criterion_type(self, key, value):
        valid = {c.value for c in CriterionCategory}
        if value not in valid:
            raise ValueError(f"Invalid criterion_type '{value}'. Must be one of: {sorted(valid)}")
        return value

    @validates("operator")
    def validate_operator(self, key, value):
        valid = {o.value for o in CriterionOperator}
        if value not in valid:
            raise ValueError(f"Invalid operator '{value}'. Must be one of: {sorted(valid)}")
        return value

    @validates("verification_status")
    def validate_verification_status(self, key, value):
        valid = {s.value for s in CriterionVerificationStatus}
        if value not in valid:
            raise ValueError(f"Invalid verification_status '{value}'. Must be one of: {sorted(valid)}")
        return value

    @validates("source_text")
    def validate_source_text(self, key, value):
        if value is None or not str(value).strip():
            raise ValueError("source_text cannot be empty or whitespace-only.")
        return str(value).strip()

    @validates("criterion_value")
    def validate_criterion_value(self, key, value):
        if value is None or not str(value).strip():
            raise ValueError("criterion_value cannot be empty or whitespace-only.")
        return str(value).strip()

    @validates("numeric_scale")
    def validate_numeric_scale(self, key, value):
        if value is not None and float(value) <= 0:
            raise ValueError("numeric_scale must be strictly greater than zero.")
        return value

@event.listens_for(OpportunityEligibilityCriterion, "before_insert")
@event.listens_for(OpportunityEligibilityCriterion, "before_update")
def validate_criterion_invariants(mapper, connection, target):
    """Enforces criterion verification invariants before persisting to database."""
    if target.verification_status == CriterionVerificationStatus.VERIFIED.value:
        if not target.verified_by:
            raise ValueError("A VERIFIED criterion must specify a non-empty verified_by administrator identity.")
        if target.verified_at is None:
            raise ValueError("A VERIFIED criterion must specify a non-null verified_at timestamp.")
        if not target.evidence_url or not str(target.evidence_url).strip():
            raise ValueError("A VERIFIED criterion must specify a non-empty authoritative evidence_url.")
    elif target.verification_status == CriterionVerificationStatus.PENDING_REVIEW.value:
        if target.verified_by is not None or target.verified_at is not None:
            raise ValueError("A PENDING_REVIEW criterion must not retain verified_by or verified_at metadata.")

class OpportunityCriterionVerificationLog(Base):
    __tablename__ = "opportunity_criterion_verification_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    criterion_id = Column(String(36), ForeignKey("opportunity_eligibility_criteria.id", ondelete="RESTRICT"), nullable=False, index=True)
    admin_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_email = Column(String(255), nullable=True)
    event_type = Column(String(50), nullable=False, default="STATUS_CHANGE")
    previous_status = Column(String(30), nullable=False)
    new_status = Column(String(30), nullable=False)
    before_snapshot = Column(Text, nullable=True)
    after_snapshot = Column(Text, nullable=True)
    evidence_url = Column(Text, nullable=True)
    evidence_notes = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_crit_ver_logs_crit_created", "criterion_id", "created_at"),
        CheckConstraint(
            "previous_status IN ('PENDING_REVIEW', 'VERIFIED', 'NEEDS_REVIEW', 'REJECTED')",
            name="ck_crit_log_prev_status"
        ),
        CheckConstraint(
            "new_status IN ('PENDING_REVIEW', 'VERIFIED', 'NEEDS_REVIEW', 'REJECTED')",
            name="ck_crit_log_new_status"
        ),
        CheckConstraint(
            "length(trim(evidence_notes)) > 0",
            name="ck_crit_log_notes_not_empty"
        ),
    )

    criterion = relationship("OpportunityEligibilityCriterion", back_populates="verification_logs")
    admin = relationship("User")


@event.listens_for(OpportunityCriterionVerificationLog, "before_update")
def prevent_audit_log_update(mapper, connection, target):
    """Enforces ORM-level append-only immutability for criterion verification audit logs."""
    raise ValueError("OpportunityCriterionVerificationLog records are immutable and cannot be updated.")


@event.listens_for(OpportunityCriterionVerificationLog, "before_delete")
def prevent_audit_log_delete(mapper, connection, target):
    """Enforces ORM-level append-only immutability for criterion verification audit logs."""
    raise ValueError("OpportunityCriterionVerificationLog records are immutable and cannot be deleted.")

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
