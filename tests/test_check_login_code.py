from types import SimpleNamespace

import cxas_app.tools.check_login_code.python_function.python_code as tool


def test_check_login_code_logs_the_caller_in(monkeypatch) -> None:
    session = SimpleNamespace(
        state={"account_id": "A1001", "auth_status": "code_sent", "auth_failure_count": 0.0}
    )
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.check_login_code("271846")
    assert reply["status"] == "ok"
    assert reply["data"]["verified"] is True
    assert session.state["auth_status"] == "pass"
