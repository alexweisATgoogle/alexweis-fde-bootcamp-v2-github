from types import SimpleNamespace

import cxas_app.tools.send_login_code.python_function.python_code as tool


def test_send_login_code_uses_the_account_in_session_state(monkeypatch) -> None:
    session = SimpleNamespace(
        state={"account_id": "A1001", "phone_last4": "0186", "auth_status": "none", "auth_failure_count": 0.0}
    )
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.send_login_code()
    assert reply["status"] == "ok"
    assert reply["data"]["destination_last4"] == "0186"
    assert session.state["auth_status"] == "code_sent"


def test_send_login_code_mock_error(monkeypatch) -> None:
    session = SimpleNamespace(state={"account_id": "A1001", "mock_error": "SYSTEM_DOWN"})
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.send_login_code()
    assert reply["status"] == "error"
    assert reply["error"] == "SYSTEM_UNAVAILABLE"
