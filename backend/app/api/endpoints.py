"""
Opportunity Intelligence AI - Stage 6 Relational Application Store Endpoints.
Provides complete CRUD APIs for:
1. Master Opportunity Discovery & Filtering (with dynamic deadline calculation)
2. Student Profiles & Preference Management (with privacy deletion)
3. Application Tracking Lifecycle (Saved -> Drafting -> Submitted -> Interview -> Accepted)
4. Interactive Application Checklists (Task generation, custom tasks, toggle, deletion)
5. Student Dashboard Metrics & Analytics
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.db.session import get_db, Base, engine
from app.models.entities import StudentProfile, Opportunity, TrackedApplication, ApplicationChecklist
from app.agent.tools import (
    tool_calculate_deadline_countdown,
    DeadlineCountdownInput,
    tool_generate_application_checklist,
    GenerateChecklistInput
)

Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/v1", tags=["Application Data & Tracking"])

# -------------------------------------------------------------
# Schemas
# -------------------------------------------------------------
class OpportunitySummaryResponse(BaseModel):
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
    status: str
    days_remaining: Optional[int] = None
    deadline_status_label: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class OpportunityDetailResponse(OpportunitySummaryResponse):
    source_notes: Optional[str] = None

class StudentProfileCreate(BaseModel):
    email: str = Field(..., description="Student email address")
    full_name: str
    university: str
    field_of_study: str
    degree_level: str
    year_of_study: int
    graduation_year: Optional[int] = None
    county_of_origin: Optional[str] = None
    gpa_or_grade: Optional[str] = None
    preferred_categories: Optional[str] = None

class StudentProfileResponse(StudentProfileCreate):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TrackApplicationRequest(BaseModel):
    student_id: str
    opportunity_id: str
    stage: Optional[str] = "Saved"
    notes: Optional[str] = None
    auto_generate_checklist: Optional[bool] = True

class ChecklistItemCreate(BaseModel):
    task_description: str
    required_document_type: Optional[str] = None

class ChecklistItemResponse(BaseModel):
    id: str
    task_description: str
    is_completed: bool
    required_document_type: Optional[str] = None
    completed_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class TrackedApplicationResponse(BaseModel):
    id: str
    student_id: str
    opportunity_id: str
    stage: str
    notes: Optional[str]
    opportunity: Optional[OpportunitySummaryResponse] = None
    checklists: List[ChecklistItemResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DashboardStatsResponse(BaseModel):
    total_saved: int
    in_progress: int
    submitted: int
    total_checklist_tasks: int
    completed_checklist_tasks: int
    checklist_completion_rate: float
    urgent_deadlines_count: int

# -------------------------------------------------------------
# 1. Opportunity Discovery & Filtering APIs
# -------------------------------------------------------------
@router.get("/opportunities", response_model=List[OpportunitySummaryResponse])
def list_opportunities(
    category: Optional[str] = Query(None, description="Filter by category: Scholarship, Internship, Graduate Trainee, etc."),
    degree_level: Optional[str] = Query(None, description="Filter by degree level: Undergraduate, Diploma, Masters, PhD"),
    search: Optional[str] = Query(None, description="Keyword search across title and provider"),
    is_open_only: bool = Query(False, description="Filter for only currently open opportunities"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Lists master structured opportunities with optional category, degree level,
    and text search filters, annotated with deterministic deadline countdowns.
    """
    query = db.query(Opportunity)

    if category:
        query = query.filter(Opportunity.category.ilike(f"%{category.strip()}%"))
    if degree_level:
        query = query.filter(Opportunity.degree_levels.ilike(f"%{degree_level.strip()}%"))
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Opportunity.title.ilike(search_term),
                Opportunity.provider.ilike(search_term),
                Opportunity.fields_of_study.ilike(search_term)
            )
        )

    opportunities = query.offset(offset).limit(limit).all()
    results = []

    for opp in opportunities:
        # Compute dynamic date countdown deterministically
        cd_res = tool_calculate_deadline_countdown(
            DeadlineCountdownInput(deadline_date_str=opp.application_deadline)
        )
        days_rem = cd_res.get("days_remaining")
        label = cd_res.get("status_label") or opp.status

        if is_open_only and cd_res.get("status") == "expired":
            continue

        item_dict = {
            "id": opp.id,
            "title": opp.title,
            "provider": opp.provider,
            "category": opp.category,
            "target_audience": opp.target_audience,
            "fields_of_study": opp.fields_of_study,
            "degree_levels": opp.degree_levels,
            "official_url": opp.official_url,
            "application_deadline": opp.application_deadline,
            "is_verified": opp.is_verified,
            "verification_date": opp.verification_date,
            "status": opp.status,
            "days_remaining": days_rem,
            "deadline_status_label": label
        }
        results.append(OpportunitySummaryResponse(**item_dict))

    return results

