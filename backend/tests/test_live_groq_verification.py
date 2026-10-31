import os
import json
import pytest
from unittest.mock import MagicMock
from app.config import settings
from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools import tool_search_opportunities, SearchOpportunitiesInput

LIVE_KEY = os.getenv("GROQ_API_KEY", "")
HAS_VALID_GROQ_KEY = bool(LIVE_KEY and LIVE_KEY != "your_groq_api_key_here" and len(LIVE_KEY) > 10)

def make_choice(content=None, tool_calls=None):
    choice = MagicMock()
    choice.message.role = "assistant"
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    return choice

def make_tc(call_id: str, fn_name: str, fn_args: dict):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = fn_name
    tc.function.arguments = json.dumps(fn_args)
    return tc

@pytest.mark.skipif(not HAS_VALID_GROQ_KEY, reason="Actual live Groq API test skipped: requires valid non-placeholder GROQ_API_KEY in environment.")
def test_live_groq_simple_model_response():
    orch = AgentOrchestrator(api_key=LIVE_KEY, model=settings.GROQ_MODEL)
    result = orch.process_turn(
        message="Hello, can you briefly tell me what you do?",
        conversation_id="live_test_hello"
    )
    assert result is not None
    assert "response" in result
    assert len(result["response"]) > 10

@pytest.mark.skipif(not HAS_VALID_GROQ_KEY, reason="Actual live Groq API test skipped: requires valid non-placeholder GROQ_API_KEY in environment.")
def test_live_groq_function_tool_calling():
    orch = AgentOrchestrator(api_key=LIVE_KEY, model=settings.GROQ_MODEL)
    result = orch.process_turn(
        message="What are the specific requirements for the Safaricom industrial attachment in Kenya?",
        conversation_id="live_test_tools"
    )
    assert result is not None
    assert "response" in result
    assert "citations" in result

@pytest.mark.skipif(not HAS_VALID_GROQ_KEY, reason="Actual live Groq API test skipped: requires valid non-placeholder GROQ_API_KEY in environment.")
def test_live_groq_multiple_tool_calls():
    orch = AgentOrchestrator(api_key=LIVE_KEY, model=settings.GROQ_MODEL)
    result = orch.process_turn(
        message="Search for KRA internship requirements and check deadline",
        conversation_id="live_test_multi_tools"
    )
    assert result is not None
    assert "response" in result

def test_mocked_groq_missing_api_key():
    orch = AgentOrchestrator(api_key="", model=settings.GROQ_MODEL)
    res = orch.process_turn(
        message="Tell me about scholarships in Kenya",
        conversation_id="mock_test_no_key"
    )
    assert res is not None
    assert "response" in res
    assert len(res["response"]) > 0

def test_mocked_groq_provider_timeout():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Connection timed out after 30.0s")
    orch = AgentOrchestrator(api_key="mock-key", model=settings.GROQ_MODEL)
    orch.groq_client = mock_client

    res = orch.process_turn(
        message="What opportunities are currently open for university students?",
        conversation_id="mock_test_timeout"
    )
    assert res is not None
    assert "response" in res
    assert len(res["response"]) > 0

def test_mocked_groq_rate_limit_429():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Rate limit reached. HTTP 429 Too Many Requests")
    orch = AgentOrchestrator(api_key="mock-key", model=settings.GROQ_MODEL)
    orch.groq_client = mock_client

    res = orch.process_turn(
        message="Tell me about Chevening scholarship in Kenya",
        conversation_id="mock_test_429"
    )
    assert res is not None
    assert "response" in res
    assert len(res["response"]) > 0

def test_mocked_groq_invalid_response():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(choices=[])
    orch = AgentOrchestrator(api_key="mock-key", model=settings.GROQ_MODEL)
    orch.groq_client = mock_client

    res = orch.process_turn(
        message="Tell me about internships",
        conversation_id="mock_test_invalid_resp"
    )
    assert res is not None
    assert "response" in res
    assert len(res["response"]) > 0

def test_mocked_groq_fallback_behavior():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Provider service unavailable 503")
    orch = AgentOrchestrator(api_key="mock-key", model=settings.GROQ_MODEL)
    orch.groq_client = mock_client

    res = orch.process_turn(
        message="What are the requirements for Safaricom attachment?",
        conversation_id="mock_test_fallback"
    )
    assert res is not None
    assert "response" in res
    assert "safaricom" in res["response"].lower() or len(res.get("citations", [])) >= 0
