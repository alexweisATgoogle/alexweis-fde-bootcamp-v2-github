from types import SimpleNamespace

import cxas_app.tools.lookup_account.python_function.python_code as tool


def test_lookup_account_reads_and_writes_session_state(monkeypatch) -> None:
    session = SimpleNamespace(state={"auth_status": "none", "auth_failure_count": 0.0})
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.lookup_account("202 555 0186")
    assert reply["status"] == "ok"
    assert session.state["account_id"] == "A1001"
    assert session.state["caller_provided_phone_last4"] == "0186"


def test_lookup_account_without_a_session() -> None:
    assert tool.lookup_account("")["error"] == "INVALID_INPUT"


def test_lookup_account_mock_error(monkeypatch) -> None:
    session = SimpleNamespace(state={"account_id": "A1001", "mock_error": "SYSTEM_DOWN"})
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.lookup_account("202 555 0186")
    assert reply["status"] == "error"
    assert reply["error"] == "SYSTEM_UNAVAILABLE"