@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetailResponse)
def get_opportunity_details(opportunity_id: str, db: Session = Depends(get_db)):
    """Retrieves full details for a single opportunity by ID."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail=f"Opportunity '{opportunity_id}' not found.")

    cd_res = tool_calculate_deadline_countdown(
        DeadlineCountdownInput(deadline_date_str=opp.application_deadline)
    )
    days_rem = cd_res.get("days_remaining")
    label = cd_res.get("status_label") or opp.status

    return OpportunityDetailResponse(
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
        days_remaining=days_rem,
        deadline_status_label=label
    )

# -------------------------------------------------------------
# 2. Student Profile & Preferences APIs
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

@router.delete("/profile/{email}", status_code=status.HTTP_200_OK)
def delete_profile(email: str, db: Session = Depends(get_db)):
    """Deletes student profile and all associated application data (Privacy & Data Protection compliance)."""
    student = db.query(StudentProfile).filter(StudentProfile.email == email).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found.")
    db.delete(student)
    db.commit()
    return {"status": "success", "message": f"Student profile {email} and all tracked records deleted."}

# -------------------------------------------------------------
# 3. Application Tracking & Checklist APIs
# -------------------------------------------------------------
@router.post("/tracker/save", status_code=status.HTTP_201_CREATED)
def save_opportunity_to_tracker(payload: TrackApplicationRequest, db: Session = Depends(get_db)):
    """
    Saves an opportunity into the student's personal application tracker,
    and automatically initializes the verified application checklist.
    """
    opp = db.query(Opportunity).filter(Opportunity.id == payload.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail=f"Opportunity '{payload.opportunity_id}' not found.")

    student = db.query(StudentProfile).filter(StudentProfile.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student ID '{payload.student_id}' not found.")

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

    # Automatically populate checklist tasks from verified knowledge base
    if payload.auto_generate_checklist:
        checklist_result = tool_generate_application_checklist(
            GenerateChecklistInput(opportunity_id=payload.opportunity_id)
        )
        if checklist_result.get("status") == "success":
            for item in checklist_result.get("tasks", []):
                chk = ApplicationChecklist(
                    tracked_application_id=tracked_app.id,
                    task_description=item["task"],
                    required_document_type=item.get("section", "General"),
                    is_completed=False
                )
                db.add(chk)
            db.commit()

    return {
        "status": "success",
        "tracked_application_id": tracked_app.id,
        "stage": tracked_app.stage
    }

@router.delete("/tracker/{student_id}/{opportunity_id}", status_code=status.HTTP_200_OK)
def remove_saved_opportunity(student_id: str, opportunity_id: str, db: Session = Depends(get_db)):
    """Removes a saved opportunity and associated checklists from the student tracker."""
    tracked_app = db.query(TrackedApplication).filter(
        TrackedApplication.student_id == student_id,
        TrackedApplication.opportunity_id == opportunity_id
    ).first()
    if not tracked_app:
        raise HTTPException(status_code=404, detail="Tracked opportunity not found.")
    db.delete(tracked_app)
    db.commit()
    return {"status": "success", "message": "Opportunity removed from tracker."}

@router.get("/tracker/{student_id}", response_model=List[TrackedApplicationResponse])
def get_student_applications(student_id: str, db: Session = Depends(get_db)):
    """Lists all tracked opportunities, stages, and checklist progress for a student."""
    apps = db.query(TrackedApplication).filter(TrackedApplication.student_id == student_id).all()
    return apps

@router.patch("/tracker/{tracked_app_id}/stage")
def update_application_stage(tracked_app_id: str, new_stage: str, db: Session = Depends(get_db)):
    """Updates application stage (e.g. Saved -> Drafting -> Submitted -> Interview)."""
    valid_stages = ["Saved", "Drafting", "Submitted", "Interview", "Accepted", "Rejected"]
    if new_stage not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage '{new_stage}'. Must be one of: {valid_stages}")

    tracked_app = db.query(TrackedApplication).filter(TrackedApplication.id == tracked_app_id).first()
    if not tracked_app:
        raise HTTPException(status_code=404, detail="Tracked application not found.")
    tracked_app.stage = new_stage
    db.commit()
    return {"status": "success", "new_stage": tracked_app.stage}

@router.post("/tracker/{tracked_app_id}/checklists", response_model=ChecklistItemResponse, status_code=status.HTTP_201_CREATED)
def add_custom_checklist_item(tracked_app_id: str, payload: ChecklistItemCreate, db: Session = Depends(get_db)):
    """Adds a custom student task to a tracked application."""
    tracked_app = db.query(TrackedApplication).filter(TrackedApplication.id == tracked_app_id).first()
    if not tracked_app:
        raise HTTPException(status_code=404, detail="Tracked application not found.")

    item = ApplicationChecklist(
        tracked_application_id=tracked_app_id,
        task_description=payload.task_description,
        required_document_type=payload.required_document_type or "Custom",
        is_completed=False
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.patch("/checklists/{checklist_id}/toggle")
def toggle_checklist_completion(checklist_id: str, db: Session = Depends(get_db)):
    """Toggles completion state of a checklist task."""
    item = db.query(ApplicationChecklist).filter(ApplicationChecklist.id == checklist_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist task not found.")

    item.is_completed = not item.is_completed
    item.completed_at = datetime.utcnow() if item.is_completed else None
    db.commit()
    return {
        "status": "success",
        "task_id": item.id,
        "is_completed": item.is_completed,
        "completed_at": item.completed_at
    }

@router.delete("/checklists/{checklist_id}", status_code=status.HTTP_200_OK)
def delete_checklist_item(checklist_id: str, db: Session = Depends(get_db)):
    """Deletes a checklist task."""
    item = db.query(ApplicationChecklist).filter(ApplicationChecklist.id == checklist_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist task not found.")
    db.delete(item)
    db.commit()
    return {"status": "success", "message": "Checklist task deleted."}

@router.get("/tracker/{student_id}/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(student_id: str, db: Session = Depends(get_db)):
    """Returns aggregated dashboard metrics for application tracking and checklist completion."""
    tracked_apps = db.query(TrackedApplication).filter(TrackedApplication.student_id == student_id).all()

    total_saved = len(tracked_apps)
    in_progress = sum(1 for app in tracked_apps if app.stage in ["Drafting", "In_Progress"])
    submitted = sum(1 for app in tracked_apps if app.stage in ["Submitted", "Interview", "Accepted"])

    app_ids = [app.id for app in tracked_apps]
    checklists = db.query(ApplicationChecklist).filter(ApplicationChecklist.tracked_application_id.in_(app_ids)).all() if app_ids else []

    total_tasks = len(checklists)
    completed_tasks = sum(1 for c in checklists if c.is_completed)
    completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0

    # Count urgent deadlines (closing within 14 days)
    urgent_count = 0
    for app in tracked_apps:
        if app.opportunity and app.opportunity.application_deadline:
            cd = tool_calculate_deadline_countdown(
                DeadlineCountdownInput(deadline_date_str=app.opportunity.application_deadline)
            )
            if cd.get("status") == "open" and 0 <= cd.get("days_remaining", 999) <= 14:
                urgent_count += 1

    return DashboardStatsResponse(
        total_saved=total_saved,
        in_progress=in_progress,
        submitted=submitted,
        total_checklist_tasks=total_tasks,
        completed_checklist_tasks=completed_tasks,
        checklist_completion_rate=completion_rate,
        urgent_deadlines_count=urgent_count
    )
