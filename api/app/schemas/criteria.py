"""
Pydantic schemas for Opportunity Eligibility Criteria and Criterion Audit Logs.

Phase 2 — Stages 2.2B-1 & 2.2B-3.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class CriterionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    criterion_type: str
    operator: str
    criterion_value: str
    grading_system: Optional[str] = None
    numeric_scale: Optional[Decimal] = None
    is_mandatory: bool = True
    source_text: str
    evidence_url: Optional[str] = None
    verification_status: str
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CriterionCreateRequest(BaseModel):
    criterion_type: str = Field(..., description="Controlled category string")
    operator: str = Field(..., description="Relational operator (GTE, LTE, EQ, IN, BETWEEN)")
    criterion_value: str = Field(..., min_length=1, description="Normalized criterion value")
    grading_system: Optional[str] = None
    numeric_scale: Optional[Decimal] = None
    is_mandatory: bool = True
    source_text: str = Field(..., min_length=1, description="Verbatim source excerpt")
    evidence_url: Optional[str] = None

    @field_validator("source_text", "criterion_value")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace only.")
        return v.strip()


class CriterionUpdateRequest(BaseModel):
    criterion_value: Optional[str] = None
    operator: Optional[str] = None
    is_mandatory: Optional[bool] = None
    source_text: Optional[str] = None
    evidence_url: Optional[str] = None
    numeric_scale: Optional[Decimal] = None
    grading_system: Optional[str] = None
    review_notes: str = Field(..., min_length=3, description="Audit reason for modifying the criterion")


class CriterionVerifyRequest(BaseModel):
    evidence_url: str = Field(..., min_length=5, description="Authoritative official URL")
    evidence_notes: str = Field(..., min_length=5, description="Administrative audit notes")


class CriterionRejectRequest(BaseModel):
    evidence_notes: str = Field(..., min_length=5, description="Reason for criterion rejection")


class CriterionFlagRequest(BaseModel):
    evidence_notes: str = Field(..., min_length=5, description="Reason for flagging criterion for review")


class CriterionReopenRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Justification for reopening previously reviewed criterion")


class CriterionAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    criterion_id: str
    admin_id: Optional[str] = None
    admin_email: Optional[str] = None
    event_type: str
    previous_status: str
    new_status: str
    before_snapshot: Optional[str] = None
    after_snapshot: Optional[str] = None
    evidence_url: Optional[str] = None
    evidence_notes: str
    created_at: datetime
