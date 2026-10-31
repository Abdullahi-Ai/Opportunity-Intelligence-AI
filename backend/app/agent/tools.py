"""
Deterministic Agent Tools for Opportunity Intelligence AI.
Implements strictly typed Pydantic tools for:
1. Semantic opportunity retrieval from ChromaDB.
2. Rule-based student eligibility evaluation.
3. Deterministic calendar date calculation and deadline countdown.
4. Actionable application checklist generation.
"""

from typing import Dict, List, Any, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.rag.vector_store import vector_store

class SearchOpportunitiesInput(BaseModel):
    query: str = Field(description="Natural language search query for scholarships, internships, or requirements.")
    category: Optional[str] = Field(default=None, description="Optional category filter: Scholarship, Internship, Graduate Trainee, Fellowship, Competition")
    top_k: int = Field(default=4, ge=1, le=10, description="Number of results to retrieve.")

def tool_search_opportunities(input_data: SearchOpportunitiesInput) -> Dict[str, Any]:
    """Retrieves grounded opportunity chunks and official source links from ChromaDB."""
    results = vector_store.search(
        query=input_data.query,
        top_k=input_data.top_k,
        category=input_data.category
    )
    if not results:
        return {
            "status": "not_found",
            "message": "No matching verified opportunities found in knowledge base.",
            "results": []
        }
    return {
        "status": "success",
        "count": len(results),
        "results": [
            {
                "opportunity_id": r["metadata"].get("opportunity_id"),
                "title": r["metadata"].get("title"),
                "provider": r["metadata"].get("provider"),
                "category": r["metadata"].get("category"),
                "section": r["metadata"].get("section_title"),
                "deadline": r["metadata"].get("application_deadline"),
                "published_deadline": r["metadata"].get("application_deadline"),
                "official_url": r["metadata"].get("official_url"),
                "verification_status": r["metadata"].get("verification_status", "verified"),
                "degree_levels": r["metadata"].get("degree_levels"),
                "fields_of_study": r["metadata"].get("fields_of_study"),
                "content_excerpt": r["content"],
                "similarity_score": r["similarity_score"]
            }
            for r in results
        ]
    }

class DeadlineCountdownInput(BaseModel):
    deadline_date_str: Optional[str] = Field(default=None, description="ISO format deadline string YYYY-MM-DD (e.g. '2026-11-30') or None/empty for rolling")
    deadline_str: Optional[str] = Field(default=None, description="Alias for deadline_date_str")

def tool_calculate_deadline_countdown(input_data: DeadlineCountdownInput) -> Dict[str, Any]:
    """
    Deterministically computes days remaining and status using Python calendar arithmetic.
    NEVER relies on LLM date arithmetic to prevent hallucinations.
    Handles missing deadlines, rolling admissions, expired dates, and boundary cases.
    """
    today = date.today()
    raw_date = input_data.deadline_date_str or input_data.deadline_str

    if not raw_date or str(raw_date).strip().lower() in ["unspecified", "rolling", "none", "n/a", ""]:
        return {
            "status": "unspecified",
            "is_open": True,
            "deadline": None,
            "today": str(today),
            "days_remaining": None,
            "days_ago": None,
            "status_label": "Rolling / Open",
            "summary": "No fixed deadline published (rolling admissions or continuous intake)."
        }

    clean_str = str(raw_date).strip()
    try:
        target_date = datetime.strptime(clean_str, "%Y-%m-%d").date()
    except ValueError:
        return {
            "status": "error",
            "is_open": False,
            "deadline": clean_str,
            "today": str(today),
            "days_remaining": None,
            "days_ago": None,
            "status_label": "Invalid date",
            "message": f"Invalid date format '{clean_str}'. Expected YYYY-MM-DD.",
            "summary": f"Could not compute countdown: '{clean_str}' is not in YYYY-MM-DD format."
        }

    delta_days = (target_date - today).days

    if delta_days < 0:
        days_ago = abs(delta_days)
        return {
            "status": "expired",
            "is_open": False,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": -days_ago,
            "days_ago": days_ago,
            "status_label": f"Expired ({days_ago}d ago)" if days_ago > 1 else "Expired yesterday",
            "summary": f"This opportunity closed {days_ago} days ago on {target_date}."
        }
    elif delta_days == 0:
        return {
            "status": "closing_today",
            "is_open": True,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": 0,
            "days_ago": 0,
            "status_label": "Closing today!",
            "summary": "Deadline is TODAY! Ensure final submission before midnight."
        }
    elif delta_days == 1:
        return {
            "status": "open",
            "is_open": True,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": 1,
            "days_ago": 0,
            "status_label": "1 day left (Tomorrow)",
            "summary": f"1 day remaining until the deadline on {target_date}."
        }
    else:
        return {
            "status": "open",
            "is_open": True,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": delta_days,
            "days_ago": 0,
            "status_label": f"{delta_days} days left",
            "summary": f"{delta_days} day(s) remaining until the deadline on {target_date}."
        }

