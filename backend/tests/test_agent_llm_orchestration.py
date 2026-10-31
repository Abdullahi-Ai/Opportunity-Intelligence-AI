import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

from app.agent.orchestrator import AgentOrchestrator
from app.agent.intent import IntentType
from app.agent.memory import ConversationState, get_or_create_conversation, load_message_history
from app.agent.tools import (
    execute_registered_tool,
    tool_calculate_deadline_countdown,
    DeadlineCountdownInput,
    tool_assess_eligibility,
    AssessEligibilityInput
)
from app.db.session import SessionLocal
from app.models.entities import Conversation, ConversationMessage, StudentProfile, User

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def make_mock_choice(content=None, tool_calls=None):
    choice = MagicMock()
    choice.message.role = "assistant"
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    return choice

def make_mock_tool_call(call_id: str, fn_name: str, fn_args: dict):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = fn_name
    tc.function.arguments = json.dumps(fn_args)
    return tc

def test_1_groq_successful_integration():
    mock_groq = MagicMock()
    mock_tc = make_mock_tool_call(
        call_id="call_search_1",
        fn_name="search_opportunities",
        fn_args={"query": "Safaricom industrial attachment"}
    )
    first_resp = MagicMock(choices=[make_mock_choice(content=None, tool_calls=[mock_tc])])
    second_resp = MagicMock(choices=[make_mock_choice(
        content="Safaricom offers verified 3-month industrial attachments for continuing university students. Apply at [Safaricom Portal](https://www.safaricom.co.ke/careers).",
        tool_calls=None
    )])
    mock_groq.chat.completions.create.side_effect = [first_resp, second_resp]

    orch = AgentOrchestrator(api_key="valid-mock-key")
    orch.groq_client = mock_groq

    res = orch.process_turn(
        message="Tell me about Safaricom attachment",
        conversation_id="conv_mock_test_1"
    )

    assert "Safaricom" in res["response"]
    assert len(res["tool_calls"]) >= 1
    assert res["tool_calls"][0]["tool"] == "search_opportunities"
    assert any("safaricom" in c["url"].lower() for c in res["citations"])
    assert mock_groq.chat.completions.create.call_count == 2

def test_2_missing_api_key_handling():
    orch = AgentOrchestrator(api_key="")
    assert orch.groq_client is None

    res = orch.process_turn(
        message="Find scholarships for university students in Kenya",
        conversation_id="conv_missing_key_test"
    )

    assert res["response"] is not None
    assert len(res["response"]) > 20
    assert res["intent"] in [IntentType.OPPORTUNITY_DISCOVERY.value, IntentType.SCHOLARSHIP_SEARCH.value]

def test_3_provider_timeout_handling():
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = TimeoutError("Connection to Groq API timed out")

    orch = AgentOrchestrator(api_key="valid-mock-key")
    orch.groq_client = mock_groq

    res = orch.process_turn(
        message="Show me engineering attachments",
        conversation_id="conv_timeout_test"
    )

    assert res["response"] is not None
    assert "verified" in res["response"].lower() or "attachment" in res["response"].lower()

def test_4_provider_rate_limiting_handling():
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("HTTP 429: Rate limit exceeded. Please retry later.")

    orch = AgentOrchestrator(api_key="valid-mock-key")
    orch.groq_client = mock_groq

    res = orch.process_turn(
        message="What are the HEF scholarship requirements?",
        conversation_id="conv_ratelimit_test"
    )

    assert res["response"] is not None
    assert len(res["response"]) > 20

def test_5_invalid_llm_response_handling():
    mock_groq = MagicMock()
    bad_tc = make_mock_tool_call(
        call_id="call_bad_args",
        fn_name="assess_eligibility",
        fn_args={"invalid_argument": 999}
    )
    first_resp = MagicMock(choices=[make_mock_choice(content=None, tool_calls=[bad_tc])])
    second_resp = MagicMock(choices=[make_mock_choice(
        content="I could not evaluate eligibility due to missing parameters. Please provide your university degree level and year of study.",
        tool_calls=None
    )])
    mock_groq.chat.completions.create.side_effect = [first_resp, second_resp]

    orch = AgentOrchestrator(api_key="valid-mock-key")
    orch.groq_client = mock_groq

    res = orch.process_turn(
        message="Am I eligible for this?",
        conversation_id="conv_invalid_resp_test"
    )

    assert res["response"] is not None
    assert len(res["tool_calls"]) >= 1
    assert res["tool_calls"][0]["status"] == "validation_error"

