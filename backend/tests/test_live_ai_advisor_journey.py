import uuid
import pytest
from app.config import settings
from app.db.session import SessionLocal, Base, engine
from app.models.entities import User, StudentProfile, Opportunity, TrackedApplication, ApplicationChecklist, VerificationStatus
from app.agent.orchestrator import AgentOrchestrator

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        opp = db.query(Opportunity).filter(Opportunity.id == "opp-safaricom-attachment-2026").first()
        if not opp:
            opp = Opportunity(
                id="opp-safaricom-attachment-2026",
                title="Safaricom PLC Technology Internship & Industrial Attachment 2026",
                provider="Safaricom PLC",
                category="Industrial Attachment",
                target_audience="Continuing 2nd, 3rd, and 4th year undergraduate students in Kenyan universities",
                fields_of_study="Computer Science, Software Engineering, Telecommunications, Information Technology, Data Science",
                degree_levels="Undergraduate",
                official_url="https://www.safaricom.co.ke/careers",
                application_deadline="2026-11-30",
                status="open",
                is_verified=True,
                verification_status=VerificationStatus.VERIFIED.value,
                verification_date="2026-10-15",
                source_notes="Official career portal verified opportunity."
            )
            db.add(opp)
            db.commit()
        yield db
    finally:
        db.close()

def test_live_ai_advisor_complete_10_step_journey(db_session):
    orch = AgentOrchestrator(api_key=settings.GROQ_API_KEY, model=settings.GROQ_MODEL)

    test_suffix = uuid.uuid4().hex[:6]
    conv_id = f"live_journey_{test_suffix}"
    email = f"student_live_{test_suffix}@uonbi.ac.ke"

    user = User(
        id=f"usr_{test_suffix}",
        email=email,
        hashed_password="mock_hashed_pw",
        full_name="Faith Mwangi",
        role="student"
    )
    db_session.add(user)
    db_session.commit()

    student = StudentProfile(
        id=f"std_{test_suffix}",
        user_id=user.id,
        email=email,
        full_name="Faith Mwangi",
        university="University of Nairobi",
        field_of_study="Computer Science",
        degree_level="Undergraduate",
        year_of_study=3
    )
    db_session.add(student)
    db_session.commit()

    opp = db_session.query(Opportunity).filter(Opportunity.id == "opp-safaricom-attachment-2026").first()
    if not opp:
        opp = db_session.query(Opportunity).first()

    tracked = TrackedApplication(
        id=f"tr_live_{test_suffix}",
        student_id=student.id,
        opportunity_id=opp.id,
        stage="Drafting",
        notes="Preparing application portfolio"
    )
    db_session.add(tracked)
    db_session.commit()

    chk = ApplicationChecklist(
        id=f"chk_live_{test_suffix}",
        tracked_application_id=tracked.id,
        task_description="Request official recommendation letter from Dean",
        is_completed=False,
        required_document_type="Recommendation Letter"
    )
    db_session.add(chk)
    db_session.commit()

    student_ctx = {
        "id": student.id,
        "student_id": student.id,
        "university": student.university,
        "field_of_study": student.field_of_study,
        "degree_level": student.degree_level,
        "year_of_study": student.year_of_study
    }

    turn1 = orch.process_turn(
        message="What internship and attachment opportunities are available in Kenya?",
        conversation_id=conv_id,
        user_id=user.id,
        student_profile=student_ctx,
        db=db_session
    )
    assert turn1 is not None
    assert "response" in turn1
    assert len(turn1["response"]) > 20
    assert len(turn1.get("citations", [])) > 0 or len(turn1.get("tool_calls", [])) > 0

    turn2 = orch.process_turn(
        message="Do I qualify for the Safaricom industrial attachment as a 3rd year Computer Science undergraduate?",
        conversation_id=conv_id,
        user_id=user.id,
        student_profile=student_ctx,
        db=db_session
    )
    assert turn2 is not None
    assert "response" in turn2
    r2_lower = turn2["response"].lower()
    assert "eligible" in r2_lower or "qualif" in r2_lower or "meets" in r2_lower or "safaricom" in r2_lower

    turn3 = orch.process_turn(
        message="What documents are required for Safaricom attachment application?",
        conversation_id=conv_id,
        user_id=user.id,
        student_profile=student_ctx,
        db=db_session
    )
    assert turn3 is not None
    assert "response" in turn3
    r3_lower = turn3["response"].lower()
    assert "letter" in r3_lower or "transcript" in r3_lower or "document" in r3_lower or "checklist" in r3_lower

    turn4 = orch.process_turn(
        message="What applications am I currently tracking in my planner?",
        conversation_id=conv_id,
        user_id=user.id,
        student_profile=student_ctx,
        db=db_session
    )
    assert turn4 is not None
    assert "response" in turn4
    r4_lower = turn4["response"].lower()
    assert opp.title.lower() in r4_lower or "drafting" in r4_lower or "tracked" in r4_lower or "application" in r4_lower

    user_other = User(
        id=f"usr_other_{test_suffix}",
        email=f"other_{test_suffix}@ku.ac.ke",
        hashed_password="mock_pw",
        full_name="Other Student",
        role="student"
    )
    db_session.add(user_other)
    student_other = StudentProfile(
        id=f"std_other_{test_suffix}",
        user_id=user_other.id,
        email=user_other.email,
        full_name="Other Student",
        university="Kenyatta University",
        field_of_study="Economics",
        degree_level="Undergraduate",
        year_of_study=1
    )
    db_session.add(student_other)
    db_session.commit()

    turn5 = orch.process_turn(
        message="What applications am I currently tracking?",
        conversation_id=f"conv_other_{test_suffix}",
        user_id=user_other.id,
        student_profile={"id": student_other.id, "student_id": student_other.id},
        db=db_session
    )
    r5_lower = turn5["response"].lower()
    assert "faith mwangi" not in r5_lower
    assert f"tr_live_{test_suffix}" not in r5_lower

    db_session.delete(chk)
    db_session.delete(tracked)
    db_session.delete(student)
    db_session.delete(user)
    db_session.delete(student_other)
    db_session.delete(user_other)
    db_session.commit()
