from types import SimpleNamespace

import cxas_app.tools.check_secret_pin.python_function.python_code as tool


def test_check_secret_pin_logs_the_caller_in(monkeypatch) -> None:
    session = SimpleNamespace(
        state={"account_id": "A1001", "auth_status": "none", "pin_failure_count": 0.0}
    )
    monkeypatch.setattr(tool, "context", session, raising=False)
    reply = tool.check_secret_pin("5903")
    assert reply["status"] == "ok"
    assert reply["data"]["verified"] is True
    assert session.state["auth_status"] == "pass"