def test_6_tool_selection():
    mock_groq = MagicMock()
    tc = make_mock_tool_call(
        call_id="call_cd_1",
        fn_name="calculate_deadline_countdown",
        fn_args={"deadline_date_str": "2026-11-30"}
    )
    first_resp = MagicMock(choices=[make_mock_choice(content=None, tool_calls=[tc])])
    second_resp = MagicMock(choices=[make_mock_choice(content="The deadline is 2026-11-30.", tool_calls=None)])
    mock_groq.chat.completions.create.side_effect = [first_resp, second_resp]

    orch = AgentOrchestrator(api_key="valid-mock-key")
    orch.groq_client = mock_groq

    res = orch.process_turn(
        message="How many days left until 2026-11-30?",
        conversation_id="conv_tool_sel_test"
    )

    assert res["tool_calls"][0]["tool"] == "calculate_deadline_countdown"

def test_7_tool_argument_validation():
    valid_res = execute_registered_tool(
        tool_name="calculate_deadline_countdown",
        tool_args={"deadline_date_str": "2026-12-31"}
    )
    assert valid_res["status"] in ["open", "closing_today", "expired"]

    invalid_res = execute_registered_tool(
        tool_name="calculate_deadline_countdown",
        tool_args={"wrong_key": "2026-12-31"}
    )
    assert invalid_res["status"] == "unspecified" or invalid_res.get("status_label") == "Rolling / Open"

    missing_field_res = execute_registered_tool(
        tool_name="assess_eligibility",
        tool_args={"opportunity_id": "opp-safaricom-attachment-2026"}
    )
    assert missing_field_res["status"] == "validation_error"

    unknown_res = execute_registered_tool(
        tool_name="arbitrary_python_executor",
        tool_args={"code": "import os; os.system('ls')"}
    )
    assert unknown_res["status"] == "error"
    assert "Unknown tool" in unknown_res["message"]

def test_8_maximum_tool_call_iteration_limit():
    mock_groq = MagicMock()
    mock_tc = make_mock_tool_call(
        call_id="call_infinite_loop",
        fn_name="search_opportunities",
        fn_args={"query": "infinite query loop"}
    )
    mock_groq.chat.completions.create.return_value = MagicMock(choices=[make_mock_choice(content=None, tool_calls=[mock_tc])])

    orch = AgentOrchestrator(api_key="valid-mock-key", max_tool_iterations=3)
    orch.groq_client = mock_groq

    res = orch.process_turn(
        message="Keep searching repeatedly",
        conversation_id="conv_loop_limit_test"
    )

    assert res["response"] is not None
    assert mock_groq.chat.completions.create.call_count <= 4

def test_9_unauthorized_application_tool_access(db_session: Session):
    unauth_res = execute_registered_tool(
        tool_name="get_tracked_applications",
        tool_args={"student_profile_id": "some_student_id"},
        authenticated_student_id=None,
        db=db_session
    )
    assert unauth_res["status"] == "unauthenticated"

    forbidden_res = execute_registered_tool(
        tool_name="get_tracked_applications",
        tool_args={"student_profile_id": "target_victim_student_id"},
        authenticated_student_id="authenticated_attacker_id",
        db=db_session
    )
    assert forbidden_res["status"] == "forbidden"

def test_10_grounded_response_generation():
    mock_groq = MagicMock()
    mock_tc = make_mock_tool_call(
        call_id="call_grounded_1",
        fn_name="search_opportunities",
        fn_args={"query": "Equity Leaders Program Kenya"}
    )
    first_resp = MagicMock(choices=[make_mock_choice(content=None, tool_calls=[mock_tc])])
    second_resp = MagicMock(choices=[make_mock_choice(
        content="The [Equity Leaders Program](https://equitygroupfoundation.com/elp/) offers university scholarships and leadership development.",
        tool_calls=None
    )])
    mock_groq.chat.completions.create.side_effect = [first_resp, second_resp]

    orch = AgentOrchestrator(api_key="valid-mock-key")
    orch.groq_client = mock_groq

    res = orch.process_turn(
        message="Tell me about Equity Leaders Program",
        conversation_id="conv_grounded_test"
    )

    assert "equitygroupfoundation" in res["response"]
    assert len(res["citations"]) >= 1
    assert any("equitygroupfoundation" in c["url"] for c in res["citations"])

