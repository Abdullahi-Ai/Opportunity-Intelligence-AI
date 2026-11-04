"""
Deterministic Agent Tools for Opportunity Intelligence AI.
Implements strictly typed Pydantic tools for:
1. Semantic opportunity retrieval from ChromaDB.
2. Rule-based student eligibility evaluation.
3. Deterministic calendar date calculation and deadline countdown.
4. Actionable application checklist generation.
"""

import logging
import re
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.rag import get_vector_store

logger = logging.getLogger(__name__)

class SearchOpportunitiesInput(BaseModel):
    query: str = Field(description="Natural language search query for scholarships, internships, or requirements.")
    category: Optional[str] = Field(default=None, description="Optional category filter: Scholarship, Internship, Graduate Trainee, Fellowship, Competition")
    top_k: int = Field(default=4, ge=1, le=10, description="Number of results to retrieve.")

def _search_opportunities_relational_fallback(
    query: str,
    category: Optional[str] = None,
    top_k: int = 4,
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Executes a deterministic SQL keyword search across verified opportunities
    when semantic vector retrieval is unavailable.
    Preserves verified official metadata, sources, and deadline dates.
    """
    from app.models.entities import Opportunity
    from app.db.session import SessionLocal

    session = db
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        base_query = session.query(Opportunity).filter(
            Opportunity.verification_status == "VERIFIED",
            Opportunity.status == "open"
        )
        if category:
            base_query = base_query.filter(Opportunity.category.ilike(f"%{category.strip()}%"))

        candidates = base_query.all()
        if not candidates:
            return []

        # Tokenize query to identify distinctive keywords (ignoring noise/common terms)
        stopwords = {
            "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
            "is", "are", "me", "my", "i", "what", "find", "show", "search", "give",
            "opportunity", "opportunities", "kenya", "kenyan", "student", "students",
            "university", "programme", "programmes", "program", "programs"
        }
        tokens = [t.lower() for t in re.findall(r'\b[a-zA-Z0-9_\-]{3,}\b', query) if t.lower() not in stopwords]

        scored_candidates = []
        for opp in candidates:
            score = 0.0
            searchable_text = " ".join([
                opp.title or "",
                opp.provider or "",
                opp.category or "",
                opp.fields_of_study or "",
                opp.target_audience or "",
                opp.source_notes or ""
            ]).lower()

            for token in tokens:
                if token in (opp.title or "").lower():
                    score += 0.4
                elif token in (opp.provider or "").lower():
                    score += 0.3
                elif token in searchable_text:
                    score += 0.2

            if not tokens or score > 0:
                normalized_score = min(0.95, max(0.50, round(score, 2))) if tokens else 0.70
                scored_candidates.append((opp, normalized_score))

        # Sort by relevance score descending, then by creation date
        scored_candidates.sort(key=lambda x: (x[1], x[0].created_at or datetime.min), reverse=True)

        results = []
        for opp, sim_score in scored_candidates[:top_k]:
            excerpt = f"{opp.title} by {opp.provider}. Target: {opp.target_audience or 'Kenyan university students'}. Notes: {opp.source_notes or 'Official opportunity.'}"
            results.append({
                "opportunity_id": opp.id,
                "title": opp.title,
                "provider": opp.provider,
                "category": opp.category,
                "section": "Overview & Eligibility",
                "deadline": opp.application_deadline,
                "published_deadline": opp.application_deadline,
                "official_url": opp.official_url,
                "verification_status": opp.verification_status or ("VERIFIED" if opp.is_verified else "UNVERIFIED"),
                "is_verified": bool(opp.is_verified),
                "degree_levels": opp.degree_levels,
                "fields_of_study": opp.fields_of_study,
                "content_excerpt": excerpt,
                "similarity_score": sim_score,
                "retrieval_mode": "relational_fallback"
            })
        return results
    finally:
        if close_session and session is not None:
            session.close()

def tool_search_opportunities(
    input_data: SearchOpportunitiesInput,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """Retrieves grounded opportunity chunks and official source links from verified vector store,
    with automatic graceful relational fallback if vector retrieval fails.
    """
    results = None
    retrieval_mode = "vector_semantic"

    try:
        raw_vector_results = get_vector_store().search(
            query=input_data.query,
            top_k=input_data.top_k,
            category=input_data.category
        )
        if raw_vector_results:
            # HIGH-01: Authoritative Relational Verification Status Lookup
            # Vector metadata must not independently certify opportunities.
            opp_ids = list({r["metadata"].get("opportunity_id") for r in raw_vector_results if r.get("metadata") and r["metadata"].get("opportunity_id")})
            rel_map = {}
            if opp_ids:
                from app.models.entities import Opportunity
                from app.db.session import SessionLocal
                session = SessionLocal()
                try:
                    opp_rows = session.query(
                        Opportunity.id,
                        Opportunity.verification_status,
                        Opportunity.is_verified,
                        Opportunity.status,
                        Opportunity.official_url
                    ).filter(Opportunity.id.in_(opp_ids)).all()
                    for oid, vstat, is_ver, ost, off_url in opp_rows:
                        rel_map[oid] = {
                            "verification_status": vstat or ("VERIFIED" if is_ver else "UNVERIFIED"),
                            "is_verified": bool(is_ver),
                            "status": ost,
                            "official_url": off_url
                        }
                finally:
                    session.close()

            results = []
            for r in raw_vector_results:
                meta = r.get("metadata", {})
                oid = meta.get("opportunity_id")
                rel_info = rel_map.get(oid, {})

                # Exclude archived opportunities from retrieval results
                if rel_info.get("status") == "archived":
                    continue

                # Fail-closed: Vector chunk metadata cannot assert verification without authoritative relational backing
                if not rel_info:
                    vstatus = "UNVERIFIED"
                else:
                    vstatus = str(rel_info.get("verification_status") or "UNVERIFIED").strip().upper()
                is_ver_bool = (vstatus == "VERIFIED")

                results.append({
                    "opportunity_id": oid,
                    "title": meta.get("title"),
                    "provider": meta.get("provider"),
                    "category": meta.get("category"),
                    "section": meta.get("section_title"),
                    "deadline": meta.get("application_deadline"),
                    "published_deadline": meta.get("application_deadline"),
                    "official_url": rel_info.get("official_url") or meta.get("official_url"),
                    "verification_status": vstatus,
                    "is_verified": is_ver_bool,
                    "degree_levels": meta.get("degree_levels"),
                    "fields_of_study": meta.get("fields_of_study"),
                    "content_excerpt": r.get("content", ""),
                    "similarity_score": r.get("similarity_score", 0.0),
                    "retrieval_mode": "vector_semantic"
                })
        else:
            results = []
    except Exception as exc:
        safe_exc = re.sub(r'password=[^ &]+', 'password=***', str(exc))
        safe_exc = re.sub(r':\/\/[^:]+:[^@]+@', '://***:***@', safe_exc)
        logger.warning(
            "Vector retrieval failed (%s: %s). Executing graceful relational fallback.",
            type(exc).__name__,
            safe_exc
        )
        retrieval_mode = "relational_fallback"
        results = _search_opportunities_relational_fallback(
            query=input_data.query,
            category=input_data.category,
            top_k=input_data.top_k,
            db=db
        )

    if not results:
        return {
            "status": "not_found",
            "retrieval_mode": retrieval_mode,
            "message": "No matching verified opportunities found in knowledge base.",
            "results": []
        }

    return {
        "status": "success",
        "retrieval_mode": retrieval_mode,
        "count": len(results),
        "results": results
    }

class DeadlineCountdownInput(BaseModel):
    deadline_date_str: Optional[str] = Field(default=None, description="ISO format deadline string YYYY-MM-DD (e.g. '2026-11-30') or None/empty for rolling")
    deadline_str: Optional[str] = Field(default=None, description="Alias for deadline_date_str")
    is_officially_verified: bool = Field(default=False, description="Whether deadline was independently checked against official organization live source")
    verification_source: Optional[str] = Field(default=None, description="Official portal/organization where verification occurred")
    verification_date: Optional[str] = Field(default=None, description="ISO date when official verification took place")

def tool_calculate_deadline_countdown(input_data: DeadlineCountdownInput) -> Dict[str, Any]:
    """
    Deterministically computes days remaining, application status, and provenance.
    NEVER relies on LLM date arithmetic to prevent hallucinations.
    Enforces clear deadline provenance:
    1. Officially verified
    2. Recorded in directory — requires official verification
    3. Deadline unavailable
    4. Application status unconfirmed
    """
    today = date.today()
    raw_date = input_data.deadline_date_str or input_data.deadline_str

    if not raw_date or str(raw_date).strip().lower() in ["unspecified", "rolling", "none", "n/a", ""]:
        is_rolling = str(raw_date or "").strip().lower() == "rolling"
        provenance = "Recorded in directory — requires official verification" if is_rolling else "Deadline unavailable"
        app_status = "Rolling / Continuous intake" if is_rolling else "Application status unconfirmed"
        return {
            "status": "unspecified",
            "is_open": True,
            "deadline": None,
            "today": str(today),
            "days_remaining": None,
            "days_ago": None,
            "deadline_provenance": provenance,
            "application_status_provenance": app_status,
            "status_label": "Rolling / Open",
            "summary": f"No fixed deadline published (rolling admissions or continuous intake). [{provenance}]"
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
            "deadline_provenance": "Deadline unavailable",
            "application_status_provenance": "Application status unconfirmed",
            "status_label": "Invalid date",
            "message": f"Invalid date format '{clean_str}'. Expected YYYY-MM-DD.",
            "summary": f"Could not compute countdown: '{clean_str}' is not in YYYY-MM-DD format."
        }

    provenance = "Officially verified" if input_data.is_officially_verified else "Recorded in directory — requires official verification"
    app_status = "Officially confirmed" if input_data.is_officially_verified else "Application status unconfirmed"
    delta_days = (target_date - today).days

    if delta_days < 0:
        days_ago = abs(delta_days)
        label_text = f"Expired ({days_ago}d ago)" if days_ago > 1 else "Expired yesterday"
        return {
            "status": "expired",
            "is_open": False,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": -days_ago,
            "days_ago": days_ago,
            "deadline_provenance": provenance,
            "application_status_provenance": app_status,
            "verification_source": input_data.verification_source,
            "verification_date": input_data.verification_date,
            "status_label": f"{label_text} — {provenance}",
            "summary": f"This opportunity closed {days_ago} days ago on {target_date}. ({provenance})"
        }
    elif delta_days == 0:
        return {
            "status": "closing_today",
            "is_open": True,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": 0,
            "days_ago": 0,
            "deadline_provenance": provenance,
            "application_status_provenance": app_status,
            "verification_source": input_data.verification_source,
            "verification_date": input_data.verification_date,
            "status_label": f"Closing today! ({target_date}) — {provenance}",
            "summary": f"Deadline is TODAY! Ensure final submission before midnight. ({provenance})"
        }
    elif delta_days == 1:
        return {
            "status": "open",
            "is_open": True,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": 1,
            "days_ago": 0,
            "deadline_provenance": provenance,
            "application_status_provenance": app_status,
            "verification_source": input_data.verification_source,
            "verification_date": input_data.verification_date,
            "status_label": f"1 day left (Tomorrow) — {provenance}",
            "summary": f"1 day remaining until deadline on {target_date}. ({provenance})"
        }
    else:
        return {
            "status": "open",
            "is_open": True,
            "deadline": str(target_date),
            "today": str(today),
            "days_remaining": delta_days,
            "days_ago": 0,
            "deadline_provenance": provenance,
            "application_status_provenance": app_status,
            "verification_source": input_data.verification_source,
            "verification_date": input_data.verification_date,
            "status_label": f"{delta_days} days left — {provenance}",
            "summary": f"{delta_days} day(s) remaining until deadline on {target_date}. ({provenance})"
        }

class AssessEligibilityInput(BaseModel):
    opportunity_id: str = Field(description="Target opportunity ID (e.g. 'opp-safaricom-attachment-2026')")
    student_degree_level: str = Field(description="e.g. 'Undergraduate', 'Diploma', 'Masters', 'PhD'")
    student_field_of_study: str = Field(description="Student major/course e.g. 'Computer Science'")
    student_year_of_study: int = Field(description="Current year of study e.g. 1, 2, 3, 4")
    student_kcse_grade: Optional[str] = Field(default=None, description="e.g. 'A', 'B+', 'B', 'B-'")

def tool_assess_eligibility(input_data: AssessEligibilityInput, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Evaluates published opportunity criteria against student parameters.
    Returns criteria breakdown classified as Meets, Does Not Meet, or Needs Verification.
    """
    results = []
    try:
        results = get_vector_store().search(
            query=f"{input_data.opportunity_id} eligibility criteria minimum requirements",
            top_k=2
        )
    except Exception as exc:
        logger.warning(
            "Vector retrieval for eligibility assessment failed (%s: %s). Checking relational database fallback.",
            type(exc).__name__,
            str(exc)
        )

    matching_chunk = None
    for r in results:
        if r["metadata"].get("opportunity_id") == input_data.opportunity_id:
            matching_chunk = r
            break

    if not matching_chunk:
        from app.models.entities import Opportunity
        from app.db.session import SessionLocal
        close_session = False
        s = db
        if s is None:
            s = SessionLocal()
            close_session = True
        try:
            rel_opp = s.query(Opportunity).filter(Opportunity.id == input_data.opportunity_id).first()
            if rel_opp:
                matching_chunk = {
                    "metadata": {
                        "opportunity_id": rel_opp.id,
                        "title": rel_opp.title,
                        "provider": rel_opp.provider,
                        "category": rel_opp.category,
                        "degree_levels": rel_opp.degree_levels or "",
                        "fields_of_study": rel_opp.fields_of_study or "",
                        "official_url": rel_opp.official_url,
                        "application_deadline": rel_opp.application_deadline
                    },
                    "content": rel_opp.source_notes or f"Opportunity {rel_opp.title} by {rel_opp.provider}."
                }
        finally:
            if close_session and s is not None:
                s.close()

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
    has_universal_field = any(any(kw in f for kw in ["all fields", "all disciplines", "all academic disciplines", "any discipline", "open to all"]) for f in allowed_fields)
    is_universal_student = any(kw in student_field for kw in ["all fields", "all disciplines", "all academic disciplines", "general"])
    if not allowed_fields or has_universal_field or is_universal_student or any(f in student_field or student_field in f for f in allowed_fields):
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

def tool_generate_application_checklist(input_data: GenerateChecklistInput, db: Optional[Session] = None) -> Dict[str, Any]:
    """Generates a structured checklist of documents and application tasks from verified records."""
    results = []
    try:
        results = get_vector_store().search(
            query=f"{input_data.opportunity_id} required documents application steps process",
            top_k=4
        )
    except Exception as exc:
        logger.warning(
            "Vector retrieval for checklist generation failed (%s: %s). Checking relational database fallback.",
            type(exc).__name__,
            str(exc)
        )

    matching_chunks = [
        r for r in results 
        if r["metadata"].get("opportunity_id") == input_data.opportunity_id
    ]

    if not matching_chunks:
        from app.models.entities import Opportunity
        from app.db.session import SessionLocal
        close_session = False
        s = db
        if s is None:
            s = SessionLocal()
            close_session = True
        try:
            rel_opp = s.query(Opportunity).filter(Opportunity.id == input_data.opportunity_id).first()
            if rel_opp:
                matching_chunks = [{
                    "metadata": {
                        "opportunity_id": rel_opp.id,
                        "title": rel_opp.title,
                        "provider": rel_opp.provider,
                        "category": rel_opp.category,
                        "official_url": rel_opp.official_url
                    },
                    "content": (
                        f"- Complete official online application form at {rel_opp.official_url}\n"
                        f"- Submit certified copies of academic transcripts and degree/diploma certificates\n"
                        f"- Provide government-issued National ID card or Birth Certificate\n"
                        f"- Submit official recommendation or introduction letter from your university\n"
                        f"- Review and adhere to all published deadline requirements"
                    )
                }]
        finally:
            if close_session and s is not None:
                s.close()

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
        if norm_name in ["search_opportunities", "tool_search_opportunities"]:
            return func(validated_input, db=db)
        if norm_name in ["assess_eligibility", "tool_assess_eligibility"]:
            return func(validated_input, db=db)
        if norm_name in ["generate_application_checklist", "tool_generate_application_checklist"]:
            return func(validated_input, db=db)
        return func(validated_input)
    except Exception as e:
        return {"status": "error", "message": f"Tool execution error: {str(e)}"}

