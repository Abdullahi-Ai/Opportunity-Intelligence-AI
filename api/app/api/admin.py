"""Administrator Opportunity Management Endpoints.
Guarded by role-based authorization (require_admin).
Allows verified administrators to curate opportunities, verify sources, and update deadlines.
"""
from typing import Optional, List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Opportunity, User
from app.core.auth import require_admin
from app.agent.tools import tool_calculate_deadline_countdown, DeadlineCountdownInput

router = APIRouter(prefix="/api/v1/admin", tags=["Administrator Operations"])

class OpportunityCreateOrUpdate(BaseModel):
    title: str = Field(..., min_length=3)
    provider: str = Field(..., min_length=2)
    category: str = Field(..., description="Scholarship, Internship, Fellowship, Competition, etc.")
    target_audience: Optional[str] = None
    fields_of_study: Optional[str] = "All Fields"
    degree_levels: Optional[str] = "Undergraduate, Postgraduate"
    official_url: str = Field(..., description="Authoritative official URL")
    application_deadline: Optional[str] = Field(None, description="ISO format YYYY-MM-DD or None for rolling")
    is_verified: bool = True
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
    verification_date: Optional[str] = None
    source_notes: Optional[str] = None
    status: str
    days_remaining: Optional[int] = None
    deadline_status_label: Optional[str] = None

class VerifyOpportunityRequest(BaseModel):
    is_verified: bool
    source_notes: str = Field(..., min_length=5, description="Notes documenting source verification")

@router.post("/opportunities", response_model=OpportunityAdminResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreateOrUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Ingest a newly verified opportunity."""
    import uuid
    opp_id = f"opp-{uuid.uuid4().hex[:8]}"
    
    ver_date = payload.verification_date or (date.today().isoformat() if payload.is_verified else None)
    
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
        is_verified=payload.is_verified,
        verification_date=ver_date,
        source_notes=payload.source_notes,
        status=payload.status
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    
    calc = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_str=opp.application_deadline))
    
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
    
    opp.title = payload.title
    opp.provider = payload.provider
    opp.category = payload.category
    opp.target_audience = payload.target_audience
    opp.fields_of_study = payload.fields_of_study
    opp.degree_levels = payload.degree_levels
    opp.official_url = payload.official_url
    opp.application_deadline = payload.application_deadline
    opp.is_verified = payload.is_verified
    if payload.verification_date:
        opp.verification_date = payload.verification_date
    opp.source_notes = payload.source_notes
    opp.status = payload.status
    
    db.commit()
    db.refresh(opp)
    
    calc = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_str=opp.application_deadline))
    
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
    """Administrator: Review and certify the source verification of an opportunity."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    
    opp.is_verified = payload.is_verified
    opp.verification_date = date.today().isoformat() if payload.is_verified else None
    opp.source_notes = payload.source_notes
    db.commit()
    db.refresh(opp)
    
    calc = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_str=opp.application_deadline))
    
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
        verification_date=opp.verification_date,
        source_notes=opp.source_notes,
        status=opp.status,
        days_remaining=calc.get("days_remaining"),
        deadline_status_label=calc.get("status_label")
    )

@router.delete("/opportunities/{opportunity_id}", status_code=status.HTTP_200_OK)
def delete_opportunity(
    opportunity_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Administrator: Delete an outdated or invalid opportunity."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    
    db.delete(opp)
    db.commit()
    return {"status": "success", "message": f"Opportunity {opportunity_id} successfully deleted."}