def test_11_unsupported_question_handling():
    orch = AgentOrchestrator(api_key="valid-mock-key")
    res = orch.process_turn(
        message="How do I get a passport renewal in Nairobi?",
        conversation_id="conv_out_of_scope_test"
    )
    assert res["intent"] == IntentType.OUT_OF_SCOPE.value
    assert "specialize specifically in verified educational and early-career opportunities" in res["response"]
    assert res["tool_calls"] == []

def test_12_missing_deadline_handling():
    cd_none = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=None))
    assert cd_none["status"] == "unspecified"
    assert cd_none["is_open"] is True
    assert cd_none["status_label"] == "Rolling / Open"

    cd_rolling = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str="rolling"))
    assert cd_rolling["status"] == "unspecified"
    assert cd_rolling["is_open"] is True

def test_13_source_citation_accuracy():
    orch = AgentOrchestrator(api_key="")
    res = orch.process_turn(
        message="Show me the Safaricom attachment link",
        conversation_id="conv_citation_acc_test"
    )
    assert len(res["citations"]) > 0
    for citation in res["citations"]:
        assert citation["url"].startswith("http://") or citation["url"].startswith("https://")
        assert len(citation["title"]) > 0

def test_14_followup_context_resolution():
    orch = AgentOrchestrator(api_key="")
    conv_id = "conv_multistep_flow_test"

    turn1 = orch.process_turn(
        message="I am a third-year Computer Science student at the University of Nairobi.",
        conversation_id=conv_id
    )
    assert turn1["state"]["student_memory"].get("year_of_study") in [3, "3"]
    assert "Computer Science" in turn1["state"]["student_memory"].get("field_of_study", "")

    turn2 = orch.process_turn(
        message="Tell me about Safaricom.",
        conversation_id=conv_id
    )
    assert any("safaricom" in o.get("id", "").lower() or "safaricom" in o.get("title", "").lower() for o in turn2["state"]["discussed_opportunities"])

    turn3 = orch.process_turn(
        message="Am I eligible?",
        conversation_id=conv_id
    )
    assert "Eligibility Assessment" in turn3["response"] or "Eligible" in turn3["response"]
    assert "Computer Science" in turn3["response"] or "Year 3" in turn3["response"]

def test_15_conversation_persistence(db_session: Session):
    orch = AgentOrchestrator(api_key="")
    conv_id = "conv_db_persist_verified_test"

    orch.process_turn(
        message="Hello! I need scholarships.",
        conversation_id=conv_id,
        db=db_session
    )

    conv = db_session.query(Conversation).filter(Conversation.id == conv_id).first()
    assert conv is not None
    assert len(conv.messages) >= 2

    messages = load_message_history(db_session, conv_id)
    assert len(messages) >= 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

def test_16_deterministic_deadline_calculation():
    today = date.today()
    target_30d = str(today + timedelta(days=30))
    res_30d = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=target_30d))
    assert res_30d["status"] == "open"
    assert res_30d["days_remaining"] == 30

    target_today = str(today)
    res_today = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=target_today))
    assert res_today["status"] == "closing_today"
    assert res_today["days_remaining"] == 0

    target_past = str(today - timedelta(days=15))
    res_past = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=target_past))
    assert res_past["status"] == "expired"
    assert res_past["days_ago"] == 15

def test_17_deterministic_eligibility_evaluation():
    eligible_res = tool_assess_eligibility(AssessEligibilityInput(
        opportunity_id="opp-safaricom-attachment-2026",
        student_degree_level="Undergraduate",
        student_field_of_study="Computer Science",
        student_year_of_study=3
    ))
    assert eligible_res["status"] == "success"
    assert eligible_res["overall_assessment"] == "Likely Eligible"
    assert any(c["criterion"] == "Year of Study (Attachment)" and c["status"] == "Meets" for c in eligible_res["criteria_breakdown"])

    ineligible_res = tool_assess_eligibility(AssessEligibilityInput(
        opportunity_id="opp-safaricom-attachment-2026",
        student_degree_level="Undergraduate",
        student_field_of_study="Computer Science",
        student_year_of_study=1
    ))
    assert ineligible_res["status"] == "success"
    assert ineligible_res["overall_assessment"] == "Ineligible / Unlikely to Meet Criteria"
    assert any(c["criterion"] == "Year of Study (Attachment)" and c["status"] == "Does Not Meet" for c in ineligible_res["criteria_breakdown"])

def test_18_regression_phase1_security():
    from app.config import settings
    assert len(settings.SECRET_KEY) >= 32
    assert len(settings.ADMIN_REGISTRATION_SECRET) >= 16
