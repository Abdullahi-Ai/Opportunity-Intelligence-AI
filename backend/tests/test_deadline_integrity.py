import pytest
from datetime import date, timedelta
from app.agent.tools import tool_calculate_deadline_countdown, DeadlineCountdownInput

def test_deadline_today():
    today_str = date.today().isoformat()
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=today_str))
    assert res["status"] == "closing_today"
    assert res["is_open"] is True
    assert res["days_remaining"] == 0
    assert "Closing today!" in res["status_label"]

def test_deadline_tomorrow():
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=tomorrow_str))
    assert res["status"] == "open"
    assert res["is_open"] is True
    assert res["days_remaining"] == 1
    assert "1 day left" in res["status_label"]

def test_deadline_future_30_days():
    future_str = (date.today() + timedelta(days=30)).isoformat()
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=future_str))
    assert res["status"] == "open"
    assert res["is_open"] is True
    assert res["days_remaining"] == 30
    assert "30 days left" in res["status_label"]

def test_deadline_yesterday():
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=yesterday_str))
    assert res["status"] == "expired"
    assert res["is_open"] is False
    assert res["days_remaining"] == -1
    assert res["days_ago"] == 1
    assert "Expired" in res["status_label"]

def test_deadline_past_90_days():
    past_str = (date.today() - timedelta(days=90)).isoformat()
    res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=past_str))
    assert res["status"] == "expired"
    assert res["is_open"] is False
    assert res["days_remaining"] == -90
    assert res["days_ago"] == 90
    assert "Expired (90d ago)" in res["status_label"]

def test_deadline_rolling_or_unspecified():
    unspecified_inputs = [None, "", "Unspecified", "Rolling", "None", "n/a"]
    for val in unspecified_inputs:
        res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=val))
        assert res["status"] == "unspecified"
        assert res["is_open"] is True
        assert res["days_remaining"] is None
        assert "Rolling / Open" in res["status_label"]

def test_deadline_invalid_date_format():
    invalid_inputs = ["2026/12/31", "30-11-2026", "tomorrow", "invalid-str"]
    for val in invalid_inputs:
        res = tool_calculate_deadline_countdown(DeadlineCountdownInput(deadline_date_str=val))
        assert res["status"] == "error"
        assert res["is_open"] is False
        assert "Invalid date" in res["status_label"]
