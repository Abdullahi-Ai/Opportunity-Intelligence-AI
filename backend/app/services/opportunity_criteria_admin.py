"""
Opportunity Eligibility Criteria Administrative Management and Verification Service.

Phase 2 — Stage 2.2B-3 Implementation.
Provides transactional service logic for:
1. Listing criteria by opportunity.
2. Listing pending criteria awaiting administrative review.
3. Fetching criterion detail and provenance.
4. Manually creating criteria.
5. Updating criteria with before-and-after audit snapshots.
6. Verifying criteria with required evidence URL and audit logs.
7. Rejecting criteria with audit justification.
8. Flagging criteria for further review (NEEDS_REVIEW).
9. Reopening previously reviewed criteria.
10. Fetching immutable criterion verification audit history.
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.entities import (
    Opportunity,
    OpportunityEligibilityCriterion,
    OpportunityCriterionVerificationLog,
    User,
    CriterionVerificationStatus,
)
from app.schemas.criteria import (
    CriterionCreateRequest,
    CriterionUpdateRequest,
    CriterionVerifyRequest,
    CriterionRejectRequest,
    CriterionFlagRequest,
    CriterionReopenRequest,
)


def _serialize_criterion_snapshot(criterion: OpportunityEligibilityCriterion) -> str:
    """Serializes essential fields of a criterion for append-only audit tracking."""
    return json.dumps({
        "id": criterion.id,
        "opportunity_id": criterion.opportunity_id,
        "criterion_type": criterion.criterion_type,
        "operator": criterion.operator,
        "criterion_value": criterion.criterion_value,
        "grading_system": criterion.grading_system,
        "numeric_scale": str(criterion.numeric_scale) if criterion.numeric_scale is not None else None,
        "is_mandatory": criterion.is_mandatory,
        "source_text": criterion.source_text,
        "evidence_url": criterion.evidence_url,
        "verification_status": criterion.verification_status,
        "verified_by": criterion.verified_by,
        "verified_at": criterion.verified_at.isoformat() if criterion.verified_at else None,
    })


def list_opportunity_criteria(
    db: Session,
    opportunity_id: str,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
) -> List[OpportunityEligibilityCriterion]:
    """Retrieves all eligibility criteria belonging to an opportunity."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity with ID '{opportunity_id}' not found."
        )

    query = db.query(OpportunityEligibilityCriterion).filter(
        OpportunityEligibilityCriterion.opportunity_id == opportunity_id
    )
    if status_filter:
        query = query.filter(OpportunityEligibilityCriterion.verification_status == status_filter.upper())
    if type_filter:
        query = query.filter(OpportunityEligibilityCriterion.criterion_type == type_filter.upper())

    return query.order_by(OpportunityEligibilityCriterion.created_at.asc()).all()


def list_pending_criteria(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    status_filter: str = "PENDING_REVIEW"
) -> List[OpportunityEligibilityCriterion]:
    """Retrieves paginated criteria awaiting review or matching specified status."""
    return (
        db.query(OpportunityEligibilityCriterion)
        .filter(OpportunityEligibilityCriterion.verification_status == status_filter.upper())
        .order_by(OpportunityEligibilityCriterion.created_at.asc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )


def get_criterion_detail(db: Session, criterion_id: str) -> OpportunityEligibilityCriterion:
    """Retrieves individual criterion by ID."""
    criterion = db.query(OpportunityEligibilityCriterion).filter(
        OpportunityEligibilityCriterion.id == criterion_id
    ).first()
    if not criterion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Criterion with ID '{criterion_id}' not found."
        )
    return criterion