class AssessEligibilityInput(BaseModel):
    opportunity_id: str = Field(description="Target opportunity ID (e.g. 'opp-safaricom-attachment-2026')")
    student_degree_level: str = Field(description="e.g. 'Undergraduate', 'Diploma', 'Masters', 'PhD'")
    student_field_of_study: str = Field(description="Student major/course e.g. 'Computer Science'")
    student_year_of_study: int = Field(description="Current year of study e.g. 1, 2, 3, 4")
    student_kcse_grade: Optional[str] = Field(default=None, description="e.g. 'A', 'B+', 'B', 'B-'")

def tool_assess_eligibility(input_data: AssessEligibilityInput) -> Dict[str, Any]:
    """
    Evaluates published opportunity criteria against student parameters.
    Returns criteria breakdown classified as Meets, Does Not Meet, or Needs Verification.
    """
    results = vector_store.search(
        query=f"{input_data.opportunity_id} eligibility criteria minimum requirements",
        top_k=2
    )

    matching_chunk = None
    for r in results:
        if r["metadata"].get("opportunity_id") == input_data.opportunity_id:
            matching_chunk = r
            break

    if not matching_chunk:
        return {
            "status": "insufficient_evidence",
            "message": f"Could not find verified criteria for opportunity '{input_data.opportunity_id}'."
        }

    meta = matching_chunk["metadata"]
    allowed_degrees = [d.strip().lower() for d in meta.get("degree_levels", "").split(",") if d.strip()]
    allowed_fields = [f.strip().lower() for f in meta.get("fields_of_study", "").split(",") if f.strip()]

    evaluations = []

    student_deg = input_data.student_degree_level.lower()
    if not allowed_degrees or any(deg in student_deg or student_deg in deg for deg in allowed_degrees):
        evaluations.append({
            "criterion": "Degree Level",
            "required": meta.get("degree_levels"),
            "provided": input_data.student_degree_level,
            "status": "Meets"
        })
    else:
        evaluations.append({
            "criterion": "Degree Level",
            "required": meta.get("degree_levels"),
            "provided": input_data.student_degree_level,
            "status": "Does Not Meet"
        })

    student_field = input_data.student_field_of_study.lower()
    if not allowed_fields or "all fields" in allowed_fields or any(f in student_field or student_field in f for f in allowed_fields):
        evaluations.append({
            "criterion": "Field of Study",
            "required": meta.get("fields_of_study"),
            "provided": input_data.student_field_of_study,
            "status": "Meets"
        })
    else:
        evaluations.append({
            "criterion": "Field of Study",
            "required": meta.get("fields_of_study"),
            "provided": input_data.student_field_of_study,
            "status": "Needs Verification"
        })

    if "attachment" in input_data.opportunity_id:
        if input_data.student_year_of_study in [2, 3, 4]:
            evaluations.append({
                "criterion": "Year of Study (Attachment)",
                "required": "2nd, 3rd, or 4th year continuing student",
                "provided": f"Year {input_data.student_year_of_study}",
                "status": "Meets"
            })
        else:
            evaluations.append({
                "criterion": "Year of Study (Attachment)",
                "required": "2nd, 3rd, or 4th year continuing student",
                "provided": f"Year {input_data.student_year_of_study}",
                "status": "Does Not Meet"
            })

    statuses = [e["status"] for e in evaluations]
    if "Does Not Meet" in statuses:
        overall = "Ineligible / Unlikely to Meet Criteria"
    elif "Needs Verification" in statuses:
        overall = "Conditionally Eligible (Requires Verification)"
    else:
        overall = "Likely Eligible"

    return {
        "status": "success",
        "opportunity_id": input_data.opportunity_id,
        "title": meta.get("title"),
        "provider": meta.get("provider"),
        "official_url": meta.get("official_url"),
        "overall_assessment": overall,
        "criteria_breakdown": evaluations,
        "disclaimer": "This automated assessment is an informational guide based on published criteria. Final eligibility is determined exclusively by the sponsoring organization."
    }

class GenerateChecklistInput(BaseModel):
    opportunity_id: str = Field(description="Target opportunity ID.")

def tool_generate_application_checklist(input_data: GenerateChecklistInput) -> Dict[str, Any]:
    """Generates a structured checklist of documents and application tasks from verified records."""
    results = vector_store.search(
        query=f"{input_data.opportunity_id} required documents application steps process",
        top_k=4
    )

    matching_chunks = [
        r for r in results 
        if r["metadata"].get("opportunity_id") == input_data.opportunity_id
    ]

    if not matching_chunks:
        return {
            "status": "error",
            "message": f"No document records found for '{input_data.opportunity_id}'."
        }

    meta = matching_chunks[0]["metadata"]
    tasks = []
    seen_tasks = set()

    for chunk in matching_chunks:
        content = chunk["content"]
        section_title = chunk["metadata"].get("section_title", "General")
        
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- ") or (len(stripped) > 3 and stripped[0].isdigit() and stripped[1] in [".", ")"]):
                task_text = stripped.lstrip("- 0123456789.)").strip()
                if len(task_text) > 5 and not task_text.startswith("Opportunity:") and not task_text.startswith("Official Link:"):
                    if task_text not in seen_tasks:
                        seen_tasks.add(task_text)
                        tasks.append({
                            "task": task_text,
                            "section": section_title,
                            "is_completed": False
                        })

    return {
        "status": "success",
        "opportunity_id": input_data.opportunity_id,
        "title": meta.get("title"),
        "official_url": meta.get("official_url"),
        "tasks": tasks
    }

