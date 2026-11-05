"""Administrator Opportunity Management Endpoints.
Guarded by role-based authorization (require_admin).
Allows verified administrators to curate opportunities, verify sources, and update deadlines.
Enforces auditable verification history, evidence-based certification, and valid state transitions.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uuid
import re
import ipaddress
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Opportunity, User, VerificationStatus, OpportunityVerificationLog
from app.core.auth import require_admin
from app.agent.tools import tool_calculate_deadline_countdown, DeadlineCountdownInput

router = APIRouter(prefix="/api/v1/admin", tags=["Administrator Operations"])

VALID_TRANSITIONS: Dict[str, set] = {
    VerificationStatus.UNVERIFIED.value: {
        VerificationStatus.PENDING_REVIEW.value,
        VerificationStatus.VERIFIED.value,
        VerificationStatus.NEEDS_REVIEW.value,
        VerificationStatus.REJECTED.value,
    },
    VerificationStatus.PENDING_REVIEW.value: {
        VerificationStatus.VERIFIED.value,
        VerificationStatus.NEEDS_REVIEW.value,
        VerificationStatus.REJECTED.value,
        VerificationStatus.UNVERIFIED.value,
    },
    VerificationStatus.VERIFIED.value: {
        VerificationStatus.NEEDS_REVIEW.value,
        VerificationStatus.REJECTED.value,
        VerificationStatus.PENDING_REVIEW.value,
    },
    VerificationStatus.NEEDS_REVIEW.value: {
        VerificationStatus.VERIFIED.value,
        VerificationStatus.PENDING_REVIEW.value,
        VerificationStatus.REJECTED.value,
    },
    VerificationStatus.REJECTED.value: {
        VerificationStatus.PENDING_REVIEW.value,
    },
}

def validate_url(url: Optional[str]) -> bool:
    """Validates official source URL syntax and host safety.
    Requires valid HTTP/HTTPS scheme and valid public domain name or public IP.
    Rejects:
    - Non-HTTP/HTTPS schemes
    - Missing hosts and malformed URLs
    - Localhost names ('localhost', 'localhost.localdomain')
    - Loopback addresses (127.0.0.0/8, ::1, IPv4-mapped IPv6 ::ffff:127.x.x.x)
    - Loopback and private IP addresses with explicit port numbers
    - Unspecified/wildcard addresses (0.0.0.0, ::)
    - Private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
    - Link-local IP ranges (169.254.0.0/16, fe80::/10)
    - Unqualified single-label hostnames without a public domain dot
    """
    if not url:
        return False
    clean = url.strip()
    try:
        parsed = urlparse(clean)
        # 1. Enforce HTTP/HTTPS scheme
        if parsed.scheme.lower() not in ("http", "https"):
            return False

        # 2. Extract hostname safely (strips port and brackets from IPv6)
        hostname = parsed.hostname
        if not hostname:
            return False
        hostname_lower = hostname.lower()

        # 3. Reject localhost strings
        if hostname_lower in ("localhost", "localhost.localdomain"):
            return False

        # 4. Check if hostname is an IP address (IPv4, IPv6, or IPv4-mapped IPv6)
        try:
            ip = ipaddress.ip_address(hostname_lower)
            # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                ip = ip.ipv4_mapped

            if ip.is_loopback or ip.is_unspecified or ip.is_private or ip.is_link_local or ip.is_reserved:
                return False
            # Valid public IP address
            return True
        except ValueError:
            # Not an IP address -> Must be a valid domain name
            pass

        # 5. Domain name validation: must contain a dot, non-empty labels, valid TLD
        labels = hostname_lower.split(".")
        if len(labels) < 2 or any(not label for label in labels):
            return False

        tld = labels[-1]
        if tld.isdigit() or len(tld) < 2:
            return False

        return True
    except Exception:
        return False

class OpportunityCreateOrUpdate(BaseModel):
    title: str = Field(..., min_length=3)
    provider: str = Field(..., min_length=2)
    category: str = Field(..., description="Scholarship, Internship, Fellowship, Competition, etc.")
    target_audience: Optional[str] = None
    fields_of_study: Optional[str] = "All Fields"
    degree_levels: Optional[str] = "Undergraduate, Postgraduate"
    official_url: str = Field(..., description="Authoritative official URL")
    application_deadline: Optional[str] = Field(None, description="ISO format YYYY-MM-DD or None for rolling")
    is_verified: bool = False
    verification_status: Optional[str] = Field(default=VerificationStatus.UNVERIFIED.value)
    verification_date: Optional[str] = None
    source_notes: Optional[str] = None
    status: str = Field(default="open")

class OpportunityAdminResponse(BaseModel):
    id: str
    title: str
    provider: str
    category: str
    target_audience: Optional[str] = None
    fields_of_study: Optional[str] = None
    degree_levels: Optional[str] = None
    official_url: str
    application_deadline: Optional[str] = None
    is_verified: bool
    verification_status: str = VerificationStatus.UNVERIFIED.value
    verification_date: Optional[str] = None
    source_notes: Optional[str] = None
    status: str
    days_remaining: Optional[int] = None
    deadline_status_label: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class VerifyOpportunityRequest(BaseModel):
    status: Optional[str] = Field(None, description="Target verification status: VERIFIED, NEEDS_REVIEW, PENDING_REVIEW, REJECTED, UNVERIFIED")
    is_verified: Optional[bool] = Field(None, description="Legacy boolean compatibility: True maps to VERIFIED, False maps to REJECTED")
    official_source_url: Optional[str] = Field(None, description="Official primary source URL supporting verification")
    evidence_notes: Optional[str] = Field(None, description="Detailed evidence notes and audit rationale (min 10 chars for VERIFIED)")
    source_notes: Optional[str] = Field(None, description="Alias for evidence_notes")
    metadata_json: Optional[str] = None

class VerificationLogResponse(BaseModel):
    id: str
    opportunity_id: str
    admin_id: Optional[str] = None
    admin_email: Optional[str] = None
    previous_status: str
    new_status: str
    official_source_url: Optional[str] = None
    evidence_notes: str
    metadata_json: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

@router.post("/opportunities", response_model=OpportunityAdminResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreateOrUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Ingest a newly curated opportunity.
    Enforces safe defaults: newly created records default to UNVERIFIED unless
    evidence is explicitly validated.
    """
    opp_id = f"opp-{uuid.uuid4().hex[:8]}"
    
    # Resolve requested verification status
    requested_status = (payload.verification_status or "UNVERIFIED").strip().upper()
    if requested_status not in [s.value for s in VerificationStatus]:
        requested_status = VerificationStatus.UNVERIFIED.value

    # If admin attempts to certify directly at creation, validate evidence
    if requested_status == VerificationStatus.VERIFIED.value or payload.is_verified:
        if not validate_url(payload.official_url):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A valid official source URL starting with http:// or https:// is required to certify an opportunity."
            )
        notes = (payload.source_notes or "").strip()
        if len(notes) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Verification evidence notes must be at least 10 characters documenting primary source proof."
            )
        final_status = VerificationStatus.VERIFIED.value
        is_ver = True
        ver_date = payload.verification_date or date.today().isoformat()
    else:
        final_status = requested_status
        is_ver = False
        ver_date = None

    opp = Opportunity(
        id=opp_id,
        title=payload.title,
        provider=payload.provider,
        category=payload.category,
        target_audience=payload.target_audience,
        fields_of_study=payload.fields_of_study,
        degree_levels=payload.degree_levels,
        official_url=payload.official_url,
        application_deadline=payload.application_deadline,
        is_verified=is_ver,
        verification_status=final_status,
        verification_date=ver_date,
        source_notes=payload.source_notes,
        status=payload.status
    )
    db.add(opp)
    db.flush()

    # Record initial audit log entry
    audit_log = OpportunityVerificationLog(
        opportunity_id=opp.id,
        admin_id=admin_user.id,
        admin_email=admin_user.email,
        previous_status="NEW",
        new_status=final_status,
        official_source_url=payload.official_url if is_ver else None,
        evidence_notes=payload.source_notes or f"Initial creation by administrator in status {final_status}.",
        metadata_json=None
    )
    db.add(audit_log)
    db.commit()
    db.refresh(opp)

    calc = tool_calculate_deadline_countdown(
        DeadlineCountdownInput(
            deadline_str=opp.application_deadline,
            is_officially_verified=(opp.verification_status == VerificationStatus.VERIFIED.value),
            verification_source=opp.provider,
            verification_date=opp.verification_date
        )
    )

    return OpportunityAdminResponse(
        id=opp.id,
        title=opp.title,
        provider=opp.provider,
        category=opp.category,
        target_audience=opp.target_audience,
        fields_of_study=opp.fields_of_study,
        degree_levels=opp.degree_levels,
        official_url=opp.official_url,
        application_deadline=opp.application_deadline,
        is_verified=opp.is_verified,
        verification_status=opp.verification_status,
        verification_date=opp.verification_date,
        source_notes=opp.source_notes,
        status=opp.status,
        days_remaining=calc.get("days_remaining"),
        deadline_status_label=calc.get("status_label")
    )