def create_manual_criterion(
    db: Session,
    opportunity_id: str,
    admin_user: User,
    payload: CriterionCreateRequest
) -> OpportunityEligibilityCriterion:
    """Creates a new criterion manually and records an atomic audit entry."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity with ID '{opportunity_id}' not found."
        )

    try:
        new_crit = OpportunityEligibilityCriterion(
            opportunity_id=opportunity_id,
            criterion_type=payload.criterion_type.upper(),
            operator=payload.operator.upper(),
            criterion_value=payload.criterion_value.strip(),
            grading_system=payload.grading_system,
            numeric_scale=payload.numeric_scale,
            is_mandatory=payload.is_mandatory,
            source_text=payload.source_text.strip(),
            evidence_url=payload.evidence_url.strip() if payload.evidence_url else opp.official_url,
            verification_status=CriterionVerificationStatus.PENDING_REVIEW.value,
            verified_by=None,
            verified_at=None,
        )
        db.add(new_crit)
        db.flush()

        # Atomic Audit Trail
        audit_log = OpportunityCriterionVerificationLog(
            criterion_id=new_crit.id,
            admin_id=admin_user.id,
            admin_email=admin_user.email,
            event_type="MANUAL_CREATE",
            previous_status="PENDING_REVIEW",
            new_status="PENDING_REVIEW",
            before_snapshot=None,
            after_snapshot=_serialize_criterion_snapshot(new_crit),
            evidence_url=new_crit.evidence_url,
            evidence_notes="Criterion created manually by administrator.",
            metadata_json=json.dumps({"author": admin_user.email})
        )
        db.add(audit_log)
        db.commit()
        db.refresh(new_crit)
        return new_crit
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create criterion transactionally: {str(e)}"
        )


def update_criterion(
    db: Session,
    criterion_id: str,
    admin_user: User,
    payload: CriterionUpdateRequest
) -> OpportunityEligibilityCriterion:
    """Updates criterion values and records before-and-after audit snapshots."""
    criterion = get_criterion_detail(db, criterion_id)
    before_snap = _serialize_criterion_snapshot(criterion)

    try:
        if payload.criterion_value is not None:
            criterion.criterion_value = payload.criterion_value.strip()
        if payload.operator is not None:
            criterion.operator = payload.operator.upper()
        if payload.is_mandatory is not None:
            criterion.is_mandatory = payload.is_mandatory
        if payload.source_text is not None:
            criterion.source_text = payload.source_text.strip()
        if payload.evidence_url is not None:
            criterion.evidence_url = payload.evidence_url.strip()
        if payload.numeric_scale is not None:
            criterion.numeric_scale = payload.numeric_scale
        if payload.grading_system is not None:
            criterion.grading_system = payload.grading_system

        # If a verified criterion was modified, flag it for review
        prev_status = criterion.verification_status
        if prev_status == CriterionVerificationStatus.VERIFIED.value:
            criterion.verification_status = CriterionVerificationStatus.NEEDS_REVIEW.value

        db.flush()
        after_snap = _serialize_criterion_snapshot(criterion)

        audit_log = OpportunityCriterionVerificationLog(
            criterion_id=criterion.id,
            admin_id=admin_user.id,
            admin_email=admin_user.email,
            event_type="UPDATE",
            previous_status=prev_status,
            new_status=criterion.verification_status,
            before_snapshot=before_snap,
            after_snapshot=after_snap,
            evidence_url=criterion.evidence_url,
            evidence_notes=payload.review_notes.strip(),
            metadata_json=json.dumps({"updated_by": admin_user.email})
        )
        db.add(audit_log)
        db.commit()
        db.refresh(criterion)
        return criterion
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update criterion transactionally: {str(e)}"
        )


def verify_criterion(
    db: Session,
    criterion_id: str,
    admin_user: User,
    payload: CriterionVerifyRequest
) -> OpportunityEligibilityCriterion:
    """Certifies a criterion as VERIFIED with required evidence URL and notes."""
    criterion = get_criterion_detail(db, criterion_id)
    before_snap = _serialize_criterion_snapshot(criterion)
    prev_status = criterion.verification_status

    try:
        clean_url = payload.evidence_url.strip()
        criterion.evidence_url = clean_url
        criterion.verified_by = admin_user.id
        criterion.verified_at = datetime.utcnow()
        criterion.verification_status = CriterionVerificationStatus.VERIFIED.value

        db.flush()
        after_snap = _serialize_criterion_snapshot(criterion)

        audit_log = OpportunityCriterionVerificationLog(
            criterion_id=criterion.id,
            admin_id=admin_user.id,
            admin_email=admin_user.email,
            event_type="VERIFY",
            previous_status=prev_status,
            new_status=CriterionVerificationStatus.VERIFIED.value,
            before_snapshot=before_snap,
            after_snapshot=after_snap,
            evidence_url=clean_url,
            evidence_notes=payload.evidence_notes.strip(),
            metadata_json=json.dumps({"verified_by": admin_user.email})
        )
        db.add(audit_log)
        db.commit()
        db.refresh(criterion)
        return criterion
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify criterion transactionally: {str(e)}"
        )


def reject_criterion(
    db: Session,
    criterion_id: str,
    admin_user: User,
    payload: CriterionRejectRequest
) -> OpportunityEligibilityCriterion:
    """Marks a criterion as REJECTED with rejection justification."""
    criterion = get_criterion_detail(db, criterion_id)
    before_snap = _serialize_criterion_snapshot(criterion)
    prev_status = criterion.verification_status

    try:
        criterion.verified_by = admin_user.id
        criterion.verified_at = datetime.utcnow()
        criterion.verification_status = CriterionVerificationStatus.REJECTED.value

        db.flush()
        after_snap = _serialize_criterion_snapshot(criterion)

        audit_log = OpportunityCriterionVerificationLog(
            criterion_id=criterion.id,
            admin_id=admin_user.id,
            admin_email=admin_user.email,
            event_type="REJECT",
            previous_status=prev_status,
            new_status=CriterionVerificationStatus.REJECTED.value,
            before_snapshot=before_snap,
            after_snapshot=after_snap,
            evidence_url=criterion.evidence_url,
            evidence_notes=payload.evidence_notes.strip(),
            metadata_json=json.dumps({"rejected_by": admin_user.email})
        )
        db.add(audit_log)
        db.commit()
        db.refresh(criterion)
        return criterion
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject criterion transactionally: {str(e)}"
        )


def flag_criterion_review(
    db: Session,
    criterion_id: str,
    admin_user: User,
    payload: CriterionFlagRequest
) -> OpportunityEligibilityCriterion:
    """Flags a criterion as NEEDS_REVIEW."""
    criterion = get_criterion_detail(db, criterion_id)
    before_snap = _serialize_criterion_snapshot(criterion)
    prev_status = criterion.verification_status

    try:
        criterion.verification_status = CriterionVerificationStatus.NEEDS_REVIEW.value
        db.flush()
        after_snap = _serialize_criterion_snapshot(criterion)

        audit_log = OpportunityCriterionVerificationLog(
            criterion_id=criterion.id,
            admin_id=admin_user.id,
            admin_email=admin_user.email,
            event_type="FLAG_REVIEW",
            previous_status=prev_status,
            new_status=CriterionVerificationStatus.NEEDS_REVIEW.value,
            before_snapshot=before_snap,
            after_snapshot=after_snap,
            evidence_url=criterion.evidence_url,
            evidence_notes=payload.evidence_notes.strip(),
            metadata_json=json.dumps({"flagged_by": admin_user.email})
        )
        db.add(audit_log)
        db.commit()
        db.refresh(criterion)
        return criterion
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to flag criterion transactionally: {str(e)}"
        )


def reopen_criterion(
    db: Session,
    criterion_id: str,
    admin_user: User,
    payload: CriterionReopenRequest
) -> OpportunityEligibilityCriterion:
    """Reopens a previously reviewed criterion back to PENDING_REVIEW."""
    criterion = get_criterion_detail(db, criterion_id)
    before_snap = _serialize_criterion_snapshot(criterion)
    prev_status = criterion.verification_status

    try:
        # Enforce invariant: PENDING_REVIEW must not retain verified metadata
        criterion.verified_by = None
        criterion.verified_at = None
        criterion.verification_status = CriterionVerificationStatus.PENDING_REVIEW.value

        db.flush()
        after_snap = _serialize_criterion_snapshot(criterion)

        audit_log = OpportunityCriterionVerificationLog(
            criterion_id=criterion.id,
            admin_id=admin_user.id,
            admin_email=admin_user.email,
            event_type="REOPEN",
            previous_status=prev_status,
            new_status=CriterionVerificationStatus.PENDING_REVIEW.value,
            before_snapshot=before_snap,
            after_snapshot=after_snap,
            evidence_url=criterion.evidence_url,
            evidence_notes=f"Reopened for review: {payload.reason.strip()}",
            metadata_json=json.dumps({"reopened_by": admin_user.email})
        )
        db.add(audit_log)
        db.commit()
        db.refresh(criterion)
        return criterion
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reopen criterion transactionally: {str(e)}"
        )


def get_criterion_audit_history(
    db: Session,
    criterion_id: str
) -> List[OpportunityCriterionVerificationLog]:
    """Retrieves chronological immutable audit logs for a criterion."""
    get_criterion_detail(db, criterion_id)  # Validate criterion exists
    return (
        db.query(OpportunityCriterionVerificationLog)
        .filter(OpportunityCriterionVerificationLog.criterion_id == criterion_id)
        .order_by(OpportunityCriterionVerificationLog.created_at.desc())
        .all()
    )