class GetTrackedApplicationsInput(BaseModel):
    student_profile_id: Optional[str] = Field(
        default=None,
        description="Optional student profile ID. If omitted, the authenticated student's tracker is loaded."
    )

def tool_get_tracked_applications(
    input_data: GetTrackedApplicationsInput,
    authenticated_student_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    if not authenticated_student_id:
        return {
            "status": "unauthenticated",
            "message": "Student is not authenticated or has not linked a student profile.",
            "applications": []
        }
    if input_data.student_profile_id and input_data.student_profile_id != authenticated_student_id:
        return {
            "status": "forbidden",
            "message": "Access denied: Cannot access other students' tracked applications.",
            "applications": []
        }
    if not db:
        return {
            "status": "error",
            "message": "Database session not available for tracking operations.",
            "applications": []
        }

    from app.models.entities import TrackedApplication, Opportunity
    tracked = db.query(TrackedApplication).filter(
        TrackedApplication.student_id == authenticated_student_id
    ).all()

    results = []
    for app in tracked:
        opp = app.opportunity
        dl_str = opp.application_deadline if opp else None
        cd_res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=dl_str))

        pending_tasks = [c.task_description for c in (app.checklists or []) if not c.is_completed]
        completed_tasks = [c.task_description for c in (app.checklists or []) if c.is_completed]

        results.append({
            "application_id": app.id,
            "opportunity_id": opp.id if opp else app.opportunity_id,
            "title": opp.title if opp else "Unknown",
            "provider": opp.provider if opp else "Unknown",
            "stage": app.stage,
            "official_url": opp.official_url if opp else None,
            "deadline": dl_str,
            "days_remaining": cd_res.get("days_remaining"),
            "deadline_status": cd_res.get("status_label"),
            "tasks_count": len(app.checklists) if app.checklists else 0,
            "completed_tasks": len(completed_tasks),
            "pending_tasks": pending_tasks,
            "notes": app.notes,
            "target_submission_date": str(app.target_submission_date) if app.target_submission_date else None
        })

    return {
        "status": "success",
        "student_id": authenticated_student_id,
        "count": len(results),
        "applications": results
    }

TOOL_REGISTRY = {
    "search_opportunities": tool_search_opportunities,
    "tool_search_opportunities": tool_search_opportunities,
    "calculate_deadline_countdown": tool_calculate_deadline_countdown,
    "tool_calculate_deadline_countdown": tool_calculate_deadline_countdown,
    "assess_eligibility": tool_assess_eligibility,
    "tool_assess_eligibility": tool_assess_eligibility,
    "generate_application_checklist": tool_generate_application_checklist,
    "tool_generate_application_checklist": tool_generate_application_checklist,
    "get_tracked_applications": tool_get_tracked_applications,
    "tool_get_tracked_applications": tool_get_tracked_applications,
}

TOOL_INPUT_MODELS = {
    "search_opportunities": SearchOpportunitiesInput,
    "tool_search_opportunities": SearchOpportunitiesInput,
    "calculate_deadline_countdown": DeadlineCountdownInput,
    "tool_calculate_deadline_countdown": DeadlineCountdownInput,
    "assess_eligibility": AssessEligibilityInput,
    "tool_assess_eligibility": AssessEligibilityInput,
    "generate_application_checklist": GenerateChecklistInput,
    "tool_generate_application_checklist": GenerateChecklistInput,
    "get_tracked_applications": GetTrackedApplicationsInput,
    "tool_get_tracked_applications": GetTrackedApplicationsInput,
}

def execute_registered_tool(
    tool_name: str,
    tool_args: Dict[str, Any],
    authenticated_student_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    norm_name = tool_name.strip()
    if norm_name not in TOOL_REGISTRY:
        return {"status": "error", "message": f"Unknown tool '{tool_name}'"}

    input_cls = TOOL_INPUT_MODELS.get(norm_name)
    func = TOOL_REGISTRY[norm_name]

    try:
        validated_input = input_cls(**tool_args)
    except Exception as e:
        return {"status": "validation_error", "message": f"Invalid arguments for {tool_name}: {str(e)}"}

    try:
        if norm_name in ["get_tracked_applications", "tool_get_tracked_applications"]:
            return func(validated_input, authenticated_student_id=authenticated_student_id, db=db)
        return func(validated_input)
    except Exception as e:
        return {"status": "error", "message": f"Tool execution error: {str(e)}"}