@router.put("/opportunities/{opportunity_id}", response_model=OpportunityAdminResponse)
def update_opportunity(
    opportunity_id: str,
    payload: OpportunityCreateOrUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Correct or update an existing opportunity's requirements, dates, or source notes."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    url_changed = (payload.official_url or "").strip() != (opp.official_url or "").strip()
    deadline_changed = (payload.application_deadline or "").strip() != (opp.application_deadline or "").strip()
    previous_status = opp.verification_status or ("VERIFIED" if opp.is_verified else "UNVERIFIED")

    opp.title = payload.title
    opp.provider = payload.provider
    opp.category = payload.category
    opp.target_audience = payload.target_audience
    opp.fields_of_study = payload.fields_of_study
    opp.degree_levels = payload.degree_levels
    opp.official_url = payload.official_url
    opp.application_deadline = payload.application_deadline
    opp.status = payload.status
    opp.source_notes = payload.source_notes

    # HIGH-02: If core evidence (official URL or application deadline) was modified on a VERIFIED opportunity,
    # automatically demote to NEEDS_REVIEW, set is_verified=False, and log an auditable event.
    if previous_status == VerificationStatus.VERIFIED.value and (url_changed or deadline_changed):
        change_reasons = []
        if url_changed:
            change_reasons.append(f"Official URL modified to '{payload.official_url}'")
        if deadline_changed:
            change_reasons.append(f"Deadline modified to '{payload.application_deadline}'")
        reason_str = "; ".join(change_reasons)

        opp.verification_status = VerificationStatus.NEEDS_REVIEW.value
        opp.is_verified = False
        opp.verification_date = None

        audit_log = OpportunityVerificationLog(
            opportunity_id=opp.id,
            admin_id=admin_user.id,
            admin_email=admin_user.email,
            previous_status=previous_status,
            new_status=VerificationStatus.NEEDS_REVIEW.value,
            official_source_url=payload.official_url,
            evidence_notes=f"Automated demotion to NEEDS_REVIEW: Core certified fields updated by {admin_user.email}. {reason_str}. Fresh administrator verification required.",
            metadata_json=None
        )
        db.add(audit_log)

    db.commit()
    db.refresh(opp)

    current_status = getattr(opp, "verification_status", None) or ("VERIFIED" if opp.is_verified else "UNVERIFIED")
    calc = tool_calculate_deadline_countdown(
        DeadlineCountdownInput(
            deadline_str=opp.application_deadline,
            is_officially_verified=(current_status == VerificationStatus.VERIFIED.value),
            verification_source=opp.provider,
            verification_date=opp.verification_date
        )
    )

    return OpportunityAdminResponse(
        id=opp.id,
        title=opp.title,
        provider=opp.provider,
        category=opp.category,
        target_audience=opp.target_audience,
        fields_of_study=opp.fields_of_study,
        degree_levels=opp.degree_levels,
        official_url=opp.official_url,
        application_deadline=opp.application_deadline,
        is_verified=opp.is_verified,
        verification_status=current_status,
        verification_date=opp.verification_date,
        source_notes=opp.source_notes,
        status=opp.status,
        days_remaining=calc.get("days_remaining"),
        deadline_status_label=calc.get("status_label")
    )

@router.post("/opportunities/{opportunity_id}/verify", response_model=OpportunityAdminResponse)
def verify_opportunity(
    opportunity_id: str,
    payload: VerifyOpportunityRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Review and certify the source verification of an opportunity.
    Enforces:
    1. Valid status transitions.
    2. Evidence validation (official URL + rationale notes).
    3. Auditable decision logging with admin identity.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    # Resolve target status
    if payload.status:
        target_status = payload.status.strip().upper()
    elif payload.is_verified is True:
        target_status = VerificationStatus.VERIFIED.value
    elif payload.is_verified is False:
        target_status = VerificationStatus.REJECTED.value
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Verification decision requires a valid 'status' (VERIFIED, NEEDS_REVIEW, PENDING_REVIEW, REJECTED, UNVERIFIED) or 'is_verified' boolean."
        )

    if target_status not in [s.value for s in VerificationStatus]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid verification status '{target_status}'. Must be one of {[s.value for s in VerificationStatus]}."
        )

    current_status = getattr(opp, "verification_status", None) or ("VERIFIED" if opp.is_verified else "UNVERIFIED")

    # Enforce state transition rules
    if target_status != current_status:
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification status transition from '{current_status}' to '{target_status}'. Allowed transitions: {sorted(list(allowed))}."
            )

    # Resolve notes and official source URL
    notes = (payload.evidence_notes or payload.source_notes or "").strip()

    # Evidence-based validation
    if target_status == VerificationStatus.VERIFIED.value:
        source_url = (payload.official_source_url or "").strip()
        if not source_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An explicit official source URL starting with http:// or https:// is strictly required to verify an opportunity. Inheriting unverified directory URLs is prohibited."
            )
        if not validate_url(source_url):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A valid official source URL starting with http:// or https:// and containing a valid domain name is strictly required to verify an opportunity."
            )
        if len(notes) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Verification evidence notes must be at least 10 characters documenting primary source proof and verification findings."
            )
    else:
        source_url = (payload.official_source_url or opp.official_url or "").strip()
        if target_status in [VerificationStatus.REJECTED.value, VerificationStatus.NEEDS_REVIEW.value]:
            if len(notes) < 5:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Audit notes of at least 5 characters are required when setting status to {target_status}."
                )

    is_verified_bool = (target_status == VerificationStatus.VERIFIED.value)
    ver_date = date.today().isoformat() if is_verified_bool else None

    # Record auditable decision log
    audit_log = OpportunityVerificationLog(
        opportunity_id=opp.id,
        admin_id=admin_user.id,
        admin_email=admin_user.email,
        previous_status=current_status,
        new_status=target_status,
        official_source_url=source_url if is_verified_bool else None,
        evidence_notes=notes or f"Transition from {current_status} to {target_status} by {admin_user.email}.",
        metadata_json=payload.metadata_json
    )
    db.add(audit_log)

    # Update opportunity authoritative record
    opp.verification_status = target_status
    opp.is_verified = is_verified_bool
    opp.verification_date = ver_date
    opp.source_notes = notes or opp.source_notes
    if payload.official_source_url:
        opp.official_url = payload.official_source_url.strip()

    db.commit()
    db.refresh(opp)

    calc = tool_calculate_deadline_countdown(
        DeadlineCountdownInput(
            deadline_str=opp.application_deadline,
            is_officially_verified=opp.is_verified,
            verification_source=opp.provider,
            verification_date=opp.verification_date
        )
    )

    return OpportunityAdminResponse(
        id=opp.id,
        title=opp.title,
        provider=opp.provider,
        category=opp.category,
        target_audience=opp.target_audience,
        fields_of_study=opp.fields_of_study,
        degree_levels=opp.degree_levels,
        official_url=opp.official_url,
        application_deadline=opp.application_deadline,
        is_verified=opp.is_verified,
        verification_status=opp.verification_status,
        verification_date=opp.verification_date,
        source_notes=opp.source_notes,
        status=opp.status,
        days_remaining=calc.get("days_remaining"),
        deadline_status_label=calc.get("status_label")
    )

