"""
FastAPI Endpoints for Student Profile, Tracked Applications, and Checklists.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db, Base, engine
from app.models.entities import StudentProfile, Opportunity, TrackedApplication, ApplicationChecklist

# Ensure tables exist
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/v1", tags=["Student Application Tracker"])

# -------------------------------------------------------------
# Schemas
# -------------------------------------------------------------
class StudentProfileCreate(BaseModel):
    email: str = Field(..., description="Student email address")
    full_name: str
    university: str
    field_of_study: str
    degree_level: str
    year_of_study: int
    graduation_year: Optional[int] = None
    county_of_origin: Optional[str] = None

class StudentProfileResponse(StudentProfileCreate):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TrackApplicationRequest(BaseModel):
    student_id: str
    opportunity_id: str
    stage: Optional[str] = "Saved"
    notes: Optional[str] = None

class ChecklistItemResponse(BaseModel):
    id: str
    task_description: str
    is_completed: bool
    required_document_type: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class TrackedApplicationResponse(BaseModel):
    id: str
    opportunity_id: str
    stage: str
    notes: Optional[str]
    checklists: List[ChecklistItemResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------
@router.post("/profile", response_model=StudentProfileResponse, status_code=status.HTTP_201_CREATED)
def create_or_update_profile(payload: StudentProfileCreate, db: Session = Depends(get_db)):
    """Creates or updates a student profile record."""
    student = db.query(StudentProfile).filter(StudentProfile.email == payload.email).first()
    if student:
        for key, val in payload.model_dump().items():
            setattr(student, key, val)
    else:
        student = StudentProfile(**payload.model_dump())
        db.add(student)
    db.commit()
    db.refresh(student)
    return student

@router.get("/profile/{email}", response_model=StudentProfileResponse)
def get_profile(email: str, db: Session = Depends(get_db)):
    """Retrieves student profile by email."""
    student = db.query(StudentProfile).filter(StudentProfile.email == email).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")
    return student

@router.post("/tracker/save", status_code=status.HTTP_201_CREATED)
def save_opportunity_to_tracker(payload: TrackApplicationRequest, db: Session = Depends(get_db)):
    """Saves an opportunity into the student's personal application tracker."""
    # Ensure opportunity exists in relational store
    opp = db.query(Opportunity).filter(Opportunity.id == payload.opportunity_id).first()
    if not opp:
        # Auto-create lightweight master record if missing
        opp = Opportunity(
            id=payload.opportunity_id,
            title=payload.opportunity_id.replace("opp-", "").replace("-", " ").title(),
            provider="Verified Partner",
            category="General",
            official_url="https://kenya-opportunities.example.com"
        )
        db.add(opp)
        db.commit()

    existing = db.query(TrackedApplication).filter(
        TrackedApplication.student_id == payload.student_id,
        TrackedApplication.opportunity_id == payload.opportunity_id
    ).first()

    if existing:
        return {"status": "already_tracked", "tracked_application_id": existing.id}

    tracked_app = TrackedApplication(
        student_id=payload.student_id,
        opportunity_id=payload.opportunity_id,
        stage=payload.stage or "Saved",
        notes=payload.notes
    )
    db.add(tracked_app)
    db.commit()
    db.refresh(tracked_app)

    return {
        "status": "success",
        "tracked_application_id": tracked_app.id,
        "stage": tracked_app.stage
    }

@router.get("/tracker/{student_id}", response_model=List[TrackedApplicationResponse])
def get_student_applications(student_id: str, db: Session = Depends(get_db)):
    """Lists all tracked opportunities and their current progress stages."""
    apps = db.query(TrackedApplication).filter(TrackedApplication.student_id == student_id).all()
    return apps

@router.patch("/tracker/{tracked_app_id}/stage")
def update_application_stage(tracked_app_id: str, new_stage: str, db: Session = Depends(get_db)):
    """Updates application stage (e.g. Saved -> Drafting -> Submitted)."""
    tracked_app = db.query(TrackedApplication).filter(TrackedApplication.id == tracked_app_id).first()
    if not tracked_app:
        raise HTTPException(status_code=404, detail="Tracked application not found.")
    tracked_app.stage = new_stage
    db.commit()
    return {"status": "success", "new_stage": tracked_app.stage}
