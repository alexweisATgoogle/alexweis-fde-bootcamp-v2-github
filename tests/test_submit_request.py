from types import SimpleNamespace

import cxas_app.tools.submit_request.python_function.python_code as tool


def test_submit_request_after_login(monkeypatch) -> None:
    session = SimpleNamespace(state={"account_id": "A1001", "auth_status": "pass"})
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.submit_request("Mail a paper statement")
    assert reply["status"] == "ok" and reply["tracking_id"].startswith("R")


def test_submit_request_refuses_without_login(monkeypatch) -> None:
    session = SimpleNamespace(state={"account_id": "A1001", "auth_status": "code_sent"})
    monkeypatch.setattr(tool, "context", session, raising=False)
    assert tool.submit_request("Mail a paper statement")["error"] == "NOT_LOGGED_IN"