@router.get("/opportunities/{opportunity_id}/verification-history", response_model=List[VerificationLogResponse])
def get_verification_history(
    opportunity_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Inspect full auditable verification history for an opportunity."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    logs = (
        db.query(OpportunityVerificationLog)
        .filter(OpportunityVerificationLog.opportunity_id == opportunity_id)
        .order_by(OpportunityVerificationLog.created_at.desc())
        .all()
    )
    return logs

@router.delete("/opportunities/{opportunity_id}", status_code=status.HTTP_200_OK)
def delete_opportunity(
    opportunity_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Delete or archive an opportunity.
    CRIT-02: Preserves verification history. If an opportunity has recorded verification
    decisions in opportunity_verification_logs, hard deletion is blocked to prevent erasing
    compliance audit trails. The opportunity is safely archived instead.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    has_audit_logs = db.query(OpportunityVerificationLog).filter(
        OpportunityVerificationLog.opportunity_id == opportunity_id
    ).first() is not None

    if has_audit_logs:
        opp.status = "archived"
        db.commit()
        return {
            "status": "archived",
            "message": f"Opportunity {opportunity_id} has permanent audit verification records and was archived rather than hard-deleted to preserve regulatory history."
        }

    db.delete(opp)
    db.commit()
    return {"status": "success", "message": f"Opportunity {opportunity_id} successfully deleted."}


# ============================================================================
# STAGE 2.2B-3: ELIGIBILITY CRITERIA ADMINISTRATIVE WORKFLOWS
# ============================================================================

from app.schemas.criteria import (
    CriterionResponse,
    CriterionCreateRequest,
    CriterionUpdateRequest,
    CriterionVerifyRequest,
    CriterionRejectRequest,
    CriterionFlagRequest,
    CriterionReopenRequest,
    CriterionAuditLogResponse,
)
from app.services import opportunity_criteria_admin as crit_admin_service


@router.get("/opportunities/{opportunity_id}/criteria", response_model=List[CriterionResponse])
def list_criteria_for_opportunity(
    opportunity_id: str,
    status: Optional[str] = None,
    type: Optional[str] = None,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: List all structured eligibility criteria belonging to an opportunity."""
    return crit_admin_service.list_opportunity_criteria(db, opportunity_id, status_filter=status, type_filter=type)


@router.get("/criteria/pending", response_model=List[CriterionResponse])
def list_pending_criteria(
    limit: int = 50,
    offset: int = 0,
    status: str = "PENDING_REVIEW",
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: List criteria awaiting review or matching a specified status."""
    return crit_admin_service.list_pending_criteria(db, limit=limit, offset=offset, status_filter=status)


@router.get("/criteria/{criterion_id}", response_model=CriterionResponse)
def get_criterion_detail(
    criterion_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Retrieve details, source excerpt and verification state of a criterion."""
    return crit_admin_service.get_criterion_detail(db, criterion_id)


@router.post("/opportunities/{opportunity_id}/criteria", response_model=CriterionResponse, status_code=status.HTTP_201_CREATED)
def create_criterion_manually(
    opportunity_id: str,
    payload: CriterionCreateRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Manually create a structured eligibility criterion for an opportunity."""
    if payload.evidence_url and not validate_url(payload.evidence_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid evidence URL: must be a valid public HTTP or HTTPS URL."
        )
    return crit_admin_service.create_manual_criterion(db, opportunity_id, admin_user, payload)


@router.put("/criteria/{criterion_id}", response_model=CriterionResponse)
def update_criterion(
    criterion_id: str,
    payload: CriterionUpdateRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Update criterion values with mandatory audit trail explanation."""
    if payload.evidence_url and not validate_url(payload.evidence_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid evidence URL: must be a valid public HTTP or HTTPS URL."
        )
    return crit_admin_service.update_criterion(db, criterion_id, admin_user, payload)


@router.post("/criteria/{criterion_id}/verify", response_model=CriterionResponse)
def verify_criterion(
    criterion_id: str,
    payload: CriterionVerifyRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Certify a criterion as VERIFIED with authoritative evidence URL and audit notes."""
    if not validate_url(payload.evidence_url):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid evidence URL: Verification requires a valid public HTTP or HTTPS source."
        )
    return crit_admin_service.verify_criterion(db, criterion_id, admin_user, payload)


@router.post("/criteria/{criterion_id}/reject", response_model=CriterionResponse)
def reject_criterion(
    criterion_id: str,
    payload: CriterionRejectRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Reject a criterion with reason and record in immutable audit log."""
    return crit_admin_service.reject_criterion(db, criterion_id, admin_user, payload)


@router.post("/criteria/{criterion_id}/flag", response_model=CriterionResponse)
def flag_criterion_for_review(
    criterion_id: str,
    payload: CriterionFlagRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Flag a criterion as NEEDS_REVIEW with audit notes."""
    return crit_admin_service.flag_criterion_review(db, criterion_id, admin_user, payload)


@router.post("/criteria/{criterion_id}/reopen", response_model=CriterionResponse)
def reopen_criterion(
    criterion_id: str,
    payload: CriterionReopenRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Reopen a previously reviewed criterion back to PENDING_REVIEW."""
    return crit_admin_service.reopen_criterion(db, criterion_id, admin_user, payload)


@router.get("/criteria/{criterion_id}/history", response_model=List[CriterionAuditLogResponse])
def get_criterion_audit_history(
    criterion_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Retrieve chronological append-only audit trail for a criterion."""
    return crit_admin_service.get_criterion_audit_history(db, criterion_id)
